from fastapi import Request
from jose import JWTError, jwt
from app.core.config import settings
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Dict
from app.game.access import grade_entrance_exam, get_questions_for_frontend
from app.api import deps
from app.models.user import User
from app.core.security import create_access_token
from app.game.access import grade_entrance_exam, get_questions_for_frontend
from pydantic import BaseModel
from app.game.state import RedisState
from app.api.game import get_current_user_id
from app.api.cache import RedisCache
from app.repositories.redis_repo import RedisRepository
from app.services.game_service import GameService
from app.services.world_service import WorldService
from app.services.restriction_service import RestrictionService

router = APIRouter()


class ExamSubmission(BaseModel):
    username: str
    answers: Dict[str, str]
    token: str = None  # 可选，老用户重新考试时携带


class ExamResponse(BaseModel):
    status: str
    score: int = None  # 可选，错误响应时不需要分数
    tier: str = None
    token: str = None
    message: str = None


@router.get("/exam/questions")
async def get_exam_questions():
    """
    获取入学考试题目
    """
    questions = get_questions_for_frontend()
    if not questions:
        # 如果没读到题，返回一个默认的保底，防止前端报错
        return [{"id": "0", "content": "系统题库连接失败，请联系管理员", "score": 0}]
    return questions


@router.post("/exam/submit", response_model=ExamResponse)
async def submit_exam(
    submission: ExamSubmission, db: AsyncSession = Depends(deps.get_db)
):
    if await RestrictionService.is_blacklisted(db, submission.username, "username"):
        return {"status": "error", "message": "该用户名已被拉黑"}
    if submission.token and await RestrictionService.is_blacklisted(
        db, submission.token, "token"
    ):
        return {"status": "error", "message": "该凭证已被拉黑"}

    # 1. 调用 access.py 进行判卷 (底层调用 C 动态库)
    result = grade_entrance_exam(submission.answers)

    if not result["passed"]:
        return {
            "status": "failed",
            "score": result["total_score"],
            "message": "分数未达标，遗憾离场。",
        }

    # 2. 判卷通过，检查用户是否已存在
    # (为了简化模拟器逻辑，如果同名则直接更新数据，或者创建新用户)
    stmt = select(User).where(User.username == submission.username)
    result_db = await db.execute(stmt)
    user = result_db.scalars().first()
    import secrets

    # 从提交数据中获取 token
    token_from_req = submission.token
    if not user:
        # 新用户，必须没有token
        if token_from_req:
            return {"status": "error", "message": "用户名不存在，凭证无效"}
        # 用户名唯一性校验通过，创建新用户
        token = secrets.token_urlsafe(16)
        user = User(
            username=submission.username,
            tier=result["tier"],
            exam_score=result["total_score"],
            token=token,
        )
        db.add(user)
    elif token_from_req:
        # 老用户，校验token
        if user.token != token_from_req:
            return {"status": "error", "message": "凭证错误或用户名不符"}
        restriction = await RestrictionService.get_active_restriction(db, user.id)
        if restriction:
            return {
                "status": "error",
                "message": f"账号受限：{restriction.restriction_type}",
            }
        # token 匹配，允许免试登录，更新分数等
        user.tier = result["tier"]
        user.exam_score = result["total_score"]
    else:
        # 用户名已存在但未提供token，拒绝注册
        return {"status": "error", "message": "用户名已被占用，请更换或填写凭证"}
    await db.commit()
    await db.refresh(user)

    # 3. 生成 Token (包含 user_id 和 tier)
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "tier": user.tier}
    )

    return {
        "status": "success",
        "score": result["total_score"],
        "tier": result["tier"],
        "token": access_token,
    }


# 分配专业API，考试通过后由前端调用
class AssignMajorRequest(BaseModel):
    token: str


@router.post("/assign_major")
async def assign_major(
    req: AssignMajorRequest, db: AsyncSession = Depends(deps.get_db)
):
    user_id, username, tier = await get_current_user_id(req.token)
    if not user_id or not tier:
        raise HTTPException(status_code=401, detail="Invalid token or missing tier")
    restriction = await RestrictionService.get_active_restriction(db, int(user_id))
    if restriction:
        raise HTTPException(
            status_code=403, detail=f"账号受限：{restriction.restriction_type}"
        )
    redis_client = RedisCache.get_client()
    repo = RedisRepository(user_id, redis_client)
    world = WorldService()
    game_service = GameService(user_id, repo, world)

    if not await repo.exists():
        state = RedisState(user_id)
        await state.init_game(username or "新同学", tier)

    result = await game_service.assign_major_and_init(tier)
    return {
        "success": True,
        "major": result["major"],
        "major_abbr": result["major_abbr"],
        "courses": result["courses"],
    }


# 获取当前用户 admission 信息
@router.get("/admission_info")
async def get_admission_info(request: Request, db: AsyncSession = Depends(deps.get_db)):
    """
    获取当前用户的用户名和分配专业（tier）。需前端携带 Authorization: Bearer <token>
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username = payload.get("username")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    # 优先查Redis专业
    from app.game.state import RedisState

    state = RedisState(user_id)
    stats = await state.get_stats()
    major = stats.get("major")
    # 查库获取用户名和tier和token
    stmt = select(User).where(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "username": username or user.username,
        "assigned_major": major or user.tier or "未分配专业",
        "token": user.token,
    }


# 允许已注册用户直接登录，无需重复考试
class QuickLoginRequest(BaseModel):
    username: str
    token: str = None  # 可选，提供则验证凭证


# POST /exam/quick_login
@router.post("/exam/quick_login")
async def quick_login(data: QuickLoginRequest, db: AsyncSession = Depends(deps.get_db)):
    stmt = select(User).where(User.username == data.username)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        return {"status": "not_found", "message": "用户未注册，请先完成入学考试"}
    if await RestrictionService.is_blacklisted(db, data.username, "username"):
        return {"status": "error", "message": "该用户名已被拉黑"}
    if data.token and await RestrictionService.is_blacklisted(db, data.token, "token"):
        return {"status": "error", "message": "该凭证已被拉黑"}
    restriction = await RestrictionService.get_active_restriction(db, user.id)
    if restriction:
        return {
            "status": "error",
            "message": f"账号受限：{restriction.restriction_type}",
        }
    # 如果提供了 token，则验证
    if data.token:
        if user.token != data.token:
            return {"status": "error", "message": "凭证错误，请检查后重试"}
    # 生成 JWT
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "tier": user.tier}
    )
    return {
        "status": "success",
        "token": access_token,
        "username": user.username,
        "assigned_major": user.tier or "未分配专业",
    }
