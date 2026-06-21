"""Environment-driven backend configuration.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
Settings are loaded through Pydantic so Docker, local development, and tests can
share one typed configuration surface.
"""

import logging
import os

from pydantic import model_validator
from pydantic_settings import BaseSettings

_config_logger = logging.getLogger("app.core.config")

# Startup rejects these defaults in production-facing secret fields.
_INSECURE_DEFAULTS = {
    "YOUR_SECRET_KEY_CHANGE_ME",
    "CHANGE_ME_ADMIN_SESSION_SECRET",
    "admin123",
    "password",
    "secret",
}


class Settings(BaseSettings):
    """Typed settings loaded from environment variables and `.env`."""

    PROJECT_NAME: str = "ZJUers Simulator"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "YOUR_SECRET_KEY_CHANGE_ME"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # Defaults use Compose service names; local overrides may point to localhost.
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://zju:password@db/zjuers"
    )

    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    REDIS_PLAYER_TTL_SECONDS: int = int(
        os.environ.get("REDIS_PLAYER_TTL_SECONDS", 60 * 60 * 24)
    )

    ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "admin123")
    ADMIN_SESSION_SECRET: str = os.environ.get(
        "ADMIN_SESSION_SECRET", "CHANGE_ME_ADMIN_SESSION_SECRET"
    )

    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
    DATABASE_ECHO: bool | None = None
    CREATE_ALL_ON_STARTUP: bool | None = None

    # MiniMax M2-her powers DingTalk roleplay unless players supply overrides.
    MINIMAX_API_KEY: str = os.environ.get("MINIMAX_API_KEY", "")
    MINIMAX_MODEL: str = os.environ.get("MINIMAX_MODEL", "M2-her")
    MINIMAX_BASE_URL: str = os.environ.get(
        "MINIMAX_BASE_URL",
        "https://api.minimaxi.com/v1",
    )
    INVITE_CODES: str = ""

    class Config:
        env_file = ".env"

    @model_validator(mode="after")
    def _check_insecure_defaults(self) -> "Settings":
        """Warn or fail when production still uses known insecure defaults."""
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
