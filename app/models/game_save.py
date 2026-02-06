from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    TIMESTAMP,
    ForeignKey,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.sql import func
from app.core.database import Base


class GameSave(Base):
    __tablename__ = "game_saves"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    save_slot = Column(Integer, default=1, nullable=False)

    # 游戏状态数据（JSON格式）
    stats_data = Column(JSON, nullable=False)
    courses_data = Column(JSON)
    course_states_data = Column(JSON)
    achievements_data = Column(JSON)

    # 元数据
    game_version = Column(String(20), default="1.0.0")
    semester_index = Column(Integer)
    total_play_time = Column(Integer, default=0)  # 总游玩时间（秒）

    created_at = Column(TIMESTAMP, server_default=func.now())
    saved_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "save_slot", name="uq_user_save_slot"),
    )
