"""
Phoenix 可观测性配置模块

配置来源: 环境变量 (.env 文件)

环境变量说明:
- PHOENIX_ENABLED: 是否启用追踪 (true/false)，默认 false
- PHOENIX_COLLECTOR_ENDPOINT: Phoenix 追踪端点
- PHOENIX_PROJECT_NAME: 项目名称 (用于在 Phoenix UI 中区分)

生产环境注意事项:
- 追踪失败时优雅降级，不影响主业务
- 使用 phoenix.otel.register() 官方方式配置
"""

import os
import logging

logger = logging.getLogger(__name__)


def _get_bool_env(key: str, default: bool = False) -> bool:
    """获取布尔类型环境变量"""
    value = os.getenv(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off"):
        return False
    return default


# 从环境变量读取配置
PHOENIX_ENABLED = _get_bool_env("PHOENIX_ENABLED", False)

PHOENIX_COLLECTOR_ENDPOINT = os.getenv(
    "PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces"
)

PHOENIX_PROJECT_NAME = os.getenv("PHOENIX_PROJECT_NAME", "rooyee_agent")

PHOENIX_API_KEY = os.getenv("PHOENIX_API_KEY", "")

_initialized: bool = False


def init_phoenix_tracing() -> bool:
    """
    初始化 Phoenix 追踪

    使用 phoenix.otel.register() 官方方式，自动处理项目名称

    Returns:
        bool: 是否成功初始化
    """
    global _initialized

    if _initialized:
        logger.debug("Phoenix 追踪已初始化，跳过重复初始化")
        return True

    if not PHOENIX_ENABLED:
        logger.info("🔕 Phoenix 追踪已禁用 (phoenix.enabled=false)")
        return False

    try:
        # 使用 Phoenix 官方 OTEL SDK
        from phoenix.otel import register
        from openinference.instrumentation.langchain import LangChainInstrumentor

        # 使用 phoenix.otel.register() 注册追踪
        # 这会自动处理项目名称、端点等配置
        register_kwargs = {
            "project_name": PHOENIX_PROJECT_NAME,
            "endpoint": PHOENIX_COLLECTOR_ENDPOINT,
        }
        if PHOENIX_API_KEY:
            register_kwargs["headers"] = {"authorization": f"Bearer {PHOENIX_API_KEY}"}
        tracer_provider = register(**register_kwargs)

        # 自动追踪所有 LangChain 调用
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

        _initialized = True
        logger.info("✅ Phoenix 追踪初始化成功")
        logger.info(f"   📡 端点: {PHOENIX_COLLECTOR_ENDPOINT}")
        logger.info(f"   📊 项目: {PHOENIX_PROJECT_NAME}")
        return True

    except ImportError as e:
        logger.warning(f"⚠️ Phoenix 依赖未安装，追踪功能不可用: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Phoenix 追踪初始化失败: {e}", exc_info=True)
        return False


def shutdown_phoenix_tracing():
    """关闭 Phoenix 追踪，清理资源"""
    global _initialized

    if _initialized:
        logger.info("🛑 Phoenix 追踪已关闭")

    _initialized = False


def is_phoenix_enabled() -> bool:
    """检查 Phoenix 追踪是否启用"""
    return _initialized and PHOENIX_ENABLED
