"""
CWatcher 應用程式配置設定

使用 Pydantic Settings 管理環境變數和配置
支援開發、測試、生產環境的不同配置
"""

import os
from typing import List, Any, Dict, Optional
from pydantic import field_validator, AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """應用程式設定類別"""
    
    # 專案基本資訊
    PROJECT_NAME: str = "CWatcher"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "Linux 系統監控平台"
    
    # 環境設定
    ENVIRONMENT: str = "development"  # development, testing, production
    DEBUG: bool = True
    
    # API 設定
    API_V1_STR: str = "/api/v1"
    
    # 伺服器設定
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 資料庫設定
    DATABASE_URL: str = "mysql+aiomysql://cabie:Aa-12345@localhost:3306/cwatcher"
    
    # 測試資料庫
    TEST_DATABASE_URL: Optional[str] = None
    
    # CORS 設定 - 直接使用字串，在應用中解析  
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:8080,http://192.168.10.165:3000,http://192.168.10.165:3001"
    
    # JWT 設定
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # SSH 連接設定
    SSH_CONNECT_TIMEOUT: int = 10  # 秒
    SSH_MAX_CONNECTIONS: int = 3   # 每個伺服器最大並發連接數
    SSH_COMMAND_TIMEOUT: int = 30  # SSH 指令執行超時
    
    # 監控設定
    MONITORING_INTERVAL: int = 30  # 監控間隔（秒）
    DATA_RETENTION_DAYS: int = 30  # 數據保留天數
    MAX_SERVERS: int = 50          # 最大監控伺服器數量
    
    # WebSocket 設定
    WS_HEARTBEAT_INTERVAL: int = 30  # WebSocket 心跳間隔
    
    # 安全性設定
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # 日誌設定
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/cwatcher.log"
    
    # Redis 設定（如果使用 Redis 作為快取）
    REDIS_URL: Optional[str] = None
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }


# 建立全域設定實例
settings = Settings()


def get_settings() -> Settings:
    """取得應用程式設定"""
    return settings


def get_cors_origins() -> List[str]:
    """取得 CORS 允許的來源列表"""
    origins = settings.BACKEND_CORS_ORIGINS
    if isinstance(origins, str):
        return [origin.strip() for origin in origins.split(",")]
    return origins