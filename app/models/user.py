from sqlalchemy import Column, Integer, String, DateTime, func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    
    # 游戏相关记录
    highest_gpa = Column(String, default="0.0")
    tier = Column(String, nullable=True) # 入学考试档位：TIER_1, TIER_2...
    exam_score = Column(Integer, default=0) # 入学考试分数
    token = Column(String, unique=True, index=True, nullable=True)  # 学生凭证token
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())