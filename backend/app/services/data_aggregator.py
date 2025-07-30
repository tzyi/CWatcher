"""
CWatcher 時序數據聚合系統

專門負責監控數據的統計聚合、圖表數據生成和歷史數據查詢
支援多時間範圍的數據聚合和高效的時序數據查詢
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc, asc, and_, or_
from statistics import mean, median
import math

from core.deps import get_db
from models.system_metrics import SystemMetrics
from models.server import Server
from core.config import settings

# 設定日誌
logger = logging.getLogger(__name__)


class TimeRange(Enum):
    """時間範圍枚舉"""
    HOUR_1 = "1h"
    HOUR_6 = "6h" 
    HOUR_24 = "24h"
    DAY_7 = "7d"
    DAY_30 = "30d"


class AggregationType(Enum):
    """聚合類型枚舉"""
    AVERAGE = "avg"
    MAXIMUM = "max"
    MINIMUM = "min"
    SUM = "sum"
    COUNT = "count"
    PERCENTILE_95 = "p95"


@dataclass
class TimeSeriesPoint:
    """時序數據點"""
    timestamp: datetime
    value: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value
        }


@dataclass
class MetricSummary:
    """指標摘要統計"""
    current_value: Optional[float] = None
    average_value: Optional[float] = None
    maximum_value: Optional[float] = None
    minimum_value: Optional[float] = None
    percentile_95: Optional[float] = None
    total_samples: int = 0
    trend_direction: str = "stable"  # up, down, stable
    trend_percentage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current": self.current_value,
            "average": self.average_value,
            "maximum": self.maximum_value,
            "minimum": self.minimum_value,
            "p95": self.percentile_95,
            "samples": self.total_samples,
            "trend": {
                "direction": self.trend_direction,
                "percentage": self.trend_percentage
            }
        }


@dataclass
class ChartData:
    """圖表數據"""
    metric_name: str
    time_range: TimeRange
    time_series: List[TimeSeriesPoint] = field(default_factory=list)
    summary: Optional[MetricSummary] = None
    unit: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric_name,
            "time_range": self.time_range.value,
            "unit": self.unit,
            "data": [point.to_dict() for point in self.time_series],
            "summary": self.summary.to_dict() if self.summary else None
        }


class TimeSeriesAggregator:
    """時序數據聚合器"""
    
    # 時間範圍配置
    TIME_RANGE_CONFIG = {
        TimeRange.HOUR_1: {"minutes": 60, "interval_minutes": 1, "max_points": 60},
        TimeRange.HOUR_6: {"minutes": 360, "interval_minutes": 5, "max_points": 72},
        TimeRange.HOUR_24: {"minutes": 1440, "interval_minutes": 15, "max_points": 96},
        TimeRange.DAY_7: {"minutes": 10080, "interval_minutes": 60, "max_points": 168},
        TimeRange.DAY_30: {"minutes": 43200, "interval_minutes": 240, "max_points": 180}
    }
    
    def __init__(self):
        self.db_session_factory = get_db
    
    async def get_metric_time_series(
        self,
        server_id: int,
        metric_name: str,
        time_range: TimeRange,
        aggregation: AggregationType = AggregationType.AVERAGE
    ) -> ChartData:
        """
        取得指標的時序數據
        
        Args:
            server_id: 伺服器ID
            metric_name: 指標名稱 (cpu_usage_percent, memory_usage_percent, etc.)
            time_range: 時間範圍
            aggregation: 聚合類型
        """
        try:
            # 取得時間範圍配置
            config = self.TIME_RANGE_CONFIG[time_range]
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=config["minutes"])
            
            # 查詢原始數據
            db = next(self.db_session_factory())
            try:
                raw_data = await self._query_raw_metrics(
                    db, server_id, metric_name, start_time, end_time
                )
                
                # 聚合數據
                time_series = await self._aggregate_time_series(
                    raw_data, config["interval_minutes"], aggregation
                )
                
                # 計算摘要統計
                summary = await self._calculate_summary_stats(raw_data, aggregation)
                
                # 取得單位
                unit = self._get_metric_unit(metric_name)
                
                return ChartData(
                    metric_name=metric_name,
                    time_range=time_range,
                    time_series=time_series,
                    summary=summary,
                    unit=unit
                )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"取得時序數據失敗: {e}")
            return ChartData(
                metric_name=metric_name,
                time_range=time_range,
                unit=self._get_metric_unit(metric_name)
            )
    
    async def get_multiple_metrics_chart_data(
        self,
        server_id: int,
        metric_names: List[str],
        time_range: TimeRange
    ) -> Dict[str, ChartData]:
        """取得多個指標的圖表數據"""
        try:
            # 並行查詢所有指標
            tasks = [
                self.get_metric_time_series(server_id, metric_name, time_range)
                for metric_name in metric_names
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 組織結果
            chart_data = {}
            for i, result in enumerate(results):
                metric_name = metric_names[i]
                if isinstance(result, ChartData):
                    chart_data[metric_name] = result
                else:
                    logger.warning(f"取得 {metric_name} 數據失敗: {result}")
                    chart_data[metric_name] = ChartData(
                        metric_name=metric_name,
                        time_range=time_range,
                        unit=self._get_metric_unit(metric_name)
                    )
            
            return chart_data
            
        except Exception as e:
            logger.error(f"取得多個指標圖表數據失敗: {e}")
            return {}
    
    async def get_server_dashboard_data(
        self,
        server_id: int,
        time_range: TimeRange = TimeRange.HOUR_1
    ) -> Dict[str, Any]:
        """
        取得伺服器儀表板數據
        符合 UI 原型需求的格式
        """
        try:
            # 核心監控指標
            core_metrics = [
                "cpu_usage_percent",
                "memory_usage_percent", 
                "disk_usage_percent"
            ]
            
            # 取得圖表數據
            chart_data = await self.get_multiple_metrics_chart_data(
                server_id, core_metrics, time_range
            )
            
            # 取得最新數據點
            latest_data = await self._get_latest_metrics(server_id)
            
            # 組織儀表板數據
            dashboard_data = {
                "server_id": server_id,
                "time_range": time_range.value,
                "timestamp": datetime.now().isoformat(),
                "charts": {
                    metric: data.to_dict() 
                    for metric, data in chart_data.items()
                },
                "current_values": latest_data,
                "status": self._calculate_overall_status(latest_data)
            }
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"取得儀表板數據失敗: {e}")
            return {
                "server_id": server_id,
                "time_range": time_range.value,
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def _query_raw_metrics(
        self,
        db: Session,
        server_id: int,
        metric_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Tuple[datetime, float]]:
        """查詢原始指標數據"""
        try:
            # 構建查詢
            query = db.query(
                SystemMetrics.timestamp,
                getattr(SystemMetrics, metric_name)
            ).filter(
                SystemMetrics.server_id == server_id,
                SystemMetrics.timestamp >= start_time,
                SystemMetrics.timestamp <= end_time,
                SystemMetrics.collection_success == True,
                getattr(SystemMetrics, metric_name).isnot(None)
            ).order_by(SystemMetrics.timestamp)
            
            results = query.all()
            
            # 過濾有效數據
            return [
                (timestamp, float(value)) 
                for timestamp, value in results 
                if value is not None
            ]
            
        except Exception as e:
            logger.error(f"查詢原始數據失敗: {e}")
            return []
    
    async def _aggregate_time_series(
        self,
        raw_data: List[Tuple[datetime, float]],
        interval_minutes: int,
        aggregation: AggregationType
    ) -> List[TimeSeriesPoint]:
        """聚合時序數據"""
        if not raw_data:
            return []
        
        try:
            # 按時間間隔分組數據
            groups = {}
            
            for timestamp, value in raw_data:
                # 計算時間間隔的起始時間
                interval_start = self._round_to_interval(timestamp, interval_minutes)
                
                if interval_start not in groups:
                    groups[interval_start] = []
                groups[interval_start].append(value)
            
            # 聚合每個時間間隔的數據
            time_series = []
            for interval_start in sorted(groups.keys()):
                values = groups[interval_start]
                
                # 根據聚合類型計算值
                if aggregation == AggregationType.AVERAGE:
                    aggregated_value = mean(values)
                elif aggregation == AggregationType.MAXIMUM:
                    aggregated_value = max(values)
                elif aggregation == AggregationType.MINIMUM:
                    aggregated_value = min(values)
                elif aggregation == AggregationType.SUM:
                    aggregated_value = sum(values)
                elif aggregation == AggregationType.COUNT:
                    aggregated_value = len(values)
                elif aggregation == AggregationType.PERCENTILE_95:
                    aggregated_value = self._percentile(values, 95)
                else:
                    aggregated_value = mean(values)
                
                time_series.append(TimeSeriesPoint(
                    timestamp=interval_start,
                    value=round(aggregated_value, 2)
                ))
            
            return time_series
            
        except Exception as e:
            logger.error(f"聚合時序數據失敗: {e}")
            return []
    
    async def _calculate_summary_stats(
        self,
        raw_data: List[Tuple[datetime, float]],
        aggregation: AggregationType
    ) -> MetricSummary:
        """計算摘要統計"""
        if not raw_data:
            return MetricSummary()
        
        try:
            values = [value for _, value in raw_data]
            
            summary = MetricSummary(
                current_value=values[-1] if values else None,
                average_value=round(mean(values), 2),
                maximum_value=round(max(values), 2),
                minimum_value=round(min(values), 2),
                percentile_95=round(self._percentile(values, 95), 2),
                total_samples=len(values)
            )
            
            # 計算趨勢
            if len(raw_data) >= 2:
                trend = self._calculate_trend(raw_data)
                summary.trend_direction = trend["direction"]
                summary.trend_percentage = trend["percentage"]
            
            return summary
            
        except Exception as e:
            logger.error(f"計算摘要統計失敗: {e}")
            return MetricSummary()
    
    async def _get_latest_metrics(self, server_id: int) -> Dict[str, Any]:
        """取得最新的監控數據"""
        try:
            db = next(self.db_session_factory())
            try:
                latest = db.query(SystemMetrics).filter(
                    SystemMetrics.server_id == server_id,
                    SystemMetrics.collection_success == True
                ).order_by(desc(SystemMetrics.timestamp)).first()
                
                if not latest:
                    return {}
                
                return {
                    "timestamp": latest.timestamp.isoformat(),
                    "cpu_usage_percent": latest.cpu_usage_percent,
                    "memory_usage_percent": latest.memory_usage_percent,
                    "disk_usage_percent": latest.disk_usage_percent,
                    "load_average_1m": latest.load_average_1m,
                    "network_bytes_sent_per_sec": latest.network_bytes_sent_per_sec,
                    "network_bytes_recv_per_sec": latest.network_bytes_recv_per_sec
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"取得最新數據失敗: {e}")
            return {}
    
    def _round_to_interval(self, timestamp: datetime, interval_minutes: int) -> datetime:
        """將時間戳四捨五入到指定間隔"""
        # 計算從午夜開始的分鐘數
        minutes_since_midnight = timestamp.hour * 60 + timestamp.minute
        
        # 四捨五入到間隔
        rounded_minutes = (minutes_since_midnight // interval_minutes) * interval_minutes
        
        # 返回四捨五入的時間戳
        return timestamp.replace(
            hour=rounded_minutes // 60,
            minute=rounded_minutes % 60,
            second=0,
            microsecond=0
        )
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """計算百分位數"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * percentile / 100.0
        f = math.floor(k)
        c = math.ceil(k)
        
        if f == c:
            return sorted_values[int(k)]
        
        return sorted_values[int(f)] * (c - k) + sorted_values[int(c)] * (k - f)
    
    def _calculate_trend(self, raw_data: List[Tuple[datetime, float]]) -> Dict[str, Any]:
        """計算數據趨勢"""
        if len(raw_data) < 2:
            return {"direction": "stable", "percentage": 0.0}
        
        try:
            # 取前25%和後25%的數據進行比較
            quarter_size = max(1, len(raw_data) // 4)
            
            early_values = [value for _, value in raw_data[:quarter_size]]
            recent_values = [value for _, value in raw_data[-quarter_size:]]
            
            early_avg = mean(early_values)
            recent_avg = mean(recent_values)
            
            if early_avg == 0:
                return {"direction": "stable", "percentage": 0.0}
            
            change_percentage = ((recent_avg - early_avg) / early_avg) * 100
            
            if abs(change_percentage) < 5:  # 5% 以內認為是穩定
                direction = "stable"
            elif change_percentage > 0:
                direction = "up"
            else:
                direction = "down"
            
            return {
                "direction": direction,
                "percentage": round(abs(change_percentage), 1)
            }
            
        except Exception as e:
            logger.warning(f"計算趨勢失敗: {e}")
            return {"direction": "stable", "percentage": 0.0}
    
    def _get_metric_unit(self, metric_name: str) -> str:
        """取得指標單位"""
        unit_mapping = {
            "cpu_usage_percent": "%",
            "memory_usage_percent": "%",
            "disk_usage_percent": "%",
            "swap_usage_percent": "%",
            "cpu_user_percent": "%",
            "cpu_system_percent": "%",
            "cpu_idle_percent": "%",
            "cpu_iowait_percent": "%",
            "load_average_1m": "",
            "load_average_5m": "",
            "load_average_15m": "",
            "memory_total_mb": "MB",
            "memory_used_mb": "MB",
            "memory_available_mb": "MB",
            "memory_cached_mb": "MB",
            "disk_read_bytes_per_sec": "B/s",
            "disk_write_bytes_per_sec": "B/s",
            "network_bytes_sent_per_sec": "B/s",
            "network_bytes_recv_per_sec": "B/s",
            "cpu_frequency_mhz": "MHz",
            "uptime_seconds": "s"
        }
        return unit_mapping.get(metric_name, "")
    
    def _calculate_overall_status(self, latest_data: Dict[str, Any]) -> str:
        """計算整體狀態"""
        if not latest_data:
            return "unknown"
        
        try:
            cpu_usage = latest_data.get("cpu_usage_percent", 0)
            memory_usage = latest_data.get("memory_usage_percent", 0)
            disk_usage = latest_data.get("disk_usage_percent", 0)
            
            # 檢查嚴重狀態
            if cpu_usage >= 90 or memory_usage >= 95 or disk_usage >= 95:
                return "critical"
            
            # 檢查警告狀態
            if cpu_usage >= 80 or memory_usage >= 85 or disk_usage >= 90:
                return "warning"
            
            return "normal"
            
        except Exception:
            return "unknown"


class BatchDataAggregator:
    """批量數據聚合器"""
    
    def __init__(self):
        self.aggregator = TimeSeriesAggregator()
    
    async def generate_server_charts_batch(
        self,
        server_ids: List[int],
        metric_names: List[str],
        time_range: TimeRange
    ) -> Dict[int, Dict[str, ChartData]]:
        """批量生成多台伺服器的圖表數據"""
        try:
            # 為每台伺服器並行生成圖表數據
            tasks = [
                self.aggregator.get_multiple_metrics_chart_data(
                    server_id, metric_names, time_range
                )
                for server_id in server_ids
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 組織結果
            batch_results = {}
            for i, result in enumerate(results):
                server_id = server_ids[i]
                if isinstance(result, dict):
                    batch_results[server_id] = result
                else:
                    logger.warning(f"伺服器 {server_id} 數據生成失敗: {result}")
                    batch_results[server_id] = {}
            
            return batch_results
            
        except Exception as e:
            logger.error(f"批量生成圖表數據失敗: {e}")
            return {}
    
    async def generate_dashboard_data_batch(
        self,
        server_ids: List[int],
        time_range: TimeRange = TimeRange.HOUR_1
    ) -> Dict[int, Dict[str, Any]]:
        """批量生成儀表板數據"""
        try:
            # 並行生成所有伺服器的儀表板數據
            tasks = [
                self.aggregator.get_server_dashboard_data(server_id, time_range)
                for server_id in server_ids
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 組織結果
            batch_results = {}
            for i, result in enumerate(results):
                server_id = server_ids[i]
                if isinstance(result, dict):
                    batch_results[server_id] = result
                else:
                    logger.warning(f"伺服器 {server_id} 儀表板數據生成失敗: {result}")
                    batch_results[server_id] = {
                        "server_id": server_id,
                        "error": str(result)
                    }
            
            return batch_results
            
        except Exception as e:
            logger.error(f"批量生成儀表板數據失敗: {e}")
            return {}


class HistoricalDataManager:
    """歷史數據管理器"""
    
    def __init__(self):
        self.db_session_factory = get_db
    
    async def get_historical_summary(
        self,
        server_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """取得歷史數據摘要"""
        try:
            db = next(self.db_session_factory())
            try:
                # 查詢歷史數據
                query = db.query(SystemMetrics).filter(
                    SystemMetrics.server_id == server_id,
                    SystemMetrics.timestamp >= start_date,
                    SystemMetrics.timestamp <= end_date,
                    SystemMetrics.collection_success == True
                )
                
                # 統計查詢
                total_records = query.count()
                
                if total_records == 0:
                    return {
                        "server_id": server_id,
                        "period": {
                            "start": start_date.isoformat(),
                            "end": end_date.isoformat()
                        },
                        "total_records": 0,
                        "message": "此時間範圍內無數據"
                    }
                
                # 聚合統計
                stats = query.with_entities(
                    func.avg(SystemMetrics.cpu_usage_percent).label('avg_cpu'),
                    func.max(SystemMetrics.cpu_usage_percent).label('max_cpu'),
                    func.avg(SystemMetrics.memory_usage_percent).label('avg_memory'),
                    func.max(SystemMetrics.memory_usage_percent).label('max_memory'),
                    func.avg(SystemMetrics.disk_usage_percent).label('avg_disk'),
                    func.max(SystemMetrics.disk_usage_percent).label('max_disk')
                ).first()
                
                return {
                    "server_id": server_id,
                    "period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    },
                    "total_records": total_records,
                    "averages": {
                        "cpu_usage_percent": round(stats.avg_cpu or 0, 2),
                        "memory_usage_percent": round(stats.avg_memory or 0, 2),
                        "disk_usage_percent": round(stats.avg_disk or 0, 2)
                    },
                    "peaks": {
                        "cpu_usage_percent": round(stats.max_cpu or 0, 2),        
                        "memory_usage_percent": round(stats.max_memory or 0, 2),
                        "disk_usage_percent": round(stats.max_disk or 0, 2)
                    }
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"取得歷史數據摘要失敗: {e}")
            return {
                "server_id": server_id,
                "error": str(e)
            }
    
    async def export_historical_data(
        self,
        server_id: int,
        start_date: datetime,
        end_date: datetime,
        format: str = "json"
    ) -> Dict[str, Any]:
        """匯出歷史數據"""
        try:
            db = next(self.db_session_factory())
            try:
                # 查詢數據
                records = db.query(SystemMetrics).filter(
                    SystemMetrics.server_id == server_id,
                    SystemMetrics.timestamp >= start_date,
                    SystemMetrics.timestamp <= end_date,
                    SystemMetrics.collection_success == True
                ).order_by(SystemMetrics.timestamp).all()
                
                if format.lower() == "csv":
                    # CSV 格式
                    csv_data = self._convert_to_csv(records)
                    return {
                        "format": "csv",
                        "data": csv_data,
                        "filename": f"server_{server_id}_metrics_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
                    }
                else:
                    # JSON 格式
                    json_data = [record.to_dict() for record in records]
                    return {
                        "format": "json",
                        "data": json_data,
                        "filename": f"server_{server_id}_metrics_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.json"
                    }
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"匯出歷史數據失敗: {e}")
            return {"error": str(e)}
    
    def _convert_to_csv(self, records: List[SystemMetrics]) -> str:
        """轉換記錄為 CSV 格式"""
        if not records:
            return ""
        
        # CSV 標題
        headers = [
            "timestamp", "cpu_usage_percent", "memory_usage_percent", 
            "disk_usage_percent", "load_average_1m", "memory_total_mb",
            "disk_total_gb", "network_bytes_sent_per_sec", "network_bytes_recv_per_sec"
        ]
        
        csv_lines = [",".join(headers)]
        
        # 數據行
        for record in records:
            row = [
                record.timestamp.isoformat(),
                str(record.cpu_usage_percent or ""),
                str(record.memory_usage_percent or ""),
                str(record.disk_usage_percent or ""),
                str(record.load_average_1m or ""),
                str(record.memory_total_mb or ""),
                str(record.disk_total_gb or ""),
                str(record.network_bytes_sent_per_sec or ""),
                str(record.network_bytes_recv_per_sec or "")
            ]
            csv_lines.append(",".join(row))
        
        return "\n".join(csv_lines)


# 全域實例
time_series_aggregator = TimeSeriesAggregator()
batch_aggregator = BatchDataAggregator()
historical_manager = HistoricalDataManager()


# 便利函數
async def get_server_chart_data(
    server_id: int,
    metric_name: str,
    time_range: TimeRange,
    aggregation: AggregationType = AggregationType.AVERAGE
) -> ChartData:
    """取得伺服器圖表數據的便利函數"""
    return await time_series_aggregator.get_metric_time_series(
        server_id, metric_name, time_range, aggregation
    )


async def get_server_dashboard_data(
    server_id: int,
    time_range: TimeRange = TimeRange.HOUR_1
) -> Dict[str, Any]:
    """取得伺服器儀表板數據的便利函數"""
    return await time_series_aggregator.get_server_dashboard_data(server_id, time_range)


async def get_multiple_servers_dashboard_data(
    server_ids: List[int],
    time_range: TimeRange = TimeRange.HOUR_1
) -> Dict[int, Dict[str, Any]]:
    """取得多台伺服器儀表板數據的便利函數"""
    return await batch_aggregator.generate_dashboard_data_batch(server_ids, time_range)


if __name__ == "__main__":
    # 測試數據聚合器
    
    async def test_time_series_aggregation():
        """測試時序數據聚合"""
        print("📊 測試時序數據聚合...")
        
        try:
            aggregator = TimeSeriesAggregator()
            
            # 測試取得圖表數據
            chart_data = await aggregator.get_metric_time_series(
                server_id=1,
                metric_name="cpu_usage_percent",
                time_range=TimeRange.HOUR_1
            )
            
            print(f"✅ 圖表數據生成完成:")
            print(f"  - 指標: {chart_data.metric_name}")
            print(f"  - 時間範圍: {chart_data.time_range.value}")
            print(f"  - 數據點數量: {len(chart_data.time_series)}")
            print(f"  - 單位: {chart_data.unit}")
            
            if chart_data.summary:
                print(f"  - 當前值: {chart_data.summary.current_value}")
                print(f"  - 平均值: {chart_data.summary.average_value}")
                print(f"  - 趨勢: {chart_data.summary.trend_direction}")
                
        except Exception as e:
            print(f"❌ 時序數據聚合測試失敗: {e}")
    
    async def test_dashboard_data():
        """測試儀表板數據生成"""
        print("\n🎛️ 測試儀表板數據生成...")
        
        try:
            aggregator = TimeSeriesAggregator()
            
            # 測試儀表板數據
            dashboard_data = await aggregator.get_server_dashboard_data(
                server_id=1,
                time_range=TimeRange.HOUR_1
            )
            
            print(f"✅ 儀表板數據生成完成:")
            print(f"  - 伺服器ID: {dashboard_data.get('server_id')}")
            print(f"  - 時間範圍: {dashboard_data.get('time_range')}")
            print(f"  - 圖表數量: {len(dashboard_data.get('charts', {}))}")
            print(f"  - 狀態: {dashboard_data.get('status')}")
            
            current_values = dashboard_data.get('current_values', {})
            if current_values:
                print(f"  - 當前CPU: {current_values.get('cpu_usage_percent')}%")
                print(f"  - 當前記憶體: {current_values.get('memory_usage_percent')}%")
                
        except Exception as e:
            print(f"❌ 儀表板數據測試失敗: {e}")
    
    async def test_batch_processing():
        """測試批量處理"""
        print("\n⚡ 測試批量處理...")
        
        try:
            batch_aggregator_test = BatchDataAggregator()
            
            # 測試批量儀表板數據
            server_ids = [1, 2]  # 假設有多台伺服器
            batch_data = await batch_aggregator_test.generate_dashboard_data_batch(
                server_ids, TimeRange.HOUR_1
            )
            
            print(f"✅ 批量處理完成:")
            print(f"  - 請求伺服器數: {len(server_ids)}")
            print(f"  - 成功處理數: {len(batch_data)}")
            
            for server_id, data in batch_data.items():
                status = data.get('status', 'unknown')
                print(f"  - 伺服器 {server_id}: {status}")
                
        except Exception as e:
            print(f"❌ 批量處理測試失敗: {e}")
    
    async def test_complete():
        """完整測試"""
        print("=" * 50)
        print("🧪 CWatcher 時序數據聚合系統測試")
        print("=" * 50)
        
        await test_time_series_aggregation()
        await test_dashboard_data()
        await test_batch_processing()
        
        print("\n✅ 時序數據聚合系統測試完成")
    
    # 執行測試
    import asyncio
    asyncio.run(test_complete())