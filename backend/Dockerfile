# CWatcher Backend Dockerfile
# 多階段建構，優化映像大小

# 第一階段：建構階段
FROM python:3.11-slim as builder

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 複製需求檔案
COPY requirements.txt .

# 建立虛擬環境並安裝 Python 依賴
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 第二階段：執行階段
FROM python:3.11-slim

# 設定環境變數
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/opt/venv/bin:$PATH"

# 安裝執行時依賴
RUN apt-get update && apt-get install -y \
    libpq5 \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# 建立非 root 使用者
RUN useradd --create-home --shell /bin/bash cwatcher

# 設定工作目錄
WORKDIR /app

# 從建構階段複製虛擬環境
COPY --from=builder /opt/venv /opt/venv

# 複製應用程式程式碼
COPY --chown=cwatcher:cwatcher . .

# 建立日誌目錄
RUN mkdir -p /app/logs && chown cwatcher:cwatcher /app/logs

# 切換到非 root 使用者
USER cwatcher

# 暴露埠
EXPOSE 8000

# 健康檢查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 啟動命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]