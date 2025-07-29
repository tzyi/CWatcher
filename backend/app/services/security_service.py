"""
CWatcher 安全性服務

提供連接白名單檢查、異常連接檢測和安全日誌記錄功能
確保 SSH 連接的安全性和監控系統的整體安全
"""

import logging
import ipaddress
import time
import json
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import re
import threading
from pathlib import Path

from core.config import settings


logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """安全等級"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventType(Enum):
    """安全事件類型"""
    CONNECTION_ATTEMPT = "connection_attempt"
    CONNECTION_SUCCESS = "connection_success"
    CONNECTION_FAILURE = "connection_failure"
    AUTHENTICATION_FAILURE = "auth_failure"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    WHITELIST_VIOLATION = "whitelist_violation"
    COMMAND_BLOCKED = "command_blocked"
    BRUTE_FORCE_DETECTED = "brute_force_detected"


@dataclass
class SecurityEvent:
    """安全事件"""
    event_type: SecurityEventType
    timestamp: datetime
    source_ip: str
    target_host: str
    username: str
    details: Dict[str, Any] = field(default_factory=dict)
    severity: SecurityLevel = SecurityLevel.LOW
    resolved: bool = False


@dataclass 
class RateLimitConfig:
    """速率限制配置"""
    max_requests: int = 10
    time_window: int = 60  # 秒
    block_duration: int = 300  # 秒


@dataclass
class ConnectionAttempt:
    """連接嘗試記錄"""
    timestamp: datetime
    source_ip: str
    target_host: str
    username: str
    success: bool
    error_message: Optional[str] = None


class SecurityService:
    """
    安全性服務
    
    提供完整的安全監控和防護功能
    """
    
    def __init__(self):
        # 白名單管理
        self.ip_whitelist: Set[str] = set()
        self.host_whitelist: Set[str] = set()
        self.user_whitelist: Set[str] = set()
        
        # 黑名單管理
        self.ip_blacklist: Set[str] = set()
        self.blocked_ips: Dict[str, datetime] = {}
        
        # 速率限制
        self.rate_limits: Dict[str, RateLimitConfig] = {
            "connection": RateLimitConfig(max_requests=5, time_window=60, block_duration=600),
            "auth_failure": RateLimitConfig(max_requests=3, time_window=300, block_duration=1800)
        }
        
        # 連接歷史追蹤
        self.connection_history: deque = deque(maxlen=10000)
        self.failed_attempts: Dict[str, List[datetime]] = defaultdict(list)
        
        # 安全事件記錄
        self.security_events: deque = deque(maxlen=5000)
        
        # 危險指令列表
        self.dangerous_commands = {
            "rm -rf /",
            "mkfs",
            "dd if=/dev/zero",
            ":(){ :|:& };:",  # fork bomb
            "chmod -R 777 /",
            "rm -rf /usr",
            "rm -rf /etc",
            "rm -rf /var",
            "format c:",
            "del /f /s /q"
        }
        
        # 可疑模式
        self.suspicious_patterns = [
            r"wget.*\|\s*sh",
            r"curl.*\|\s*sh", 
            r"nc.*-l.*-p",
            r"python.*-c.*exec",
            r"perl.*-e.*exec",
            r"base64.*-d.*exec"
        ]
        
        # 線程鎖
        self.lock = threading.Lock()
        
        # 載入配置
        self._load_security_config()
    
    def _load_security_config(self):
        """載入安全配置"""
        try:
            # 從環境變數或配置文件載入白名單
            default_whitelist = [
                "127.0.0.1",
                "::1",
                "localhost"
            ]
            
            # 可以從配置文件或環境變數擴展
            self.ip_whitelist.update(default_whitelist)
            
            logger.info(f"載入安全配置完成，IP白名單: {len(self.ip_whitelist)} 項")
            
        except Exception as e:
            logger.error(f"載入安全配置失敗: {e}")
    
    def add_to_whitelist(self, item_type: str, item: str) -> bool:
        """
        添加項目到白名單
        
        Args:
            item_type: 類型 (ip, host, user)
            item: 項目值
            
        Returns:
            是否成功添加
        """
        try:
            with self.lock:
                if item_type == "ip":
                    # 驗證 IP 格式
                    ipaddress.ip_address(item)
                    self.ip_whitelist.add(item)
                elif item_type == "host":
                    self.host_whitelist.add(item)
                elif item_type == "user":
                    self.user_whitelist.add(item)
                else:
                    return False
            
            logger.info(f"添加到白名單: {item_type}={item}")
            return True
            
        except Exception as e:
            logger.error(f"添加白名單項目失敗: {e}")
            return False
    
    def remove_from_whitelist(self, item_type: str, item: str) -> bool:
        """從白名單移除項目"""
        try:
            with self.lock:
                if item_type == "ip" and item in self.ip_whitelist:
                    self.ip_whitelist.remove(item)
                elif item_type == "host" and item in self.host_whitelist:
                    self.host_whitelist.remove(item)
                elif item_type == "user" and item in self.user_whitelist:
                    self.user_whitelist.remove(item)
                else:
                    return False
            
            logger.info(f"從白名單移除: {item_type}={item}")
            return True
            
        except Exception as e:
            logger.error(f"移除白名單項目失敗: {e}")
            return False
    
    def check_ip_whitelist(self, ip: str) -> bool:
        """檢查 IP 是否在白名單中"""
        try:
            # 如果白名單為空，允許所有 IP
            if not self.ip_whitelist:
                return True
            
            # 檢查精確匹配
            if ip in self.ip_whitelist:
                return True
            
            # 檢查網段匹配
            ip_obj = ipaddress.ip_address(ip)
            for whitelist_item in self.ip_whitelist:
                try:
                    if '/' in whitelist_item:
                        # CIDR 網段
                        network = ipaddress.ip_network(whitelist_item, strict=False)
                        if ip_obj in network:
                            return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"檢查 IP 白名單失敗: {e}")
            return False
    
    def check_connection_allowed(self, source_ip: str, target_host: str, username: str) -> Tuple[bool, str]:
        """
        檢查連接是否被允許
        
        Args:
            source_ip: 來源 IP
            target_host: 目標主機
            username: 使用者名稱
            
        Returns:
            (是否允許, 拒絕原因)
        """
        # 檢查 IP 黑名單
        if source_ip in self.ip_blacklist:
            return False, "IP 在黑名單中"
        
        # 檢查是否被暫時封鎖
        if source_ip in self.blocked_ips:
            block_until = self.blocked_ips[source_ip]
            if datetime.now() < block_until:
                remaining = (block_until - datetime.now()).seconds
                return False, f"IP 被暫時封鎖，剩餘 {remaining} 秒"
            else:
                # 解除封鎖
                del self.blocked_ips[source_ip]
        
        # 檢查 IP 白名單
        if not self.check_ip_whitelist(source_ip):
            self._log_security_event(
                SecurityEventType.WHITELIST_VIOLATION,
                source_ip, target_host, username,
                {"reason": "IP not in whitelist"},
                SecurityLevel.HIGH
            )
            return False, "IP 不在白名單中"
        
        # 檢查主機白名單
        if self.host_whitelist and target_host not in self.host_whitelist:
            return False, "目標主機不在白名單中"
        
        # 檢查使用者白名單
        if self.user_whitelist and username not in self.user_whitelist:
            return False, "使用者不在白名單中"
        
        # 檢查速率限制
        if not self._check_rate_limits(source_ip, "connection"):
            return False, "連接頻率過高"
        
        return True, ""
    
    def _check_rate_limits(self, identifier: str, limit_type: str) -> bool:
        """檢查速率限制"""
        if limit_type not in self.rate_limits:
            return True
        
        config = self.rate_limits[limit_type]
        current_time = datetime.now()
        window_start = current_time - timedelta(seconds=config.time_window)
        
        # 清理過期記錄
        if identifier in self.failed_attempts:
            self.failed_attempts[identifier] = [
                ts for ts in self.failed_attempts[identifier] 
                if ts > window_start
            ]
        
        # 檢查是否超過限制
        attempt_count = len(self.failed_attempts[identifier])
        if attempt_count >= config.max_requests:
            # 封鎖 IP
            block_until = current_time + timedelta(seconds=config.block_duration)
            self.blocked_ips[identifier] = block_until
            
            self._log_security_event(
                SecurityEventType.RATE_LIMIT_EXCEEDED,
                identifier, "", "",
                {
                    "limit_type": limit_type,
                    "attempts": attempt_count,
                    "block_duration": config.block_duration
                },
                SecurityLevel.HIGH
            )
            
            return False
        
        return True
    
    def record_connection_attempt(
        self, 
        source_ip: str, 
        target_host: str, 
        username: str, 
        success: bool,
        error_message: Optional[str] = None
    ):
        """記錄連接嘗試"""
        attempt = ConnectionAttempt(
            timestamp=datetime.now(),
            source_ip=source_ip,
            target_host=target_host,
            username=username,
            success=success,
            error_message=error_message
        )
        
        with self.lock:
            self.connection_history.append(attempt)
        
        # 記錄失敗嘗試
        if not success:
            self.failed_attempts[source_ip].append(datetime.now())
            
            # 檢查是否可能是暴力破解
            self._check_brute_force(source_ip, username)
            
            # 記錄安全事件
            self._log_security_event(
                SecurityEventType.CONNECTION_FAILURE,
                source_ip, target_host, username,
                {"error": error_message},
                SecurityLevel.MEDIUM
            )
        else:
            # 成功連接，清理失敗記錄
            if source_ip in self.failed_attempts:
                self.failed_attempts[source_ip].clear()
            
            self._log_security_event(
                SecurityEventType.CONNECTION_SUCCESS,
                source_ip, target_host, username,
                {},
                SecurityLevel.LOW
            )
    
    def _check_brute_force(self, source_ip: str, username: str):
        """檢查暴力破解攻擊"""
        recent_failures = [
            ts for ts in self.failed_attempts[source_ip]
            if ts > datetime.now() - timedelta(minutes=10)
        ]
        
        if len(recent_failures) >= 5:
            # 疑似暴力破解攻擊
            block_until = datetime.now() + timedelta(hours=1)
            self.blocked_ips[source_ip] = block_until
            
            self._log_security_event(
                SecurityEventType.BRUTE_FORCE_DETECTED,
                source_ip, "", username,
                {
                    "failure_count": len(recent_failures),
                    "time_span": "10 minutes",
                    "action": "blocked for 1 hour"
                },
                SecurityLevel.CRITICAL
            )
            
            logger.warning(f"檢測到暴力破解攻擊，封鎖 IP: {source_ip}")
    
    def validate_command(self, command: str, username: str, target_host: str) -> Tuple[bool, str]:
        """
        驗證指令是否安全
        
        Args:
            command: 要執行的指令
            username: 使用者名稱
            target_host: 目標主機
            
        Returns:
            (是否安全, 拒絕原因)
        """
        # 檢查危險指令
        command_lower = command.lower().strip()
        
        for dangerous_cmd in self.dangerous_commands:
            if dangerous_cmd in command_lower:
                self._log_security_event(
                    SecurityEventType.COMMAND_BLOCKED,
                    "", target_host, username,
                    {
                        "command": command,
                        "reason": f"Contains dangerous pattern: {dangerous_cmd}"
                    },
                    SecurityLevel.CRITICAL
                )
                return False, f"指令包含危險模式: {dangerous_cmd}"
        
        # 檢查可疑模式
        for pattern in self.suspicious_patterns:
            if re.search(pattern, command):
                self._log_security_event(
                    SecurityEventType.SUSPICIOUS_ACTIVITY,
                    "", target_host, username,
                    {
                        "command": command,
                        "pattern": pattern
                    },
                    SecurityLevel.HIGH
                )
                # 可疑模式記錄但不直接阻止，可以根據需要調整
                logger.warning(f"檢測到可疑指令模式: {pattern} in {command}")
        
        return True, ""
    
    def _log_security_event(
        self,
        event_type: SecurityEventType,
        source_ip: str,
        target_host: str,
        username: str,
        details: Dict[str, Any],
        severity: SecurityLevel
    ):
        """記錄安全事件"""
        event = SecurityEvent(
            event_type=event_type,
            timestamp=datetime.now(),
            source_ip=source_ip,
            target_host=target_host,
            username=username,
            details=details,
            severity=severity
        )
        
        with self.lock:
            self.security_events.append(event)
        
        # 記錄到日誌
        log_message = (
            f"Security Event: {event_type.value} | "
            f"Severity: {severity.value} | "
            f"Source: {source_ip} | "
            f"Target: {target_host} | "
            f"User: {username} | "
            f"Details: {details}"
        )
        
        if severity == SecurityLevel.CRITICAL:
            logger.critical(log_message)
        elif severity == SecurityLevel.HIGH:
            logger.error(log_message)
        elif severity == SecurityLevel.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def get_security_summary(self) -> Dict[str, Any]:
        """獲取安全摘要"""
        with self.lock:
            recent_events = [
                e for e in self.security_events 
                if e.timestamp > datetime.now() - timedelta(hours=24)
            ]
            
            event_counts = defaultdict(int)
            severity_counts = defaultdict(int)
            
            for event in recent_events:
                event_counts[event.event_type.value] += 1
                severity_counts[event.severity.value] += 1
            
            return {
                "total_events_24h": len(recent_events),
                "event_types": dict(event_counts),
                "severity_distribution": dict(severity_counts),
                "blocked_ips": len(self.blocked_ips),
                "whitelist_size": {
                    "ip": len(self.ip_whitelist),
                    "host": len(self.host_whitelist),
                    "user": len(self.user_whitelist)
                },
                "connection_attempts_24h": len([
                    a for a in self.connection_history
                    if a.timestamp > datetime.now() - timedelta(hours=24)
                ])
            }
    
    def get_recent_events(self, limit: int = 50, severity_filter: Optional[SecurityLevel] = None) -> List[Dict[str, Any]]:
        """獲取最近的安全事件"""
        with self.lock:
            events = list(self.security_events)
        
        # 按嚴重程度過濾
        if severity_filter:
            events = [e for e in events if e.severity == severity_filter]
        
        # 按時間排序（最新的在前）
        events.sort(key=lambda x: x.timestamp, reverse=True)
        
        # 限制數量
        events = events[:limit]
        
        # 轉換為字典格式
        return [
            {
                "event_type": e.event_type.value,
                "timestamp": e.timestamp.isoformat(),
                "source_ip": e.source_ip,
                "target_host": e.target_host,
                "username": e.username,
                "details": e.details,
                "severity": e.severity.value,
                "resolved": e.resolved
            }
            for e in events
        ]
    
    def cleanup_old_data(self, days: int = 7):
        """清理舊數據"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        with self.lock:
            # 清理連接歷史
            self.connection_history = deque([
                a for a in self.connection_history 
                if a.timestamp > cutoff_time
            ], maxlen=10000)
            
            # 清理失敗嘗試記錄
            for ip in list(self.failed_attempts.keys()):
                self.failed_attempts[ip] = [
                    ts for ts in self.failed_attempts[ip]
                    if ts > cutoff_time
                ]
                if not self.failed_attempts[ip]:
                    del self.failed_attempts[ip]
            
            # 清理過期的封鎖
            current_time = datetime.now()
            expired_blocks = [
                ip for ip, block_time in self.blocked_ips.items()
                if current_time >= block_time
            ]
            for ip in expired_blocks:
                del self.blocked_ips[ip]
        
        logger.info(f"清理 {days} 天前的安全數據完成")


# 全域安全服務實例
security_service = SecurityService()


# 便利函數
def check_connection_security(source_ip: str, target_host: str, username: str) -> Tuple[bool, str]:
    """檢查連接安全性的便利函數"""
    return security_service.check_connection_allowed(source_ip, target_host, username)


def validate_command_security(command: str, username: str, target_host: str) -> Tuple[bool, str]:
    """驗證指令安全性的便利函數"""
    return security_service.validate_command(command, username, target_host)


def record_security_event(source_ip: str, target_host: str, username: str, success: bool, error: Optional[str] = None):
    """記錄安全事件的便利函數"""
    security_service.record_connection_attempt(source_ip, target_host, username, success, error)


if __name__ == "__main__":
    # 測試安全服務
    print("🛡️ 測試安全服務...")
    
    try:
        # 測試白名單
        security_service.add_to_whitelist("ip", "192.168.1.100")
        print(f"IP 白名單檢查: {security_service.check_ip_whitelist('192.168.1.100')}")
        
        # 測試連接檢查
        allowed, reason = security_service.check_connection_allowed(
            "192.168.1.100", "test-server", "admin"
        )
        print(f"連接檢查: {allowed}, 原因: {reason}")
        
        # 測試指令驗證
        safe, reason = security_service.validate_command("ls -la", "admin", "test-server")
        print(f"安全指令: {safe}")
        
        unsafe, reason = security_service.validate_command("rm -rf /", "admin", "test-server")
        print(f"危險指令: {unsafe}, 原因: {reason}")
        
        # 測試安全摘要
        summary = security_service.get_security_summary()
        print(f"安全摘要: {summary}")
        
        print("✅ 安全服務測試完成")
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")