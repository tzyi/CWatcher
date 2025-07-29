"""
CWatcher WebSocket 推送服務

整合監控數據收集系統與 WebSocket 即時推送
提供定時推送、事件驅動推送和狀態變化通知功能
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from app.services.websocket_manager import (
    websocket_manager, WebSocketMessage, MessageType,
    broadcast_monitoring_update, broadcast_status_change
)
from app.services.monitoring_collector import (
    monitoring_service, MonitoringCollectorService, MetricType, AlertLevel
)
from app.services.data_processor import data_processor, process_server_monitoring_data
from app.services.ssh_manager import ssh_manager, SSHConnectionConfig
from app.schemas.websocket import (
    create_monitoring_update_message, create_status_change_message,
    WSServerStatus, WSAlertLevel
)
from app.core.config import settings

# 設定日誌
logger = logging.getLogger(__name__)


@dataclass
class ServerPushState:
    """伺服器推送狀態"""
    server_id: int
    last_push_time: datetime = field(default_factory=datetime.now)
    last_status: str = "unknown"
    push_interval: int = 30  # 秒
    consecutive_failures: int = 0
    total_pushes: int = 0
    is_active: bool = True
    last_metrics: Optional[Dict[str, Any]] = None
    
    def should_push(self) -> bool:
        """檢查是否應該推送數據"""
        if not self.is_active:
            return False
        
        elapsed = (datetime.now() - self.last_push_time).total_seconds()
        return elapsed >= self.push_interval
    
    def update_push_success(self, metrics: Dict[str, Any]):
        """更新推送成功狀態"""
        self.last_push_time = datetime.now()
        self.consecutive_failures = 0
        self.total_pushes += 1
        self.last_metrics = metrics
    
    def update_push_failure(self):
        """更新推送失敗狀態"""
        self.consecutive_failures += 1
        if self.consecutive_failures >= 5:
            self.is_active = False
            logger.warning(f"伺服器 {self.server_id} 連續推送失敗，暫停推送")


class WebSocketPushService:
    """WebSocket 推送服務"""
    
    def __init__(self):
        self.server_states: Dict[int, ServerPushState] = {}
        self.push_task: Optional[asyncio.Task] = None
        self.status_monitor_task: Optional[asyncio.Task] = None
        self.is_running = False
        self._stats = {
            "total_pushes": 0,
            "successful_pushes": 0,
            "failed_pushes": 0,
            "status_changes": 0,
            "start_time": datetime.now()
        }
    
    async def start(self):
        """啟動推送服務"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # 啟動定時推送任務
        if not self.push_task or self.push_task.done():
            self.push_task = asyncio.create_task(self._push_loop())
        
        # 啟動狀態監控任務
        if not self.status_monitor_task or self.status_monitor_task.done():
            self.status_monitor_task = asyncio.create_task(self._status_monitor_loop())
        
        logger.info("WebSocket 推送服務已啟動")
    
    async def stop(self):
        """停止推送服務"""
        self.is_running = False
        
        # 停止定時推送任務
        if self.push_task and not self.push_task.done():
            self.push_task.cancel()
            try:
                await self.push_task
            except asyncio.CancelledError:
                pass
        
        # 停止狀態監控任務
        if self.status_monitor_task and not self.status_monitor_task.done():
            self.status_monitor_task.cancel()
            try:
                await self.status_monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("WebSocket 推送服務已停止")
    
    def add_server(self, server_id: int, push_interval: int = 30):
        """添加伺服器到推送列表"""
        if server_id not in self.server_states:
            self.server_states[server_id] = ServerPushState(
                server_id=server_id,
                push_interval=push_interval
            )
            logger.info(f"添加伺服器 {server_id} 到推送列表，間隔 {push_interval} 秒")
    
    def remove_server(self, server_id: int):
        """從推送列表移除伺服器"""
        if server_id in self.server_states:
            del self.server_states[server_id]
            logger.info(f"從推送列表移除伺服器 {server_id}")
    
    def update_server_interval(self, server_id: int, push_interval: int):
        """更新伺服器推送間隔"""
        if server_id in self.server_states:
            self.server_states[server_id].push_interval = push_interval
            logger.info(f"更新伺服器 {server_id} 推送間隔為 {push_interval} 秒")
    
    def activate_server(self, server_id: int):
        """啟用伺服器推送"""
        if server_id in self.server_states:
            self.server_states[server_id].is_active = True
            self.server_states[server_id].consecutive_failures = 0
            logger.info(f"啟用伺服器 {server_id} 推送")
    
    def deactivate_server(self, server_id: int):
        """停用伺服器推送"""
        if server_id in self.server_states:
            self.server_states[server_id].is_active = False
            logger.info(f"停用伺服器 {server_id} 推送")
    
    async def _push_loop(self):
        """主要推送循環"""
        while self.is_running:
            try:
                # 檢查所有伺服器的推送狀態
                push_tasks = []
                
                for server_id, state in self.server_states.items():
                    if state.should_push():
                        push_tasks.append(self._push_server_data(server_id))
                
                # 並行執行推送任務
                if push_tasks:
                    await asyncio.gather(*push_tasks, return_exceptions=True)
                
                # 等待一段時間再檢查
                await asyncio.sleep(5)  # 每5秒檢查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"推送循環錯誤: {e}")
                await asyncio.sleep(10)
    
    async def _push_server_data(self, server_id: int):
        """推送單個伺服器的數據"""
        if server_id not in self.server_states:
            return
        
        state = self.server_states[server_id]
        
        try:
            # 取得伺服器資訊
            server_data = await self._get_server_data(server_id)
            if not server_data:
                state.update_push_failure()
                return
            
            # 收集監控數據
            monitoring_data = await self._collect_server_monitoring_data(server_data)
            
            if monitoring_data.get("collection_status") == "success":
                # 處理數據（可選，用於存儲）
                try:
                    await self._process_monitoring_data(server_id, monitoring_data)
                except Exception as e:
                    logger.warning(f"處理監控數據失敗: {e}")
                
                # 推送到 WebSocket 客戶端
                await self._broadcast_monitoring_data(server_id, monitoring_data)
                
                # 檢查狀態變化
                await self._check_status_changes(server_id, monitoring_data, state)
                
                # 更新推送狀態
                state.update_push_success(monitoring_data)
                self._stats["successful_pushes"] += 1
                
                logger.debug(f"成功推送伺服器 {server_id} 監控數據")
            else:
                # 推送失敗
                state.update_push_failure()
                self._stats["failed_pushes"] += 1
                
                # 廣播伺服器離線狀態
                await self._broadcast_server_status_change(
                    server_id, state.last_status, "offline", 
                    monitoring_data.get("error", "數據收集失敗")
                )
                
                logger.warning(f"伺服器 {server_id} 監控數據收集失敗")
            
            self._stats["total_pushes"] += 1
            
        except Exception as e:
            logger.error(f"推送伺服器 {server_id} 數據失敗: {e}")
            state.update_push_failure()
            self._stats["failed_pushes"] += 1
    
    async def _get_server_data(self, server_id: int) -> Optional[Dict[str, Any]]:
        """取得伺服器資料"""
        try:
            # 這裡應該從數據庫中取得伺服器資料
            # 暫時返回模擬數據
            return {
                "id": server_id,
                "host": "localhost",
                "port": 22,
                "username": "test",
                "password": "test123",
                "name": f"Server {server_id}",
                "status": "online"
            }
        except Exception as e:
            logger.error(f"取得伺服器 {server_id} 資料失敗: {e}")
            return None
    
    async def _collect_server_monitoring_data(self, server_data: Dict[str, Any]) -> Dict[str, Any]:
        """收集伺服器監控數據"""
        try:
            # 建立 SSH 連接配置
            config = SSHConnectionConfig(
                host=server_data.get("host"),
                port=server_data.get("port", 22),
                username=server_data.get("username"),
                password=server_data.get("password")  # 實際使用中應該要解密
            )
            
            # 收集監控數據
            monitoring_data = await monitoring_service.collect_summary_metrics(
                config, server_data.get("id")
            )
            
            return monitoring_data
            
        except Exception as e:
            logger.error(f"收集伺服器監控數據失敗: {e}")
            return {
                "collection_status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _process_monitoring_data(self, server_id: int, monitoring_data: Dict[str, Any]):
        """處理監控數據（存儲到數據庫）"""
        try:
            # 將監控數據轉換為標準格式並存儲
            # 這裡可以選擇性地存儲數據，因為主要目的是即時推送
            pass
        except Exception as e:
            logger.warning(f"處理監控數據失敗: {e}")
    
    async def _broadcast_monitoring_data(self, server_id: int, monitoring_data: Dict[str, Any]):
        """廣播監控數據到 WebSocket 客戶端"""
        try:
            # 使用 WebSocket 管理器廣播數據
            await broadcast_monitoring_update(server_id, monitoring_data)
            
        except Exception as e:
            logger.error(f"廣播監控數據失敗: {e}")
    
    async def _check_status_changes(self, server_id: int, monitoring_data: Dict[str, Any], 
                                  state: ServerPushState):
        """檢查並處理狀態變化"""
        try:
            current_status = self._determine_server_status(monitoring_data)
            
            if current_status != state.last_status:
                # 狀態發生變化
                await self._broadcast_server_status_change(
                    server_id, state.last_status, current_status,
                    self._get_status_change_reason(monitoring_data)
                )
                
                state.last_status = current_status
                self._stats["status_changes"] += 1
                
                logger.info(f"伺服器 {server_id} 狀態變化: {state.last_status} -> {current_status}")
            
        except Exception as e:
            logger.error(f"檢查狀態變化失敗: {e}")
    
    def _determine_server_status(self, monitoring_data: Dict[str, Any]) -> str:
        """根據監控數據判斷伺服器狀態"""
        if monitoring_data.get("collection_status") != "success":
            return "offline"
        
        overall_alert_level = monitoring_data.get("overall_alert_level", "ok")
        
        if overall_alert_level == "critical":
            return "error"
        elif overall_alert_level == "warning":
            return "warning"
        else:
            return "online"
    
    def _get_status_change_reason(self, monitoring_data: Dict[str, Any]) -> str:
        """取得狀態變化原因"""
        metrics = monitoring_data.get("metrics", {})
        
        # 檢查各項指標的警告訊息
        reasons = []
        for metric_name, metric_data in metrics.items():
            if isinstance(metric_data, dict) and metric_data.get("alert_message"):
                reasons.append(f"{metric_name}: {metric_data['alert_message']}")
        
        return "; ".join(reasons) if reasons else "狀態自動檢測"
    
    async def _broadcast_server_status_change(self, server_id: int, old_status: str, 
                                            new_status: str, reason: str = None):
        """廣播伺服器狀態變化"""
        try:
            await broadcast_status_change(server_id, old_status, new_status, reason)
        except Exception as e:
            logger.error(f"廣播狀態變化失敗: {e}")
    
    async def _status_monitor_loop(self):
        """狀態監控循環"""
        while self.is_running:
            try:
                # 清理非活躍的伺服器
                inactive_servers = [
                    server_id for server_id, state in self.server_states.items()
                    if not state.is_active and state.consecutive_failures >= 10
                ]
                
                for server_id in inactive_servers:
                    logger.info(f"清理非活躍伺服器: {server_id}")
                    del self.server_states[server_id]
                
                # 重新啟用失敗次數較少的伺服器
                for state in self.server_states.values():
                    if not state.is_active and state.consecutive_failures < 10:
                        # 每10分鐘嘗試重新啟用一次
                        if (datetime.now() - state.last_push_time).total_seconds() >= 600:
                            state.is_active = True
                            state.consecutive_failures = 0
                            logger.info(f"重新啟用伺服器推送: {state.server_id}")
                
                await asyncio.sleep(60)  # 每分鐘檢查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"狀態監控循環錯誤: {e}")
                await asyncio.sleep(30)
    
    async def push_server_data_immediately(self, server_id: int) -> bool:
        """立即推送特定伺服器的數據"""
        try:
            await self._push_server_data(server_id)
            return True
        except Exception as e:
            logger.error(f"立即推送伺服器 {server_id} 數據失敗: {e}")
            return False
    
    async def push_all_servers_immediately(self) -> int:
        """立即推送所有伺服器的數據"""
        pushed_count = 0
        
        for server_id in self.server_states.keys():
            try:
                await self._push_server_data(server_id)
                pushed_count += 1
            except Exception as e:
                logger.error(f"推送伺服器 {server_id} 失敗: {e}")
        
        return pushed_count
    
    def get_push_stats(self) -> Dict[str, Any]:
        """取得推送統計"""
        active_servers = sum(1 for state in self.server_states.values() if state.is_active)
        
        return {
            "total_servers": len(self.server_states),
            "active_servers": active_servers,
            "inactive_servers": len(self.server_states) - active_servers,
            "total_pushes": self._stats["total_pushes"],
            "successful_pushes": self._stats["successful_pushes"],
            "failed_pushes": self._stats["failed_pushes"],
            "success_rate": (
                self._stats["successful_pushes"] / self._stats["total_pushes"] * 100
                if self._stats["total_pushes"] > 0 else 0
            ),
            "status_changes": self._stats["status_changes"],
            "uptime_seconds": int((datetime.now() - self._stats["start_time"]).total_seconds()),
            "is_running": self.is_running
        }
    
    def get_server_states(self) -> Dict[int, Dict[str, Any]]:
        """取得所有伺服器狀態"""
        return {
            server_id: {
                "server_id": state.server_id,
                "last_push_time": state.last_push_time.isoformat(),
                "last_status": state.last_status,
                "push_interval": state.push_interval,
                "consecutive_failures": state.consecutive_failures,
                "total_pushes": state.total_pushes,
                "is_active": state.is_active,
                "should_push": state.should_push()
            }
            for server_id, state in self.server_states.items()
        }
    
    def has_active_connections(self) -> bool:
        """檢查是否有活躍的 WebSocket 連接"""
        return websocket_manager.get_connection_count() > 0
    
    def get_connection_count(self) -> int:
        """取得活躍連接數量"""
        return websocket_manager.get_connection_count()
    
    def is_service_running(self) -> bool:
        """檢查推送服務是否運行中"""
        return self.is_running
    
    async def execute_scheduled_push(self) -> Dict[str, Any]:
        """執行排程的推送任務（供任務調度器調用）"""
        try:
            start_time = time.time()
            
            # 檢查是否有活躍連接
            active_connections = self.get_connection_count()
            if active_connections == 0:
                return {
                    "active_connections": 0,
                    "pushes_sent": 0,
                    "errors": 0,
                    "message": "沒有活躍的WebSocket連接"
                }
            
            # 執行推送
            pushes_sent = await self.push_scheduled_data()
            
            # 計算統計
            errors = self._stats["failed_pushes"] - self._stats.get("last_failed_count", 0)
            self._stats["last_failed_count"] = self._stats["failed_pushes"]
            
            elapsed_time = time.time() - start_time
            
            result = {
                "active_connections": active_connections,
                "pushes_sent": pushes_sent,
                "errors": errors,
                "elapsed_time": elapsed_time,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.debug(f"定時推送完成: {pushes_sent} 次推送, {active_connections} 個連接")
            
            return result
            
        except Exception as e:
            logger.error(f"執行定時推送時發生錯誤: {e}")
            return {
                "active_connections": self.get_connection_count(),
                "pushes_sent": 0,
                "errors": 1,
                "error_message": str(e),
                "timestamp": datetime.now().isoformat()
            }


# 全域推送服務實例
push_service = WebSocketPushService()


# 便利函數
async def start_push_service():
    """啟動推送服務"""
    await push_service.start()


async def stop_push_service():
    """停止推送服務"""
    await push_service.stop()


async def add_server_to_push_list(server_id: int, push_interval: int = 30):
    """添加伺服器到推送列表"""
    push_service.add_server(server_id, push_interval)


async def remove_server_from_push_list(server_id: int):
    """從推送列表移除伺服器"""
    push_service.remove_server(server_id)


async def push_server_monitoring_data(server_id: int) -> bool:
    """立即推送特定伺服器的監控數據"""
    return await push_service.push_server_data_immediately(server_id)


async def get_push_service_stats() -> Dict[str, Any]:
    """取得推送服務統計"""
    return push_service.get_push_stats()


if __name__ == "__main__":
    # 測試推送服務
    
    async def test_push_service():
        """測試推送服務"""
        print("🧪 測試 WebSocket 推送服務")
        
        # 啟動服務
        await push_service.start()
        
        # 添加測試伺服器
        push_service.add_server(1, 10)  # 10秒間隔
        push_service.add_server(2, 15)  # 15秒間隔
        
        # 運行一段時間
        print("運行推送服務 30 秒...")
        await asyncio.sleep(30)
        
        # 取得統計
        stats = push_service.get_push_stats()
        print(f"推送統計: {stats}")
        
        # 取得伺服器狀態
        server_states = push_service.get_server_states()
        print(f"伺服器狀態: {server_states}")
        
        # 停止服務
        await push_service.stop()
        print("✅ 推送服務測試完成")
    
    # 執行測試
    import asyncio
    asyncio.run(test_push_service())