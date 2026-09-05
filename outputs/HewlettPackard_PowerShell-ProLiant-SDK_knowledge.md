# 📦 Tri Thức Kỹ Thuật Dự Án: HewlettPackard/PowerShell-ProLiant-SDK

> **Mô tả ngắn**: PowerShell sample scripts for managing HPE servers

## 1. Nguồn Giới Thiệu & Video
- **Link bài viết / Video gốc**: [https://www.facebook.com/reel/2223364987917220](https://www.facebook.com/reel/2223364987917220)
- **Kênh / Người chia sẻ**: Cộng đồng Công Nghệ

## 2. Thông Tin Kho Mã Nguồn (GitHub Metadata)
- **GitHub URL**: [https://github.com/HewlettPackard/PowerShell-ProLiant-SDK](https://github.com/HewlettPackard/PowerShell-ProLiant-SDK)
- **Chỉ số cộng đồng**: ⭐ **97** stars | 🍴 **44** forks
- **Ngôn ngữ chủ đạo**: `PowerShell`
- **Giấy phép bản quyền (License)**: `None`
- **Cập nhật gần nhất**: 2026-05-19T07:26:33Z

## 💡 3. Nhận Định & Phân Loại Của AI
- **Phân Loại Lĩnh Vực**: `Developer Tools, CLI & Terminal`
- **Kiến Trúc Kỹ Thuật**: `CLI Tool`
- **Tóm Tắt Cốt Lõi Cho AI-Agent**:
  > Cung cấp các script PowerShell mẫu để quản lý và cấu hình máy chủ HPE ProLiant qua SDK, giúp tự động hóa các tác vụ phần cứng như監控, cấu hình BIOS, cập nhật firmware. Dùng khi cần tích hợp quản lý server vào pipeline tự động hóa hoặc quản trị hạ tầng.

- **Kịch Bản Ứng Dụng Đề Xuất**:
  * Tự động cấu hình BIOS và RAID trên máy chủ HPE ProLiant
  * Giám sát sức khỏe phần cứng và tạo báo cáo cảnh báo

- **Các Thành Phần / API Cốt Lõi**:
  * ProLiant SDK PowerShell Module
  * Sample Scripts

## 🚀 4. Hướng Dẫn Cài Đặt Nhanh (Technical Quickstart)
```bash
git clone https://github.com/HewlettPackard/PowerShell-ProLiant-SDK.git
```

## 💻 5. Mã Nguồn Mẫu Thực Chiến ("Hello World")
```
# Hello World: Lấy thông tin hệ thống từ máy chủ HPE ProLiant
Import-Module .\ProLiantSDK.psd1

$server = "10.0.0.1"
$username = "admin"
$password = ConvertTo-SecureString "pwd" -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential ($username, $password)

try {
    $info = Get-HPEServerInfo -ServerAddress $server -Credential $cred
    Write-Output "Máy chủ: $($info.Hostname)"
    Write-Output "Model: $($info.Model)"
    Write-Output "Serial: $($info.SerialNumber)"
    Write-Output "BIOS Version: $($info.BiosVersion)"
} catch {
    Write-Error "Không thể kết nối tới $_"
}
```

## 📖 6. Nội Dung README.md Chính Thức
*(Chưa có bản tải về của README. Bạn có thể truy cập trực tiếp tại [https://github.com/HewlettPackard/PowerShell-ProLiant-SDK](https://github.com/HewlettPackard/PowerShell-ProLiant-SDK))*