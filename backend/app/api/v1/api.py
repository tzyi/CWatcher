"""
API v1 路由匯總

統一管理所有 v1 版本的 API 路由
"""

from fastapi import APIRouter

# 導入已實現的端點
from api.v1.endpoints import ssh, command, monitoring, data_management, websocket, servers, task_management

api_router = APIRouter()

# 包含 SSH 管理路由
api_router.include_router(ssh.router, prefix="/ssh", tags=["SSH 管理"])

# 包含指令執行路由
api_router.include_router(command.router, prefix="/command", tags=["指令執行"])

# 包含監控數據路由
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["監控數據"])

# 包含數據管理路由
api_router.include_router(data_management.router, prefix="/data", tags=["數據管理"])

# 包含 WebSocket 路由
api_router.include_router(websocket.router, prefix="/websocket", tags=["WebSocket 即時推送"])

# 包含伺服器管理路由
api_router.include_router(servers.router, prefix="/servers", tags=["伺服器管理"])

# 包含任務管理路由
api_router.include_router(task_management.router, prefix="/tasks", tags=["任務管理"])

# TODO: 在實現具體端點後取消註解
# api_router.include_router(auth.router, prefix="/auth", tags=["認證"])

# 臨時健康檢查端點
@api_router.get("/ping")
async def ping():
    """API 健康檢查"""
    return {"message": "pong"}

@api_router.get("/health")
async def api_health_check():
    """API 健康檢查端點"""
    return {
        "message": "CWatcher API v1 Service",
        "version": "0.1.0",
        "status": "running"
    }