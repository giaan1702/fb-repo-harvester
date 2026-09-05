# 📦 Tri Thức Kỹ Thuật Dự Án: RfidResearchGroup/ChameleonUltra

> **Mô tả ngắn**: The new generation chameleon based on NRF52840 makes the performance of card emulation more stable. And gave the chameleon the ability to read, write, and decrypt cards.

## 1. Nguồn Giới Thiệu & Video
- **Link bài viết / Video gốc**: [https://www.facebook.com/reel/1034903429549840](https://www.facebook.com/reel/1034903429549840)
- **Kênh / Người chia sẻ**: Cộng đồng Công Nghệ

## 2. Thông Tin Kho Mã Nguồn (GitHub Metadata)
- **GitHub URL**: [https://github.com/RfidResearchGroup/ChameleonUltra](https://github.com/RfidResearchGroup/ChameleonUltra)
- **Chỉ số cộng đồng**: ⭐ **2,977** stars | 🍴 **440** forks
- **Ngôn ngữ chủ đạo**: `C`
- **Giấy phép bản quyền (License)**: `GPL-3.0`
- **Chủ đề (Topics)**: `125khz`, `chameleon`, `chameleonultra`, `detection`, `iso14443a`, `mifare`, `nfc`, `ntag`, `rfid`, `simulate`, `ultralight`
- **Cập nhật gần nhất**: 2026-09-05T11:56:00Z

## 💡 3. Nhận Định & Phân Loại Của AI
- **Phân Loại Lĩnh Vực**: `Cybersecurity & Reverse Engineering`
- **Kiến Trúc Kỹ Thuật**: `Embedded Firmware with CLI Interface`
- **Tóm Tắt Cốt Lõi Cho AI-Agent**:
  > ChameleonUltra là firmware phần cứng dựa trên NRF52840 cho phép mô phỏng, đọc, ghi và giải mã thẻ RFID/NFC. Nó cung cấp nền tảng ổn định để kiểm thử và phát triển các ứng dụng thẻ thông minh, đặc biệt hữu ích trong nghiên cứu bảo mật và reverse engineering.

- **Kịch Bản Ứng Dụng Đề Xuất**:
  * Kiểm tra và đánh giá độ bảo mật của hệ thống kiểm soát truy cập RFID/NFC
  * Phát triển và mô phỏng các loại thẻ thông minh (Mifare, Ultralight, ISO14443A) để thử nghiệm ứng dụng

- **Các Thành Phần / API Cốt Lõi**:
  * NRF52840 MCU
  * USB CDC Interface
  * RFID Frontend (125kHz/13.56MHz)

## 🚀 4. Hướng Dẫn Cài Đặt Nhanh (Technical Quickstart)
```bash
git clone https://github.com/RfidResearchGroup/ChameleonUltra.git && cd ChameleonUltra && make
```

## 💻 5. Mã Nguồn Mẫu Thực Chiến ("Hello World")
```
#include <nrfx.h>
#include <nrfx_uart.h>

static const nrfx_uart_t uart = NRFX_UART_INSTANCE(0);

void uart_handler(nrfx_uart_event_t const * p_event, void* p_context)
{
    if (p_event->type == NRFX_UART_EVT_TX_DONE)
        ; // nothing
}

int main(void)
{
    nrfx_uart_config_t config = NRFX_UART_DEFAULT_CONFIG;
    config.pseltxd = 6;   // TX pin
    config.pselrxd = 8;   // RX pin
    config.baudrate = NRF_UART_BAUDRATE_115200;
    nrfx_uart_init(&uart, &config, uart_handler);
    nrfx_uart_tx(&uart, (uint8_t*)"Hello ChameleonUltra\n", 24);
    while (true) {
        __WFE();
    }
}
```

## 📖 6. Nội Dung README.md Chính Thức
![logo](docs/images/ultra-logo.png)

![ultra picture](docs/images/ultra-overview.png)

# ChameleonUltra Authorized Distributors

Lyon, France: [Lab401](https://lab401.com/)

Santa Ana, United States: [Hackerwarehouse](https://hackerwarehouse.com/)

Hastings, UK: [KSEC](https://labs.ksec.co.uk/product/proxgrind-chameleon-ultra/)

Montreal, Canada: [TechSecurityTools](https://techsecuritytools.com/product/chameleon-ultra/)

Shenzhen, China: [Sneaktechnology](https://sneaktechnology.com)

Guangdong, China: [MTools Tec](https://shop.mtoolstec.com/)

Lazada One, Singapore: [Aliexpress by RRG](https://proxgrind.aliexpress.com/store/1101312023)

# What is it and how to use ?

Read the [available documentation](https://github.com/RfidResearchGroup/ChameleonUltra/wiki).

# Compatible applications

* [ChameleonUltraGUI](https://github.com/GameTec-live/ChameleonUltraGUI)
* [MTools BLE](https://github.com/RfidResearchGroup/ChameleonUltra/wiki/mtoolsble)
* [Mifare Chameleon Tool (iOS only, Beta)](https://apps.apple.com/it/app/mifare-chameleon-tool/id6761231484)
* [Chameleon Ultra (Sailfish OS only)](https://sailfishos-chum.github.io/apps/harbour-chameleon-ultra)

# Videos

*Beware some of the instructions might have changed since recording, check the current documentation when in doubt!*

* [Downloading and compiling the official CLI](https://www.youtube.com/watch?v=VGpAeitNXH0)
* [Downloading ChameleonUltraGUI](https://www.youtube.com/watch?v=rHH7iqbX3nY)
* [ChameleonUltraGUI features overview](https://www.youtube.com/watch?v=YqE8wyVSse4)
* [Using ChameleonUltraGUI and the Chameleon Ultra](https://www.youtube.com/watch?v=9jtKNJ5-kVY)
* [MTools BLE - How to clone a card with ChameleonUltra](https://youtu.be/IvH-xtdW1Wk?si=4exqgAAeJ-kxU3aN)

# Official channels

Where do you find the community?
* [RFID Hacking community discord server](https://t.ly/d4_C)
  * Software/chameleon-dev for firmware and clients development discussions
  * Devices/chameleon-ultra for usage discussions
* [GameTec_live discord server](https://discord.gg/DJ2A4wxncK)

###### Searching for the docs repo? Find it [here](https://github.com/RfidResearchGroup/ChameleonUltraDocs)