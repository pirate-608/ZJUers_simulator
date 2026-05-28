from jose import JWTError, jwt
from app.core.config import settings
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Dict, List, Optional
from app.api import deps
from app.models.user import User
from app.core.security import create_access_token
from app.game.state import RedisState
from app.api.cache import RedisCache
from app.repositories.redis_repo import RedisRepository
from app.services.game_service import GameService
from app.services.world_service import WorldService
from app.services.restriction_service import RestrictionService

router = APIRouter()

# ─── 模型 ───


class AuthRequest(BaseModel):
    username: str
    invite_code: str
    token: Optional[str] = None  # 老玩家凭证
    custom_llm_model: Optional[str] = None
    custom_llm_api_key: Optional[str] = None
    custom_llm_provider: Optional[str] = None


class AuthResponse(BaseModel):
    status: str  # "new_user" | "returning"
    jwt: Optional[str] = None
    user_token: Optional[str] = None  # 持久凭证（新用户）
    username: str
    user_id: Optional[int] = None
    message: Optional[str] = None


class MajorOption(BaseModel):
    name: str
    abbr: str
    iq_buff: int
    stress_base: int
    desc: str


class InitCharacterRequest(BaseModel):
    token: str  # JWT
    major_abbr: str
    iq: int = 100
    eq: int = 100
    luck: int = 50


class InitCharacterResponse(BaseModel):
    success: bool
    major: str
    major_abbr: str
    courses: List[Dict[str, str]]


class AdmissionInfoResponse(BaseModel):
    username: str
    assigned_major: str
    token: str


# ─── 安全校验 ───

BLACKLIST = [
    "SYSTEM MODE", "系统提示", "IGNORE START",
    "flag{", "====", "====================",
    "Happy Hacking", "Is it SQL Injection",
]


def is_username_safe(username: str) -> bool:
    if not username:
        return False
    if len(username) > 50:
        return False
    for keyword in BLACKLIST:
        if keyword in username:
            return False
    return True


def _validate_invite_code(code: str) -> bool:
    raw = settings.INVITE_CODES.strip()
    if not raw:
        return False
    codes = [c.strip() for c in raw.split(",") if c.strip()]
    return code.strip() in codes


# ─── 路由 ───


@router.post("/auth", response_model=AuthResponse)
async def auth(data: AuthRequest, db: AsyncSession = Depends(deps.get_db)):
    """邀请码认证：验证用户名+邀请码，返回 JWT 和持久凭证"""
    if not is_username_safe(data.username):
        return AuthResponse(
            status="error", username=data.username,
            message="用户名包含不允许的内容或过长",
        )

    if await RestrictionService.is_blacklisted(db, data.username, "username"):
        return AuthResponse(
            status="error", username=data.username,
            message="该用户名已被拉黑",
        )

    if not _validate_invite_code(data.invite_code):
        return AuthResponse(
            status="error", username=data.username,
            message="邀请码无效",
        )

    stmt = select(User).where(User.username == data.username)
    result = await db.execute(stmt)
    user = result.scalars().first()

    import secrets

    if not user:
        # 新用户
        user_token = secrets.token_urlsafe(16)
        user = User(
            username=data.username,
            token=user_token,
            custom_llm_model=data.custom_llm_model,
            custom_llm_api_key=data.custom_llm_api_key,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        jwt_token = create_access_token(
            data={"sub": str(user.id), "username": user.username}
        )
        return AuthResponse(
            status="new_user",
            jwt=jwt_token,
            user_token=user_token,
            username=user.username,
            user_id=user.id,
        )

    # 老用户
    if data.token and user.token == data.token:
        jwt_token = create_access_token(
            data={"sub": str(user.id), "username": user.username}
        )
        return AuthResponse(
            status="returning",
            jwt=jwt_token,
            username=user.username,
            user_id=user.id,
        )

    return AuthResponse(
        status="error", username=data.username,
        message="用户名已被占用，请填写老玩家凭证重试",
    )


@router.get("/majors", response_model=List[MajorOption])
async def get_majors():
    """返回 majors.json 中所有可选专业"""
    world = WorldService()
    all_majors = await world.get_all_majors()
    return [MajorOption(**m) for m in all_majors]


@router.post("/init_character", response_model=InitCharacterResponse)
async def init_character(
    req: InitCharacterRequest, db: AsyncSession = Depends(deps.get_db)
):
    """初始化角色：选择专业并分配初始属性"""
    # 解码 JWT
    try:
        payload = jwt.decode(
            req.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        username = payload.get("username")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    restriction = await RestrictionService.get_active_restriction(db, int(user_id))
    if restriction:
        raise HTTPException(
            status_code=403, detail=f"账号受限：{restriction.restriction_type}"
        )

    # 查找专业
    world = WorldService()
    major = await world.get_major_by_abbr(req.major_abbr)
    if not major:
        raise HTTPException(status_code=404, detail=f"专业 {req.major_abbr} 不存在")

    # 初始化 Redis 游戏状态
    redis_client = RedisCache.get_client()
    repo = RedisRepository(user_id, redis_client)
    game_service = GameService(str(user_id), repo, world)

    stat_overrides = {
        "iq": max(0, min(200, req.iq)),
        "eq": max(0, min(200, req.eq)),
        "luck": max(0, min(200, req.luck)),
    }

    result = await game_service.assign_major_and_init(
        major_abbr=req.major_abbr, stat_overrides=stat_overrides
    )

    return InitCharacterResponse(
        success=True,
        major=result["major"],
        major_abbr=result["major_abbr"],
        courses=result["courses"],
    )


# ─── 入学信息查询（admission_info） ───


@router.get("/admission_info", response_model=AdmissionInfoResponse)
async def get_admission_info(
    authorization: str = Header(..., description="Bearer <JWT>"),
    db: AsyncSession = Depends(deps.get_db),
):
    """查询当前用户的用户名和已分配专业"""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1]
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

    state = RedisState(user_id)
    stats = await state.get_stats()
    major = stats.get("major")

    stmt = select(User).where(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return AdmissionInfoResponse(
        username=username or user.username,
        assigned_major=major or "未分配专业",
        token=user.token,
    )
