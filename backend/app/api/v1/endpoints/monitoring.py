"""
CWatcher 監控數據 API 端點

提供各種監控數據收集和查詢的 RESTful API
支援即時數據、歷史數據和警告狀態查詢
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks
from datetime import datetime, timedelta
import logging

from app.core.deps import get_db
from app.schemas.metrics import (
    MonitoringDataResponse, 
    MonitoringSummaryResponse,
    MetricTypeFilter,
    MonitoringThresholdsUpdate
)
from app.services.monitoring_collector import (
    monitoring_service,
    collect_server_monitoring_data,
    test_server_connection_and_monitoring,
    MetricType,
    AlertLevel,
    MonitoringThresholds
)
from app.services.ssh_manager import ssh_manager
from app.models.server import Server
from sqlalchemy.orm import Session

# 設定日誌
logger = logging.getLogger(__name__)

# 建立路由器
router = APIRouter()


@router.get("/servers/{server_id}/monitoring/summary", response_model=MonitoringSummaryResponse)
async def get_server_monitoring_summary(
    server_id: int = Path(..., description="伺服器 ID"),
    db: Session = Depends(get_db)
):
    """
    取得伺服器監控數據摘要
    
    回傳符合 UI 原型需求的監控數據格式：
    - CPU: 使用率、核心數、頻率、負載平均
    - 記憶體: 使用率、總容量、已用、快取
    - 磁碟: 使用率、容量、I/O 速度
    - 網路: 上傳/下載速度、流量、連接數
    """
    try:
        # 查詢伺服器資訊
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail=f"伺服器 {server_id} 不存在")
        
        # 收集監控數據
        server_data = {
            "id": server.id,
            "host": server.host,
            "port": server.port,
            "username": server.username,
            "encrypted_password": server.encrypted_password,
            "encrypted_private_key": server.encrypted_private_key
        }
        
        summary_data = await collect_server_monitoring_data(server_data)
        
        return MonitoringSummaryResponse(
            success=True,
            data=summary_data,
            message="監控數據收集成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得伺服器 {server_id} 監控摘要失敗: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"監控數據收集失敗: {str(e)}"
        )


@router.get("/servers/{server_id}/monitoring/metrics/{metric_type}")
async def get_server_specific_metric(
    server_id: int = Path(..., description="伺服器 ID"),
    metric_type: str = Path(..., description="監控指標類型 (cpu/memory/disk/network)"),
    db: Session = Depends(get_db)
):
    """
    取得伺服器特定類型的詳細監控數據
    """
    try:
        # 驗證指標類型
        try:
            metric_enum = MetricType(metric_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"不支援的監控指標類型: {metric_type}"
            )
        
        # 查詢伺服器資訊
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail=f"伺服器 {server_id} 不存在")
        
        # 解密伺服器憑證
        config = ssh_manager.decrypt_server_credentials({
            "id": server.id,
            "host": server.host,
            "port": server.port,
            "username": server.username,
            "encrypted_password": server.encrypted_password,
            "encrypted_private_key": server.encrypted_private_key
        })
        
        # 收集特定類型的監控數據
        if metric_enum == MetricType.CPU:
            from app.services.monitoring_collector import collect_cpu_monitoring_data
            metric_data = await collect_cpu_monitoring_data(config, server_id)
        elif metric_enum == MetricType.MEMORY:
            from app.services.monitoring_collector import collect_memory_monitoring_data
            metric_data = await collect_memory_monitoring_data(config, server_id)
        elif metric_enum == MetricType.DISK:
            from app.services.monitoring_collector import collect_disk_monitoring_data
            metric_data = await collect_disk_monitoring_data(config, server_id)
        elif metric_enum == MetricType.NETWORK:
            from app.services.monitoring_collector import collect_network_monitoring_data
            metric_data = await collect_network_monitoring_data(config, server_id)
        else:
            raise HTTPException(status_code=400, detail=f"不支援的監控指標: {metric_type}")
        
        return MonitoringDataResponse(
            success=True,
            data=metric_data.to_dict(),
            message=f"{metric_type.upper()} 監控數據收集成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得伺服器 {server_id} {metric_type} 監控數據失敗: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"監控數據收集失敗: {str(e)}"
        )


@router.get("/servers/{server_id}/monitoring/test")
async def test_server_monitoring_connection(
    server_id: int = Path(..., description="伺服器 ID"),
    db: Session = Depends(get_db)
):
    """
    測試伺服器連接並收集基本監控數據
    用於驗證伺服器設定是否正確
    """
    try:
        # 查詢伺服器資訊
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail=f"伺服器 {server_id} 不存在")
        
        # 測試連接和監控
        server_data = {
            "id": server.id,
            "host": server.host,
            "port": server.port,
            "username": server.username,
            "encrypted_password": server.encrypted_password,
            "encrypted_private_key": server.encrypted_private_key
        }
        
        test_result = await test_server_connection_and_monitoring(server_data)
        
        return {
            "success": True,
            "data": test_result,
            "message": "伺服器連接測試完成"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"測試伺服器 {server_id} 連接失敗: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"連接測試失敗: {str(e)}"
        )


@router.get("/servers/{server_id}/monitoring/alerts")
async def get_server_alerts(
    server_id: int = Path(..., description="伺服器 ID"),
    alert_level: Optional[str] = Query(None, description="警告等級過濾 (ok/warning/critical/unknown)"),
    db: Session = Depends(get_db)
):
    """
    取得伺服器當前警告狀態
    """
    try:
        # 查詢伺服器資訊
        server = db.query(Server).filter(Server.id == server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail=f"伺服器 {server_id} 不存在")
        
        # 收集監控數據以獲取警告狀態
        server_data = {
            "id": server.id,
            "host": server.host,
            "port": server.port,
            "username": server.username,
            "encrypted_password": server.encrypted_password,
            "encrypted_private_key": server.encrypted_private_key
        }
        
        config = ssh_manager.decrypt_server_credentials(server_data)
        all_metrics = await monitoring_service.collect_all_metrics(config, server_id)
        
        # 整理警告資訊
        alerts = []
        for metric_type, metric_data in all_metrics.items():
            if metric_data.alert_level != AlertLevel.OK:
                # 如果有警告等級過濾，則進行過濾
                if alert_level and metric_data.alert_level.value != alert_level.lower():
                    continue
                
                alerts.append({
                    "metric_type": metric_type.value,
                    "alert_level": metric_data.alert_level.value,
                    "alert_message": metric_data.alert_message,
                    "timestamp": metric_data.timestamp.isoformat(),
                    "data_summary": {
                        "cpu_usage": metric_data.data.get("usage_percent") if metric_type == MetricType.CPU else None,
                        "memory_usage": metric_data.data.get("usage_percent") if metric_type == MetricType.MEMORY else None,
                        "disk_usage": metric_data.data.get("overall_usage_percent") if metric_type == MetricType.DISK else None,
                        "network_errors": len([k for k, v in metric_data.data.get("interfaces", {}).items() 
                                             if v.get("rx_errors", 0) + v.get("tx_errors", 0) > 0]) if metric_type == MetricType.NETWORK else None
                    }
                })
        
        return {
            "success": True,
            "data": {
                "server_id": server_id,
                "alert_count": len(alerts),
                "alerts": alerts,
                "timestamp": datetime.now().isoformat()
            },
            "message": f"找到 {len(alerts)} 個警告"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得伺服器 {server_id} 警告狀態失敗: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"警告狀態查詢失敗: {str(e)}"
        )


@router.post("/monitoring/thresholds")
async def update_monitoring_thresholds(
    thresholds: MonitoringThresholdsUpdate,
    background_tasks: BackgroundTasks
):
    """
    更新全域監控閾值設定
    """
    try:
        # 建立新的閾值設定
        new_thresholds = MonitoringThresholds(
            cpu_warning=thresholds.cpu_warning,
            cpu_critical=thresholds.cpu_critical,
            memory_warning=thresholds.memory_warning,
            memory_critical=thresholds.memory_critical,
            disk_warning=thresholds.disk_warning,
            disk_critical=thresholds.disk_critical,
            load_warning=thresholds.load_warning,
            load_critical=thresholds.load_critical
        )
        
        # 更新監控服務的閾值
        monitoring_service.update_thresholds(new_thresholds)
        
        return {
            "success": True,
            "data": {
                "cpu_warning": new_thresholds.cpu_warning,
                "cpu_critical": new_thresholds.cpu_critical,
                "memory_warning": new_thresholds.memory_warning,
                "memory_critical": new_thresholds.memory_critical,
                "disk_warning": new_thresholds.disk_warning,
                "disk_critical": new_thresholds.disk_critical,
                "load_warning": new_thresholds.load_warning,
                "load_critical": new_thresholds.load_critical,
                "updated_at": datetime.now().isoformat()
            },
            "message": "監控閾值更新成功"
        }
        
    except Exception as e:
        logger.error(f"更新監控閾值失敗: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"閾值更新失敗: {str(e)}"
        )


@router.get("/monitoring/thresholds")
async def get_monitoring_thresholds():
    """
    取得當前監控閾值設定
    """
    try:
        current_thresholds = monitoring_service.thresholds
        
        return {
            "success": True,
            "data": {
                "cpu_warning": current_thresholds.cpu_warning,
                "cpu_critical": current_thresholds.cpu_critical,
                "memory_warning": current_thresholds.memory_warning,
                "memory_critical": current_thresholds.memory_critical,
                "disk_warning": current_thresholds.disk_warning,
                "disk_critical": current_thresholds.disk_critical,
                "load_warning": current_thresholds.load_warning,
                "load_critical": current_thresholds.load_critical
            },
            "message": "監控閾值查詢成功"
        }
        
    except Exception as e:
        logger.error(f"查詢監控閾值失敗: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"閾值查詢失敗: {str(e)}"
        )


@router.get("/servers/monitoring/batch")
async def get_multiple_servers_monitoring(
    server_ids: str = Query(..., description="伺服器 ID 列表，用逗號分隔"),
    metric_types: Optional[str] = Query(None, description="監控指標類型，用逗號分隔 (cpu,memory,disk,network)"),
    db: Session = Depends(get_db)
):
    """
    批量取得多台伺服器的監控數據
    適用於儀表板顯示多台伺服器狀態
    """
    try:
        # 解析伺服器 ID 列表
        try:
            server_id_list = [int(id.strip()) for id in server_ids.split(",") if id.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="伺服器 ID 格式錯誤")
        
        if len(server_id_list) > 20:  # 限制批量查詢數量
            raise HTTPException(status_code=400, detail="一次最多查詢 20 台伺服器")
        
        # 解析監控指標類型
        requested_metrics = None
        if metric_types:
            try:
                requested_metrics = [MetricType(t.strip().lower()) for t in metric_types.split(",") if t.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="監控指標類型格式錯誤")
        
        # 查詢伺服器資訊
        servers = db.query(Server).filter(Server.id.in_(server_id_list)).all()
        if not servers:
            raise HTTPException(status_code=404, detail="未找到指定的伺服器")
        
        # 並行收集監控數據
        import asyncio
        
        async def collect_server_data(server):
            try:
                config = ssh_manager.decrypt_server_credentials({
                    "id": server.id,
                    "host": server.host,
                    "port": server.port,
                    "username": server.username,
                    "encrypted_password": server.encrypted_password,
                    "encrypted_private_key": server.encrypted_private_key
                })
                
                if requested_metrics:
                    # 收集指定類型的監控數據
                    metrics_data = await monitoring_service.collect_all_metrics(
                        config, server.id, requested_metrics
                    )
                    return {
                        "server_id": server.id,
                        "server_name": server.name,
                        "host": server.host,
                        "status": "success",
                        "metrics": {k.value: v.to_dict() for k, v in metrics_data.items()}
                    }
                else:
                    # 收集摘要數據
                    summary_data = await monitoring_service.collect_summary_metrics(config, server.id)
                    return {
                        "server_id": server.id,
                        "server_name": server.name,
                        "host": server.host,
                        "status": "success",
                        "summary": summary_data
                    }
                    
            except Exception as e:
                logger.warning(f"收集伺服器 {server.id} 監控數據失敗: {e}")
                return {
                    "server_id": server.id,
                    "server_name": server.name,
                    "host": server.host,
                    "status": "failed",
                    "error": str(e)
                }
        
        # 並行執行所有收集任務
        tasks = [collect_server_data(server) for server in servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 處理結果
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
        
        return {
            "success": True,
            "data": {
                "servers": [r for r in results if isinstance(r, dict)],
                "summary": {
                    "total_servers": len(servers),
                    "success_count": success_count,
                    "failed_count": len(servers) - success_count,
                    "collection_time": datetime.now().isoformat()
                }
            },
            "message": f"批量監控數據收集完成，成功 {success_count}/{len(servers)} 台"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量監控數據收集失敗: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"批量監控失敗: {str(e)}"
        )