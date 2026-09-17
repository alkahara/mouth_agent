"""
统一的日志配置模块
分为系统级日志和图级日志两种
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path


class LoggingConfig:
    """日志配置管理器"""

    # 日志格式
    CONSOLE_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s'
    FILE_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    DATE_FORMAT = '%H:%M:%S'
    FILE_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    # 日志级别
    CONSOLE_LEVEL = logging.INFO
    FILE_LEVEL = logging.DEBUG

    # 日志目录
    LOG_DIR = None

    @classmethod
    def initialize(cls, log_dir: str = None):
        """初始化日志系统"""
        # 确定日志目录
        if log_dir:
            cls.LOG_DIR = Path(log_dir)
        else:
            # 默认在项目根目录下的 logs 文件夹
            project_root = Path(__file__).parent.parent
            cls.LOG_DIR = project_root / 'logs'

        # 创建日志目录
        cls.LOG_DIR.mkdir(exist_ok=True)

        # 配置根日志记录器
        cls._configure_root_logger()

        logging.info(f"日志系统已初始化，日志目录: {cls.LOG_DIR}")

    @classmethod
    def _configure_root_logger(cls):
        """配置根日志记录器（系统级）"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # 清除现有处理器
        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        # 控制台处理器 - 只显示 INFO 及以上
        console_handler = logging.StreamHandler()
        console_handler.setLevel(cls.CONSOLE_LEVEL)
        console_formatter = logging.Formatter(
            cls.CONSOLE_FORMAT, datefmt=cls.DATE_FORMAT
        )
        console_handler.setFormatter(console_formatter)

        # ✅ 系统日志文件处理器 - 使用 TimedRotatingFileHandler
        system_log_file = cls.LOG_DIR / 'system.log'
        system_file_handler = TimedRotatingFileHandler(
            filename=system_log_file,
            when='midnight',  # 每天午夜轮转
            interval=1,  # 每1天
            backupCount=30,  # 保留30天的日志
            encoding='utf-8',
            delay=True,  # 延迟创建文件，避免启动时锁定
        )
        # ✅ 配置日志文件名格式：system.log.20260205
        system_file_handler.suffix = "%Y%m%d"
        system_file_handler.setLevel(cls.FILE_LEVEL)
        file_formatter = logging.Formatter(
            cls.FILE_FORMAT, datefmt=cls.FILE_DATE_FORMAT
        )
        system_file_handler.setFormatter(file_formatter)

        # 添加处理器
        root_logger.addHandler(console_handler)
        root_logger.addHandler(system_file_handler)

    @classmethod
    def get_graph_logger(cls, graph_type: str, graph_class_name: str) -> logging.Logger:
        """
        获取图专用的日志记录器

        Args:
            graph_type: 图类型标识符（如 'general_graph'）
            graph_class_name: 图类名（如 'GeneralGraph'）

        Returns:
            配置好的日志记录器
        """
        # 确保日志系统已初始化，避免 LOG_DIR 为空
        if cls.LOG_DIR is None:
            cls.initialize()

        # 创建图专用的 logger
        logger_name = f"graph.{graph_type}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)

        # 防止日志向上传播到根 logger
        logger.propagate = False

        # 避免重复添加处理器
        if logger.hasHandlers():
            logger.handlers.clear()

        # 控制台处理器 - 只显示 INFO 及以上
        console_handler = logging.StreamHandler()
        console_handler.setLevel(cls.CONSOLE_LEVEL)
        console_formatter = logging.Formatter(
            cls.CONSOLE_FORMAT, datefmt=cls.DATE_FORMAT
        )
        console_handler.setFormatter(console_formatter)

        # ✅ 图专用日志文件处理器 - 使用 TimedRotatingFileHandler
        graph_log_file = cls.LOG_DIR / f'{graph_type}.log'
        graph_file_handler = TimedRotatingFileHandler(
            filename=graph_log_file,
            when='midnight',  # 每天午夜轮转
            interval=1,  # 每1天
            backupCount=30,  # 保留30天的日志
            encoding='utf-8',
            delay=True,  # 延迟创建文件，避免启动时锁定
        )
        # ✅ 配置日志文件名格式：omni_graph.log.20260205
        graph_file_handler.suffix = "%Y%m%d"
        graph_file_handler.setLevel(cls.FILE_LEVEL)
        file_formatter = logging.Formatter(
            cls.FILE_FORMAT, datefmt=cls.FILE_DATE_FORMAT
        )
        graph_file_handler.setFormatter(file_formatter)

        # 添加处理器
        logger.addHandler(console_handler)
        logger.addHandler(graph_file_handler)
        return logger

    @classmethod
    def get_system_logger(cls, module_name: str) -> logging.Logger:
        """
        获取系统级日志记录器

        Args:
            module_name: 模块名称

        Returns:
            系统级日志记录器
        """
        return logging.getLogger(module_name)
