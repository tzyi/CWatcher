#!/usr/bin/env python3
"""
創建 CWatcher MySQL 資料庫腳本

在運行 Alembic 遷移之前，需要先創建資料庫
"""

import pymysql
import sys
from core.config import settings


def create_database():
    """創建 CWatcher 資料庫"""
    try:
        # 解析資料庫連接資訊
        database_url = settings.DATABASE_URL
        
        # 提取連接參數
        # mysql+aiomysql://cabie:Aa-12345@localhost:3306/cwatcher
        parts = database_url.replace("mysql+aiomysql://", "").split("/")
        auth_host = parts[0]
        db_name = parts[1]
        
        auth, host_port = auth_host.split("@")
        username, password = auth.split(":")
        host, port = host_port.split(":")
        
        print(f"連接到 MySQL 伺服器: {username}@{host}:{port}")
        
        # 連接到 MySQL（不指定資料庫）
        connection = pymysql.connect(
            host=host,
            port=int(port),
            user=username,
            password=password,
            charset='utf8mb4'
        )
        
        try:
            with connection.cursor() as cursor:
                # 創建資料庫
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                print(f"✅ 資料庫 '{db_name}' 創建成功")
                
                # 創建測試資料庫
                test_db_name = f"{db_name}_test"
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{test_db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                print(f"✅ 測試資料庫 '{test_db_name}' 創建成功")
                
            connection.commit()
            
        finally:
            connection.close()
            
        print("🎉 資料庫創建完成！")
        return True
        
    except Exception as e:
        print(f"❌ 創建資料庫失敗: {e}")
        return False


if __name__ == "__main__":
    success = create_database()
    sys.exit(0 if success else 1)