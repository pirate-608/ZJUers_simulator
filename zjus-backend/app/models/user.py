from sqlalchemy import Column, Integer, String, DateTime, func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)

    highest_gpa = Column(String, default="0.0")
    token = Column(String, unique=True, index=True, nullable=True)  # 学生凭证token

    # 用户自定义 LLM 配置（可选）
    custom_llm_model = Column(String, nullable=True)
    custom_llm_api_key = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
