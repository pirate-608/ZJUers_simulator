from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "ZJUers Simulator"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "YOUR_SECRET_KEY_CHANGE_ME")  # 用于JWT加密，生产环境请修改
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # Token有效期7天

    # 数据库配置 (默认为 Docker 中的服务名，本地调试可改为 localhost)
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://zju:password@db/zjuers"
    )

    # Redis配置
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    REDIS_PLAYER_TTL_SECONDS: int = int(os.environ.get("REDIS_PLAYER_TTL_SECONDS", 60 * 60 * 24))

    # Admin配置
    ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "admin123")
    ADMIN_SESSION_SECRET: str = os.environ.get("ADMIN_SESSION_SECRET", "CHANGE_ME_ADMIN_SESSION_SECRET")

    class Config:
        env_file = ".env"


settings = Settings()
