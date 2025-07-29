"""
CWatcher 任務調度服務

專門負責定時任務的排程和執行
包括數據清理、系統監控、健康檢查等背景任務
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import signal
import sys

from app.core.config import settings
from app.services.data_cleaner import data_cleaner, CleanupLevel
from app.services.data_processor import data_processor
from app.services.monitoring_collector import monitoring_service
from app.services.websocket_push_service import push_service
from app.services.system_collector import system_collector
from app.services.ssh_manager import ssh_manager
from app.db.base import get_db
from app.models.server import Server

# 設定日誌
logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任務類型"""
    # 核心監控任務
    MONITORING_COLLECTION = "monitoring_collection"
    WEBSOCKET_PUSH = "websocket_push"
    SYSTEM_INFO_UPDATE = "system_info_update"
    
    # 維護任務
    DATA_CLEANUP = "data_cleanup"
    ARCHIVE_CLEANUP = "archive_cleanup"
    HEALTH_CHECK = "health_check"
    BUFFER_FLUSH = "buffer_flush"
    STORAGE_MONITOR = "storage_monitor"


class TaskStatus(Enum):
    """任務狀態"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class TaskExecutionResult:
    """任務執行結果"""
    task_id: str
    task_type: TaskType
    status: TaskStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: float = 0.0
    result_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "result_data": self.result_data,
            "error_message": self.error_message
        }


@dataclass
class ScheduledTask:
    """排程任務定義"""
    task_id: str
    task_type: TaskType
    name: str
    description: str
    trigger: str  # cron expression or interval
    function: Callable
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0  # 連續失敗次數
    max_retries: int = 3  # 最大重試次數
    retry_delay: float = 60.0  # 重試延遲（秒）
    auto_disable_threshold: int = 5  # 自動停用閾值（連續失敗次數）
    last_failure_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "consecutive_failures": self.consecutive_failures,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "auto_disable_threshold": self.auto_disable_threshold,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class TaskScheduler:
    """任務調度器"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.tasks: Dict[str, ScheduledTask] = {}
        self.execution_history: List[TaskExecutionResult] = []
        self.max_history_size = 1000
        self.is_running = False
        
        # 設定信號處理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信號處理器"""
        logger.info(f"收到信號 {signum}，正在停止任務調度器...")
        asyncio.create_task(self.stop())
    
    async def start(self):
        """啟動任務調度器"""
        if self.is_running:
            logger.warning("任務調度器已在運行中")
            return
        
        try:
            logger.info("正在啟動任務調度器...")
            
            # 註冊預設任務
            await self._register_default_tasks()
            
            # 啟動 WebSocket 推送服務
            await push_service.start()
            
            # 啟動調度器
            self.scheduler.start()
            self.is_running = True
            
            logger.info(f"任務調度器已啟動，註冊了 {len(self.tasks)} 個任務")
            
            # 輸出任務清單
            for task in self.tasks.values():
                status = "啟用" if task.enabled else "停用"
                logger.info(f"  - {task.name} ({task.task_type.value}): {status}")
            
        except Exception as e:
            logger.error(f"啟動任務調度器失敗: {e}")
            raise
    
    async def stop(self):
        """停止任務調度器"""
        if not self.is_running:
            return
        
        try:
            logger.info("正在停止任務調度器...")
            
            # 停止 WebSocket 推送服務
            await push_service.stop()
            
            # 停止調度器
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            
            logger.info("任務調度器已停止")
            
        except Exception as e:
            logger.error(f"停止任務調度器失敗: {e}")
    
    async def _register_default_tasks(self):
        """註冊預設任務"""
        
        # ===== 核心監控任務 =====
        
        # 1. 監控數據收集任務（每30秒執行）
        await self.register_task(
            task_id="monitoring_collection",
            task_type=TaskType.MONITORING_COLLECTION,
            name="監控數據收集",
            description="定時收集所有伺服器的CPU、記憶體、磁碟、網路監控數據",
            trigger="30s",  # 每30秒
            function=self._execute_monitoring_collection
        )
        
        # 2. WebSocket 即時推送任務（每30秒執行，略晚於數據收集）
        await self.register_task(
            task_id="websocket_push",
            task_type=TaskType.WEBSOCKET_PUSH,
            name="即時數據推送",
            description="推送最新監控數據和狀態變化到所有訂閱的客戶端",
            trigger="30s",  # 每30秒
            function=self._execute_websocket_push
        )
        
        # 3. 系統資訊更新任務（每5分鐘執行）
        await self.register_task(
            task_id="system_info_update",
            task_type=TaskType.SYSTEM_INFO_UPDATE,
            name="系統資訊更新",
            description="更新伺服器系統資訊（硬體、軟體、運行時間等）",
            trigger="*/5 * * * *",  # 每5分鐘
            function=self._execute_system_info_update
        )
        
        # ===== 維護任務 =====
        
        # 4. 數據緩衝區刷新（每2分鐘執行）
        await self.register_task(
            task_id="buffer_flush",
            task_type=TaskType.BUFFER_FLUSH,
            name="緩衝區刷新",
            description="強制刷新數據處理緩衝區",
            trigger="*/2 * * * *",  # 每2分鐘
            function=self._execute_buffer_flush
        )
        
        # 5. 系統健康檢查（每5分鐘執行）
        await self.register_task(
            task_id="system_health_check",
            task_type=TaskType.HEALTH_CHECK,
            name="系統健康檢查",
            description="檢查SSH連接、資料庫、WebSocket等系統組件狀態",
            trigger="*/5 * * * *",  # 每5分鐘
            function=self._execute_system_health_check
        )
        
        # 6. 儲存空間監控（每30分鐘執行）
        await self.register_task(
            task_id="storage_monitor",
            task_type=TaskType.STORAGE_MONITOR,
            name="儲存空間監控",
            description="監控磁碟使用率並發出警告",
            trigger="*/30 * * * *",  # 每30分鐘
            function=self._execute_storage_monitor
        )
        
        # 7. 數據清理任務（每天凌晨2點執行）
        await self.register_task(
            task_id="daily_data_cleanup",
            task_type=TaskType.DATA_CLEANUP,
            name="每日數據清理",
            description="自動清理30天以上的舊監控數據",
            trigger="0 2 * * *",  # 每天凌晨2點
            function=self._execute_data_cleanup
        )
        
        # 8. 歸檔清理任務（每週日凌晨3點執行）
        await self.register_task(
            task_id="weekly_archive_cleanup",
            task_type=TaskType.ARCHIVE_CLEANUP,
            name="每週歸檔清理",
            description="自動清理90天以上的歸檔檔案",
            trigger="0 3 * * 0",  # 每週日凌晨3點
            function=self._execute_archive_cleanup
        )
    
    async def register_task(
        self,
        task_id: str,
        task_type: TaskType,
        name: str,
        description: str,
        trigger: str,
        function: Callable,
        enabled: bool = True
    ):
        """註冊新任務"""
        try:
            # 創建任務定義
            task = ScheduledTask(
                task_id=task_id,
                task_type=task_type,
                name=name,
                description=description,
                trigger=trigger,
                function=function,
                enabled=enabled
            )
            
            # 解析觸發器
            if self._is_cron_expression(trigger):
                # Cron 表達式
                trigger_obj = CronTrigger.from_crontab(trigger)
            else:
                # 間隔表達式（如 "5m", "1h"）
                trigger_obj = self._parse_interval_trigger(trigger)
            
            # 添加到調度器
            if enabled:
                job = self.scheduler.add_job(
                    func=self._execute_task_wrapper,
                    trigger=trigger_obj,
                    args=[task_id],
                    id=task_id,
                    name=name,
                    replace_existing=True
                )
                
                # 設定下次執行時間
                task.next_run = job.next_run_time
            
            # 保存任務
            self.tasks[task_id] = task
            
            logger.info(f"任務 '{name}' 註冊成功 (ID: {task_id})")
            
        except Exception as e:
            logger.error(f"註冊任務 '{name}' 失敗: {e}")
            raise
    
    async def _execute_task_wrapper(self, task_id: str, retry_count: int = 0):
        """任務執行包裝器（含重試機制）"""
        if task_id not in self.tasks:
            logger.error(f"任務 {task_id} 不存在")
            return
        
        task = self.tasks[task_id]
        
        if not task.enabled:
            logger.info(f"任務 '{task.name}' 已停用，跳過執行")
            return
        
        # 創建執行結果記錄
        execution_result = TaskExecutionResult(
            task_id=task_id,
            task_type=task.task_type,
            status=TaskStatus.RUNNING,
            start_time=datetime.now()
        )
        
        retry_info = f" (重試 {retry_count}/{task.max_retries})" if retry_count > 0 else ""
        logger.info(f"開始執行任務: {task.name}{retry_info}")
        
        try:
            # 執行任務函數
            result_data = await task.function()
            
            # 更新執行結果
            execution_result.end_time = datetime.now()
            execution_result.duration = (
                execution_result.end_time - execution_result.start_time
            ).total_seconds()
            execution_result.status = TaskStatus.COMPLETED
            execution_result.result_data = result_data or {}
            
            # 任務成功，重置連續失敗計數器
            task.consecutive_failures = 0
            task.last_run = execution_result.end_time
            task.run_count += 1
            
            logger.info(f"任務 '{task.name}' 執行完成，耗時 {execution_result.duration:.2f}s")
            
        except Exception as e:
            # 更新執行結果
            execution_result.end_time = datetime.now()
            execution_result.duration = (
                execution_result.end_time - execution_result.start_time
            ).total_seconds()
            execution_result.status = TaskStatus.FAILED
            execution_result.error_message = str(e)
            
            # 更新任務統計
            task.failure_count += 1
            task.consecutive_failures += 1
            task.last_failure_time = execution_result.end_time
            
            logger.error(f"任務 '{task.name}' 執行失敗{retry_info}: {e}")
            
            # 檢查是否需要重試
            should_retry = (
                retry_count < task.max_retries and 
                task.consecutive_failures <= task.auto_disable_threshold and
                task.enabled
            )
            
            if should_retry:
                logger.info(f"任務 '{task.name}' 將在 {task.retry_delay} 秒後重試")
                
                # 安排重試
                await asyncio.sleep(task.retry_delay)
                return await self._execute_task_wrapper(task_id, retry_count + 1)
            else:
                # 檢查是否需要自動停用任務
                if task.consecutive_failures >= task.auto_disable_threshold:
                    logger.critical(
                        f"任務 '{task.name}' 連續失敗 {task.consecutive_failures} 次，"
                        f"達到自動停用閾值，將停用該任務"
                    )
                    await self.disable_task(task_id)
                    execution_result.result_data = {
                        "auto_disabled": True,
                        "consecutive_failures": task.consecutive_failures
                    }
        
        finally:
            # 記錄執行歷史
            self._add_execution_history(execution_result)
            
            # 更新下次執行時間
            if task.enabled:
                job = self.scheduler.get_job(task_id)
                if job:
                    task.next_run = job.next_run_time
    
    def _add_execution_history(self, result: TaskExecutionResult):
        """添加執行歷史記錄"""
        self.execution_history.append(result)
        
        # 保持歷史記錄數量限制
        if len(self.execution_history) > self.max_history_size:
            self.execution_history = self.execution_history[-self.max_history_size:]
    
    def _is_cron_expression(self, trigger: str) -> bool:
        """判斷是否為 Cron 表達式"""
        return len(trigger.split()) == 5
    
    def _parse_interval_trigger(self, trigger: str) -> IntervalTrigger:
        """解析間隔觸發器"""
        # 簡單的間隔解析器（如 "5m", "1h", "30s"）
        if trigger.endswith('s'):
            seconds = int(trigger[:-1])
            return IntervalTrigger(seconds=seconds)
        elif trigger.endswith('m'):
            minutes = int(trigger[:-1])
            return IntervalTrigger(minutes=minutes)
        elif trigger.endswith('h'):
            hours = int(trigger[:-1])
            return IntervalTrigger(hours=hours)
        else:
            raise ValueError(f"不支援的間隔格式: {trigger}")
    
    # ===== 任務執行函數 =====
    
    # ===== 核心監控任務執行函數 =====
    
    async def _execute_monitoring_collection(self) -> Dict[str, Any]:
        """執行監控數據收集任務"""
        try:
            start_time = time.time()
            
            # 獲取所有活躍的伺服器
            async for db in get_db():
                servers = db.query(Server).filter(Server.is_active == True).all()
                
                if not servers:
                    logger.info("沒有找到活躍的伺服器，跳過監控數據收集")
                    return {"servers_processed": 0, "success_count": 0}
                
                success_count = 0
                error_count = 0
                total_servers = len(servers)
                
                logger.debug(f"開始收集 {total_servers} 台伺服器的監控數據")
                
                # 並行收集所有伺服器的監控數據
                collection_tasks = []
                for server in servers:
                    task = asyncio.create_task(
                        self._collect_server_monitoring_data(server)
                    )
                    collection_tasks.append((server.id, task))
                
                # 等待所有收集任務完成
                for server_id, task in collection_tasks:
                    try:
                        await task
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        logger.error(f"收集伺服器 {server_id} 監控數據失敗: {e}")
                
                elapsed_time = time.time() - start_time
                
                result = {
                    "servers_processed": total_servers,
                    "success_count": success_count,
                    "error_count": error_count,
                    "elapsed_time": elapsed_time,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(
                    f"監控數據收集完成: {success_count}/{total_servers} 成功, "
                    f"耗時 {elapsed_time:.2f}s"
                )
                
                return result
                
        except Exception as e:
            logger.error(f"監控數據收集任務失敗: {e}")
            raise
    
    async def _collect_server_monitoring_data(self, server: Server):
        """收集單一伺服器的監控數據"""
        try:
            # 檢查SSH連接狀態
            if not ssh_manager.is_connected(server.id):
                await ssh_manager.connect_to_server(server.id)
            
            # 收集監控數據
            metrics_data = await monitoring_service.collect_all_metrics(server.id)
            
            # 處理和存儲數據
            if metrics_data:
                await data_processor.process_monitoring_data(server.id, metrics_data)
                logger.debug(f"伺服器 {server.id} 監控數據收集成功")
            else:
                logger.warning(f"伺服器 {server.id} 未收集到監控數據")
                
        except Exception as e:
            logger.error(f"收集伺服器 {server.id} 監控數據時發生錯誤: {e}")
            raise
    
    async def _execute_websocket_push(self) -> Dict[str, Any]:
        """執行WebSocket推送任務"""
        try:
            start_time = time.time()
            
            # 檢查是否有連接的客戶端
            if not push_service.has_active_connections():
                return {
                    "active_connections": 0,
                    "pushes_sent": 0,
                    "message": "沒有活躍的WebSocket連接"
                }
            
            # 執行推送服務的定時推送
            push_result = await push_service.execute_scheduled_push()
            
            elapsed_time = time.time() - start_time
            
            result = {
                "active_connections": push_result.get("active_connections", 0),
                "pushes_sent": push_result.get("pushes_sent", 0),
                "errors": push_result.get("errors", 0),
                "elapsed_time": elapsed_time,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.debug(
                f"WebSocket推送完成: {result['pushes_sent']} 次推送, "
                f"{result['active_connections']} 個連接, 耗時 {elapsed_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"WebSocket推送任務失敗: {e}")
            raise
    
    async def _execute_system_info_update(self) -> Dict[str, Any]:
        """執行系統資訊更新任務"""
        try:
            start_time = time.time()
            
            # 獲取所有活躍的伺服器
            async for db in get_db():
                servers = db.query(Server).filter(Server.is_active == True).all()
                
                if not servers:
                    return {"servers_processed": 0, "success_count": 0}
                
                success_count = 0
                error_count = 0
                
                # 並行更新所有伺服器的系統資訊
                for server in servers:
                    try:
                        await system_collector.update_server_system_info(server.id)
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        logger.error(f"更新伺服器 {server.id} 系統資訊失敗: {e}")
                
                elapsed_time = time.time() - start_time
                
                result = {
                    "servers_processed": len(servers),
                    "success_count": success_count,
                    "error_count": error_count,
                    "elapsed_time": elapsed_time,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(
                    f"系統資訊更新完成: {success_count}/{len(servers)} 成功, "
                    f"耗時 {elapsed_time:.2f}s"
                )
                
                return result
                
        except Exception as e:
            logger.error(f"系統資訊更新任務失敗: {e}")
            raise
    
    # ===== 維護任務執行函數 =====
    
    async def _execute_buffer_flush(self) -> Dict[str, Any]:
        """執行緩衝區刷新任務"""
        try:
            stats = await data_processor.flush_all_data()
            return stats.__dict__
        except Exception as e:
            logger.error(f"緩衝區刷新任務失敗: {e}")
            raise
    
    async def _execute_system_health_check(self) -> Dict[str, Any]:
        """執行系統健康檢查任務"""
        try:
            health_data = {
                "timestamp": datetime.now().isoformat(),
                "ssh_connections": {},
                "websocket_status": {},
                "database_status": {},
                "processing_status": {}
            }
            
            # 檢查SSH連接狀態
            async for db in get_db():
                servers = db.query(Server).filter(Server.is_active == True).all()
                ssh_stats = {
                    "total_servers": len(servers),
                    "connected_count": 0,
                    "failed_count": 0,
                    "server_status": {}
                }
                
                for server in servers:
                    is_connected = ssh_manager.is_connected(server.id)
                    ssh_stats["server_status"][server.id] = {
                        "connected": is_connected,
                        "host": server.host
                    }
                    if is_connected:
                        ssh_stats["connected_count"] += 1
                    else:
                        ssh_stats["failed_count"] += 1
                
                health_data["ssh_connections"] = ssh_stats
            
            # 檢查WebSocket狀態
            ws_status = {
                "active_connections": push_service.get_connection_count(),
                "service_running": push_service.is_service_running()
            }
            health_data["websocket_status"] = ws_status
            
            # 檢查數據處理狀態
            processing_stats = data_processor.get_processing_stats()
            health_data["processing_status"] = {
                "total_processed": processing_stats.total_processed,
                "error_count": len(processing_stats.errors),
                "buffer_size": processing_stats.buffer_size
            }
            
            # 檢查儲存空間
            storage_info = await data_cleaner.get_storage_info()
            health_data["database_status"] = {
                "usage_percentage": storage_info.usage_percentage,
                "database_size_mb": storage_info.database_size_bytes / (1024**2)
            }
            
            # 發出警告
            if ssh_stats["failed_count"] > 0:
                logger.warning(f"有 {ssh_stats['failed_count']} 台伺服器SSH連接失敗")
            
            if not ws_status["service_running"]:
                logger.warning("WebSocket推送服務未運行")
            
            if len(processing_stats.errors) > 5:
                logger.warning(f"數據處理錯誤過多: {len(processing_stats.errors)} 個錯誤")
            
            if storage_info.usage_percentage > 90:
                logger.warning(f"磁碟使用率過高: {storage_info.usage_percentage}%")
            
            return health_data
            
        except Exception as e:
            logger.error(f"系統健康檢查任務失敗: {e}")
            raise
    
    async def _execute_storage_monitor(self) -> Dict[str, Any]:
        """執行儲存空間監控任務"""
        try:
            storage_info = await data_cleaner.get_storage_info()
            
            monitor_data = {
                "usage_percentage": storage_info.usage_percentage,
                "free_space_gb": storage_info.free_space_bytes / (1024**3),
                "database_size_mb": storage_info.database_size_bytes / (1024**2),
                "archive_size_mb": storage_info.archive_size_bytes / (1024**2),
                "timestamp": datetime.now().isoformat()
            }
            
            # 儲存使用率警告
            if storage_info.usage_percentage > 95:
                logger.critical(f"磁碟空間嚴重不足: {storage_info.usage_percentage}%")
            elif storage_info.usage_percentage > 85:
                logger.warning(f"磁碟空間不足: {storage_info.usage_percentage}%")
            
            return monitor_data
        except Exception as e:
            logger.error(f"儲存監控任務失敗: {e}")
            raise
    
    async def _execute_data_cleanup(self) -> Dict[str, Any]:
        """執行數據清理任務"""
        try:
            stats = await data_cleaner.cleanup_old_data(CleanupLevel.BASIC)
            return stats.to_dict()
        except Exception as e:
            logger.error(f"數據清理任務失敗: {e}")
            raise
    
    async def _execute_archive_cleanup(self) -> Dict[str, Any]:
        """執行歸檔清理任務"""
        try:
            stats = await data_cleaner.cleanup_archive_files(90)
            return stats.to_dict()
        except Exception as e:
            logger.error(f"歸檔清理任務失敗: {e}")
            raise
    
    # ===== 管理方法 =====
    
    def get_task_list(self) -> List[Dict[str, Any]]:
        """取得任務清單"""
        return [task.to_dict() for task in self.tasks.values()]
    
    def get_execution_history(
        self, 
        task_id: Optional[str] = None, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """取得執行歷史"""
        history = self.execution_history
        
        # 按任務ID過濾
        if task_id:
            history = [h for h in history if h.task_id == task_id]
        
        # 限制數量並排序（最新的在前）
        history = sorted(history, key=lambda x: x.start_time, reverse=True)[:limit]
        
        return [h.to_dict() for h in history]
    
    async def enable_task(self, task_id: str):
        """啟用任務"""
        if task_id not in self.tasks:
            raise ValueError(f"任務 {task_id} 不存在")
        
        task = self.tasks[task_id]
        
        if task.enabled:
            logger.info(f"任務 '{task.name}' 已經是啟用狀態")
            return
        
        # 啟用任務
        task.enabled = True
        
        # 重新添加到調度器
        if self.is_running:
            trigger_obj = CronTrigger.from_crontab(task.trigger)
            job = self.scheduler.add_job(
                func=self._execute_task_wrapper,
                trigger=trigger_obj,
                args=[task_id],
                id=task_id,
                name=task.name,
                replace_existing=True
            )
            task.next_run = job.next_run_time
        
        logger.info(f"任務 '{task.name}' 已啟用")
    
    async def disable_task(self, task_id: str):
        """停用任務"""
        if task_id not in self.tasks:
            raise ValueError(f"任務 {task_id} 不存在")
        
        task = self.tasks[task_id]
        
        if not task.enabled:
            logger.info(f"任務 '{task.name}' 已經是停用狀態")
            return
        
        # 停用任務
        task.enabled = False
        task.next_run = None
        
        # 從調度器移除
        if self.is_running:
            try:
                self.scheduler.remove_job(task_id)
            except Exception:
                pass  # 任務可能已經不在調度器中
        
        logger.info(f"任務 '{task.name}' 已停用")
    
    async def run_task_now(self, task_id: str) -> TaskExecutionResult:
        """立即執行任務"""
        if task_id not in self.tasks:
            raise ValueError(f"任務 {task_id} 不存在")
        
        task = self.tasks[task_id]
        
        logger.info(f"手動執行任務: {task.name}")
        
        # 直接執行任務（不通過調度器）
        await self._execute_task_wrapper(task_id)
        
        # 返回最新的執行結果
        for result in reversed(self.execution_history):
            if result.task_id == task_id:
                return result
        
        raise RuntimeError(f"任務 {task_id} 執行後未找到結果記錄")
    
    async def reset_task_failures(self, task_id: str):
        """重置任務失敗計數"""
        if task_id not in self.tasks:
            raise ValueError(f"任務 {task_id} 不存在")
        
        task = self.tasks[task_id]
        task.consecutive_failures = 0
        task.last_failure_time = None
        
        logger.info(f"任務 '{task.name}' 失敗計數已重置")
    
    async def update_task_retry_config(
        self, 
        task_id: str, 
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
        auto_disable_threshold: Optional[int] = None
    ):
        """更新任務重試配置"""
        if task_id not in self.tasks:
            raise ValueError(f"任務 {task_id} 不存在")
        
        task = self.tasks[task_id]
        
        if max_retries is not None:
            task.max_retries = max_retries
        if retry_delay is not None:
            task.retry_delay = retry_delay
        if auto_disable_threshold is not None:
            task.auto_disable_threshold = auto_disable_threshold
        
        logger.info(f"任務 '{task.name}' 重試配置已更新")
    
    def get_failed_tasks(self) -> List[Dict[str, Any]]:
        """取得有失敗記錄的任務清單"""
        failed_tasks = []
        for task in self.tasks.values():
            if task.consecutive_failures > 0:
                failed_tasks.append({
                    "task_id": task.task_id,
                    "name": task.name,
                    "consecutive_failures": task.consecutive_failures,
                    "total_failures": task.failure_count,
                    "last_failure_time": task.last_failure_time.isoformat() if task.last_failure_time else None,
                    "enabled": task.enabled,
                    "auto_disable_threshold": task.auto_disable_threshold
                })
        
        return failed_tasks
    
    def get_task_health_summary(self) -> Dict[str, Any]:
        """取得任務健康狀況摘要"""
        total_tasks = len(self.tasks)
        enabled_tasks = sum(1 for t in self.tasks.values() if t.enabled)
        failed_tasks = sum(1 for t in self.tasks.values() if t.consecutive_failures > 0)
        critical_tasks = sum(1 for t in self.tasks.values() if t.consecutive_failures >= t.auto_disable_threshold)
        
        # 計算成功率
        total_runs = sum(t.run_count for t in self.tasks.values())
        total_failures = sum(t.failure_count for t in self.tasks.values())
        success_rate = ((total_runs - total_failures) / total_runs * 100) if total_runs > 0 else 100
        
        return {
            "total_tasks": total_tasks,
            "enabled_tasks": enabled_tasks,
            "disabled_tasks": total_tasks - enabled_tasks,
            "failed_tasks": failed_tasks,
            "critical_tasks": critical_tasks,
            "success_rate": round(success_rate, 2),
            "total_runs": total_runs,
            "total_failures": total_failures,
            "scheduler_running": self.is_running
        }


# 全域任務調度器實例
task_scheduler = TaskScheduler()


# 便利函數
async def start_task_scheduler():
    """啟動任務調度器的便利函數"""
    await task_scheduler.start()


async def stop_task_scheduler():
    """停止任務調度器的便利函數"""
    await task_scheduler.stop()


def get_scheduler_status() -> Dict[str, Any]:
    """取得調度器狀態的便利函數"""
    return {
        "is_running": task_scheduler.is_running,
        "task_count": len(task_scheduler.tasks),
        "enabled_tasks": sum(1 for t in task_scheduler.tasks.values() if t.enabled),
        "execution_history_size": len(task_scheduler.execution_history)
    }


if __name__ == "__main__":
    # 測試任務調度器
    
    async def test_scheduler():
        """測試調度器"""
        print("🕐 測試任務調度器...")
        
        try:
            # 啟動調度器
            await task_scheduler.start()
            
            print(f"✅ 調度器啟動成功")
            print(f"  - 註冊任務數: {len(task_scheduler.tasks)}")
            print(f"  - 運行狀態: {task_scheduler.is_running}")
            
            # 列出所有任務
            tasks = task_scheduler.get_task_list()
            for task in tasks:
                print(f"  - {task['name']}: {task['trigger']}")
            
            # 手動執行一個任務
            print("\n🚀 手動執行健康檢查任務...")
            result = await task_scheduler.run_task_now("hourly_health_check")
            print(f"  - 執行狀態: {result.status.value}")
            print(f"  - 執行時間: {result.duration:.2f}s")
            
            # 等待一段時間後停止
            await asyncio.sleep(2)
            
            # 停止調度器
            await task_scheduler.stop()
            print(f"✅ 調度器已停止")
            
        except Exception as e:
            print(f"❌ 調度器測試失敗: {e}")
    
    # 執行測試
    asyncio.run(test_scheduler())