"""
数据库连接和会话管理
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import contextmanager, asynccontextmanager

from .models.models import Base

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


def get_database_url(async_mode: bool = False) -> str:
    """获取数据库URL"""
    db_path = PROJECT_ROOT / "data" / "monitor.db"
    # 确保目录存在
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if async_mode:
        return f"sqlite+aiosqlite:///{db_path}"
    return f"sqlite:///{db_path}"


# 同步引擎和会话
engine = create_engine(
    get_database_url(async_mode=False),
    echo=False,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 异步引擎和会话
async_engine = create_async_engine(
    get_database_url(async_mode=True),
    echo=False
)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


def init_db():
    """初始化数据库（创建所有表）"""
    Base.metadata.create_all(bind=engine)


async def init_db_async():
    """异步初始化数据库"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@contextmanager
def get_db_session() -> Session:
    """获取同步数据库会话（上下文管理器）"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def get_async_db_session() -> AsyncSession:
    """获取异步数据库会话（上下文管理器）"""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db():
    """FastAPI依赖注入用的异步会话生成器"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_sync_db():
    """FastAPI依赖注入用的同步会话生成器"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
