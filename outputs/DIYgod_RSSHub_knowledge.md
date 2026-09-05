# 📦 Tri Thức Kỹ Thuật Dự Án: DIYgod/RSSHub

> **Mô tả ngắn**: 🧡 Everything is RSSible

## 1. Nguồn Giới Thiệu & Video
- **Link bài viết / Video gốc**: [https://www.facebook.com/reel/1550984832863943](https://www.facebook.com/reel/1550984832863943)
- **Kênh / Người chia sẻ**: Cộng đồng Công Nghệ

## 2. Thông Tin Kho Mã Nguồn (GitHub Metadata)
- **GitHub URL**: [https://github.com/DIYgod/RSSHub](https://github.com/DIYgod/RSSHub)
- **Chỉ số cộng đồng**: ⭐ **46,037** stars | 🍴 **10,195** forks
- **Ngôn ngữ chủ đạo**: `TypeScript`
- **Giấy phép bản quyền (License)**: `AGPL-3.0`
- **Chủ đề (Topics)**: `bilibili`, `douban`, `dribbble`, `instagram`, `lofter`, `pixiv`, `rss`, `rsshub`, `spotify`, `telegram`, `tiktok`, `twitter`, `v2ex`, `wechat`, `weibo`, `ximalaya`, `youtube`, `zhihu`
- **Cập nhật gần nhất**: 2026-09-05T14:51:33Z

## 💡 3. Nhận Định & Phân Loại Của AI
- **Phân Loại Lĩnh Vực**: `Backend & High-Performance Systems`
- **Kiến Trúc Kỹ Thuật**: `Node.js/Express-based web service with modular route handlers and async processing`
- **Tóm Tắt Cốt Lõi Cho AI-Agent**:
  > RSSHub là một dịch vụ tự động tạo RSS feed từ nhiều trang web và API khác nhau, cho phép người dùng theo dõi nội dung mà không cần API chính thức. Dùng khi muốn tổng hợp tin tức, bài viết, video từ các nền tảng như YouTube, Twitter, Bilibili… vào một reader RSS.

- **Kịch Bản Ứng Dụng Đề Xuất**:
  * Tạo feed cá nhân cho các trang web không cung cấp RSS (ví dụ: Twitter, Bilibili) và đọc qua Inoreader, Feedbin.
  * Tích hợp vào quy trình tự động hoá (IFTTT, Zapier, GitHub Actions) để kích hoạt công việc khi có bài viết mới.

- **Các Thành Phần / API Cốt Lõi**:
  * lib/rss.js – hàm tạo RSS feed chuẩn
  * routes/ – bộ xử lý route cho từng nền tảng (bilibili, twitter, youtube, …)
  * lib/cache.js – hệ thống caching nội dung
  * lib/utils.js – các tiện ích chung (request, parse)

## 🚀 4. Hướng Dẫn Cài Đặt Nhanh (Technical Quickstart)
```bash
git clone https://github.com/DIYgod/RSSHub.git && cd RSSHub && npm install && npm start
```

## 💻 5. Mã Nguồn Mẫu Thực Chiến ("Hello World")
```typescript
import express from 'express';
import { createRSSHub } from 'rsshub';

const app = express();
const rsshub = createRSSHub();

// Mount RSSHub middleware
app.use(rsshub.middleware);

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 RSSHub is running on http://localhost:${PORT}`);
});
```

## 📖 6. Nội Dung README.md Chính Thức
<p align="center">
<img src="https://docs.rsshub.app/img/logo.png" alt="RSSHub" width="100">
</p>
<h1 align="center">RSSHub</h1>

> 🧡 Everything is RSSible

[![](https://img.shields.io/badge/dynamic/json?url=https://rsshub-analytics.diygod.workers.dev/&query=requests&color=F38020&label=requests&logo=cloudflare&style=flat-square&suffix=/month)](https://rsshub.app)
[![docker publish](https://img.shields.io/docker/pulls/diygod/rsshub?label=docker%20pulls&logo=docker&style=flat-square)](https://hub.docker.com/r/diygod/rsshub)
[![npm publish](https://img.shields.io/npm/dt/rsshub?label=npm%20downloads&logo=npm&style=flat-square)](https://www.npmjs.com/package/rsshub)
[![test](https://img.shields.io/github/actions/workflow/status/DIYgod/RSSHub/test.yml?branch=master&label=test&logo=github&style=flat-square)](https://github.com/DIYgod/RSSHub/actions/workflows/test.yml?query=event%3Apush+branch%3Amaster)
[![Test coverage](https://img.shields.io/codecov/c/github/DIYgod/RSSHub.svg?style=flat-square&logo=codecov)](https://app.codecov.io/gh/DIYgod/RSSHub/branch/master)
[![Visitors](https://hitscounter.dev/api/hit?url=https%3A%2F%2Fgithub.com%2FDIYgod%2FRSSHub&label=RSS+lovers&icon=rss-fill&color=%23ff752e)](https://github.com/DIYgod/RSSHub)

[![Telegram group](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.swo.moe%2Fstats%2Ftelegram%2Frsshub&query=count&color=2CA5E0&label=Telegram%20Group&logo=telegram&cacheSeconds=3600&style=flat-square)](https://t.me/rsshub) [![Telegram channel](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.swo.moe%2Fstats%2Ftelegram%2FawesomeRSSHub&query=count&color=2CA5E0&label=Telegram%20Channel&logo=telegram&cacheSeconds=3600&style=flat-square)](https://t.me/awesomeRSSHub) [![X (Twitter)](https://img.shields.io/badge/any_text-Follow-blue?color=2CA5E0&label=Twitter&logo=X&cacheSeconds=3600&style=flat-square)](https://x.com/intent/follow?screen_name=_RSSHub)

<table>
<tr>
<td align="center" width="100%">
<a href="https://folo.is/"><img src="https://github.com/user-attachments/assets/68c66528-8c79-4a8a-8e43-ade7d936ab80" alt="Folo" width="419"></a>
<br>
RSSHub pairs especially well with <a href="https://folo.is/">Folo</a>, an AI RSS reader for feed discovery and modern reading workflows. The project is also open source on <a href="https://github.com/RSSNext/Folo">GitHub</a>.
</td>
</tr>
</table>

## Introduction

RSSHub is the world's largest RSS network, consisting of over 5,000 global instances.

RSSHub delivers millions of contents aggregated from all kinds of sources, our vibrant open source community is ensuring the deliver of RSSHub's new routes, new features and bug fixes.

[Documentation](https://docs.rsshub.app) | [Folo](https://folo.is/) | [Telegram Group](https://t.me/rsshub) | [Telegram Channel](https://t.me/awesomeRSSHub) | [X (Twitter)](https://x.com/intent/follow?screen_name=_RSSHub)

## Related Projects

- [Folo](https://folo.is/) | An AI RSS reader that works especially well with RSSHub. Source code: [GitHub](https://github.com/RSSNext/Folo).
- [RSSHub Radar](https://github.com/DIYgod/RSSHub-Radar) | A browser extension that can help you quickly discover and subscribe to the RSS and RSSHub of current websites.
- [RSSBud](https://github.com/Cay-Zhang/RSSBud) | RSSHub Radar for iOS platform, designed specifically for mobile ecosystem optimization.
- [RSSAid](https://github.com/LeetaoGoooo/RSSAid) | RSSHub Radar for Android platform built with Flutter.
- [DocSearch](https://github.com/Fatpandac/DocSearch) | Link RSSHub DocSearch into Raycast.
- [Awesome RSSHub Routes](https://github.com/JackyST0/awesome-rsshub-routes) | Curated list of RSS feeds and RSSHub routes.

## Contribute

We welcome all pull requests. Suggestions and feedback are also welcomed [here](https://github.com/DIYgod/RSSHub/issues).

Refer to [Quick Start](https://docs.rsshub.app/joinus/)

## Deployment

Refer to [Deployment](https://docs.rsshub.app/deploy/)

## Special Thanks

<div align="center">

[![](https://opencollective.com/RSSHub/contributors.svg?width=890)](https://github.com/DIYgod/RSSHub/graphs/contributors)

Logo designer [sheldonrrr](https://dribbble.com/sheldonrrr)

[![](https://raw.githubusercontent.com/DIYgod/sponsors/main/sponsors.simple.svg)](https://github.com/DIYgod/sponsors)

<a href="https://www.cloudflare.com" target="_blank"><img height="50px" src="https://i.imgur.com/7Ph27Fq.png"></a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href="https://www.netlify.com" target="_blank"><img height="40px" src="https://i.imgur.com/cU01915.png"></a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href="https://1password.com" target="_blank"><img height="40px" src="https://i.imgur.com/a2XjflO.png"></a>

</div>

## Author

**RSSHub** © [DIYgod](https://github.com/DIYgod), Released under the [AGPL-3.0](./LICENSE) License.<br>
Authored and maintained by DIYgod with help from contributors ([list](https://github.com/DIYgod/RSSHub/contributors)).

> Blog [@DIYgod](https://diygod.cc) · GitHub [@DIYgod](https://github.com/DIYgod) · X (Twitter) [@DIYgod](https://x.com/DIYgod) · Telegram Channel [@awesomeDIYgod](https://t.me/awesomeDIYgod)