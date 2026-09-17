视频播放改为独立页 + 引导全屏（修订版）

## 改动文件

### 1. pages/index/index.js
- `openInlineVideo(event)`: 改为 `wx.navigateTo` 跳转到 `/pages/video/video`，参数 url/password 用 encodeURIComponent 编码。不再 setData videoPlayer。
- 删除 `closeInlineVideo()` 方法。
- 删除 `data.videoPlayer: { visible: false, url: '' }` 初始状态。

### 2. pages/index/index.wxml
- 删除文件末尾的 `<block wx:if="{{videoPlayer.visible}}"> ... <web-view> ... </block>`（约 215-226 行）。
- 视频卡片入口（缩略图 bindtap=openInlineVideo、密码复制按钮）保持不变。

### 3. pages/index/index.wxss
- 删除 `.video-player-toolbar` 和 `.video-player-return` 两条规则。

### 4. pages/video/video.js（重写）
```
Page({
  data: { videoUrl: '', loadError: false, hinted: false },
  onLoad(options) {
    const originalUrl = options.url ? decodeURIComponent(options.url) : ''
    const password = options.password ? decodeURIComponent(options.password) : ''
    const youkuMatch = originalUrl.match(/id_([a-zA-Z0-9=]+)/)
    const videoUrl = youkuMatch
      ? `https://player.youku.com/embed/${youkuMatch[1]}${password ? `?password=${encodeURIComponent(password)}` : ''}`
      : originalUrl
    this.setData({ videoUrl })
  },
  onWebviewLoad() {
    if (this.data.hinted) return
    this.setData({ hinted: true })
    wx.showToast({ title: '建议点击播放器右下角全屏按钮观看', icon: 'none', duration: 3000 })
  },
  onWebviewError() {
    this.setData({ loadError: true })
  },
  handleBack() {
    wx.navigateBack()
  },
})
```

### 5. pages/video/video.wxml（重写）
```
<view wx:if="{{loadError}}" class="error-state">
  <view class="error-text">视频加载失败，请稍后重试</view>
  <button class="error-back" bindtap="handleBack">返回聊天</button>
</view>
<web-view wx:elif="{{videoUrl}}" src="{{videoUrl}}" bindload="onWebviewLoad" binderror="onWebviewError"></web-view>
<view wx:else class="error-state">
  <view class="error-text">视频地址无效</view>
  <button class="error-back" bindtap="handleBack">返回聊天</button>
</view>
```
（无 cover-view，返回主要靠系统导航栏）

### 6. pages/video/video.wxss（重写）
```
page { height: 100%; background: #020617; }
.error-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; gap: 30rpx;
}
.error-text { color: #94a3b8; font-size: 28rpx; }
.error-back {
  width: auto; margin: 0; padding: 0 40rpx; height: 72rpx; line-height: 72rpx;
  border-radius: 14rpx; background: #0284c7; color: #fff; font-size: 26rpx;
}
```

### 7. pages/video/video.json
```json
{
  "navigationBarTitleText": "视频教程",
  "navigationStyle": "default",
  "navigationBarBackgroundColor": "#020617",
  "navigationBarTextStyle": "white"
}
```

## 不改的部分
- 视频卡片入口、密码复制按钮、isDirectVideo 原生 mp4/m3u8 分支、全部业务逻辑

## 预期（收敛）
- iOS 全屏后大概率系统播放器接管，安全区/进度条明显改善
- Android 取决于优酷播放器实现，不承诺完全解决