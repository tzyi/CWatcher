"""
CWatcher 依賴注入系統

提供 FastAPI 依賴注入函數，包括資料庫會話、身份驗證等
"""

from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from db.base import AsyncSessionLocal
from core.config import settings


# 資料庫依賴
async def get_db() -> AsyncGenerator[AsyncSession, None]:
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


# 設定依賴
def get_settings():
    """取得應用程式設定"""
    return settings


# JWT 認證依賴
security = HTTPBearer()


def create_access_token(data: dict) -> str:
    """創建 JWT 訪問令牌"""
    to_encode = data.copy()
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm="HS256"
    )
    return encoded_jwt


def verify_token(token: str) -> dict:
    """驗證 JWT 令牌"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    取得當前已認證用戶
    
    從 JWT 令牌中解析用戶資訊
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    # TODO: 從資料庫查詢用戶資訊（Phase 2 實現）
    # 目前返回令牌載荷
    return payload


# 可選的認證依賴（用於某些不需要強制認證的端點）
async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict | None:
    """
    取得可選的當前用戶
    
    如果提供有效令牌則返回用戶資訊，否則返回 None
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token)
        return payload
    except HTTPException:
        return None


# 資料庫查詢協助函數
async def get_db_session() -> AsyncSession:
    """
    取得單個資料庫會話
    
    用於非 FastAPI 上下文中的資料庫操作
    """
    async with AsyncSessionLocal() as session:
        return session


# 管理員權限檢查
async def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    要求管理員權限
    
    檢查當前用戶是否具有管理員權限
    """
    # TODO: 實現用戶角色系統（Phase 2）
    # 目前所有認證用戶都有管理員權限
    return current_user


# API 限流依賴（簡單實現）
class RateLimitChecker:
    """API 請求頻率限制檢查器"""
    
    def __init__(self, max_requests: int = 100, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        # TODO: 實現基於 Redis 的分散式限流（Phase 3）
        self._requests = {}
    
    async def __call__(self, request):
        """檢查請求頻率限制"""
        # 簡單實現，生產環境需要更複雜的邏輯
        client_ip = request.client.host
        
        # TODO: 實現真正的限流邏輯
        # 目前總是允許請求
        return True


# 建立限流實例
rate_limiter = RateLimitChecker()


# WebSocket 連接管理依賴
class ConnectionManager:
    """WebSocket 連接管理器"""
    
    def __init__(self):
        self.active_connections: list = []
    
    async def connect(self, websocket):
        """接受 WebSocket 連接"""
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket):
        """斷開 WebSocket 連接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket):
        """發送個人訊息"""
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        """廣播訊息給所有連接"""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # 移除失效的連接
                await self.disconnect(connection)


# 建立 WebSocket 管理器實例
websocket_manager = ConnectionManager()


def get_websocket_manager() -> ConnectionManager:
    """取得 WebSocket 連接管理器"""
    return websocket_manager