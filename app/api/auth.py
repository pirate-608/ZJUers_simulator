# 允许已注册用户直接登录，无需重复考试
class QuickLoginRequest(BaseModel):
    username: str

# POST /exam/quick_login
@router.post("/exam/quick_login")
async def quick_login(data: QuickLoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == data.username)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        return {"status": "not_found", "message": "用户未注册，请先完成入学考试"}
    # 生成token
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "tier": user.tier}
    )
    return {
        "status": "success",
        "token": access_token,
        "username": user.username,
        "assigned_major": user.tier or "未分配专业"
    }
from fastapi import Request
from jose import JWTError, jwt
from app.core.config import settings
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Dict
from app.game.access import grade_entrance_exam, get_questions_for_frontend
from app.core.database import get_db
from app.models.user import User
from app.core.security import create_access_token
from app.game.access import grade_entrance_exam, get_questions_for_frontend

router = APIRouter()

class ExamSubmission(BaseModel):
    username: str
    answers: Dict[str, str]

class ExamResponse(BaseModel):
    status: str
    score: int
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
async def submit_exam(submission: ExamSubmission, db: AsyncSession = Depends(get_db)):
    # 1. 调用 access.py 进行判卷 (底层调用 C 动态库)
    result = grade_entrance_exam(submission.answers)
    
    if not result["passed"]:
        return {
            "status": "failed",
            "score": result["total_score"],
            "message": "分数未达标，遗憾离场。"
        }

    # 2. 判卷通过，检查用户是否已存在
    # (为了简化模拟器逻辑，如果同名则直接更新数据，或者创建新用户)
    stmt = select(User).where(User.username == submission.username)
    result_db = await db.execute(stmt)
    user = result_db.scalars().first()

    if not user:
        user = User(
            username=submission.username,
            tier=result["tier"],
            exam_score=result["total_score"]
        )
        db.add(user)
    else:
        # 老玩家重开，更新档位和分数
        user.tier = result["tier"]
        user.exam_score = result["total_score"]
    
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
        "token": access_token
    }

# 获取当前用户 admission 信息
@router.get("/admission_info")
async def get_admission_info(request: Request, db: AsyncSession = Depends(get_db)):
    """
    获取当前用户的用户名和分配专业（tier）。需前端携带 Authorization: Bearer <token>
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("username")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    # 查库获取专业
    stmt = select(User).where(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "username": username or user.username,
        "assigned_major": user.tier or "未分配专业"
    }