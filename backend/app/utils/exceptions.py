"""
CWatcher 自訂異常類別

定義應用程式中使用的各種異常類型
"""

from typing import Optional, Dict, Any


class CWatcherException(Exception):
    """CWatcher 基礎異常類別"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class SSHConnectionError(CWatcherException):
    """SSH 連接相關錯誤"""
    
    def __init__(self, message: str, host: Optional[str] = None, port: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        self.host = host
        self.port = port
        super().__init__(message, details)


class CommandExecutionError(CWatcherException):
    """指令執行相關錯誤"""
    
    def __init__(self, message: str, command: Optional[str] = None, exit_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        self.command = command
        self.exit_code = exit_code
        super().__init__(message, details)


class SecurityError(CWatcherException):
    """安全相關錯誤"""
    
    def __init__(self, message: str, command: Optional[str] = None, security_level: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.command = command
        self.security_level = security_level
        super().__init__(message, details)


class EncryptionError(CWatcherException):
    """加密/解密相關錯誤"""
    pass


class DatabaseError(CWatcherException):
    """資料庫相關錯誤"""
    pass


class ValidationError(CWatcherException):
    """資料驗證相關錯誤"""
    pass


class AuthenticationError(CWatcherException):
    """認證相關錯誤"""
    pass


class AuthorizationError(CWatcherException):
    """授權相關錯誤"""
    pass


class ConfigurationError(CWatcherException):
    """配置相關錯誤"""
    pass


class SystemInfoCollectionError(CWatcherException):
    """系統資訊收集相關錯誤"""
    
    def __init__(self, message: str, info_type: Optional[str] = None, server_info: Optional[Dict[str, str]] = None, details: Optional[Dict[str, Any]] = None):
        self.info_type = info_type
        self.server_info = server_info
        super().__init__(message, details)


class MonitoringError(CWatcherException):
    """監控相關錯誤"""
    pass


class NotificationError(CWatcherException):
    """通知相關錯誤"""
    pass