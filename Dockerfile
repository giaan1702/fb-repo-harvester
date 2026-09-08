# Dockerfile cho Autonomous Knowledge Vault v3.0
FROM python:3.11-slim

# Thiết lập môi trường
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    HOST=0.0.0.0

WORKDIR /app

# Cài đặt các gói hệ thống cần thiết cho Playwright và Git
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt dependencies Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Mở cổng dịch vụ
EXPOSE 7860

# Khởi chạy máy chủ Web UI Autonomous Knowledge Vault tương thích cổng động của Render
CMD ["sh", "-c", "python -m uvicorn vault_engine.server:app --host 0.0.0.0 --port ${PORT:-7860}"]

