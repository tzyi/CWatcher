-- CWatcher PostgreSQL 開發環境初始化腳本

-- 建立擴展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 建立開發用使用者
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'cwatcher') THEN

      CREATE ROLE cwatcher LOGIN PASSWORD 'cwatcher_dev';
   END IF;
END
$do$;

-- 授予權限
GRANT ALL PRIVILEGES ON DATABASE cwatcher_dev TO cwatcher;
ALTER DATABASE cwatcher_dev OWNER TO cwatcher;

-- 設定時區
SET timezone = 'Asia/Taipei';

-- 建立測試資料表
CREATE TABLE IF NOT EXISTS test_logs (
    id SERIAL PRIMARY KEY,
    message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 插入測試資料
INSERT INTO test_logs (message) VALUES 
('CWatcher 開發環境初始化完成'),
('資料庫連接測試成功');

-- 設定權限
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cwatcher;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cwatcher;

COMMENT ON DATABASE cwatcher_dev IS 'CWatcher 開發環境資料庫';