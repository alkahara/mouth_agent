#!/usr/bin/env python3
"""
OpenAI Compatible API Server
FastAPI + LangGraph implementation
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

# ✅ 关键修复：Windows 平台事件循环策略（必须在所有导入之前）
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 加载 .env 配置文件
load_dotenv()

import uvicorn
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# 初始化日志系统（必须在其他导入之前）
from src.logging_config import LoggingConfig

LoggingConfig.initialize()

# 现在可以安全地导入其他模块
logger = LoggingConfig.get_system_logger(__name__)

from src.main import app
from src.config import config


def main():
    """Main entry point"""
    # Get server configuration from environment or config
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"

    logger.info("Starting OpenAI Compatible API Server...")
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Debug: {debug}")
    logger.info(f"Available models: {config.list_available_models()}")

    # Run the server
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if not debug else "debug",
        access_log=True,
    )


if __name__ == "__main__":
    main()
