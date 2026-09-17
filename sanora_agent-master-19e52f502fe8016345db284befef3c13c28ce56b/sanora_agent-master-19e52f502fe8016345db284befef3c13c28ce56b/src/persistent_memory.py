import logging
import os
import sys
from urllib.parse import quote_plus
import asyncio

from langgraph.checkpoint.memory import MemorySaver

# PostgreSQL 相关导入改为可选（延迟导入）
# from langgraph.checkpoint.postgres import PostgresSaver
# import psycopg
# from psycopg.rows import dict_row

try:
    from .config import config
except ImportError:
    from config import config

logger = logging.getLogger(__name__)


def _build_dsn() -> str:
    """构建PostgreSQL连接字符串，对特殊字符进行URL编码"""
    pg = config.database.postgres
    if getattr(pg, "connection_string", ""):
        return pg.connection_string

    # 对密码进行URL编码
    encoded_password = quote_plus(pg.password)

    return f"postgresql://{pg.username}:{encoded_password}@{pg.host}:{pg.port}/{pg.database}"


# 模块级单例，保证全进程共享同一个 Saver/连接
_CHECKPOINTER = None
_CHECKPOINTER_CTX = None  # from_conn_string 的上下文，用于关闭连接
_CHECKPOINTER_LOCK = asyncio.Lock()


async def get_checkpointer():
    """优先返回持久化的 AsyncPostgresSaver（已 setup），否则回退 MemorySaver。"""
    global _CHECKPOINTER, _CHECKPOINTER_CTX

    async with _CHECKPOINTER_LOCK:
        if _CHECKPOINTER is not None:
            logger.debug(
                "Reusing existing checkpointer (ctx=%s)",
                bool(_CHECKPOINTER_CTX),
            )
            return _CHECKPOINTER

        pg = config.database.postgres
        if getattr(pg, "enabled", False):
            try:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

                dsn = _build_dsn()
                logger.info(
                    "Initializing PostgreSQL checkpointer (single connection): %s@***",
                    dsn.split("@")[0],
                )

                # 官方推荐：直接使用 from_conn_string，内部设置 autocommit/prepare_threshold/row_factory
                ctx = AsyncPostgresSaver.from_conn_string(dsn)
                cp = await ctx.__aenter__()
                try:
                    await cp.setup()
                except Exception:
                    # setup 失败时确保关闭连接
                    await ctx.__aexit__(*sys.exc_info())
                    raise
                _CHECKPOINTER_CTX = ctx
                _CHECKPOINTER = cp
                logger.info(
                    "AsyncPostgresSaver initialized successfully (single-connection from_conn_string)"
                )
                return _CHECKPOINTER
            except ImportError as e:
                logger.warning(f"PostgreSQL dependencies not available: {e}")
            except Exception as e:
                logger.error(f"Failed to initialize PostgreSQL checkpointer: {e}")
                if _CHECKPOINTER_CTX:
                    try:
                        await _CHECKPOINTER_CTX.__aexit__(*sys.exc_info())
                    except Exception:
                        logger.warning(
                            "Failed to close PG ctx after init error", exc_info=True
                        )
                    finally:
                        _CHECKPOINTER_CTX = None

        # 回退到支持异步的 SQLite
        logger.info("Using MemorySaver as fallback checkpointer (PostgreSQL disabled or init failed)")

        _CHECKPOINTER = MemorySaver()
        return _CHECKPOINTER


def get_checkpointer_sync():
    """同步包装器，用于在 __init__ 等同步上下文中调用"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(get_checkpointer())


# 简单连通测试
def test_db_connection() -> bool:
    try:
        dsn = _build_dsn()
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone()[0] == 1
    except Exception as e:
        logger.error(f"DB test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # 获取可复用的 checkpointer（若启用 PG 会自动 setup 并持久化）
    cp = get_checkpointer()

    # 最小记忆图自测：两次调用是否"记得上次"
    from typing import TypedDict, Annotated, List
    from operator import add
    from langgraph.graph import StateGraph, START, END

    class State(TypedDict):
        messages: Annotated[List[str], add]

    def bot_node(s: State):
        last = s["messages"][-1]
        return {"messages": [f"记忆检验：你刚才说：{last}"]}

    builder = StateGraph(State)
    builder.add_node("bot", bot_node)
    builder.add_edge(START, "bot")
    builder.add_edge("bot", END)

    graph = builder.compile(checkpointer=cp)

    cfg = {"configurable": {"thread_id": "demo-12222221231222"}}
    print("== 第一次 ==")
    print(graph.invoke({"messages": ["你好"]}, cfg))

    print("== 第二次 ==")
    print(graph.invoke({"messages": ["我刚才说了什么？"]}, cfg))
