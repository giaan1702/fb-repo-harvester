# 📦 Tri Thức Kỹ Thuật Dự Án: maitrungduc1410/viblo-microfrontend

> **Mô tả ngắn**: Không có mô tả.

## 1. Nguồn Giới Thiệu & Video
- **Link bài viết / Video gốc**: [https://www.facebook.com/reel/713362178109860](https://www.facebook.com/reel/713362178109860)
- **Kênh / Người chia sẻ**: Cộng đồng Công Nghệ

## 2. Thông Tin Kho Mã Nguồn (GitHub Metadata)
- **GitHub URL**: [https://github.com/maitrungduc1410/viblo-microfrontend](https://github.com/maitrungduc1410/viblo-microfrontend)
- **Chỉ số cộng đồng**: ⭐ **21** stars | 🍴 **18** forks
- **Ngôn ngữ chủ đạo**: `TypeScript`
- **Giấy phép bản quyền (License)**: `None`
- **Cập nhật gần nhất**: 2026-05-02T16:14:03Z

## 💡 3. Nhận Định & Phân Loại Của AI
- **Phân Loại Lĩnh Vực**: `Fullstack, Web & UI Frameworks`
- **Kiến Trúc Kỹ Thuật**: `Microfrontend (Module Federation) App Shell`
- **Tóm Tắt Cốt Lõi Cho AI-Agent**:
  > Repository minh hoá cách xây dựng ứng dụng microfrontend kết hợp Vue, Angular và React trong một app shell. Giải quyết bài toán tách biệt các đội phát triển và cho phép tích hợp nhiều framework khác nhau mà không ảnh hưởng đến trải nghiệm người dùng.

- **Kịch Bản Ứng Dụng Đề Xuất**:
  * Xây dựng ứng dụng web lớn với nhiều đội làm việc độc lập trên các công nghệ frontend khác nhau
  * Tích hợp Gradually các thành phần mới (Vue/Angular/React) vào hệ thống legacy mà không cần viết lại toàn bộ

- **Các Thành Phần / API Cốt Lõi**:
  * App Shell
  * Vue Microfrontend
  * Angular Microfrontend
  * React Microfrontend

## 🚀 4. Hướng Dẫn Cài Đặt Nhanh (Technical Quickstart)
```bash
npm install
```

## 💻 5. Mã Nguồn Mẫu Thực Chiến ("Hello World")
```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';

const App = () => <h1>Hello from React Microfrontend</h1>;

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);
root.render(<App />);
```

## 📖 6. Nội Dung README.md Chính Thức
# Viblo Microfrontend DEMO

To start, first run `npm install` for **each** project

Then for each project, open new terminal and run:
```
npm start
```

Finally, access the app shell at `http://localhost:4200` to see result

Note: microfrontends run in the following addresses:
- Vue: localhost:3000
- Angular: localhost:3001
- React: localhost:3002