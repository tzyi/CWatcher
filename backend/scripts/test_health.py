#!/usr/bin/env python3
"""
測試 CWatcher 健康檢查端點
"""

import asyncio
from httpx import AsyncClient
from app.main import app


async def test_health():
    """測試健康檢查端點"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        print("Health check status:", response.status_code)
        print("Health check response:", response.json())
        
        # 測試根端點
        root_response = await client.get("/")
        print("\nRoot endpoint status:", root_response.status_code)
        print("Root endpoint response:", root_response.json())


if __name__ == "__main__":
    asyncio.run(test_health())