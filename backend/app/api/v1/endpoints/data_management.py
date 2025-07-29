"""
CWatcher 數據管理 API 端點

提供數據清理、歸檔、聚合統計和儲存監控的 RESTful API
支援自動化清理策略和數據生命週期管理
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging

from app.core.deps import get_db
from app.services.data_cleaner import (
    data_cleaner,
    scheduled_cleaner,
    CleanupLevel,
    CleanupPolicy,
    cleanup_old_monitoring_data,
    get_storage_status,
    get_cleanup_suggestions
)
from app.services.data_aggregator import (
    time_series_aggregator,
    batch_aggregator,
    historical_manager,
    TimeRange,
    AggregationType,
    get_server_chart_data,
    get_server_dashboard_data,
    get_multiple_servers_dashboard_data
)
from app.services.data_processor import (
    data_processor,
    flush_monitoring_data
)
from app.services.task_scheduler import (
    task_scheduler,
    get_scheduler_status
)
from sqlalchemy.orm import Session

# 設定日誌
logger = logging.getLogger(__name__)

# 建立路由器
router = APIRouter()


# Schemas
class CleanupRequest(BaseModel):
    """清理請求"""
    cleanup_level: str = Field(..., description="清理等級 (basic/aggressive/emergency)")
    archive_before_delete: bool = Field(True, description="刪除前是否歸檔")
    retention_days: Optional[int] = Field(None, description="保留天數（覆蓋預設值）")
    server_ids: Optional[List[int]] = Field(None, description="指定伺服器ID（可選）")


class TimeSeriesRequest(BaseModel):
    """時序數據請求"""
    server_id: int = Field(..., description="伺服器ID")
    metric_name: str = Field(..., description="指標名稱")
    time_range: str = Field(..., description="時間範圍 (1h/6h/24h/7d/30d)")
    aggregation: str = Field("avg", description="聚合類型 (avg/max/min/sum/count/p95)")


class BatchChartRequest(BaseModel):
    """批量圖表請求"""
    server_ids: List[int] = Field(..., description="伺服器ID列表")
    metric_names: List[str] = Field(..., description="指標名稱列表")
    time_range: str = Field(..., description="時間範圍")


class HistoricalDataRequest(BaseModel):
    """歷史數據請求"""
    server_id: int = Field(..., description="伺服器ID")
    start_date: datetime = Field(..., description="開始日期")
    end_date: datetime = Field(..., description="結束日期")
    export_format: str = Field("json", description="匯出格式 (json/csv)")


# ===== 數據清理 API =====

@router.get("/storage/status")
async def get_storage_status():
    """
    取得儲存空間狀態
    
    回傳系統磁碟使用情況、資料庫大小和歸檔空間資訊
    """
    try:
        storage_info = await get_storage_status()
        
        return {
            "success": True,
            "data": storage_info.to_dict(),
            "message": "儲存狀態查詢成功"
        }
        
    except Exception as e:
        logger.error(f"取得儲存狀態失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"儲存狀態查詢失敗: {str(e)}"
        )


@router.get("/cleanup/recommendations")
async def get_cleanup_recommendations():
    """
    取得數據清理建議
    
    基於儲存空間使用率和數據量提供智能清理建議
    """
    try:
        recommendations = await get_cleanup_suggestions()
        
        return {
            "success": True,
            "data": recommendations,
            "message": "清理建議生成成功"
        }
        
    except Exception as e:
        logger.error(f"取得清理建議失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"清理建議生成失敗: {str(e)}"
        )


@router.post("/cleanup/execute")
async def execute_data_cleanup(
    request: CleanupRequest,
    background_tasks: BackgroundTasks
):
    """
    執行數據清理
    
    支援不同清理等級和自定義清理策略
    """
    try:
        # 驗證清理等級
        try:
            cleanup_level = CleanupLevel(request.cleanup_level.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支援的清理等級: {request.cleanup_level}"
            )
        
        # 建立自定義策略（如果提供了保留天數）
        custom_policy = None
        if request.retention_days is not None:
            custom_policy = CleanupPolicy(
                name=f"自定義清理（{request.retention_days}天）",
                retention_days=request.retention_days,
                archive_before_delete=request.archive_before_delete,
                server_ids=request.server_ids
            )
        
        # 執行清理（異步背景任務）
        def cleanup_task():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                stats = loop.run_until_complete(
                    data_cleaner.cleanup_old_data(cleanup_level, custom_policy)
                )
                logger.info(f"背景清理完成: {stats.to_dict()}")
            finally:
                loop.close()
        
        background_tasks.add_task(cleanup_task)
        
        return {
            "success": True,
            "message": f"數據清理任務已啟動（{cleanup_level.value}）",
            "data": {
                "cleanup_level": cleanup_level.value,
                "archive_before_delete": request.archive_before_delete,
                "retention_days": request.retention_days,
                "server_ids": request.server_ids,
                "started_at": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"執行數據清理失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"數據清理執行失敗: {str(e)}"
        )


@router.post("/cleanup/archives")
async def cleanup_archive_files(
    days_to_keep: int = Query(90, description="保留歸檔天數"),
    background_tasks: BackgroundTasks
):
    """
    清理舊的歸檔檔案
    """
    try:
        # 驗證參數
        if days_to_keep < 1:
            raise HTTPException(
                status_code=400,
                detail="保留天數必須大於0"
            )
        
        # 執行歸檔清理（異步背景任務）
        def archive_cleanup_task():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                stats = loop.run_until_complete(
                    data_cleaner.cleanup_archive_files(days_to_keep)
                )
                logger.info(f"歸檔清理完成: {stats.to_dict()}")
            finally:
                loop.close()
        
        background_tasks.add_task(archive_cleanup_task)
        
        return {
            "success": True,
            "message": f"歸檔清理任務已啟動（保留 {days_to_keep} 天）",
            "data": {
                "days_to_keep": days_to_keep,
                "started_at": datetime.now().isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"執行歸檔清理失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"歸檔清理執行失敗: {str(e)}"
        )


# ===== 數據聚合 API =====

@router.post("/charts/timeseries")
async def get_time_series_chart(request: TimeSeriesRequest):
    """
    取得時序圖表數據
    
    支援多種時間範圍和聚合類型的圖表數據生成
    """
    try:
        # 驗證時間範圍
        try:
            time_range = TimeRange(request.time_range)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支援的時間範圍: {request.time_range}"
            )
        
        # 驗證聚合類型
        try:
            aggregation = AggregationType(request.aggregation.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支援的聚合類型: {request.aggregation}"
            )
        
        # 取得圖表數據
        chart_data = await get_server_chart_data(
            request.server_id,
            request.metric_name,
            time_range,
            aggregation
        )
        
        return {
            "success": True,
            "data": chart_data.to_dict(),
            "message": "圖表數據生成成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得時序圖表失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"圖表數據生成失敗: {str(e)}"
        )


@router.get("/servers/{server_id}/dashboard")
async def get_server_dashboard(
    server_id: int = Path(..., description="伺服器ID"),
    time_range: str = Query("1h", description="時間範圍 (1h/6h/24h/7d)")
):
    """
    取得伺服器儀表板數據
    
    符合 UI 原型需求的完整儀表板數據格式
    """
    try:
        # 驗證時間範圍
        try:
            time_range_enum = TimeRange(time_range)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支援的時間範圍: {time_range}"
            )
        
        # 取得儀表板數據
        dashboard_data = await get_server_dashboard_data(server_id, time_range_enum)
        
        return {
            "success": True,
            "data": dashboard_data,
            "message": "儀表板數據生成成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得伺服器儀表板失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"儀表板數據生成失敗: {str(e)}"
        )


@router.post("/charts/batch")
async def get_batch_chart_data(request: BatchChartRequest):
    """
    批量取得圖表數據
    
    支援多台伺服器、多個指標的批量圖表數據生成
    """
    try:
        # 驗證時間範圍
        try:
            time_range = TimeRange(request.time_range)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支援的時間範圍: {request.time_range}"
            )
        
        # 限制批量查詢數量
        if len(request.server_ids) > 20:
            raise HTTPException(
                status_code=400,
                detail="一次最多查詢 20 台伺服器"
            )
        
        if len(request.metric_names) > 10:
            raise HTTPException(
                status_code=400,
                detail="一次最多查詢 10 個指標"
            )
        
        # 批量生成圖表數據
        batch_data = await batch_aggregator.generate_server_charts_batch(
            request.server_ids,
            request.metric_names,
            time_range
        )
        
        return {
            "success": True,
            "data": {
                "servers": batch_data,
                "summary": {
                    "server_count": len(request.server_ids),
                    "metric_count": len(request.metric_names),
                    "time_range": time_range.value,
                    "generated_at": datetime.now().isoformat()
                }
            },
            "message": "批量圖表數據生成成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量取得圖表數據失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"批量圖表數據生成失敗: {str(e)}"
        )


@router.get("/servers/dashboard/batch")
async def get_multiple_servers_dashboard(
    server_ids: str = Query(..., description="伺服器ID列表，用逗號分隔"),
    time_range: str = Query("1h", description="時間範圍")
):
    """
    批量取得多台伺服器儀表板數據
    """
    try:
        # 解析伺服器ID列表
        try:
            server_id_list = [int(id.strip()) for id in server_ids.split(",") if id.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="伺服器ID格式錯誤")
        
        if len(server_id_list) > 20:
            raise HTTPException(status_code=400, detail="一次最多查詢 20 台伺服器")
        
        # 驗證時間範圍
        try:
            time_range_enum = TimeRange(time_range)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"不支援的時間範圍: {time_range}"
            )
        
        # 批量取得儀表板數據
        dashboard_data = await get_multiple_servers_dashboard_data(
            server_id_list, 
            time_range_enum
        )
        
        return {
            "success": True,
            "data": {
                "servers": dashboard_data,
                "summary": {
                    "server_count": len(server_id_list),
                    "time_range": time_range,
                    "generated_at": datetime.now().isoformat()
                }
            },
            "message": "批量儀表板數據生成成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量取得儀表板數據失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"批量儀表板數據生成失敗: {str(e)}"
        )


# ===== 歷史數據 API =====

@router.post("/history/summary")
async def get_historical_summary(request: HistoricalDataRequest):
    """
    取得歷史數據摘要
    
    提供指定時間範圍的數據統計摘要
    """
    try:
        # 驗證日期範圍
        if request.start_date >= request.end_date:
            raise HTTPException(
                status_code=400,
                detail="開始日期必須早於結束日期"
            )
        
        # 限制查詢範圍（最多1年）
        if (request.end_date - request.start_date).days > 365:
            raise HTTPException(
                status_code=400,
                detail="查詢範圍不能超過1年"
            )
        
        # 取得歷史摘要
        summary = await historical_manager.get_historical_summary(
            request.server_id,
            request.start_date,
            request.end_date
        )
        
        return {
            "success": True,
            "data": summary,
            "message": "歷史數據摘要生成成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得歷史數據摘要失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"歷史數據摘要生成失敗: {str(e)}"
        )


@router.post("/history/export")
async def export_historical_data(request: HistoricalDataRequest):
    """
    匯出歷史數據
    
    支援 JSON 和 CSV 格式的數據匯出
    """
    try:
        # 驗證匯出格式
        if request.export_format.lower() not in ["json", "csv"]:
            raise HTTPException(
                status_code=400,
                detail="僅支援 json 和 csv 格式"
            )
        
        # 驗證日期範圍
        if request.start_date >= request.end_date:
            raise HTTPException(
                status_code=400,
                detail="開始日期必須早於結束日期"
            )
        
        # 限制匯出範圍（最多30天）
        if (request.end_date - request.start_date).days > 30:
            raise HTTPException(
                status_code=400,
                detail="匯出範圍不能超過30天"
            )
        
        # 匯出歷史數據
        export_result = await historical_manager.export_historical_data(
            request.server_id,
            request.start_date,
            request.end_date,
            request.export_format
        )
        
        return {
            "success": True,
            "data": export_result,
            "message": "歷史數據匯出成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"匯出歷史數據失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"歷史數據匯出失敗: {str(e)}"
        )


# ===== 數據處理狀態 API =====

@router.get("/processing/stats")
async def get_processing_statistics():
    """
    取得數據處理統計
    
    回傳當前數據處理器的統計資訊
    """
    try:
        stats = data_processor.get_processing_stats()
        
        return {
            "success": True,
            "data": stats.__dict__,
            "message": "處理統計查詢成功"
        }
        
    except Exception as e:
        logger.error(f"取得處理統計失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"處理統計查詢失敗: {str(e)}"
        )


@router.post("/processing/flush")
async def flush_data_buffer():
    """
    強制刷新數據緩衝區
    
    立即將緩衝區中的數據寫入資料庫
    """
    try:
        stats = await flush_monitoring_data()
        
        return {
            "success": True,
            "data": stats.__dict__,
            "message": "數據緩衝區刷新成功"
        }
        
    except Exception as e:
        logger.error(f"刷新數據緩衝區失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"數據緩衝區刷新失敗: {str(e)}"
        )


# ===== 任務調度器 API =====

@router.get("/scheduler/status")
async def get_task_scheduler_status():
    """
    取得任務調度器狀態
    """
    try:
        status = get_scheduler_status()
        return {
            "success": True,
            "data": status,
            "message": "調度器狀態查詢成功"
        }
        
    except Exception as e:
        logger.error(f"取得調度器狀態失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"調度器狀態查詢失敗: {str(e)}"
        )


@router.get("/scheduler/tasks")
async def get_scheduled_tasks():
    """
    取得所有排程任務
    """
    try:
        tasks = task_scheduler.get_task_list()
        return {
            "success": True,
            "data": {
                "tasks": tasks,
                "total_count": len(tasks),
                "enabled_count": sum(1 for t in tasks if t["enabled"])
            },
            "message": "任務清單查詢成功"
        }
        
    except Exception as e:
        logger.error(f"取得任務清單失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"任務清單查詢失敗: {str(e)}"
        )


@router.get("/scheduler/tasks/{task_id}/history")
async def get_task_execution_history(
    task_id: str = Path(..., description="任務ID"),
    limit: int = Query(50, description="歷史記錄數量限制", ge=1, le=200)
):
    """
    取得任務執行歷史
    """
    try:
        history = task_scheduler.get_execution_history(task_id, limit)
        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "history": history,
                "total_count": len(history)
            },
            "message": "執行歷史查詢成功"
        }
        
    except Exception as e:
        logger.error(f"取得任務執行歷史失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"執行歷史查詢失敗: {str(e)}"
        )


@router.post("/scheduler/tasks/{task_id}/run")
async def run_task_immediately(
    task_id: str = Path(..., description="任務ID")
):
    """
    立即執行指定任務
    """
    try:
        result = await task_scheduler.run_task_now(task_id)
        return {
            "success": True,
            "data": result.to_dict(),
            "message": f"任務 {task_id} 執行完成"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"執行任務失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"任務執行失敗: {str(e)}"
        )


@router.post("/scheduler/tasks/{task_id}/enable")
async def enable_task(
    task_id: str = Path(..., description="任務ID")
):
    """
    啟用指定任務
    """
    try:
        await task_scheduler.enable_task(task_id)
        return {
            "success": True,
            "message": f"任務 {task_id} 已啟用"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"啟用任務失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"任務啟用失敗: {str(e)}"
        )


@router.post("/scheduler/tasks/{task_id}/disable")
async def disable_task(
    task_id: str = Path(..., description="任務ID")
):
    """
    停用指定任務
    """
    try:
        await task_scheduler.disable_task(task_id)
        return {
            "success": True,
            "message": f"任務 {task_id} 已停用"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"停用任務失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"任務停用失敗: {str(e)}"
        )


# ===== 系統健康檢查 API =====

@router.get("/health")
async def system_health_check():
    """
    系統健康檢查
    
    檢查各個數據處理組件的健康狀態
    """
    try:
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "components": {
                "data_processor": "healthy",
                "data_cleaner": "healthy", 
                "time_series_aggregator": "healthy",
                "historical_manager": "healthy",
                "task_scheduler": "healthy"
            },
            "metrics": {}
        }
        
        # 檢查儲存狀態
        try:
            storage_info = await get_storage_status()
            health_status["metrics"]["storage_usage"] = storage_info.usage_percentage
            
            if storage_info.usage_percentage > 95:
                health_status["components"]["storage"] = "critical"
            elif storage_info.usage_percentage > 85:
                health_status["components"]["storage"] = "warning"
            else:
                health_status["components"]["storage"] = "healthy"
                
        except Exception as e:
            health_status["components"]["storage"] = "error"
            health_status["errors"] = health_status.get("errors", [])
            health_status["errors"].append(f"Storage check failed: {e}")
        
        # 檢查數據處理統計
        try:
            processing_stats = data_processor.get_processing_stats()
            health_status["metrics"]["processing_errors"] = len(processing_stats.errors)
            
            if len(processing_stats.errors) > 10:
                health_status["components"]["data_processor"] = "warning"
                
        except Exception as e:
            health_status["components"]["data_processor"] = "error"
            health_status["errors"] = health_status.get("errors", [])
            health_status["errors"].append(f"Processing stats check failed: {e}")
        
        # 檢查任務調度器狀態
        try:
            scheduler_status = get_scheduler_status()
            health_status["metrics"]["scheduler_running"] = scheduler_status["is_running"]
            health_status["metrics"]["active_tasks"] = scheduler_status["enabled_tasks"]
            
            if not scheduler_status["is_running"]:
                health_status["components"]["task_scheduler"] = "warning"
                
        except Exception as e:
            health_status["components"]["task_scheduler"] = "error"
            health_status["errors"] = health_status.get("errors", [])
            health_status["errors"].append(f"Scheduler check failed: {e}")
        
        # 計算整體健康狀態
        component_statuses = list(health_status["components"].values())
        if "critical" in component_statuses:
            overall_status = "critical"
        elif "error" in component_statuses:
            overall_status = "error"
        elif "warning" in component_statuses:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        health_status["overall_status"] = overall_status
        
        return {
            "success": True,
            "data": health_status,
            "message": f"系統健康狀態: {overall_status}"
        }
        
    except Exception as e:
        logger.error(f"系統健康檢查失敗: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"健康檢查失敗: {str(e)}"
        )