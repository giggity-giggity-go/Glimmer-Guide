"""统一日志"""
from __future__ import annotations

import sys
from loguru import logger

# 移除默认 handler
logger.remove()
# 简洁格式
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
)
