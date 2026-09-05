# Dockerfile cho FB Repo Harvester & Co-Ideation Service trên Render
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

# Cài đặt trình duyệt Playwright Chromium kèm các thư viện đồ họa headless
RUN playwright install --with-deps chromium

# Cài đặt nlm CLI (Google NotebookLM)
RUN pip install --no-cache-dir notebooklm-mcp-cli || true

# Copy toàn bộ mã nguồn vào container
COPY . .

# Mở cổng dịch vụ
EXPOSE 7860

# Khởi chạy máy chủ Web UI kết hợp Background Scheduler
CMD ["python", "-m", "fb_harvester.server"]
