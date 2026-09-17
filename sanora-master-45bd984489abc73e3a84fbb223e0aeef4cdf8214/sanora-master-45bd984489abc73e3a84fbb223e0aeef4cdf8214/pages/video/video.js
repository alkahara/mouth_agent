Page({
  data: {
    videoUrl: '',
    loadError: false,
    hinted: false,
  },

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
    if (this.data.hinted) {
      return
    }
    this.setData({ hinted: true })
    wx.showToast({
      title: '建议点击播放器右下角全屏按钮观看',
      icon: 'none',
      duration: 3000,
    })
  },

  onWebviewError() {
    this.setData({ loadError: true })
  },

  handleBack() {
    wx.navigateBack()
  },
})
