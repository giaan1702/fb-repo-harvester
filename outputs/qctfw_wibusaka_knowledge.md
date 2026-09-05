# 📦 Tri Thức Kỹ Thuật Dự Án: qctfw/wibusaka

> **Mô tả ngắn**: A simple website to inform you where to watch anime legally in Indonesia.

## 1. Nguồn Giới Thiệu & Video
- **Link bài viết / Video gốc**: [https://www.facebook.com/reel/324276933867256](https://www.facebook.com/reel/324276933867256)
- **Kênh / Người chia sẻ**: Cộng đồng Công Nghệ

## 2. Thông Tin Kho Mã Nguồn (GitHub Metadata)
- **GitHub URL**: [https://github.com/qctfw/wibusaka](https://github.com/qctfw/wibusaka)
- **Chỉ số cộng đồng**: ⭐ **61** stars | 🍴 **5** forks
- **Ngôn ngữ chủ đạo**: `PHP`
- **Giấy phép bản quyền (License)**: `None`
- **Chủ đề (Topics)**: `anime`, `laravel`, `redis`
- **Cập nhật gần nhất**: 2025-06-10T10:21:39Z

## 💡 3. Nhận Định & Phân Loại Của AI
- **Phân Loại Lĩnh Vực**: `Backend & High-Performance Systems`
- **Kiến Trúc Kỹ Thuật**: `Open-source PHP Module`
- **Tóm Tắt Cốt Lõi Cho AI-Agent**:
  > Dự án qctfw/wibusaka: A simple website to inform you where to watch anime legally in Indonesia.

- **Kịch Bản Ứng Dụng Đề Xuất**:
  * Áp dụng tự động hóa quy trình làm việc.
  * Tích hợp vào hệ thống lập trình cá nhân.

- **Các Thành Phần / API Cốt Lõi**:
  * Core Engine
  * CLI / Entrypoint

## 🚀 4. Hướng Dẫn Cài Đặt Nhanh (Technical Quickstart)
```bash
git clone https://github.com/qctfw/wibusaka && cd wibusaka
```

## 💻 5. Mã Nguồn Mẫu Thực Chiến ("Hello World")
```
# Khởi chạy nhanh dự án wibusaka
import sys
print('Đang nạp module wibusaka...')
```

## 📖 6. Nội Dung README.md Chính Thức
# WibuSaka

A simple app to inform you where to watch anime legally in Indonesia.

WibuSaka uses [Jikan.moe](https://jikan.moe) API to fetch anime datas.

## API References
For API references, refer to our API's [repository](https://github.com/qctfw/wibusaka-api).

## Requirements
- PHP 8.2+
- MySQL 5.7+
- Redis

## Installation and Configuration

1. Copy `.env.example` into `.env` and edit these values

    - Database
    ```env
    DB_CONNECTION=mysql
    DB_HOST=127.0.0.1
    DB_PORT=3306
    DB_DATABASE=YOUR_DATABASE_NAME
    DB_USERNAME=YOUR_DATABASE_USERNAME
    DB_PASSWORD=YOUR_DATABASE_PASSWORD
    ```
    - Redis
    ```env
    REDIS_CLIENT=predis
    REDIS_SCHEME=tcp
    REDIS_PATH=YOUR_REDIS_PATH_IF_SCHEME_IS_UNIX
    REDIS_HOST=127.0.0.1
    REDIS_PASSWORD=YOUR_REDIS_PASSWORD
    REDIS_PORT=6379
    ```

2. Install composer packages
    ```bash
    composer install
    ```

3. Generate Laravel Application Key
    ```bash
    php artisan key:generate
    ```

3. Install npm dependencies.
    ```bash 
    npm install
    ```

4. After the dependencies has been installed, build the Laravel Mix assets
    ```bash
    npm run dev
    ```
    > **Note**
    >
    > Change `dev` into `build` for purging unused styles and scripts.

## Contributing

Contributions are always welcome! Create a pull request **[here](https://github.com/qctfw/wibusaka/pulls)**!

Please make sure to check the existing pull request to avoid duplication.