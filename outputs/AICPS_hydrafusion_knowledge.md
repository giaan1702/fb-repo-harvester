# 📦 Tri Thức Kỹ Thuật Dự Án: AICPS/hydrafusion

> **Mô tả ngắn**: Model code for our paper titled "HydraFusion: Context-Aware Selective Sensor Fusion for Robust and Efficient Autonomous Vehicle Perception"

## 1. Nguồn Giới Thiệu & Video
- **Link bài viết / Video gốc**: [https://www.facebook.com/reel/4101443290149537](https://www.facebook.com/reel/4101443290149537)
- **Kênh / Người chia sẻ**: Cộng đồng Công Nghệ

## 2. Thông Tin Kho Mã Nguồn (GitHub Metadata)
- **GitHub URL**: [https://github.com/AICPS/hydrafusion](https://github.com/AICPS/hydrafusion)
- **Chỉ số cộng đồng**: ⭐ **30** stars | 🍴 **8** forks
- **Ngôn ngữ chủ đạo**: `Python`
- **Giấy phép bản quyền (License)**: `MIT`
- **Cập nhật gần nhất**: 2026-05-02T03:14:44Z

## 💡 3. Nhận Định & Phân Loại Của AI
- **Phân Loại Lĩnh Vực**: `Computer Vision & Generative Media`
- **Kiến Trúc Kỹ Thuật**: `Modular Neural Network with Stem-Branch-Gate-Fusion pipeline`
- **Tóm Tắt Cốt Lõi Cho AI-Agent**:
  > HydraFusion là mô hình fusión cảm biến bối cảnh cho xe tự hành, kết hợp dữ liệu từ camera, radar và lidar để cải thiện độ chính xác và hiệu suất nhận diện đối tượng trong các điều kiện môi trường phức tạp. Mô hình sử dụng kiến trúc Stem-Branch-Gate với backbone ResNet-18 và Faster R-CNN để chọn lọc và fusión các đặc trưng từ các cảm biến hoạt động.

- **Kịch Bản Ứng Dụng Đề Xuất**:
  * Nhận diện và theo dõi đối tượng cho xe tự hành trong thời tiết schlecht (mưa, sương, đêm)
  * Tích hợp vào hệ thống percep­tion của xe tự động để giảm số lượng cảm biến cần thiết mà vẫn duy trì độ tin cậy cao

- **Các Thành Phần / API Cốt Lõi**:
  * HydraFusion
  * Stem
  * Branch
  * Gate
  * Fusion

## 🚀 4. Hướng Dẫn Cài Đặt Nhanh (Technical Quickstart)
```bash
pip install torch==1.9 torchvision
```

## 💻 5. Mã Nguồn Mẫu Thực Chiến ("Hello World")
```python
import torch
from hydranet import HydraFusion
from stem import Stem
from branch import Branch
from gate import Gate
from fusion import Fusion

# Dummy inputs: 2 camera images, 1 radar, 1 lidar (B=1, C=3, H=224, W=224)
cam1 = torch.randn(1, 3, 224, 224)
cam2 = torch.randn(1, 3, 224, 224)
radar = torch.randn(1, 3, 224, 224)
lidar = torch.randn(1, 3, 224, 224)

# Initialize model
model = HydraFusion()

# Forward pass
outputs = model([cam1, cam2, radar, lidar])
print('Detected boxes:', outputs['boxes'])
print('Scores:', outputs['scores'])
print('Labels:', outputs['labels'])
```

## 📖 6. Nội Dung README.md Chính Thức
# HydraFusion
Code for our paper titled _**"HydraFusion: Context-Aware Selective Sensor Fusion for Robust and Efficient Autonomous Vehicle Perception,"**_ accepted to be published in **ICCPS 2022.**

This repository contains the algorithmic implementation of our HydraFusion model. 
Our model is intended to be used with the RADIATE dataset available here: https://pro.hw.ac.uk/radiate/

## Model

**hydranet.py** -- contains the class HydraFusion, which defines our top-level model specification.

**stem.py** -- defines the stem modules in HydraFusion

**branch.py** -- defines the branches implemented in our model.

**gate.py** -- contains the gating module implementations.

**fusion.py** -- contains the definition of the fusion block along with the algorithms to fuse the bounding boxes output by each active branch.


The stems and branches are built using a split architecture implementation of Faster R-CNN with a ResNet-18 backbone.
HydraFusion can be used with any image-based multi-modal dataset. In our evaluations we used two cameras, one radar sensor, and one lidar sensor as inputs to the model.

## Requirements
PyTorch 1.9