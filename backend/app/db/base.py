"""
CWatcher 資料庫基礎設定

提供 SQLAlchemy 2.0 異步基礎類別和資料庫連接管理
支援 MySQL 8.0 並配置適當的連接池和會話管理
"""

from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from core.config import settings

# 建立異步 SQLAlchemy 引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    # 連接池配置
    pool_size=20,              # 連接池大小
    max_overflow=30,           # 最大溢出連接數
    pool_pre_ping=True,        # 連接前檢查
    pool_recycle=3600,         # 連接回收時間（秒）
    echo=settings.DEBUG,       # 是否輸出 SQL 語句
    # MySQL 特定設定
    connect_args={
        "charset": "utf8mb4",
    }
)

# 建立同步 SQLAlchemy 引擎（用於後台任務）
sync_engine = create_engine(
    settings.DATABASE_URL.replace("+aiomysql", "+pymysql"),  # 使用同步驅動
    # 連接池配置
    pool_size=10,              # 連接池大小
    max_overflow=20,           # 最大溢出連接數
    pool_pre_ping=True,        # 連接前檢查
    pool_recycle=3600,         # 連接回收時間（秒）
    echo=settings.DEBUG,       # 是否輸出 SQL 語句
    # MySQL 特定設定
    connect_args={
        "charset": "utf8mb4",
    }
)

# 建立異步會話工廠
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 建立同步會話工廠（用於後台任務）
SyncSessionLocal = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 建立基礎模型類別
Base = declarative_base()

# 設定元數據命名約定
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
)
Base.metadata = metadata


async def get_db() -> AsyncSession:
    """
    取得異步資料庫會話
    
    用於 FastAPI 依賴注入系統
    確保會話正確關閉和異常處理
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化資料庫，建立所有表格"""
    async with engine.begin() as conn:
        # 匯入所有模型以確保表格被建立
        from models import server, system_metrics, system_info
        
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """關閉資料庫連接"""
    await engine.dispose()


def get_sync_db() -> Session:
    """
    取得同步資料庫會話（用於後台任務）
    
    用於非 FastAPI 環境的背景任務和服務
    """
    session = SyncSessionLocal()
    try:
        return session
    except Exception:
        session.close()
        raise