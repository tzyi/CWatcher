"""
CWatcher 監控 API 端點測試

測試監控相關的 API 端點功能
包括數據收集、警告查詢、閾值管理等功能的測試
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from main import app
from models.server import Server
from services.monitoring_collector import (
    MonitoringData,
    MetricType,
    AlertLevel,
    MonitoringThresholds
)


@pytest.fixture
def client():
    """測試客戶端"""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Mock 資料庫會話"""
    session = Mock()
    return session


@pytest.fixture
def sample_server():
    """測試用伺服器數據"""
    server = Mock(spec=Server)
    server.id = 1
    server.name = "Test Server"
    server.host = "192.168.1.100"
    server.port = 22
    server.username = "test-user"
    server.encrypted_password = "encrypted_password"
    server.encrypted_private_key = None
    return server


@pytest.fixture
def sample_monitoring_summary():
    """測試用監控摘要數據"""
    return {
        "server_id": 1,
        "timestamp": "2024-01-15T10:30:00",
        "collection_status": "success",
        "overall_alert_level": "ok",
        "connection_status": "success",
        "metrics": {
            "cpu": {
                "usage_percent": 42.0,
                "core_count": 4,
                "frequency_mhz": 2400.0,
                "load_average": {"1min": 0.38, "5min": 0.45, "15min": 0.52},
                "model_name": "Intel Core i5",
                "alert_level": "ok",
                "alert_message": None
            },
            "memory": {
                "usage_percent": 68.0,
                "total_gb": 8.0,
                "used_gb": 5.4,
                "free_gb": 1.4,
                "cached_gb": 1.2,
                "swap_usage_percent": 0.0,
                "alert_level": "ok",
                "alert_message": None
            },
            "disk": {
                "usage_percent": 76.0,
                "total_gb": 500.0,
                "used_gb": 380.0,
                "free_gb": 120.0,
                "read_mb_per_sec": 12.4,
                "write_mb_per_sec": 8.7,
                "filesystems": [],
                "alert_level": "ok",
                "alert_message": None
            },
            "network": {
                "download_mb_per_sec": 2.4,
                "upload_mb_per_sec": 0.8,
                "total_traffic_gb": 1.2,
                "active_connections": 45,
                "interfaces": {},
                "alert_level": "ok",
                "alert_message": None
            }
        }
    }


class TestMonitoringSummaryAPI:
    """監控摘要 API 測試"""
    
    @patch('app.api.v1.endpoints.monitoring.get_db')
    @patch('app.api.v1.endpoints.monitoring.collect_server_monitoring_data')
    def test_get_server_monitoring_summary_success(
        self, 
        mock_collect_data, 
        mock_get_db, 
        client, 
        mock_db_session, 
        sample_server, 
        sample_monitoring_summary
    ):
        """測試成功取得伺服器監控摘要"""
        # 設定 Mock
        mock_get_db.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_server
        mock_collect_data.return_value = sample_monitoring_summary
        
        # 發送請求
        response = client.get("/api/v1/monitoring/servers/1/monitoring/summary")
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "監控數據收集成功"
        assert data["data"]["server_id"] == 1
        assert data["data"]["collection_status"] == "success"
        assert "metrics" in data["data"]
        assert "cpu" in data["data"]["metrics"]
        assert "memory" in data["data"]["metrics"]
        assert "disk" in data["data"]["metrics"]
        assert "network" in data["data"]["metrics"]
        
        # 驗證 Mock 調用
        mock_collect_data.assert_called_once()
    
    @patch('app.api.v1.endpoints.monitoring.get_db')
    def test_get_server_monitoring_summary_server_not_found(
        self, 
        mock_get_db, 
        client, 
        mock_db_session
    ):
        """測試伺服器不存在的情況"""
        # 設定 Mock - 伺服器不存在
        mock_get_db.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        # 發送請求
        response = client.get("/api/v1/monitoring/servers/999/monitoring/summary")
        
        # 驗證回應
        assert response.status_code == 404
        data = response.json()
        assert "伺服器 999 不存在" in data["detail"]
    
    @patch('app.api.v1.endpoints.monitoring.get_db')
    @patch('app.api.v1.endpoints.monitoring.collect_server_monitoring_data')
    def test_get_server_monitoring_summary_collection_failed(
        self, 
        mock_collect_data, 
        mock_get_db, 
        client, 
        mock_db_session, 
        sample_server
    ):
        """測試監控數據收集失敗的情況"""
        # 設定 Mock
        mock_get_db.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_server
        mock_collect_data.side_effect = Exception("SSH connection failed")
        
        # 發送請求
        response = client.get("/api/v1/monitoring/servers/1/monitoring/summary")
        
        # 驗證回應
        assert response.status_code == 500
        data = response.json()
        assert "監控數據收集失敗" in data["detail"]


class TestSpecificMetricAPI:
    """特定監控指標 API 測試"""
    
    @patch('app.api.v1.endpoints.monitoring.get_db')
    @patch('app.api.v1.endpoints.monitoring.ssh_manager')
    @patch('app.api.v1.endpoints.monitoring.collect_cpu_monitoring_data')
    def test_get_server_cpu_metric(
        self, 
        mock_collect_cpu, 
        mock_ssh_manager, 
        mock_get_db, 
        client, 
        mock_db_session, 
        sample_server
    ):
        """測試取得 CPU 監控數據"""
        # 設定 Mock
        mock_get_db.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_server
        mock_ssh_manager.decrypt_server_credentials.return_value = Mock()
        
        # 建立 CPU 監控數據
        cpu_data = MonitoringData(
            metric_type=MetricType.CPU,
            server_id=1,
            data={
                "usage_percent": 45.0,
                "core_count": 4,
                "frequency_mhz": 2400.0,
                "load_average": {"1min": 0.5, "5min": 0.6, "15min": 0.7},
                "model_name": "Intel Core i5"
            },
            alert_level=AlertLevel.OK,
            collection_time=1.23
        )
        mock_collect_cpu.return_value = cpu_data
        
        # 發送請求
        response = client.get("/api/v1/monitoring/servers/1/monitoring/metrics/cpu")
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "CPU 監控數據收集成功"
        assert data["data"]["metric_type"] == "cpu"
        assert data["data"]["server_id"] == 1
        assert data["data"]["data"]["usage_percent"] == 45.0
        assert data["data"]["alert_level"] == "ok"
    
    @patch('app.api.v1.endpoints.monitoring.get_db')
    def test_get_server_invalid_metric_type(
        self, 
        mock_get_db, 
        client, 
        mock_db_session, 
        sample_server
    ):
        """測試無效的監控指標類型"""
        # 設定 Mock
        mock_get_db.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_server
        
        # 發送請求 - 無效的指標類型
        response = client.get("/api/v1/monitoring/servers/1/monitoring/metrics/invalid")
        
        # 驗證回應
        assert response.status_code == 400
        data = response.json()
        assert "不支援的監控指標類型" in data["detail"]


class TestServerAlertsAPI:
    """伺服器警告 API 測試"""
    
    @patch('app.api.v1.endpoints.monitoring.get_db')
    @patch('app.api.v1.endpoints.monitoring.ssh_manager')
    @patch('app.api.v1.endpoints.monitoring.monitoring_service')
    def test_get_server_alerts_success(
        self, 
        mock_monitoring_service, 
        mock_ssh_manager, 
        mock_get_db, 
        client, 
        mock_db_session, 
        sample_server
    ):
        """測試成功取得伺服器警告"""
        # 設定 Mock
        mock_get_db.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_server
        mock_ssh_manager.decrypt_server_credentials.return_value = Mock()
        
        # 建立監控數據 - 包含警告
        mock_metrics = {
            MetricType.CPU: MonitoringData(
                metric_type=MetricType.CPU,
                data={"usage_percent": 95.0},
                alert_level=AlertLevel.CRITICAL,
                alert_message="CPU使用率過高: 95.0%",
                timestamp=datetime.now()
            ),
            MetricType.MEMORY: MonitoringData(
                metric_type=MetricType.MEMORY,
                data={"usage_percent": 60.0},
                alert_level=AlertLevel.OK,
                timestamp=datetime.now()
            )
        }
        mock_monitoring_service.collect_all_metrics.return_value = mock_metrics
        
        # 發送請求
        response = client.get("/api/v1/monitoring/servers/1/monitoring/alerts")
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["server_id"] == 1
        assert data["data"]["alert_count"] == 1
        assert len(data["data"]["alerts"]) == 1
        
        alert = data["data"]["alerts"][0]
        assert alert["metric_type"] == "cpu"
        assert alert["alert_level"] == "critical"
        assert alert["alert_message"] == "CPU使用率過高: 95.0%"
    
    @patch('app.api.v1.endpoints.monitoring.get_db')
    @patch('app.api.v1.endpoints.monitoring.ssh_manager')
    @patch('app.api.v1.endpoints.monitoring.monitoring_service')
    def test_get_server_alerts_with_filter(
        self, 
        mock_monitoring_service, 
        mock_ssh_manager, 
        mock_get_db, 
        client, 
        mock_db_session, 
        sample_server
    ):
        """測試使用警告等級過濾器"""
        # 設定 Mock
        mock_get_db.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_server
        mock_ssh_manager.decrypt_server_credentials.return_value = Mock()
        
        # 建立監控數據 - 混合警告等級
        mock_metrics = {
            MetricType.CPU: MonitoringData(
                metric_type=MetricType.CPU,
                alert_level=AlertLevel.CRITICAL,
                alert_message="CPU使用率過高",
                timestamp=datetime.now()
            ),
            MetricType.MEMORY: MonitoringData(
                metric_type=MetricType.MEMORY,
                alert_level=AlertLevel.WARNING,
                alert_message="記憶體使用率偏高",
                timestamp=datetime.now()
            )
        }
        mock_monitoring_service.collect_all_metrics.return_value = mock_metrics
        
        # 發送請求 - 只要 critical 等級
        response = client.get("/api/v1/monitoring/servers/1/monitoring/alerts?alert_level=critical")
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["alert_count"] == 1
        assert data["data"]["alerts"][0]["alert_level"] == "critical"


class TestThresholdsAPI:
    """監控閾值 API 測試"""
    
    @patch('app.api.v1.endpoints.monitoring.monitoring_service')
    def test_get_monitoring_thresholds_success(self, mock_monitoring_service, client):
        """測試成功取得監控閾值"""
        # 設定 Mock
        mock_thresholds = MonitoringThresholds(
            cpu_warning=80.0,
            cpu_critical=90.0,
            memory_warning=85.0,
            memory_critical=95.0,
            disk_warning=85.0,
            disk_critical=95.0,
            load_warning=5.0,
            load_critical=10.0
        )
        mock_monitoring_service.thresholds = mock_thresholds
        
        # 發送請求
        response = client.get("/api/v1/monitoring/monitoring/thresholds")
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "監控閾值查詢成功"
        assert data["data"]["cpu_warning"] == 80.0
        assert data["data"]["cpu_critical"] == 90.0
        assert data["data"]["memory_warning"] == 85.0
        assert data["data"]["memory_critical"] == 95.0
    
    @patch('app.api.v1.endpoints.monitoring.monitoring_service')
    def test_update_monitoring_thresholds_success(self, mock_monitoring_service, client):
        """測試成功更新監控閾值"""
        # 準備更新數據
        update_data = {
            "cpu_warning": 75.0,
            "cpu_critical": 85.0,
            "memory_warning": 80.0,
            "memory_critical": 90.0,
            "disk_warning": 80.0,
            "disk_critical": 90.0,
            "load_warning": 4.0,
            "load_critical": 8.0
        }
        
        # 發送請求
        response = client.post("/api/v1/monitoring/monitoring/thresholds", json=update_data)
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "監控閾值更新成功"
        assert data["data"]["cpu_warning"] == 75.0
        assert data["data"]["cpu_critical"] == 85.0
        
        # 驗證 Mock 調用
        mock_monitoring_service.update_thresholds.assert_called_once()
    
    def test_update_monitoring_thresholds_invalid_data(self, client):
        """測試無效的閾值更新數據"""
        # 準備無效數據 - critical 小於 warning
        invalid_data = {
            "cpu_warning": 90.0,
            "cpu_critical": 80.0,  # 小於 warning
            "memory_warning": 85.0,
            "memory_critical": 95.0
        }
        
        # 發送請求
        response = client.post("/api/v1/monitoring/monitoring/thresholds", json=invalid_data)
        
        # 驗證回應
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data


class TestBatchMonitoringAPI:
    """批量監控 API 測試"""
    
    @patch('app.api.v1.endpoints.monitoring.get_db')
    @patch('app.api.v1.endpoints.monitoring.ssh_manager')
    @patch('app.api.v1.endpoints.monitoring.monitoring_service')
    def test_get_multiple_servers_monitoring_success(
        self, 
        mock_monitoring_service, 
        mock_ssh_manager, 
        mock_get_db, 
        client, 
        mock_db_session
    ):
        """測試成功批量取得多台伺服器監控"""
        # 準備多台伺服器
        servers = [
            Mock(id=1, name="Server 1", host="192.168.1.100"),
            Mock(id=2, name="Server 2", host="192.168.1.101")
        ]
        
        # 設定 Mock
        mock_get_db.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.all.return_value = servers
        mock_ssh_manager.decrypt_server_credentials.return_value = Mock()
        
        # Mock 監控摘要數據
        mock_monitoring_service.collect_summary_metrics.return_value = {
            "collection_status": "success",
            "metrics": {"cpu": {"usage_percent": 45.0}}
        }
        
        # 發送請求
        response = client.get("/api/v1/monitoring/servers/monitoring/batch?server_ids=1,2")
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert len(data["data"]["servers"]) == 2
        assert data["data"]["summary"]["total_servers"] == 2
        assert "success_count" in data["data"]["summary"]
    
    def test_get_multiple_servers_monitoring_invalid_ids(self, client):
        """測試無效的伺服器 ID 列表"""
        # 發送請求 - 無效 ID 格式
        response = client.get("/api/v1/monitoring/servers/monitoring/batch?server_ids=invalid,ids")
        
        # 驗證回應
        assert response.status_code == 400
        data = response.json()
        assert "伺服器 ID 格式錯誤" in data["detail"]
    
    def test_get_multiple_servers_monitoring_too_many_servers(self, client):
        """測試請求過多伺服器"""
        # 準備超過限制的伺服器 ID
        server_ids = ",".join([str(i) for i in range(1, 22)])  # 21 台伺服器
        
        # 發送請求
        response = client.get(f"/api/v1/monitoring/servers/monitoring/batch?server_ids={server_ids}")
        
        # 驗證回應
        assert response.status_code == 400
        data = response.json()
        assert "一次最多查詢 20 台伺服器" in data["detail"]


class TestMonitoringTestAPI:
    """監控測試 API 測試"""
    
    @patch('app.api.v1.endpoints.monitoring.get_db')
    @patch('app.api.v1.endpoints.monitoring.test_server_connection_and_monitoring')
    def test_test_server_monitoring_connection_success(
        self, 
        mock_test_connection, 
        mock_get_db, 
        client, 
        mock_db_session, 
        sample_server
    ):
        """測試成功的伺服器連接測試"""
        # 設定 Mock
        mock_get_db.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_server
        
        mock_test_connection.return_value = {
            "connection_status": "success",
            "collection_status": "success",
            "metrics": {"cpu": {"usage_percent": 45.0}}
        }
        
        # 發送請求
        response = client.get("/api/v1/monitoring/servers/1/monitoring/test")
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["message"] == "伺服器連接測試完成"
        assert data["data"]["connection_status"] == "success"
        assert data["data"]["collection_status"] == "success"
    
    @patch('app.api.v1.endpoints.monitoring.get_db')
    @patch('app.api.v1.endpoints.monitoring.test_server_connection_and_monitoring')
    def test_test_server_monitoring_connection_failed(
        self, 
        mock_test_connection, 
        mock_get_db, 
        client, 
        mock_db_session, 
        sample_server
    ):
        """測試失敗的伺服器連接測試"""
        # 設定 Mock
        mock_get_db.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_server
        
        mock_test_connection.return_value = {
            "connection_status": "failed",
            "error": "Connection timeout"
        }
        
        # 發送請求
        response = client.get("/api/v1/monitoring/servers/1/monitoring/test")
        
        # 驗證回應
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["connection_status"] == "failed"
        assert data["data"]["error"] == "Connection timeout"


@pytest.mark.integration
class TestMonitoringAPIIntegration:
    """監控 API 整合測試"""
    
    @pytest.mark.asyncio
    async def test_monitoring_workflow_integration(self):
        """測試監控工作流程整合"""
        # 這裡可以添加端到端的整合測試
        # 包括實際的 SSH 連接、數據收集、API 調用等
        pass


if __name__ == "__main__":
    # 執行測試
    pytest.main([__file__, "-v"])