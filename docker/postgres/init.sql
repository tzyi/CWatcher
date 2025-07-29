-- CWatcher PostgreSQL 初始化腳本
-- 建立生產環境所需的資料庫和使用者

-- 建立擴展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 建立 cwatcher 使用者 (如果不存在)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'cwatcher') THEN

      CREATE ROLE cwatcher LOGIN PASSWORD 'cwatcher_password';
   END IF;
END
$do$;

-- 授予權限
GRANT ALL PRIVILEGES ON DATABASE cwatcher TO cwatcher;
ALTER DATABASE cwatcher OWNER TO cwatcher;

-- 設定時區
SET timezone = 'Asia/Taipei';

-- 建立審計日誌表 (稍後會透過 Alembic 建立其他表)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    operation VARCHAR(10) NOT NULL, -- INSERT, UPDATE, DELETE
    old_data JSONB,
    new_data JSONB,
    changed_by VARCHAR(255),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 建立索引
CREATE INDEX IF NOT EXISTS idx_audit_logs_table_name ON audit_logs(table_name);
CREATE INDEX IF NOT EXISTS idx_audit_logs_changed_at ON audit_logs(changed_at);

-- 設定權限
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cwatcher;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cwatcher;

COMMENT ON DATABASE cwatcher IS 'CWatcher Linux 系統監控平台資料庫';