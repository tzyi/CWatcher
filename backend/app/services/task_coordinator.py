"""
CWatcher 統一任務協調器

統籌所有定時任務的執行，確保任務間的協調性和避免資源衝突
負責優化任務執行順序、資源管理和系統整體效能
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from collections import defaultdict

from services.task_scheduler import task_scheduler, TaskType, TaskStatus
from services.ssh_manager import ssh_manager
from services.websocket_push_service import push_service
from services.data_processor import data_processor
from core.config import settings

# 設定日誌
logger = logging.getLogger(__name__)


class CoordinatorMode(Enum):
    """協調器模式"""
    NORMAL = "normal"          # 正常模式
    HIGH_LOAD = "high_load"    # 高負載模式
    MAINTENANCE = "maintenance" # 維護模式
    EMERGENCY = "emergency"    # 緊急模式


class ResourceType(Enum):
    """資源類型"""
    SSH_CONNECTION = "ssh_connection"
    DATABASE = "database"
    WEBSOCKET = "websocket"
    CPU = "cpu"
    MEMORY = "memory"
    DISK_IO = "disk_io"


@dataclass
class ResourceLock:
    """資源鎖定記錄"""
    resource_type: ResourceType
    resource_id: str
    locked_by: str  # 任務ID
    lock_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timeout: float = 300.0  # 超時時間（秒）
    
    def is_expired(self) -> bool:
        """檢查鎖是否過期"""
        current_time = datetime.now(timezone.utc)
        if self.lock_time.tzinfo is None:
            # 如果 lock_time 是 naive datetime，轉換為 UTC
            lock_time_utc = self.lock_time.replace(tzinfo=timezone.utc)
        else:
            lock_time_utc = self.lock_time
        return (current_time - lock_time_utc).total_seconds() > self.timeout


@dataclass
class TaskDependency:
    """任務依賴關係"""
    task_id: str
    depends_on: Set[str]  # 依賴的任務ID集合
    conflicts_with: Set[str]  # 衝突的任務ID集合
    required_resources: Set[ResourceType]
    priority: int = 0  # 優先級（數字越大優先級越高）


@dataclass
class CoordinatorStats:
    """協調器統計"""
    total_coordinated_tasks: int = 0
    resource_conflicts_resolved: int = 0
    dependency_delays: int = 0
    optimization_savings_seconds: float = 0.0
    mode_switches: Dict[CoordinatorMode, int] = field(default_factory=lambda: defaultdict(int))
    last_optimization_time: Optional[datetime] = None


class TaskCoordinator:
    """統一任務協調器"""
    
    def __init__(self):
        self.mode = CoordinatorMode.NORMAL
        self.resource_locks: Dict[str, ResourceLock] = {}
        self.task_dependencies: Dict[str, TaskDependency] = {}
        self.execution_queue: List[str] = []
        self.stats = CoordinatorStats()
        self.is_running = False
        self._coordinator_task: Optional[asyncio.Task] = None
        
        # 系統負載監控
        self.system_load = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "active_connections": 0,
            "pending_tasks": 0
        }
        
        # 初始化任務依賴關係
        self._setup_task_dependencies()
    
    def _setup_task_dependencies(self):
        """設置任務依賴關係"""
        
        # 監控數據收集任務
        self.task_dependencies["monitoring_collection"] = TaskDependency(
            task_id="monitoring_collection",
            depends_on=set(),  # 獨立任務
            conflicts_with={"system_info_update"},  # 避免與系統資訊更新衝突
            required_resources={ResourceType.SSH_CONNECTION, ResourceType.DATABASE},
            priority=10  # 最高優先級
        )
        
        # WebSocket 推送任務
        self.task_dependencies["websocket_push"] = TaskDependency(
            task_id="websocket_push",
            depends_on={"monitoring_collection"},  # 依賴監控數據收集
            conflicts_with=set(),
            required_resources={ResourceType.WEBSOCKET, ResourceType.DATABASE},
            priority=9
        )
        
        # 系統資訊更新任務
        self.task_dependencies["system_info_update"] = TaskDependency(
            task_id="system_info_update",
            depends_on=set(),
            conflicts_with={"monitoring_collection"},  # 避免SSH資源衝突
            required_resources={ResourceType.SSH_CONNECTION, ResourceType.DATABASE},
            priority=5
        )
        
        # 緩衝區刷新任務
        self.task_dependencies["buffer_flush"] = TaskDependency(
            task_id="buffer_flush",
            depends_on=set(),
            conflicts_with={"daily_data_cleanup", "weekly_archive_cleanup"},
            required_resources={ResourceType.DATABASE, ResourceType.DISK_IO},
            priority=6
        )
        
        # 系統健康檢查
        self.task_dependencies["system_health_check"] = TaskDependency(
            task_id="system_health_check",
            depends_on=set(),
            conflicts_with=set(),
            required_resources={ResourceType.SSH_CONNECTION, ResourceType.DATABASE},
            priority=7
        )
        
        # 數據清理任務
        self.task_dependencies["daily_data_cleanup"] = TaskDependency(
            task_id="daily_data_cleanup",
            depends_on=set(),
            conflicts_with={"buffer_flush", "weekly_archive_cleanup"},
            required_resources={ResourceType.DATABASE, ResourceType.DISK_IO},
            priority=3
        )
        
        # 歸檔清理任務
        self.task_dependencies["weekly_archive_cleanup"] = TaskDependency(
            task_id="weekly_archive_cleanup",
            depends_on={"daily_data_cleanup"},
            conflicts_with={"buffer_flush"},
            required_resources={ResourceType.DISK_IO},
            priority=2
        )
        
        # 儲存監控任務
        self.task_dependencies["storage_monitor"] = TaskDependency(
            task_id="storage_monitor",
            depends_on=set(),
            conflicts_with=set(),
            required_resources={ResourceType.DISK_IO},
            priority=4
        )
    
    async def start(self):
        """啟動任務協調器"""
        if self.is_running:
            logger.warning("任務協調器已在運行中")
            return
        
        self.is_running = True
        logger.info("任務協調器啟動中...")
        
        # 啟動協調器主循環
        self._coordinator_task = asyncio.create_task(self._coordinator_loop())
        
        logger.info("任務協調器已啟動")
    
    async def stop(self):
        """停止任務協調器"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self._coordinator_task and not self._coordinator_task.done():
            self._coordinator_task.cancel()
            try:
                await self._coordinator_task
            except asyncio.CancelledError:
                pass
        
        # 清理資源鎖
        self.resource_locks.clear()
        
        logger.info("任務協調器已停止")
    
    async def _coordinator_loop(self):
        """協調器主循環"""
        while self.is_running:
            try:
                # 更新系統負載
                await self._update_system_load()
                
                # 調整協調器模式
                await self._adjust_coordinator_mode()
                
                # 清理過期的資源鎖
                self._cleanup_expired_locks()
                
                # 優化任務執行
                await self._optimize_task_execution()
                
                # 每30秒執行一次協調檢查
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"協調器循環發生錯誤: {e}")
                await asyncio.sleep(5)
    
    async def _update_system_load(self):
        """更新系統負載指標"""
        try:
            # 獲取處理統計
            processing_stats = data_processor.get_processing_stats()
            
            # 獲取連接統計
            active_connections = push_service.get_connection_count()
            
            # 獲取任務統計
            scheduler_status = task_scheduler.get_task_health_summary()
            
            self.system_load.update({
                "memory_usage": processing_stats.buffer_size / 1000,  # 簡化的記憶體使用率
                "active_connections": active_connections,
                "pending_tasks": len([t for t in task_scheduler.tasks.values() if t.enabled])
            })
            
        except Exception as e:
            logger.error(f"更新系統負載失敗: {e}")
    
    async def _adjust_coordinator_mode(self):
        """根據系統負載調整協調器模式"""
        current_mode = self.mode
        
        # 檢查系統負載指標
        high_load_indicators = 0
        
        if self.system_load["memory_usage"] > 80:
            high_load_indicators += 1
        
        if self.system_load["active_connections"] > 50:
            high_load_indicators += 1
        
        if self.system_load["pending_tasks"] > 10:
            high_load_indicators += 1
        
        # 檢查失敗任務
        failed_tasks = task_scheduler.get_failed_tasks()
        critical_failures = [t for t in failed_tasks if t["consecutive_failures"] >= 3]
        
        # 決定模式
        if critical_failures:
            new_mode = CoordinatorMode.EMERGENCY
        elif high_load_indicators >= 2:
            new_mode = CoordinatorMode.HIGH_LOAD
        else:
            new_mode = CoordinatorMode.NORMAL
        
        # 切換模式
        if new_mode != current_mode:
            self.mode = new_mode
            self.stats.mode_switches[new_mode] += 1
            logger.info(f"協調器模式切換: {current_mode.value} -> {new_mode.value}")
            
            # 根據新模式調整策略
            await self._apply_mode_strategy()
    
    async def _apply_mode_strategy(self):
        """應用模式策略"""
        if self.mode == CoordinatorMode.HIGH_LOAD:
            # 高負載模式：延長任務間隔，減少並發
            logger.info("應用高負載策略：降低任務頻率")
            
        elif self.mode == CoordinatorMode.EMERGENCY:
            # 緊急模式：僅執行關鍵任務
            logger.warning("應用緊急策略：僅執行核心監控任務")
            
            # 暫時停用非關鍵任務
            non_critical_tasks = ["storage_monitor", "daily_data_cleanup", "weekly_archive_cleanup"]
            for task_id in non_critical_tasks:
                if task_id in task_scheduler.tasks:
                    await task_scheduler.disable_task(task_id)
        
        elif self.mode == CoordinatorMode.NORMAL:
            # 正常模式：確保所有任務都啟用
            logger.info("恢復正常模式：重新啟用所有任務")
            
            for task_id in task_scheduler.tasks:
                task = task_scheduler.tasks[task_id]
                if not task.enabled and task.consecutive_failures < task.auto_disable_threshold:
                    await task_scheduler.enable_task(task_id)
    
    def _cleanup_expired_locks(self):
        """清理過期的資源鎖"""
        expired_locks = []
        for lock_key, lock in self.resource_locks.items():
            if lock.is_expired():
                expired_locks.append(lock_key)
        
        for lock_key in expired_locks:
            del self.resource_locks[lock_key]
            logger.debug(f"清理過期資源鎖: {lock_key}")
    
    async def _optimize_task_execution(self):
        """優化任務執行"""
        if self.mode == CoordinatorMode.EMERGENCY:
            return  # 緊急模式不進行優化
        
        start_time = time.time()
        
        # 檢查即將執行的任務
        upcoming_tasks = self._get_upcoming_tasks()
        
        if not upcoming_tasks:
            return
        
        # 根據依賴關係和衝突優化執行順序
        optimized_order = self._calculate_optimal_execution_order(upcoming_tasks)
        
        # 應用優化
        conflicts_resolved = await self._apply_execution_optimization(optimized_order)
        
        optimization_time = time.time() - start_time
        
        if conflicts_resolved > 0:
            self.stats.resource_conflicts_resolved += conflicts_resolved
            self.stats.optimization_savings_seconds += optimization_time
            self.stats.last_optimization_time = datetime.now(timezone.utc)
            
            logger.info(f"任務執行優化完成：解決 {conflicts_resolved} 個衝突，耗時 {optimization_time:.2f}s")
    
    def _get_upcoming_tasks(self) -> List[str]:
        """獲取即將執行的任務列表"""
        upcoming_tasks = []
        current_time = datetime.now(timezone.utc)
        
        for task_id, task in task_scheduler.tasks.items():
            if task.enabled and task.next_run:
                # 檢查是否在未來5分鐘內執行
                time_until_run = (task.next_run - current_time).total_seconds()
                if 0 <= time_until_run <= 300:  # 5分鐘內
                    upcoming_tasks.append(task_id)
        
        return upcoming_tasks
    
    def _calculate_optimal_execution_order(self, task_ids: List[str]) -> List[str]:
        """計算最佳執行順序"""
        # 根據優先級和依賴關係排序
        task_priorities = []
        
        for task_id in task_ids:
            dependency = self.task_dependencies.get(task_id)
            if dependency:
                priority = dependency.priority
                # 檢查依賴是否滿足
                dependencies_met = all(
                    dep_id not in task_ids or self._is_dependency_satisfied(dep_id)
                    for dep_id in dependency.depends_on
                )
                
                if not dependencies_met:
                    priority -= 5  # 降低優先級
                
                task_priorities.append((task_id, priority))
            else:
                task_priorities.append((task_id, 0))
        
        # 按優先級排序（高優先級在前）
        task_priorities.sort(key=lambda x: x[1], reverse=True)
        
        return [task_id for task_id, _ in task_priorities]
    
    def _is_dependency_satisfied(self, task_id: str) -> bool:
        """檢查任務依賴是否滿足"""
        if task_id not in task_scheduler.tasks:
            return False
        
        task = task_scheduler.tasks[task_id]
        
        # 檢查任務最近是否成功執行
        if task.last_run and task.consecutive_failures == 0:
            # 確保時間比較一致性
            current_time = datetime.now(timezone.utc) if hasattr(task.last_run, 'tzinfo') and task.last_run.tzinfo else datetime.now()
            
            # 如果 task.last_run 沒有時區信息，假設為當前系統時區
            if hasattr(task.last_run, 'tzinfo') and task.last_run.tzinfo is None:
                task_last_run = task.last_run
            else:
                task_last_run = task.last_run
                
            time_since_run = (current_time - task_last_run).total_seconds()
            return time_since_run < 3600  # 1小時內成功執行過
        
        return False
    
    async def _apply_execution_optimization(self, optimized_order: List[str]) -> int:
        """應用執行優化"""
        conflicts_resolved = 0
        
        for i, task_id in enumerate(optimized_order):
            dependency = self.task_dependencies.get(task_id)
            if not dependency:
                continue
            
            # 檢查資源衝突
            for conflicting_task_id in dependency.conflicts_with:
                if conflicting_task_id in optimized_order:
                    conflicting_index = optimized_order.index(conflicting_task_id)
                    
                    # 如果衝突任務在當前任務之前，調整時間
                    if conflicting_index < i:
                        await self._delay_task_execution(task_id, 60)  # 延遲1分鐘
                        conflicts_resolved += 1
                        logger.info(f"解決任務衝突：{task_id} 延遲執行以避免與 {conflicting_task_id} 衝突")
        
        return conflicts_resolved
    
    async def _delay_task_execution(self, task_id: str, delay_seconds: int):
        """延遲任務執行"""
        if task_id not in task_scheduler.tasks:
            return
        
        task = task_scheduler.tasks[task_id]
        if task.next_run:
            new_run_time = task.next_run + timedelta(seconds=delay_seconds)
            
            # 重新安排任務
            job = task_scheduler.scheduler.get_job(task_id)
            if job:
                job.modify(next_run_time=new_run_time)
                task.next_run = new_run_time
                self.stats.dependency_delays += 1
    
    def get_coordination_status(self) -> Dict[str, Any]:
        """獲取協調器狀態"""
        return {
            "mode": self.mode.value,
            "is_running": self.is_running,
            "system_load": self.system_load.copy(),
            "active_resource_locks": len(self.resource_locks),
            "task_dependencies": len(self.task_dependencies),
            "stats": {
                "total_coordinated_tasks": self.stats.total_coordinated_tasks,
                "resource_conflicts_resolved": self.stats.resource_conflicts_resolved,
                "dependency_delays": self.stats.dependency_delays,
                "optimization_savings_seconds": self.stats.optimization_savings_seconds,
                "mode_switches": dict(self.stats.mode_switches),
                "last_optimization_time": self.stats.last_optimization_time.isoformat() if self.stats.last_optimization_time else None
            }
        }
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """獲取資源使用情況"""
        resource_usage = defaultdict(list)
        
        for lock_key, lock in self.resource_locks.items():
            resource_usage[lock.resource_type.value].append({
                "resource_id": lock.resource_id,
                "locked_by": lock.locked_by,
                "lock_time": lock.lock_time.isoformat(),
                "timeout": lock.timeout
            })
        
        return dict(resource_usage)


# 全域任務協調器實例
task_coordinator = TaskCoordinator()


# 便利函數
async def start_task_coordinator():
    """啟動任務協調器"""
    await task_coordinator.start()


async def stop_task_coordinator():
    """停止任務協調器"""
    await task_coordinator.stop()


def get_coordination_status():
    """獲取協調器狀態"""
    return task_coordinator.get_coordination_status()


if __name__ == "__main__":
    # 測試任務協調器
    
    async def test_coordinator():
        """測試協調器"""
        print("🎯 測試任務協調器...")
        
        try:
            # 啟動協調器
            await task_coordinator.start()
            print("✅ 協調器啟動成功")
            
            # 運行一段時間
            await asyncio.sleep(60)
            
            # 獲取狀態
            status = task_coordinator.get_coordination_status()
            print(f"📊 協調器狀態: {status}")
            
            # 停止協調器
            await task_coordinator.stop()
            print("✅ 協調器已停止")
            
        except Exception as e:
            print(f"❌ 協調器測試失敗: {e}")
    
    # 執行測試
    asyncio.run(test_coordinator())