# 📦 Tri Thức Kỹ Thuật Dự Án: daimajia/AndroidViewAnimations

> **Mô tả ngắn**: Cute view animation collection.

## 1. Nguồn Giới Thiệu & Video
- **Link bài viết / Video gốc**: [https://www.facebook.com/reel/1012093204026724](https://www.facebook.com/reel/1012093204026724)
- **Kênh / Người chia sẻ**: Cộng đồng Công Nghệ

## 2. Thông Tin Kho Mã Nguồn (GitHub Metadata)
- **GitHub URL**: [https://github.com/daimajia/AndroidViewAnimations](https://github.com/daimajia/AndroidViewAnimations)
- **Chỉ số cộng đồng**: ⭐ **12,442** stars | 🍴 **2,412** forks
- **Ngôn ngữ chủ đạo**: `Java`
- **Giấy phép bản quyền (License)**: `MIT`
- **Chủ đề (Topics)**: `android`, `animation`, `easing-functions`
- **Cập nhật gần nhất**: 2026-09-05T13:11:42Z

## 💡 3. Nhận Định & Phân Loại Của AI
- **Phân Loại Lĩnh Vực**: `Fullstack, Web & UI Frameworks`
- **Kiến Trúc Kỹ Thuật**: `Android Library (AAR)`
- **Tóm Tắt Cốt Lõi Cho AI-Agent**:
  > Thư viện AndroidViewAnimations cung cấp bộ sưu tập các hiệu ứng animation đẹp và dễ sử dụng cho các view Android, bao gồm flash, pulse, shake, wobble... Dùng để tăng tính tương tác và sinh động cho giao diện mà không cần viết animation phức tạp từ đầu.

- **Kịch Bản Ứng Dụng Đề Xuất**:
  * Thêm hiệu ứng khi nút được nhấn hoặc khi hiển thị dialog
  * Tạo hiệu ứng loading hoặc khi item trong RecyclerView xuất hiện

- **Các Thành Phần / API Cốt Lõi**:
  * YoYo
  * Techniques

## 🚀 4. Hướng Dẫn Cài Đặt Nhanh (Technical Quickstart)
```bash
git clone https://github.com/daimajia/AndroidViewAnimations.git
```

## 💻 5. Mã Nguồn Mẫu Thực Chiến ("Hello World")
```
import android.os.Bundle;
import android.support.v7.app.AppCompatActivity;
import android.view.View;
import com.daimajia.androidanimations.library.Techniques;
import com.daimajia.androidanimations.library.YoYo;

public class MainActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        View myView = findViewById(R.id.my_view);
        // Áp dụng hiệu ứng Tada lặp 3 lần, mỗi lần 600ms
        YoYo.with(Techniques.Tada)
            .duration(600)
            .repeat(3)
            .playOn(myView);
    }
}
```

## 📖 6. Nội Dung README.md Chính Thức
# Android View Animations [![Build Status](https://travis-ci.org/daimajia/AndroidViewAnimations.svg)](https://travis-ci.org/daimajia/AndroidViewAnimations)

One day, I saw [an iOS library](https://github.com/ArtFeel/AFViewShaker), which is a view shaker, it's very beautiful. I think Android also need one, and should be better.

So, I started to collect animation effects... and in two days, this project born.

# Demo

![](http://ww3.sinaimg.cn/mw690/610dc034gw1ej75mi2w77g20c30jb4qr.gif)

[Download Demo](https://github.com/daimajia/AndroidViewAnimations/releases/download/v1.1.2/AndroidViewAnimations-1.1.2.apk)
# Usage

> Since Version 2.0, NineOldAndroids has been removed. Thanks Jake Wharton.

For making animations more real, I created another project named [Android Easing Functions](https://github.com/daimajia/AnimationEasingFunctions) which is an implementations of [easing functions](http://easings.net/) on Android. So, we need to dependent that project.

## Step 1

#### Gradle
```groovy
dependencies {
    implementation 'com.daimajia.androidanimations:library:2.4@aar'
}
```
#### Maven

```xml
<dependency>
    <groupId>com.daimajia.androidanimation</groupId>
    <artifactId>library</artifactId>
    <version>2.4</version>
</dependency>
```

## Step 2

Just like play Yo-yo.

```java
YoYo.with(Techniques.Tada)
    .duration(700)
    .repeat(5)
    .playOn(findViewById(R.id.edit_area));
```

### Effects
#### Attension
`Flash`, `Pulse`, `RubberBand`, `Shake`, `Swing`, `Wobble`, `Bounce`, `Tada`, `StandUp`, `Wave`

#### Special
`Hinge`, `RollIn`, `RollOut`,`Landing`,`TakingOff`,`DropOut`

#### Bounce
`BounceIn`, `BounceInDown`, `BounceInLeft`, `BounceInRight`, `BounceInUp`

#### Fade
`FadeIn`, `FadeInUp`, `FadeInDown`, `FadeInLeft`, `FadeInRight`

`FadeOut`, `FadeOutDown`, `FadeOutLeft`, `FadeOutRight`, `FadeOutUp`

#### Flip
`FlipInX`, `FlipOutX`, `FlipOutY`

#### Rotate
`RotateIn`, `RotateInDownLeft`, `RotateInDownRight`, `RotateInUpLeft`, `RotateInUpRight`

`RotateOut`, `RotateOutDownLeft`, `RotateOutDownRight`, `RotateOutUpLeft`, `RotateOutUpRight`

#### Slide
`SlideInLeft`, `SlideInRight`, `SlideInUp`, `SlideInDown`

`SlideOutLeft`, `SlideOutRight`, `SlideOutUp`, `SlideOutDown`

#### Zoom
`ZoomIn`, `ZoomInDown`, `ZoomInLeft`, `ZoomInRight`, `ZoomInUp`

`ZoomOut`, `ZoomOutDown`, `ZoomOutLeft`, `ZoomOutRight`, `ZoomOutUp`

Welcome contribute your amazing animation effect. :-D

# Thanks

- [AFViewShaker](https://github.com/ArtFeel/AFViewShaker)
- [Animate.css](https://github.com/daneden/animate.css)

# Why YoYo?

YoYo is a [toy](https://en.wikipedia.org/wiki/Yo-yo), with a lot of [Techniques](./library/src/main/java/com/daimajia/androidanimations/library/Techniques.java).

# About me

(2013)
A student in mainland China.

Welcome to [offer me an internship](mailto:daimajia@gmail.com).
If you have any new idea about this project, feel free to [contact me](mailto:daimajia@gmail.com).

(2019)
Five years later, now I become an investment associate in China.

Welcome to send your business plan to [me](mailto:daimajia@gmail.com). Maybe I would have a better understanding on your startup project than others. Trust me.