"""
CWatcher WebSocket 性能優化工具

提供數據壓縮、批量傳輸、連接管理和性能監控功能
優化 WebSocket 通訊效率和資源使用
"""

import asyncio
import json
import gzip
import zlib
import logging
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid

# 設定日誌
logger = logging.getLogger(__name__)


class CompressionType(Enum):
    """壓縮類型"""
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    JSON_MINIFY = "json_minify"


class MessagePriority(Enum):
    """訊息優先級"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class CompressionStats:
    """壓縮統計"""
    original_size: int
    compressed_size: int
    compression_ratio: float
    compression_time: float
    compression_type: CompressionType
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_size": self.original_size,
            "compressed_size": self.compressed_size,
            "compression_ratio": self.compression_ratio,
            "compression_time": self.compression_time,
            "compression_type": self.compression_type.value
        }


@dataclass
class QueuedMessage:
    """佇列中的訊息"""
    message_id: str
    content: str
    priority: MessagePriority
    target_connections: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    max_retries: int = 3
    
    def should_retry(self) -> bool:
        """檢查是否應該重試"""
        return self.retry_count < self.max_retries
    
    def increment_retry(self):
        """增加重試次數"""
        self.retry_count += 1


class MessageCompressor:
    """訊息壓縮器"""
    
    def __init__(self, default_compression: CompressionType = CompressionType.JSON_MINIFY):
        self.default_compression = default_compression
        self.compression_threshold = 1024  # 超過 1KB 才壓縮
        self.stats = {
            "total_messages": 0,
            "compressed_messages": 0,
            "total_original_size": 0,
            "total_compressed_size": 0,
            "compression_time": 0.0
        }
    
    def compress_message(
        self, 
        message: str, 
        compression_type: Optional[CompressionType] = None
    ) -> Tuple[str, CompressionStats]:
        """壓縮訊息"""
        start_time = time.time()
        
        if compression_type is None:
            compression_type = self.default_compression
        
        original_size = len(message.encode('utf-8'))
        
        # 決定是否需要壓縮
        if original_size < self.compression_threshold and compression_type != CompressionType.JSON_MINIFY:
            compression_type = CompressionType.NONE
        
        try:
            if compression_type == CompressionType.GZIP:
                compressed_data = gzip.compress(message.encode('utf-8'))
                compressed_message = f"GZIP:{len(compressed_data)}:{compressed_data.hex()}"
                
            elif compression_type == CompressionType.ZLIB:
                compressed_data = zlib.compress(message.encode('utf-8'))
                compressed_message = f"ZLIB:{len(compressed_data)}:{compressed_data.hex()}"
                
            elif compression_type == CompressionType.JSON_MINIFY:
                # JSON 最小化（移除不必要的空白）
                try:
                    json_obj = json.loads(message)
                    compressed_message = json.dumps(json_obj, separators=(',', ':'), ensure_ascii=False)
                except json.JSONDecodeError:
                    compressed_message = message
                    
            else:  # CompressionType.NONE
                compressed_message = message
            
            compressed_size = len(compressed_message.encode('utf-8'))
            compression_ratio = compressed_size / original_size if original_size > 0 else 1.0
            compression_time = time.time() - start_time
            
            # 更新統計
            self.stats["total_messages"] += 1
            self.stats["total_original_size"] += original_size
            self.stats["total_compressed_size"] += compressed_size
            self.stats["compression_time"] += compression_time
            
            if compression_type != CompressionType.NONE:
                self.stats["compressed_messages"] += 1
            
            stats = CompressionStats(
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=compression_ratio,
                compression_time=compression_time,
                compression_type=compression_type
            )
            
            return compressed_message, stats
            
        except Exception as e:
            logger.error(f"訊息壓縮失敗: {e}")
            # 壓縮失敗時返回原始訊息
            stats = CompressionStats(
                original_size=original_size,
                compressed_size=original_size,
                compression_ratio=1.0,
                compression_time=time.time() - start_time,
                compression_type=CompressionType.NONE
            )
            return message, stats
    
    def decompress_message(self, compressed_message: str) -> str:
        """解壓縮訊息"""
        try:
            if compressed_message.startswith("GZIP:"):
                parts = compressed_message.split(":", 2)
                if len(parts) == 3:
                    size = int(parts[1])
                    hex_data = parts[2]
                    compressed_data = bytes.fromhex(hex_data)
                    return gzip.decompress(compressed_data).decode('utf-8')
                    
            elif compressed_message.startswith("ZLIB:"):
                parts = compressed_message.split(":", 2)
                if len(parts) == 3:
                    size = int(parts[1])
                    hex_data = parts[2]
                    compressed_data = bytes.fromhex(hex_data)
                    return zlib.decompress(compressed_data).decode('utf-8')
            
            # 沒有壓縮標記，返回原始訊息
            return compressed_message
            
        except Exception as e:
            logger.error(f"訊息解壓縮失敗: {e}")
            return compressed_message
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """取得壓縮統計"""
        total_saved = self.stats["total_original_size"] - self.stats["total_compressed_size"]
        overall_ratio = (
            self.stats["total_compressed_size"] / self.stats["total_original_size"]
            if self.stats["total_original_size"] > 0 else 1.0
        )
        
        return {
            **self.stats,
            "bytes_saved": total_saved,
            "overall_compression_ratio": overall_ratio,
            "compression_percentage": (1 - overall_ratio) * 100,
            "average_compression_time": (
                self.stats["compression_time"] / self.stats["total_messages"]
                if self.stats["total_messages"] > 0 else 0
            )
        }


class MessageBatcher:
    """訊息批量處理器"""
    
    def __init__(self, batch_size: int = 10, batch_timeout: float = 1.0):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.message_queue: List[QueuedMessage] = []
        self.processing_task: Optional[asyncio.Task] = None
        self.is_running = False
        self.stats = {
            "batches_processed": 0,
            "messages_processed": 0,
            "failed_messages": 0,
            "average_batch_size": 0.0,
            "processing_time": 0.0
        }
    
    async def start(self):
        """啟動批量處理"""
        if self.is_running:
            return
        
        self.is_running = True
        self.processing_task = asyncio.create_task(self._batch_processing_loop())
        logger.info("訊息批量處理器已啟動")
    
    async def stop(self):
        """停止批量處理"""
        self.is_running = False
        
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        # 處理剩餘訊息
        if self.message_queue:
            await self._process_batch(self.message_queue)
            self.message_queue.clear()
        
        logger.info("訊息批量處理器已停止")
    
    def queue_message(self, message: QueuedMessage):
        """將訊息加入佇列"""
        self.message_queue.append(message)
        
        # 按優先級排序
        self.message_queue.sort(key=lambda m: m.priority.value, reverse=True)
    
    async def _batch_processing_loop(self):
        """批量處理循環"""
        while self.is_running:
            try:
                if len(self.message_queue) >= self.batch_size:
                    # 達到批量大小，立即處理
                    batch = self.message_queue[:self.batch_size]
                    self.message_queue = self.message_queue[self.batch_size:]
                    await self._process_batch(batch)
                    
                elif self.message_queue:
                    # 等待超時後處理
                    await asyncio.sleep(self.batch_timeout)
                    if self.message_queue:
                        batch = self.message_queue.copy()
                        self.message_queue.clear()
                        await self._process_batch(batch)
                else:
                    # 佇列為空，等待一段時間
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"批量處理循環錯誤: {e}")
                await asyncio.sleep(1)
    
    async def _process_batch(self, batch: List[QueuedMessage]):
        """處理一批訊息"""
        if not batch:
            return
        
        start_time = time.time()
        
        try:
            # 按目標連接分組
            connection_groups: Dict[str, List[QueuedMessage]] = {}
            
            for message in batch:
                for connection_id in message.target_connections:
                    if connection_id not in connection_groups:
                        connection_groups[connection_id] = []
                    connection_groups[connection_id].append(message)
            
            # 並行處理各個連接
            tasks = [
                self._send_to_connection(connection_id, messages)
                for connection_id, messages in connection_groups.items()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 統計結果
            successful_messages = 0
            failed_messages = 0
            
            for result in results:
                if isinstance(result, Exception):
                    failed_messages += 1
                else:
                    successful_messages += result
            
            # 更新統計
            self.stats["batches_processed"] += 1
            self.stats["messages_processed"] += successful_messages
            self.stats["failed_messages"] += failed_messages
            self.stats["processing_time"] += time.time() - start_time
            
            if self.stats["batches_processed"] > 0:
                self.stats["average_batch_size"] = (
                    self.stats["messages_processed"] / self.stats["batches_processed"]
                )
            
            logger.debug(f"批量處理完成: {len(batch)} 訊息, {successful_messages} 成功, {failed_messages} 失敗")
            
        except Exception as e:
            logger.error(f"批量處理失敗: {e}")
    
    async def _send_to_connection(self, connection_id: str, messages: List[QueuedMessage]) -> int:
        """發送訊息到特定連接"""
        successful_count = 0
        
        try:
            # 這裡應該實際發送到 WebSocket 連接
            # 暫時模擬發送成功
            await asyncio.sleep(0.01)  # 模擬網路延遲
            successful_count = len(messages)
            
        except Exception as e:
            logger.error(f"發送到連接 {connection_id} 失敗: {e}")
            
            # 處理重試
            for message in messages:
                if message.should_retry():
                    message.increment_retry()
                    self.queue_message(message)
        
        return successful_count
    
    def get_batch_stats(self) -> Dict[str, Any]:
        """取得批量處理統計"""
        return {
            **self.stats,
            "queue_size": len(self.message_queue),
            "is_running": self.is_running,
            "batch_size": self.batch_size,
            "batch_timeout": self.batch_timeout
        }


class ConnectionLimiter:
    """連接數量限制器"""
    
    def __init__(self, max_connections: int = 1000, max_connections_per_ip: int = 10):
        self.max_connections = max_connections
        self.max_connections_per_ip = max_connections_per_ip
        self.connections: Dict[str, str] = {}  # connection_id -> client_ip
        self.ip_connections: Dict[str, Set[str]] = {}  # client_ip -> connection_ids
        self.connection_lock = asyncio.Lock()
    
    async def can_accept_connection(self, client_ip: str) -> bool:
        """檢查是否可以接受新連接"""
        async with self.connection_lock:
            # 檢查總連接數
            if len(self.connections) >= self.max_connections:
                return False
            
            # 檢查單個 IP 的連接數
            ip_connection_count = len(self.ip_connections.get(client_ip, set()))
            if ip_connection_count >= self.max_connections_per_ip:
                return False
            
            return True
    
    async def add_connection(self, connection_id: str, client_ip: str):
        """添加連接"""
        async with self.connection_lock:
            self.connections[connection_id] = client_ip
            
            if client_ip not in self.ip_connections:
                self.ip_connections[client_ip] = set()
            self.ip_connections[client_ip].add(connection_id)
    
    async def remove_connection(self, connection_id: str):
        """移除連接"""
        async with self.connection_lock:
            if connection_id not in self.connections:
                return
            
            client_ip = self.connections[connection_id]
            del self.connections[connection_id]
            
            if client_ip in self.ip_connections:
                self.ip_connections[client_ip].discard(connection_id)
                
                # 如果該 IP 沒有其他連接，移除記錄
                if not self.ip_connections[client_ip]:
                    del self.ip_connections[client_ip]
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """取得連接統計"""
        return {
            "total_connections": len(self.connections),
            "max_connections": self.max_connections,
            "max_connections_per_ip": self.max_connections_per_ip,
            "unique_ips": len(self.ip_connections),
            "ip_distribution": {
                ip: len(connections) 
                for ip, connections in self.ip_connections.items()
            }
        }


class WebSocketOptimizer:
    """WebSocket 優化管理器"""
    
    def __init__(self):
        self.compressor = MessageCompressor()
        self.batcher = MessageBatcher()
        self.connection_limiter = ConnectionLimiter()
        self.is_running = False
    
    async def start(self):
        """啟動優化器"""
        if self.is_running:
            return
        
        self.is_running = True
        await self.batcher.start()
        logger.info("WebSocket 優化器已啟動")
    
    async def stop(self):
        """停止優化器"""
        if not self.is_running:
            return
        
        self.is_running = False
        await self.batcher.stop()
        logger.info("WebSocket 優化器已停止")
    
    async def optimize_and_send_message(
        self,
        message: str,
        target_connections: List[str],
        priority: MessagePriority = MessagePriority.NORMAL,
        compression_type: Optional[CompressionType] = None
    ) -> bool:
        """優化並發送訊息"""
        try:
            # 壓縮訊息
            compressed_message, compression_stats = self.compressor.compress_message(
                message, compression_type
            )
            
            # 建立佇列訊息
            queued_message = QueuedMessage(
                message_id=str(uuid.uuid4()),
                content=compressed_message,
                priority=priority,
                target_connections=target_connections
            )
            
            # 加入批量處理佇列
            self.batcher.queue_message(queued_message)
            
            return True
            
        except Exception as e:
            logger.error(f"優化並發送訊息失敗: {e}")
            return False
    
    async def can_accept_connection(self, client_ip: str) -> bool:
        """檢查是否可以接受新連接"""
        return await self.connection_limiter.can_accept_connection(client_ip)
    
    async def register_connection(self, connection_id: str, client_ip: str):
        """註冊新連接"""
        await self.connection_limiter.add_connection(connection_id, client_ip)
    
    async def unregister_connection(self, connection_id: str):
        """註銷連接"""
        await self.connection_limiter.remove_connection(connection_id)
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """取得優化統計"""
        return {
            "compression_stats": self.compressor.get_compression_stats(),
            "batch_stats": self.batcher.get_batch_stats(),
            "connection_stats": self.connection_limiter.get_connection_stats(),
            "is_running": self.is_running
        }


# 全域優化器實例
websocket_optimizer = WebSocketOptimizer()


# 便利函數
async def start_websocket_optimizer():
    """啟動 WebSocket 優化器"""
    await websocket_optimizer.start()


async def stop_websocket_optimizer():
    """停止 WebSocket 優化器"""
    await websocket_optimizer.stop()


async def send_optimized_message(
    message: str,
    target_connections: List[str],
    priority: MessagePriority = MessagePriority.NORMAL,
    compression_type: Optional[CompressionType] = None
) -> bool:
    """發送優化過的訊息"""
    return await websocket_optimizer.optimize_and_send_message(
        message, target_connections, priority, compression_type
    )


if __name__ == "__main__":
    # 測試優化工具
    
    async def test_compression():
        """測試壓縮功能"""
        print("📦 測試訊息壓縮...")
        
        compressor = MessageCompressor()
        
        # 測試數據
        test_message = json.dumps({
            "type": "monitoring_update",
            "data": {
                "server_id": 1,
                "cpu": {"usage": 45.2, "cores": 4},
                "memory": {"usage": 68.5, "total": 8192},
                "disk": {"usage": 76.3, "total": 500000},
                "network": {"download": 2.4, "upload": 0.8}
            }
        }, indent=2)
        
        print(f"原始大小: {len(test_message)} bytes")
        
        # 測試不同壓縮方式
        for compression_type in CompressionType:
            compressed, stats = compressor.compress_message(test_message, compression_type)
            print(f"{compression_type.value}: {stats.compressed_size} bytes "
                  f"({stats.compression_ratio:.2%})")
        
        print(f"✅ 壓縮統計: {compressor.get_compression_stats()}")
    
    async def test_batcher():
        """測試批量處理"""
        print("\n📨 測試批量處理...")
        
        batcher = MessageBatcher(batch_size=3, batch_timeout=0.5)
        await batcher.start()
        
        # 添加測試訊息
        for i in range(5):
            message = QueuedMessage(
                message_id=f"msg_{i}",
                content=f"Test message {i}",
                priority=MessagePriority.NORMAL,
                target_connections=[f"conn_{i % 2}"]
            )
            batcher.queue_message(message)
        
        # 等待處理
        await asyncio.sleep(2)
        
        print(f"✅ 批量統計: {batcher.get_batch_stats()}")
        
        await batcher.stop()
    
    async def test_optimizer():
        """測試完整優化器"""
        print("\n🚀 測試 WebSocket 優化器...")
        
        optimizer = WebSocketOptimizer()
        await optimizer.start()
        
        # 測試連接限制
        can_connect = await optimizer.can_accept_connection("127.0.0.1")
        print(f"可以建立連接: {can_connect}")
        
        # 註冊連接
        await optimizer.register_connection("conn_1", "127.0.0.1")
        
        # 發送優化訊息
        test_data = {"type": "test", "data": {"value": 123}}
        success = await optimizer.send_optimized_message(
            json.dumps(test_data),
            ["conn_1"],
            MessagePriority.HIGH
        )
        print(f"訊息發送成功: {success}")
        
        # 等待處理
        await asyncio.sleep(1)
        
        # 取得統計
        stats = optimizer.get_optimization_stats()
        print(f"✅ 優化統計: {json.dumps(stats, indent=2, ensure_ascii=False)}")
        
        await optimizer.stop()
    
    async def test_complete():
        """完整測試"""
        print("=" * 50)
        print("🧪 WebSocket 性能優化工具測試")
        print("=" * 50)
        
        await test_compression()
        await test_batcher()
        await test_optimizer()
        
        print("\n✅ 性能優化工具測試完成")
    
    # 執行測試
    import asyncio
    asyncio.run(test_complete())