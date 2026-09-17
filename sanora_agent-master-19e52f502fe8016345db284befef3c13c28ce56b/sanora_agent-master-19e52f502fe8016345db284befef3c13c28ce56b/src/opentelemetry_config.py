import logging
from typing import Optional, Union
from os import environ

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk._logs import LoggerProvider as SDKLoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider as SDKMeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry._logs import set_logger_provider, get_logger_provider
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry._logs import get_logger


# 全局变量用于存储初始化状态
_otel_initialized = False


# ✅ 早期初始化LLM仪器化，确保在任何LLM客户端创建前执行
def _setup_llm_instrumentation():
    """在模块加载时就设置LLM仪器化，确保在任何LLM客户端初始化前执行"""
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from openinference.instrumentation.langchain import LangChainInstrumentor
        
        # 必须在首次调用 openai/langchain 前 instrument
        OpenAIInstrumentor().instrument()
        LangChainInstrumentor().instrument()
        print("✅ OpenTelemetry OpenAI and LangChain instrumentation enabled (early setup)")
    except ImportError as e:
        print(f"⚠️ LLM instrumentation not available: {e}")
    except Exception as e:
        print(f"⚠️ Failed to enable LLM instrumentation (early setup): {e}")


def setup_opentelemetry(service_name: str = None):
    """
    设置OpenTelemetry配置（追踪、日志、指标）

    Args:
        service_name (str): 服务名称，默认从环境变量OTEL_SERVICE_NAME获取，回退到"rooyee-agent"
    """
    global _otel_initialized

    if _otel_initialized:
        return

    # 从环境变量获取服务名称，如果未设置则使用默认值
    if service_name is None:
        service_name = environ.get("OTEL_SERVICE_NAME", "rooyee-agent")

    # 创建统一资源
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0"
    })
    # 初始化各组件（顺序重要：tracing → logging → metrics）
    setup_tracing(resource)    # ✅ 启用 tracing（必须）
    setup_logging(service_name)
    setup_metrics(resource)

    # 在OpenTelemetry配置完成后执行LLM仪器化
    _setup_llm_instrumentation()

    _otel_initialized = True



def setup_tracing(resource: Resource):
    """设置追踪配置"""
    current = trace.get_tracer_provider()
    if isinstance(current, SDKTracerProvider):
        return

    tracer_provider = SDKTracerProvider(resource=resource)
    otlp_endpoint = environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://47.111.67.253:4317")
    otlp_span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
    trace.set_tracer_provider(tracer_provider)



def setup_logging(service_name: Optional[str] = None, level: Optional[Union[str, int]] = None):
    """设置日志配置（OTLP + 控制台）"""
    if level is None:
        level_str = environ.get('LOG_LEVEL', 'INFO').upper()
        level = getattr(logging, level_str, logging.INFO)

    if service_name is None:
        service_name = environ.get("OTEL_SERVICE_NAME", "rooyee-agent")
    resource = Resource.create({"service.name": service_name})

    current = get_logger_provider()
    if isinstance(current, SDKLoggerProvider):
        return

    logger_provider = SDKLoggerProvider(resource=resource)
    set_logger_provider(logger_provider)

    otlp_endpoint = environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://47.111.67.253:4317")
    exporter = OTLPLogExporter(endpoint=otlp_endpoint, insecure=True)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    # 安全添加处理器：避免重复，保留控制台
    root_logger = logging.getLogger()
    if level is not None:
        root_logger.setLevel(level)

    # 移除可能存在的旧OTel handler（避免重复）
    for handler in list(root_logger.handlers):
        if isinstance(handler, LoggingHandler):
            root_logger.removeHandler(handler)

    # 添加OTel handler
    otel_handler = LoggingHandler(logger_provider=logger_provider)
    root_logger.addHandler(otel_handler)

    # 确保有控制台handler
    has_console = any(
        isinstance(h, logging.StreamHandler) and hasattr(h.stream, 'name') and h.stream.name == '<stdout>'
        for h in root_logger.handlers
    )
    if not has_console:
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    root_logger.propagate = True



def setup_metrics(resource: Resource):
    """设置指标配置"""
    current = metrics.get_meter_provider()
    if isinstance(current, SDKMeterProvider):
        return

    otlp_endpoint = environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://47.111.67.253:4317")
    otlp_metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
    # 添加错误处理和重试机制，保持默认导出间隔
    reader = PeriodicExportingMetricReader(
        otlp_metric_exporter,
        export_timeout_millis=30000
    )
    meter_provider = SDKMeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)



def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """获取标准logging.Logger实例"""
    logger = logging.getLogger(name)
    if level:
        logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))
    return logger



def instrument_fastapi(app):
    """为FastAPI应用添加仪器化"""
    FastAPIInstrumentor.instrument_app(app)
    print("✅ FastAPI instrumentation enabled")



def shutdown():
    """Shutdown OpenTelemetry providers"""
    try:
        trace.get_tracer_provider().shutdown()
        metrics.get_meter_provider().shutdown()
        get_logger_provider().shutdown()
    except Exception as e:
        print(f"⚠️ Error during OpenTelemetry shutdown: {e}")


# 当模块被导入时自动初始化OpenTelemetry
setup_opentelemetry()

# Create tracer, meter, and logger instances for direct use
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)
logger = get_logger(__name__)

# 导出配置和实例用于外部访问
otel_config = {
    "tracer": tracer,
    "meter": meter,
    "logger": logger,
    "setup_opentelemetry": setup_opentelemetry,
    "instrument_fastapi": instrument_fastapi,
    "shutdown": shutdown,
    "get_logger": get_logger
}
