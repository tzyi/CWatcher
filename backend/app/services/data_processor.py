"""
CWatcher 數據處理與存儲服務

專門負責監控數據的標準化、批量存儲、聚合統計和數據管理
支援高效的時序數據處理和圖表數據生成
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc, asc
from contextlib import asynccontextmanager

from app.core.deps import get_db
from app.models.system_metrics import SystemMetrics
from app.models.server import Server
from app.services.monitoring_collector import MonitoringData, MetricType, AlertLevel
from app.core.config import settings

# 設定日誌
logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """數據驗證錯誤"""
    pass


class StorageError(Exception):
    """存儲錯誤"""
    pass


@dataclass
class ProcessingStats:
    """數據處理統計"""
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    duplicate_records: int = 0
    processing_time: float = 0.0
    storage_time: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class StandardizedMetrics:
    """標準化監控數據"""
    server_id: int
    timestamp: datetime
    
    # CPU 指標 (標準化為百分比和數值)
    cpu_usage_percent: Optional[float] = None
    cpu_user_percent: Optional[float] = None
    cpu_system_percent: Optional[float] = None
    cpu_idle_percent: Optional[float] = None
    cpu_iowait_percent: Optional[float] = None
    cpu_count: Optional[int] = None
    cpu_frequency_mhz: Optional[float] = None
    load_average_1m: Optional[float] = None
    load_average_5m: Optional[float] = None
    load_average_15m: Optional[float] = None
    
    # 記憶體指標 (標準化為 MB)
    memory_total_mb: Optional[int] = None
    memory_used_mb: Optional[int] = None
    memory_available_mb: Optional[int] = None
    memory_free_mb: Optional[int] = None
    memory_cached_mb: Optional[int] = None
    memory_buffers_mb: Optional[int] = None
    memory_usage_percent: Optional[float] = None
    
    # Swap 指標 (標準化為 MB)
    swap_total_mb: Optional[int] = None
    swap_used_mb: Optional[int] = None
    swap_free_mb: Optional[int] = None
    swap_usage_percent: Optional[float] = None
    
    # 磁碟指標 (標準化為 GB)
    disk_total_gb: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_free_gb: Optional[float] = None
    disk_usage_percent: Optional[float] = None
    
    # 磁碟 I/O 指標 (bytes/s)
    disk_read_bytes_per_sec: Optional[int] = None
    disk_write_bytes_per_sec: Optional[int] = None
    disk_read_iops: Optional[int] = None
    disk_write_iops: Optional[int] = None
    
    # 網路指標 (bytes/s)
    network_interface: Optional[str] = None
    network_bytes_sent_per_sec: Optional[int] = None
    network_bytes_recv_per_sec: Optional[int] = None
    network_packets_sent_per_sec: Optional[int] = None
    network_packets_recv_per_sec: Optional[int] = None
    network_errors_in: Optional[int] = None
    network_errors_out: Optional[int] = None
    
    # 系統指標
    uptime_seconds: Optional[int] = None
    processes_total: Optional[int] = None
    processes_running: Optional[int] = None
    processes_sleeping: Optional[int] = None
    processes_zombie: Optional[int] = None
    
    # 狀態指標
    collection_duration_ms: Optional[int] = None
    collection_success: bool = True
    error_message: Optional[str] = None
    
    def to_system_metrics(self) -> SystemMetrics:
        """轉換為 SystemMetrics 模型"""
        return SystemMetrics(
            server_id=self.server_id,
            timestamp=self.timestamp,
            
            # CPU 指標
            cpu_usage_percent=self.cpu_usage_percent,
            cpu_user_percent=self.cpu_user_percent,
            cpu_system_percent=self.cpu_system_percent,
            cpu_idle_percent=self.cpu_idle_percent,
            cpu_iowait_percent=self.cpu_iowait_percent,
            cpu_count=self.cpu_count,
            cpu_frequency_mhz=self.cpu_frequency_mhz,
            load_average_1m=self.load_average_1m,
            load_average_5m=self.load_average_5m,
            load_average_15m=self.load_average_15m,
            
            # 記憶體指標
            memory_total_mb=self.memory_total_mb,
            memory_used_mb=self.memory_used_mb,
            memory_available_mb=self.memory_available_mb,
            memory_free_mb=self.memory_free_mb,
            memory_cached_mb=self.memory_cached_mb,
            memory_buffers_mb=self.memory_buffers_mb,
            memory_usage_percent=self.memory_usage_percent,
            
            # Swap 指標
            swap_total_mb=self.swap_total_mb,
            swap_used_mb=self.swap_used_mb,
            swap_free_mb=self.swap_free_mb,
            swap_usage_percent=self.swap_usage_percent,
            
            # 磁碟指標
            disk_total_gb=self.disk_total_gb,
            disk_used_gb=self.disk_used_gb,
            disk_free_gb=self.disk_free_gb,
            disk_usage_percent=self.disk_usage_percent,
            
            # 磁碟 I/O 指標
            disk_read_bytes_per_sec=self.disk_read_bytes_per_sec,
            disk_write_bytes_per_sec=self.disk_write_bytes_per_sec,
            disk_read_iops=self.disk_read_iops,
            disk_write_iops=self.disk_write_iops,
            
            # 網路指標
            network_interface=self.network_interface,
            network_bytes_sent_per_sec=self.network_bytes_sent_per_sec,
            network_bytes_recv_per_sec=self.network_bytes_recv_per_sec,
            network_packets_sent_per_sec=self.network_packets_sent_per_sec,
            network_packets_recv_per_sec=self.network_packets_recv_per_sec,
            network_errors_in=self.network_errors_in,
            network_errors_out=self.network_errors_out,
            
            # 系統指標
            uptime_seconds=self.uptime_seconds,
            processes_total=self.processes_total,
            processes_running=self.processes_running,
            processes_sleeping=self.processes_sleeping,
            processes_zombie=self.processes_zombie,
            
            # 狀態指標
            collection_duration_ms=self.collection_duration_ms,
            collection_success=self.collection_success,
            error_message=self.error_message
        )


class DataStandardizer:
    """數據標準化處理器"""
    
    @staticmethod
    def standardize_monitoring_data(
        server_id: int,
        monitoring_data: Dict[MetricType, MonitoringData]
    ) -> StandardizedMetrics:
        """
        標準化監控數據
        
        將收集器的原始數據轉換為統一格式
        處理單位轉換、數據驗證和格式統一
        """
        try:
            # 建立標準化數據對象
            standardized = StandardizedMetrics(
                server_id=server_id,
                timestamp=datetime.now()
            )
            
            # 處理 CPU 數據
            if MetricType.CPU in monitoring_data:
                cpu_data = monitoring_data[MetricType.CPU]
                if cpu_data.data and cpu_data.data.get("collection_status") == "success":
                    # 提取並驗證 CPU 數據
                    standardized.cpu_usage_percent = DataStandardizer._validate_percentage(
                        cpu_data.data.get("usage_percent")
                    )
                    standardized.cpu_count = DataStandardizer._validate_positive_int(
                        cpu_data.data.get("core_count")
                    )
                    standardized.cpu_frequency_mhz = DataStandardizer._validate_positive_float(
                        cpu_data.data.get("frequency_mhz")
                    )
                    
                    # 負載平均值
                    load_avg = cpu_data.data.get("load_average", {})
                    standardized.load_average_1m = DataStandardizer._validate_positive_float(
                        load_avg.get("1min")
                    )
                    standardized.load_average_5m = DataStandardizer._validate_positive_float(
                        load_avg.get("5min")
                    )
                    standardized.load_average_15m = DataStandardizer._validate_positive_float(
                        load_avg.get("15min")
                    )
                    
                    # 收集時間
                    standardized.collection_duration_ms = int(cpu_data.collection_time * 1000)
            
            # 處理記憶體數據
            if MetricType.MEMORY in monitoring_data:
                memory_data = monitoring_data[MetricType.MEMORY]
                if memory_data.data and memory_data.data.get("collection_status") == "success":
                    # 轉換 bytes 到 MB
                    standardized.memory_total_mb = DataStandardizer._bytes_to_mb(
                        memory_data.data.get("total_bytes")
                    )
                    standardized.memory_used_mb = DataStandardizer._bytes_to_mb(
                        memory_data.data.get("used_bytes")
                    )
                    standardized.memory_available_mb = DataStandardizer._bytes_to_mb(
                        memory_data.data.get("available_bytes")
                    )
                    standardized.memory_free_mb = DataStandardizer._bytes_to_mb(
                        memory_data.data.get("free_bytes")
                    )
                    standardized.memory_cached_mb = DataStandardizer._bytes_to_mb(
                        memory_data.data.get("cached_bytes")
                    )
                    standardized.memory_buffers_mb = DataStandardizer._bytes_to_mb(
                        memory_data.data.get("buffers_bytes")
                    )
                    standardized.memory_usage_percent = DataStandardizer._validate_percentage(
                        memory_data.data.get("usage_percent")
                    )
                    
                    # Swap 數據
                    standardized.swap_total_mb = DataStandardizer._bytes_to_mb(
                        memory_data.data.get("swap_total_bytes")
                    )
                    standardized.swap_used_mb = DataStandardizer._bytes_to_mb(
                        memory_data.data.get("swap_used_bytes")
                    )
                    standardized.swap_free_mb = DataStandardizer._bytes_to_mb(
                        memory_data.data.get("swap_free_bytes")
                    )
                    standardized.swap_usage_percent = DataStandardizer._validate_percentage(
                        memory_data.data.get("swap_usage_percent")
                    )
            
            # 處理磁碟數據
            if MetricType.DISK in monitoring_data:
                disk_data = monitoring_data[MetricType.DISK]
                if disk_data.data and disk_data.data.get("collection_status") == "success":
                    # 轉換 bytes 到 GB
                    standardized.disk_total_gb = DataStandardizer._bytes_to_gb(
                        disk_data.data.get("total_space_bytes")
                    )
                    standardized.disk_used_gb = DataStandardizer._bytes_to_gb(
                        disk_data.data.get("used_space_bytes")
                    )
                    standardized.disk_free_gb = DataStandardizer._bytes_to_gb(
                        disk_data.data.get("free_space_bytes")
                    )
                    standardized.disk_usage_percent = DataStandardizer._validate_percentage(
                        disk_data.data.get("overall_usage_percent")
                    )
                    
                    # I/O 統計 (取主要設備的平均值)
                    io_stats = disk_data.data.get("io_stats", {})
                    if io_stats:
                        total_read_kbps = sum(stats.get("read_kb_per_sec", 0) for stats in io_stats.values())
                        total_write_kbps = sum(stats.get("write_kb_per_sec", 0) for stats in io_stats.values())
                        
                        standardized.disk_read_bytes_per_sec = int(total_read_kbps * 1024) if total_read_kbps > 0 else None
                        standardized.disk_write_bytes_per_sec = int(total_write_kbps * 1024) if total_write_kbps > 0 else None
                        
                        # IOPS 統計
                        total_read_iops = sum(stats.get("reads_per_sec", 0) for stats in io_stats.values())
                        total_write_iops = sum(stats.get("writes_per_sec", 0) for stats in io_stats.values())
                        
                        standardized.disk_read_iops = int(total_read_iops) if total_read_iops > 0 else None
                        standardized.disk_write_iops = int(total_write_iops) if total_write_iops > 0 else None
            
            # 處理網路數據
            if MetricType.NETWORK in monitoring_data:
                network_data = monitoring_data[MetricType.NETWORK]
                if network_data.data and network_data.data.get("collection_status") == "success":
                    # 取主要網路介面的數據
                    interfaces = network_data.data.get("interfaces", {})
                    
                    # 找到流量最大的介面 (排除 lo)
                    main_interface = None
                    max_traffic = 0
                    
                    for iface, stats in interfaces.items():
                        if iface == "lo":
                            continue
                        
                        traffic = stats.get("rx_bytes", 0) + stats.get("tx_bytes", 0)
                        if traffic > max_traffic:
                            max_traffic = traffic
                            main_interface = iface
                    
                    if main_interface and main_interface in interfaces:
                        iface_stats = interfaces[main_interface]
                        
                        standardized.network_interface = main_interface
                        standardized.network_bytes_sent_per_sec = DataStandardizer._validate_positive_int(
                            iface_stats.get("tx_speed_bps")
                        )
                        standardized.network_bytes_recv_per_sec = DataStandardizer._validate_positive_int(
                            iface_stats.get("rx_speed_bps")
                        )
                        standardized.network_errors_in = DataStandardizer._validate_positive_int(
                            iface_stats.get("rx_errors")
                        )
                        standardized.network_errors_out = DataStandardizer._validate_positive_int(
                            iface_stats.get("tx_errors")
                        )
            
            # 設定收集成功狀態
            standardized.collection_success = all(
                data.alert_level != AlertLevel.UNKNOWN 
                for data in monitoring_data.values()
            )
            
            # 收集錯誤訊息
            error_messages = [
                data.alert_message for data in monitoring_data.values() 
                if data.alert_message and data.alert_level == AlertLevel.UNKNOWN
            ]
            if error_messages:
                standardized.error_message = "; ".join(error_messages)
            
            return standardized
            
        except Exception as e:
            logger.error(f"標準化監控數據失敗: {e}")
            # 回傳基本的錯誤記錄
            return StandardizedMetrics(
                server_id=server_id,
                timestamp=datetime.now(),
                collection_success=False,
                error_message=f"數據標準化失敗: {str(e)}"
            )
    
    @staticmethod
    def _validate_percentage(value: Any) -> Optional[float]:
        """驗證百分比數值 (0-100)"""
        if value is None:
            return None
        try:
            val = float(value)
            return max(0.0, min(100.0, val))
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _validate_positive_int(value: Any) -> Optional[int]:
        """驗證正整數"""
        if value is None:
            return None
        try:
            val = int(float(value))
            return max(0, val)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _validate_positive_float(value: Any) -> Optional[float]:
        """驗證正浮點數"""
        if value is None:
            return None
        try:
            val = float(value)
            return max(0.0, val)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _bytes_to_mb(value: Any) -> Optional[int]:
        """轉換 bytes 到 MB"""
        if value is None:
            return None
        try:
            val = int(float(value))
            return max(0, val // (1024 * 1024))
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def _bytes_to_gb(value: Any) -> Optional[float]:
        """轉換 bytes 到 GB"""
        if value is None:
            return None
        try:
            val = float(value)
            return max(0.0, round(val / (1024 * 1024 * 1024), 2))
        except (ValueError, TypeError):
            return None


class BatchStorageManager:
    """批量存儲管理器"""
    
    def __init__(self, batch_size: int = 100, flush_interval: int = 30):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._batch_buffer: List[StandardizedMetrics] = []
        self._last_flush_time = time.time()
        self._flush_lock = asyncio.Lock()
    
    async def add_metrics(self, metrics: Union[StandardizedMetrics, List[StandardizedMetrics]]) -> ProcessingStats:
        """
        添加指標到批量緩衝區
        達到批量大小或時間間隔時自動刷新
        """
        stats = ProcessingStats()
        
        try:
            # 標準化輸入
            if isinstance(metrics, StandardizedMetrics):
                metrics = [metrics]
            
            async with self._flush_lock:
                # 添加到緩衝區
                self._batch_buffer.extend(metrics)
                stats.total_records = len(metrics)
                
                # 檢查是否需要刷新
                should_flush = (
                    len(self._batch_buffer) >= self.batch_size or
                    time.time() - self._last_flush_time >= self.flush_interval
                )
                
                if should_flush:
                    flush_stats = await self._flush_batch()
                    stats.valid_records = flush_stats.valid_records
                    stats.invalid_records = flush_stats.invalid_records
                    stats.duplicate_records = flush_stats.duplicate_records
                    stats.storage_time = flush_stats.storage_time
                    stats.errors.extend(flush_stats.errors)
                else:
                    stats.valid_records = len(metrics)
            
            return stats
            
        except Exception as e:
            logger.error(f"批量添加指標失敗: {e}")
            stats.errors.append(str(e))
            return stats
    
    async def flush(self) -> ProcessingStats:
        """強制刷新緩衝區"""
        async with self._flush_lock:
            return await self._flush_batch()
    
    async def _flush_batch(self) -> ProcessingStats:
        """內部批量刷新實現"""
        stats = ProcessingStats()
        
        if not self._batch_buffer:
            return stats
        
        start_time = time.time()
        
        try:
            # 驗證數據
            valid_metrics = []
            for metric in self._batch_buffer:
                try:
                    self._validate_metrics(metric)
                    valid_metrics.append(metric)
                    stats.valid_records += 1
                except DataValidationError as e:
                    stats.invalid_records += 1
                    stats.errors.append(f"數據驗證失敗: {e}")
                    logger.warning(f"數據驗證失敗: {e}")
            
            # 批量存儲
            if valid_metrics:
                stored_count = await self._batch_insert_metrics(valid_metrics)
                stats.duplicate_records = len(valid_metrics) - stored_count
            
            # 清空緩衝區
            stats.total_records = len(self._batch_buffer)
            self._batch_buffer.clear()
            self._last_flush_time = time.time()
            
            stats.storage_time = time.time() - start_time
            
            logger.info(f"批量存儲完成: {stats.valid_records} 成功, {stats.invalid_records} 失敗, "
                       f"{stats.duplicate_records} 重複, 耗時 {stats.storage_time:.2f}s")
            
            return stats
            
        except Exception as e:
            logger.error(f"批量刷新失敗: {e}")
            stats.errors.append(str(e))
            return stats
    
    def _validate_metrics(self, metrics: StandardizedMetrics):
        """驗證數據完整性"""
        if not metrics.server_id:
            raise DataValidationError("缺少 server_id")
        
        if not metrics.timestamp:
            raise DataValidationError("缺少 timestamp")
        
        # 檢查時間戳是否合理 (不能是未來時間，不能超過24小時前)
        now = datetime.now()
        if metrics.timestamp > now:
            raise DataValidationError(f"時間戳不能是未來時間: {metrics.timestamp}")
        
        if metrics.timestamp < now - timedelta(hours=24):
            raise DataValidationError(f"時間戳過於久遠: {metrics.timestamp}")
        
        # 驗證百分比數值範圍
        percentage_fields = [
            'cpu_usage_percent', 'cpu_user_percent', 'cpu_system_percent',
            'cpu_idle_percent', 'cpu_iowait_percent', 'memory_usage_percent',
            'swap_usage_percent', 'disk_usage_percent'
        ]
        
        for field in percentage_fields:
            value = getattr(metrics, field)
            if value is not None and (value < 0 or value > 100):
                raise DataValidationError(f"{field} 數值範圍錯誤: {value}")
    
    async def _batch_insert_metrics(self, metrics: List[StandardizedMetrics]) -> int:
        """批量插入指標數據"""
        if not metrics:
            return 0
        
        try:
            # 使用數據庫會話
            async with self._get_db_session() as db:
                # 轉換為 SystemMetrics 模型
                db_metrics = [metric.to_system_metrics() for metric in metrics]
                
                # 批量插入
                db.add_all(db_metrics)
                await db.commit()
                
                return len(db_metrics)
                
        except Exception as e:
            logger.error(f"批量插入失敗: {e}")
            raise StorageError(f"數據存儲失敗: {e}")
    
    @asynccontextmanager
    async def _get_db_session(self):
        """取得數據庫會話"""
        db = next(get_db())
        try:
            yield db
        finally:
            db.close()


class DataProcessor:
    """數據處理主服務"""
    
    def __init__(self):
        self.standardizer = DataStandardizer()
        self.storage_manager = BatchStorageManager(
            batch_size=settings.BATCH_SIZE if hasattr(settings, 'BATCH_SIZE') else 100,
            flush_interval=settings.FLUSH_INTERVAL if hasattr(settings, 'FLUSH_INTERVAL') else 30
        )
        self._processing_stats = ProcessingStats()
    
    async def process_monitoring_data(
        self, 
        server_id: int, 
        monitoring_data: Dict[MetricType, MonitoringData]
    ) -> ProcessingStats:
        """
        處理監控數據的主要入口
        
        1. 標準化數據格式
        2. 驗證數據完整性
        3. 批量存儲到數據庫
        """
        start_time = time.time()
        
        try:
            # 標準化數據
            standardized_metrics = self.standardizer.standardize_monitoring_data(
                server_id, monitoring_data
            )
            
            # 批量存儲
            storage_stats = await self.storage_manager.add_metrics(standardized_metrics)
            
            # 更新統計
            storage_stats.processing_time = time.time() - start_time
            
            return storage_stats
            
        except Exception as e:
            logger.error(f"處理監控數據失敗: {e}")
            error_stats = ProcessingStats()
            error_stats.total_records = 1
            error_stats.invalid_records = 1
            error_stats.processing_time = time.time() - start_time
            error_stats.errors.append(str(e))
            return error_stats
    
    async def batch_process_monitoring_data(
        self, 
        server_data_list: List[Tuple[int, Dict[MetricType, MonitoringData]]]
    ) -> ProcessingStats:
        """批量處理多台伺服器的監控數據"""
        start_time = time.time()
        combined_stats = ProcessingStats()
        
        try:
            # 並行處理所有伺服器數據
            tasks = [
                self.process_monitoring_data(server_id, monitoring_data)
                for server_id, monitoring_data in server_data_list
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 合併統計結果
            for result in results:
                if isinstance(result, ProcessingStats):
                    combined_stats.total_records += result.total_records
                    combined_stats.valid_records += result.valid_records
                    combined_stats.invalid_records += result.invalid_records
                    combined_stats.duplicate_records += result.duplicate_records
                    combined_stats.storage_time += result.storage_time
                    combined_stats.errors.extend(result.errors)
                elif isinstance(result, Exception):
                    combined_stats.invalid_records += 1
                    combined_stats.errors.append(str(result))
            
            combined_stats.processing_time = time.time() - start_time
            
            logger.info(f"批量處理完成: {len(server_data_list)} 台伺服器, "
                       f"{combined_stats.valid_records} 成功, {combined_stats.invalid_records} 失敗")
            
            return combined_stats
            
        except Exception as e:
            logger.error(f"批量處理監控數據失敗: {e}")
            combined_stats.invalid_records = len(server_data_list)
            combined_stats.processing_time = time.time() - start_time
            combined_stats.errors.append(str(e))
            return combined_stats
    
    async def flush_all_data(self) -> ProcessingStats:
        """強制刷新所有緩衝數據"""
        return await self.storage_manager.flush()
    
    def get_processing_stats(self) -> ProcessingStats:
        """取得處理統計"""
        return self._processing_stats


# 全域數據處理器實例
data_processor = DataProcessor()


# 便利函數
async def process_server_monitoring_data(
    server_id: int, 
    monitoring_data: Dict[MetricType, MonitoringData]
) -> ProcessingStats:
    """處理單台伺服器監控數據的便利函數"""
    return await data_processor.process_monitoring_data(server_id, monitoring_data)


async def batch_process_servers_monitoring_data(
    server_data_list: List[Tuple[int, Dict[MetricType, MonitoringData]]]
) -> ProcessingStats:
    """批量處理多台伺服器監控數據的便利函數"""
    return await data_processor.batch_process_monitoring_data(server_data_list)


async def flush_monitoring_data() -> ProcessingStats:
    """刷新監控數據緩衝區的便利函數"""
    return await data_processor.flush_all_data()


if __name__ == "__main__":
    # 測試數據處理器
    
    async def test_data_standardization():
        """測試數據標準化"""
        print("🔧 測試數據標準化...")
        
        # 模擬監控數據
        from app.services.monitoring_collector import MonitoringData, MetricType, AlertLevel
        
        mock_cpu_data = MonitoringData(
            metric_type=MetricType.CPU,
            server_id=1,
            data={
                "collection_status": "success",
                "usage_percent": 45.2,
                "core_count": 4,
                "frequency_mhz": 2400.0,
                "load_average": {"1min": 1.5, "5min": 1.2, "15min": 0.8}
            },
            alert_level=AlertLevel.OK,
            collection_time=0.5
        )
        
        mock_memory_data = MonitoringData(
            metric_type=MetricType.MEMORY,
            server_id=1,
            data={
                "collection_status": "success",
                "total_bytes": 8589934592,  # 8GB
                "used_bytes": 5497558138,   # ~5.1GB
                "available_bytes": 3092376454,  # ~2.9GB
                "usage_percent": 64.0,
                "swap_total_bytes": 2147483648,  # 2GB
                "swap_used_bytes": 0,
                "swap_usage_percent": 0.0
            },
            alert_level=AlertLevel.OK,
            collection_time=0.3
        )
        
        monitoring_data = {
            MetricType.CPU: mock_cpu_data,
            MetricType.MEMORY: mock_memory_data
        }
        
        # 測試標準化
        standardized = DataStandardizer.standardize_monitoring_data(1, monitoring_data)
        
        print(f"✅ 標準化完成:")
        print(f"  - CPU使用率: {standardized.cpu_usage_percent}%")
        print(f"  - CPU核心數: {standardized.cpu_count}")
        print(f"  - 記憶體總量: {standardized.memory_total_mb}MB")
        print(f"  - 記憶體使用率: {standardized.memory_usage_percent}%")
        print(f"  - 收集狀態: {standardized.collection_success}")
    
    async def test_batch_storage():
        """測試批量存儲"""
        print("\n💾 測試批量存儲...")
        
        try:
            # 建立測試數據
            test_metrics = []
            for i in range(5):
                metrics = StandardizedMetrics(
                    server_id=1,
                    timestamp=datetime.now() - timedelta(seconds=i*30),
                    cpu_usage_percent=40.0 + i * 5,
                    memory_usage_percent=60.0 + i * 2,
                    collection_success=True
                )
                test_metrics.append(metrics)
            
            # 測試批量存儲
            storage_manager = BatchStorageManager(batch_size=3)
            stats = await storage_manager.add_metrics(test_metrics)
            
            print(f"✅ 批量存儲完成:")
            print(f"  - 總記錄數: {stats.total_records}")
            print(f"  - 有效記錄: {stats.valid_records}")
            print(f"  - 無效記錄: {stats.invalid_records}")
            print(f"  - 存儲時間: {stats.storage_time:.3f}s")
            
            if stats.errors:
                print(f"  - 錯誤: {stats.errors}")
                
        except ImportError:
            print("⚠️ 無法連接數據庫，跳過存儲測試")
        except Exception as e:
            print(f"❌ 批量存儲測試失敗: {e}")
    
    async def test_data_processor():
        """測試完整數據處理流程"""
        print("\n🚀 測試完整數據處理流程...")
        
        # 模擬監控數據
        from app.services.monitoring_collector import MonitoringData, MetricType, AlertLevel
        
        mock_monitoring_data = {
            MetricType.CPU: MonitoringData(
                metric_type=MetricType.CPU,
                server_id=1,
                data={
                    "collection_status": "success",
                    "usage_percent": 55.0,
                    "core_count": 8,
                    "frequency_mhz": 3200.0
                },
                alert_level=AlertLevel.OK
            ),
            MetricType.MEMORY: MonitoringData(
                metric_type=MetricType.MEMORY,
                server_id=1,
                data={
                    "collection_status": "success",
                    "total_bytes": 17179869184,  # 16GB
                    "used_bytes": 12884901888,   # 12GB
                    "usage_percent": 75.0
                },
                alert_level=AlertLevel.WARNING
            )
        }
        
        # 測試處理
        processor = DataProcessor()
        stats = await processor.process_monitoring_data(1, mock_monitoring_data)
        
        print(f"✅ 數據處理完成:")
        print(f"  - 處理時間: {stats.processing_time:.3f}s")
        print(f"  - 總記錄數: {stats.total_records}")
        print(f"  - 有效記錄: {stats.valid_records}")
        
        if stats.errors:
            print(f"  - 錯誤: {stats.errors}")
    
    async def test_complete():
        """完整測試"""
        print("=" * 50)
        print("🧪 CWatcher 數據處理與存儲服務測試")
        print("=" * 50)
        
        await test_data_standardization()
        await test_batch_storage()
        await test_data_processor()
        
        print("\n✅ 數據處理與存儲服務測試完成")
    
    # 執行測試
    import asyncio
    asyncio.run(test_complete())