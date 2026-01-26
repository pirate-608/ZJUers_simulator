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