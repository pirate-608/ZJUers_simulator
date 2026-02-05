"""
单机版配置文件
支持 SQLite 和 fakeredis，用于打包成独立可执行文件
"""

from pydantic_settings import BaseSettings
import os
import sys
from pathlib import Path


def get_base_path():
    """获取应用程序的基础路径（支持PyInstaller打包）"""
    if getattr(sys, "frozen", False):
        # 打包后的可执行文件
        return Path(sys._MEIPASS)
    else:
        # 开发环境
        return Path(__file__).parent.parent.parent


class StandaloneSettings(BaseSettings):
    PROJECT_NAME: str = "ZJUers Simulator (单机版)"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = "zjuers-simulator-standalone-secret-key-2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # Token有效期7天

    # 运行模式
    STANDALONE_MODE: bool = True

    # 自动打开浏览器（单机版默认开启）
    AUTO_OPEN_BROWSER: bool = True

    # SQLite 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./zjuers_data.db"

    # fakeredis 配置（使用内存模式）
    REDIS_URL: str = "redis://localhost:6379/0"  # fakeredis 会拦截
    USE_FAKE_REDIS: bool = True

    # 大模型配置（可选）
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM: str = "gpt-3.5-turbo"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 单机版设置实例
standalone_settings = StandaloneSettings()
