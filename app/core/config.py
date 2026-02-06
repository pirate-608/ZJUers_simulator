from pydantic_settings import BaseSettings
from pydantic import model_validator
import os
import logging
import secrets

_config_logger = logging.getLogger("app.core.config")

# 危险的默认值列表，启动时必须检测
_INSECURE_DEFAULTS = {
    "YOUR_SECRET_KEY_CHANGE_ME",
    "CHANGE_ME_ADMIN_SESSION_SECRET",
    "admin123",
    "password",
    "secret",
}


class Settings(BaseSettings):
    PROJECT_NAME: str = "ZJUers Simulator"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "YOUR_SECRET_KEY_CHANGE_ME"
    )  # 用于JWT加密，生产环境请修改
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # Token有效期7天

    # 数据库配置 (默认为 Docker 中的服务名，本地调试可改为 localhost)
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://zju:password@db/zjuers"
    )

    # Redis配置
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    REDIS_PLAYER_TTL_SECONDS: int = int(
        os.environ.get("REDIS_PLAYER_TTL_SECONDS", 60 * 60 * 24)
    )

    # Admin配置
    ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "admin123")
    ADMIN_SESSION_SECRET: str = os.environ.get(
        "ADMIN_SESSION_SECRET", "CHANGE_ME_ADMIN_SESSION_SECRET"
    )

    # 环境标识：production / development
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")

    class Config:
        env_file = ".env"

    @model_validator(mode="after")
    def _check_insecure_defaults(self) -> "Settings":
        """启动时校验是否存在不安全的默认密钥"""
        is_prod = self.ENVIRONMENT.lower() in ("production", "prod")

        warnings = []
        if self.SECRET_KEY in _INSECURE_DEFAULTS:
            warnings.append("SECRET_KEY 使用了不安全的默认值！JWT 签名可被伪造")
        if self.ADMIN_PASSWORD in _INSECURE_DEFAULTS:
            warnings.append("ADMIN_PASSWORD 使用了不安全的默认值！后台将被入侵")
        if self.ADMIN_SESSION_SECRET in _INSECURE_DEFAULTS:
            warnings.append(
                "ADMIN_SESSION_SECRET 使用了不安全的默认值！Session 可被篡改"
            )

        if warnings:
            msg = (
                "\n⚠️  安全配置告警 ⚠️\n"
                + "\n".join(f"  - {w}" for w in warnings)
                + "\n请通过环境变量或 .env 文件设置安全密钥"
            )
            if is_prod:
                raise ValueError(msg + "\n生产环境无法启动，请先修复。")
            else:
                _config_logger.warning(msg + "\n(开发环境已放行，生产部署务必修改)")

        return self


settings = Settings()
