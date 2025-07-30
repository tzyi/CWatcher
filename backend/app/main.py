"""
CWatcher FastAPI 主應用程式

Linux 系統監控平台的後端 API 服務
提供 SSH 連接管理、系統監控數據收集、即時 WebSocket 通訊等功能
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import traceback

from core.config import settings, get_cors_origins
from db.base import init_db, close_db
from services.auth_service import AuthenticationError
from utils.encryption import EncryptionError


print('>>> [main.py] 啟動 main.py')


@asynccontextmanager
async def lifespan(app: FastAPI):
    print('>>> [main.py] 進入 lifespan context manager')
    """應用程式生命週期管理"""
    # 啟動時執行
    print("🚀 CWatcher 後端服務啟動中...")
    
    # 初始化資料庫連接
    try:
        await init_db()
        print("✅ 資料庫連接初始化完成")
    except Exception as e:
        print(f"❌ 資料庫初始化失敗: {e}")
        raise
    
    # 啟動任務調度器
    try:
        from services.task_scheduler import start_task_scheduler
        await start_task_scheduler()
        print("✅ 任務調度器啟動完成")
    except Exception as e:
        print(f"❌ 任務調度器啟動失敗: {e}")
        # 任務調度器失敗不會阻止服務啟動
    
    # 啟動任務協調器
    try:
        from services.task_coordinator import start_task_coordinator
        await start_task_coordinator()
        print("✅ 任務協調器啟動完成")
    except Exception as e:
        print(f"❌ 任務協調器啟動失敗: {e}")
        # 協調器失敗不會阻止服務啟動
    
    # 初始化 WebSocket 管理器
    try:
        from api.v1.endpoints.websocket import setup_websocket_manager
        await setup_websocket_manager()
        print("✅ WebSocket 管理器初始化完成")
    except Exception as e:
        print(f"❌ WebSocket 管理器初始化失敗: {e}")
    
    yield
    
    # 關閉時執行
    print("🛑 CWatcher 後端服務關閉中...")
    
    # 停止任務協調器
    try:
        from services.task_coordinator import stop_task_coordinator
        await stop_task_coordinator()
        print("✅ 任務協調器已停止")
    except Exception as e:
        print(f"❌ 任務協調器停止失敗: {e}")
    
    # 停止任務調度器
    try:
        from services.task_scheduler import stop_task_scheduler
        await stop_task_scheduler()
        print("✅ 任務調度器已停止")
    except Exception as e:
        print(f"❌ 任務調度器停止失敗: {e}")
    
    # 關閉 WebSocket 管理器
    try:
        from api.v1.endpoints.websocket import shutdown_websocket_manager
        await shutdown_websocket_manager()
        print("✅ WebSocket 管理器已關閉")
    except Exception as e:
        print(f"❌ WebSocket 管理器關閉失敗: {e}")
    
    # 關閉資料庫連接
    try:
        await close_db()
        print("✅ 資料庫連接已關閉")
    except Exception as e:
        print(f"❌ 資料庫關閉失敗: {e}")


# 建立 FastAPI 應用程式實例
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# 設定 CORS 中間件
cors_origins = get_cors_origins()
if settings.ENVIRONMENT == "development":
    # 開發環境允許所有來源
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True if cors_origins != ["*"] else False,  # credentials 與 "*" 不兼容
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# 添加信任主機中間件（生產環境安全）
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=settings.ALLOWED_HOSTS
    )


# 全域異常處理器
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 異常處理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Exception",
            "detail": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全域異常處理器"""
    error_detail = str(exc)
    
    if settings.DEBUG:
        # 開發模式顯示完整錯誤訊息
        error_detail = {
            "error": error_detail,
            "traceback": traceback.format_exc()
        }
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": error_detail
        }
    )


@app.exception_handler(AuthenticationError)
async def auth_error_handler(request: Request, exc: AuthenticationError):
    """認證錯誤處理器"""
    return JSONResponse(
        status_code=401,
        content={"detail": f"認證錯誤: {str(exc)}"}
    )


@app.exception_handler(EncryptionError)
async def encryption_error_handler(request: Request, exc: EncryptionError):
    """加密錯誤處理器"""
    return JSONResponse(
        status_code=500,
        content={"detail": f"加密錯誤: {str(exc)}"}
    )


# 包含 API 路由
from api.v1.api import api_router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """根路由 - 健康檢查"""
    return {
        "message": "CWatcher API Service",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康檢查端點"""
    from db.base import engine
    from sqlalchemy import text
    
    # 檢查資料庫連接
    db_status = "healthy"
    try:
        # 測試資料庫連接
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "cwatcher-backend",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.ENVIRONMENT == "development" else False
    )