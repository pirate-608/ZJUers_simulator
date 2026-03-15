"""
统一结构化日志配置

支持两种输出格式：
- development: 彩色可读格式，便于本地调试
- production:  JSON 结构化格式，便于 ELK/Loki 等日志系统采集

所有现有的 logger.info/error/warning 调用无需修改。
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON 结构化日志格式器（生产环境）"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 附加上下文字段（通过 extra 传入）
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "action"):
            log_entry["action"] = record.action
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        # 异常信息
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
            }
            if record.exc_text:
                log_entry["exception"]["traceback"] = record.exc_text
            else:
                log_entry["exception"]["traceback"] = self.formatException(
                    record.exc_info
                )

        # 来源定位
        if record.levelno >= logging.WARNING:
            log_entry["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class DevFormatter(logging.Formatter):
    """彩色可读日志格式器（开发环境）"""

    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level = f"{color}{record.levelname:<8}{self.RESET}"
        name = f"\033[90m{record.name}\033[0m"

        msg = f"{timestamp} {level} {name} │ {record.getMessage()}"

        # 附加 extra 字段
        extras = []
        for key in ("user_id", "action", "duration_ms"):
            if hasattr(record, key):
                extras.append(f"{key}={getattr(record, key)}")
        if extras:
            msg += f"  \033[90m({', '.join(extras)})\033[0m"

        # 异常信息
        if record.exc_info and record.exc_info[1]:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def setup_logging(
    environment: str = "development",
    level: Optional[str] = None,
) -> None:
    """
    初始化全局日志配置。应在应用启动时调用一次。

    Args:
        environment: "development" 或 "production"
        level: 日志级别，默认 dev=DEBUG / prod=INFO
    """
    is_prod = environment.lower() in ("production", "prod")

    if level is None:
        log_level = logging.INFO if is_prod else logging.DEBUG
    else:
        log_level = getattr(logging, level.upper(), logging.INFO)

    # 选择格式器
    if is_prod:
        formatter = JSONFormatter()
    else:
        formatter = DevFormatter()

    # 配置 root handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # 配置根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除已有 handler（避免重复）
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # 降低第三方库噪音
    for noisy_logger in (
        "uvicorn.access",
        "uvicorn.error",
        "httpcore",
        "httpx",
        "asyncio",
        "sqlalchemy.engine",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # uvicorn 主日志保留 INFO
    logging.getLogger("uvicorn").setLevel(logging.INFO)

    logging.getLogger(__name__).info(
        "Logging initialized: env=%s, level=%s, format=%s",
        environment,
        logging.getLevelName(log_level),
        "JSON" if is_prod else "colored",
    )
