#!/usr/bin/env python3
"""
CWatcher 後端整合測試腳本

驗證後端 API 端點和服務的基本功能
"""

import asyncio
import aiohttp
import json
import sys
from typing import Dict, Any, List


class BackendIntegrationTester:
    """後端整合測試器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results: Dict[str, bool] = {}
    
    async def run_all_tests(self) -> bool:
        """執行所有測試"""
        print("🚀 開始後端整合測試...")
        print("=" * 50)
        
        async with aiohttp.ClientSession() as session:
            # 基礎健康檢查
            await self.test_health_check(session)
            
            # 測試伺服器管理 API
            await self.test_server_management(session)
            
            # 測試監控 API
            await self.test_monitoring_api(session)
            
            # 測試 SSH API
            await self.test_ssh_api(session)
            
            # 測試 WebSocket API
            await self.test_websocket_api(session)
            
            # 測試數據管理 API
            await self.test_data_management_api(session)
        
        # 生成報告
        self.generate_report()
        
        # 返回整體測試結果
        passed_count = sum(self.test_results.values())
        total_count = len(self.test_results)
        return passed_count / total_count >= 0.8 if total_count > 0 else False
    
    async def test_health_check(self, session: aiohttp.ClientSession):
        """測試健康檢查端點"""
        print("📊 測試健康檢查...")
        
        # 測試根端點
        try:
            async with session.get(f"{self.base_url}/") as response:
                data = await response.json()
                self.test_results['root_endpoint'] = response.status == 200 and 'CWatcher' in data.get('message', '')
                print(f"✅ 根端點: {data}")
        except Exception as e:
            print(f"❌ 根端點失敗: {e}")
            self.test_results['root_endpoint'] = False
        
        # 測試健康檢查端點
        try:
            async with session.get(f"{self.base_url}/health") as response:
                data = await response.json()
                self.test_results['health_check'] = response.status == 200 and data.get('status') in ['healthy', 'running']
                print(f"✅ 健康檢查: {data}")
        except Exception as e:
            print(f"❌ 健康檢查失敗: {e}")
            self.test_results['health_check'] = False
        
        # 測試 API ping
        try:
            async with session.get(f"{self.base_url}/api/v1/ping") as response:
                data = await response.json()
                self.test_results['api_ping'] = response.status == 200 and data.get('message') == 'pong'
                print(f"✅ API Ping: {data}")
        except Exception as e:
            print(f"❌ API Ping 失敗: {e}")
            self.test_results['api_ping'] = False
    
    async def test_server_management(self, session: aiohttp.ClientSession):
        """測試伺服器管理 API"""
        print("\n🖥️ 測試伺服器管理 API...")
        
        # 測試取得伺服器列表
        try:
            async with session.get(f"{self.base_url}/api/v1/servers") as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_results['get_servers'] = True
                    print(f"✅ 取得伺服器列表: {len(data.get('data', []))} 台伺服器")
                else:
                    print(f"❌ 取得伺服器列表失敗: HTTP {response.status}")
                    self.test_results['get_servers'] = False
        except Exception as e:
            print(f"❌ 取得伺服器列表異常: {e}")
            self.test_results['get_servers'] = False
        
        # 測試伺服器統計
        try:
            async with session.get(f"{self.base_url}/api/v1/servers/stats/overview") as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_results['server_stats'] = True
                    print(f"✅ 伺服器統計: {data}")
                else:
                    print(f"❌ 伺服器統計失敗: HTTP {response.status}")
                    self.test_results['server_stats'] = False
        except Exception as e:
            print(f"❌ 伺服器統計異常: {e}")
            self.test_results['server_stats'] = False
    
    async def test_monitoring_api(self, session: aiohttp.ClientSession):
        """測試監控 API"""
        print("\n📈 測試監控 API...")
        
        # 測試監控批量端點
        try:
            async with session.get(f"{self.base_url}/api/v1/servers/monitoring/batch") as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_results['monitoring_batch'] = True
                    print(f"✅ 監控批量端點: {data}")
                else:
                    print(f"❌ 監控批量端點失敗: HTTP {response.status}")
                    self.test_results['monitoring_batch'] = False
        except Exception as e:
            print(f"❌ 監控批量端點異常: {e}")
            self.test_results['monitoring_batch'] = False
        
        # 測試監控閾值設定
        try:
            async with session.get(f"{self.base_url}/api/v1/monitoring/thresholds") as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_results['monitoring_thresholds'] = True
                    print(f"✅ 監控閾值設定: {data}")
                else:
                    print(f"❌ 監控閾值設定失敗: HTTP {response.status}")
                    self.test_results['monitoring_thresholds'] = False
        except Exception as e:
            print(f"❌ 監控閾值設定異常: {e}")
            self.test_results['monitoring_thresholds'] = False
    
    async def test_ssh_api(self, session: aiohttp.ClientSession):
        """測試 SSH API"""
        print("\n🔐 測試 SSH API...")
        
        # 測試 SSH 管理器統計
        try:
            async with session.get(f"{self.base_url}/api/v1/ssh/manager/statistics") as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_results['ssh_stats'] = True
                    print(f"✅ SSH 管理器統計: {data}")
                else:
                    print(f"❌ SSH 管理器統計失敗: HTTP {response.status}")
                    self.test_results['ssh_stats'] = False
        except Exception as e:
            print(f"❌ SSH 管理器統計異常: {e}")
            self.test_results['ssh_stats'] = False
        
        # 測試 SSH 連接測試 (使用假數據)
        try:
            test_data = {
                "host": "127.0.0.1",
                "port": 22,
                "username": "test",
                "password": "test"
            }
            async with session.post(
                f"{self.base_url}/api/v1/ssh/test-connection",
                json=test_data
            ) as response:
                if response.status in [200, 400, 422]:  # 預期可能失敗
                    data = await response.json()
                    self.test_results['ssh_test'] = True
                    print(f"✅ SSH 連接測試 (預期失敗): {data}")
                else:
                    print(f"❌ SSH 連接測試異常: HTTP {response.status}")
                    self.test_results['ssh_test'] = False
        except Exception as e:
            print(f"❌ SSH 連接測試異常: {e}")
            self.test_results['ssh_test'] = False
    
    async def test_websocket_api(self, session: aiohttp.ClientSession):
        """測試 WebSocket API"""
        print("\n🔌 測試 WebSocket API...")
        
        # 測試 WebSocket 健康檢查
        try:
            async with session.get(f"{self.base_url}/api/v1/websocket/health") as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_results['websocket_health'] = True
                    print(f"✅ WebSocket 健康檢查: {data}")
                else:
                    print(f"❌ WebSocket 健康檢查失敗: HTTP {response.status}")
                    self.test_results['websocket_health'] = False
        except Exception as e:
            print(f"❌ WebSocket 健康檢查異常: {e}")
            self.test_results['websocket_health'] = False
        
        # 測試 WebSocket 連接統計
        try:
            async with session.get(f"{self.base_url}/api/v1/websocket/connections/stats") as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_results['websocket_stats'] = True
                    print(f"✅ WebSocket 連接統計: {data}")
                else:
                    print(f"❌ WebSocket 連接統計失敗: HTTP {response.status}")
                    self.test_results['websocket_stats'] = False
        except Exception as e:
            print(f"❌ WebSocket 連接統計異常: {e}")
            self.test_results['websocket_stats'] = False
    
    async def test_data_management_api(self, session: aiohttp.ClientSession):
        """測試數據管理 API"""
        print("\n📊 測試數據管理 API...")
        
        # 測試存儲狀態
        try:
            async with session.get(f"{self.base_url}/api/v1/data/storage/status") as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_results['storage_status'] = True
                    print(f"✅ 存儲狀態: {data}")
                else:
                    print(f"❌ 存儲狀態失敗: HTTP {response.status}")
                    self.test_results['storage_status'] = False
        except Exception as e:
            print(f"❌ 存儲狀態異常: {e}")
            self.test_results['storage_status'] = False
        
        # 測試數據健康檢查
        try:
            async with session.get(f"{self.base_url}/api/v1/data/health") as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_results['data_health'] = True
                    print(f"✅ 數據健康檢查: {data}")
                else:
                    print(f"❌ 數據健康檢查失敗: HTTP {response.status}")
                    self.test_results['data_health'] = False
        except Exception as e:
            print(f"❌ 數據健康檢查異常: {e}")
            self.test_results['data_health'] = False
    
    def generate_report(self):
        """生成測試報告"""
        print("\n" + "=" * 50)
        print("📋 後端整合測試報告")
        print("=" * 50)
        
        passed_count = 0
        total_count = len(self.test_results)
        
        for test_name, passed in self.test_results.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {test_name}")
            if passed:
                passed_count += 1
        
        pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0
        
        print(f"\n📊 總體結果: {passed_count}/{total_count} 通過 ({pass_rate:.1f}%)")
        
        if pass_rate >= 80:
            print("🎉 後端整合測試通過！")
        elif pass_rate >= 60:
            print("⚠️ 後端整合測試部分通過")
        else:
            print("❌ 後端整合測試失敗")
        
        print("=" * 50)


async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='CWatcher 後端整合測試')
    parser.add_argument('--url', default='http://localhost:8000', help='後端 API URL')
    
    args = parser.parse_args()
    
    tester = BackendIntegrationTester(args.url)
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())