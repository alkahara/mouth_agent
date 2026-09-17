const mouthV2 = require('../../services/mouth-v2')
const auth = require('../../services/auth')
const createUuid = require('../../utils/uuid')
const presetQuestions = require('../../data/mouth-v2-presets')

const DEFAULT_REASSESS_PROMPT = '请提供一条人文关怀话术'
const OTHER_KEYWORDS = ['其他', '其它', '其他表现', '其他选择', 'other']

const SLOT_DEFINITIONS = [
  { key: 'is_surgical_area', label: '手术区域' },
  { key: 'cause_trigger', label: '诱因' },
  { key: 'latest_time', label: '时间分期' },
  { key: 'surgery_type', label: '手术类型' },
  { key: 'bleeding_severity', label: '出血程度' },
  { key: 'can_compress', label: '压迫状态' },
]

const SLOT_VALUE_LABELS = {
  is_surgical_area: { yes: '是', no: '否' },
  cause_trigger: { has_trigger: '有诱因', no_trigger: '无诱因' },
  latest_time: { early: '术后<24h', rebleed: '术后24h~5天', late: '术后>5天' },
  surgery_type: { vascular: '涉血管手术', non_vascular: '常规手术' },
  bleeding_severity: { minor: '轻微渗血', active: '活动性出血', floor: '口底血肿' },
  can_compress: {
    can: '可压迫',
    cannot: '无法压迫',
    no_gauze: '无纱布',
    tried_but_bleeding: '压迫后仍出血',
  },
}

const RISK_LABELS = {
  none: '无风险',
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

const RISK_COLORS = {
  none: '#4caf50',
  low: '#8bc34a',
  medium: '#ffc107',
  high: '#f44336',
}

function formatTime(date) {
  const pad = (value) => (value < 10 ? `0${value}` : String(value))
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function getSlotValue(rawValue) {
  if (typeof rawValue === 'string' || typeof rawValue === 'number') {
    return String(rawValue)
  }
  if (!rawValue || typeof rawValue !== 'object') {
    return ''
  }
  const candidate = rawValue.value || rawValue.final_value || rawValue.result || rawValue.label
  return typeof candidate === 'string' || typeof candidate === 'number' ? String(candidate) : ''
}

function isOtherOption(option) {
  const values = [option.key, option.label]
    .map((value) => String(value || '').replace(/[：:]/g, '').trim().toLowerCase())
    .filter(Boolean)
  return values.some((value) => OTHER_KEYWORDS.includes(value)
    || value.startsWith('其他') || value.startsWith('其它'))
}

Page({
  data: {
    isIOS: false,
    debugEnabled: true,
    debugPanelVisible: false,
    navbarHeight: 88,
    messages: [],
    draft: '',
    canSend: false,
    isLoading: false,
    error: '',
    presetQuestions,
    collectedSlots: {},
    slotItems: SLOT_DEFINITIONS.map((slot) => ({ ...slot, filled: false, valueLabel: '待收集' })),
    filledSlotCount: 0,
    slotProgress: 0,
    slotProgressStyle: 'width: 0%;',
    triageVisible: false,
    riskLabel: '',
    riskColor: '#64748b',
    carePlanId: '',
    canReassess: false,
    scrollIntoView: '',
    showOtherDialog: false,
    otherDialogTitle: '请输入详细描述',
    otherDialogHint: '请详细描述',
    otherInput: '',
    otherCanSubmit: false,
    // 当前正在/曾在播放的直链视频状态，用于切后台续播
    videoState: { messageId: '', currentTime: 0, playing: false },
  },

  onLoad() {
    if (!auth.getToken()) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    const systemInfo = wx.getSystemInfoSync()
    this.setData({ isIOS: systemInfo.platform === 'ios' })
    this.setData({ navbarHeight: this.computeNavbarHeight() })
    this.threadId = createUuid()
    this.messageSequence = 0
    this.currentRequest = null
    this.abortRequested = false
    this.pendingOther = null
    // 直链视频续播：记录上次播放进度，供 onShow 恢复
    this.videoResumeInfo = { messageId: '', currentTime: 0, shouldResume: false }
    this.handleReassess(true)
  },

  onUnload() {
    this.pauseActiveVideo()
    if (this.currentRequest) {
      this.currentRequest.abort()
    }
  },

  handleLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定退出当前账号吗？',
      success: (result) => {
        if (!result.confirm) return
        auth.clearToken()
        wx.reLaunch({ url: '/pages/login/login' })
      },
    })
  },

  // 小程序进后台（切别的 App / 按 Home / 微信本身切后台）
  onHide() {
    this.pauseActiveVideo()
  },

  // 小程序回前台：如果切后台前正在播放，从上次进度续播
  onShow() {
    const info = this.videoResumeInfo
    if (!info || !info.shouldResume) {
      return
    }
    info.shouldResume = false
    this.resumeVideo(info.messageId, info.currentTime)
  },

  // 记录当前播放进度（bindtimeupdate，约每 250ms 触发一次）
  onVideoTimeUpdate(event) {
    const id = event.currentTarget.dataset.messageId
    if (this.data.videoState.messageId !== id) {
      return
    }
    this.setData({ videoState: { ...this.data.videoState, currentTime: event.detail.currentTime } })
    if (this.videoResumeInfo && this.videoResumeInfo.messageId === id) {
      this.videoResumeInfo.currentTime = event.detail.currentTime
    }
  },

  onVideoPlay(event) {
    const id = event.currentTarget.dataset.messageId
    const currentTime = event.detail.currentTime || this.data.videoState.currentTime
    this.setData({ videoState: { messageId: id, currentTime, playing: true } })
  },

  onVideoPause(event) {
    const id = event.currentTarget.dataset.messageId
    if (this.data.videoState.messageId !== id) {
      return
    }
    this.setData({ videoState: { ...this.data.videoState, playing: false } })
    // 记住续播信息：切后台/离开页时若仍在播，回来继续
    this.videoResumeInfo = {
      messageId: id,
      currentTime: this.data.videoState.currentTime,
      shouldResume: true,
    }
  },

  // 播放结束：清掉状态，回来不再自动续播
  onVideoEnded(event) {
    const id = event.currentTarget.dataset.messageId
    if (this.data.videoState.messageId !== id) {
      return
    }
    this.setData({ videoState: { messageId: '', currentTime: 0, playing: false } })
    this.videoResumeInfo = { messageId: '', currentTime: 0, shouldResume: false }
  },

  // 暂停当前正在播放的视频（用于 onHide / onUnload）
  pauseActiveVideo() {
    const { messageId, playing } = this.data.videoState
    if (!messageId || !playing) {
      return
    }
    const ctx = wx.createVideoContext(messageId, this)
    if (ctx) {
      ctx.pause()
    }
  },

  // 恢复指定视频到指定进度并继续播放
  resumeVideo(messageId, currentTime) {
    if (!messageId) {
      return
    }
    const ctx = wx.createVideoContext(messageId, this)
    if (!ctx) {
      return
    }
    if (currentTime > 0) {
      ctx.seek(currentTime)
    }
    ctx.play()
    this.setData({ videoState: { messageId, currentTime, playing: true } })
  },

  handleDraftInput(event) {
    const draft = event.detail.value
    this.setData({ draft, canSend: Boolean(draft.trim()) })
  },

  handleOtherInput(event) {
    const otherInput = event.detail.value
    this.setData({ otherInput, otherCanSubmit: Boolean(otherInput.trim()) })
  },

  toggleDebug() {
    this.setData({ debugPanelVisible: !this.data.debugPanelVisible })
  },

  closeDebugPanel() {
    this.setData({ debugPanelVisible: false })
  },

  computeNavbarHeight() {
    try {
      const platform = (wx.getDeviceInfo() || wx.getSystemInfoSync()).platform
      const baseHeight = platform === 'android' ? 48 : 44
      const { top = 0 } = (wx.getWindowInfo() || wx.getSystemInfoSync()).safeArea || {}
      const statusBarHeight = (wx.getWindowInfo() || wx.getSystemInfoSync()).statusBarHeight || top
      return baseHeight + statusBarHeight
    } catch (error) {
      return 88
    }
  },

  handleSend() {
    const input = this.data.draft.trim()
    if (!input || this.data.isLoading) {
      return
    }
    this.setData({ draft: '', canSend: false })
    this.executePrompt(input, false)
  },

  handlePresetTap(event) {
    const question = event.currentTarget.dataset.question
    if (!question || this.data.isLoading) {
      return
    }
    this.executePrompt(question, false)
  },

  async executePrompt(input, skipUserPush) {
    const prompt = String(input || '').trim()
    if (!prompt || this.data.isLoading) {
      return
    }

    if (!skipUserPush) {
      this.pushMessage({ role: 'user', text: prompt })
    }

    this.abortRequested = false
    this.setData({ isLoading: true, error: '', canReassess: false })
    this.scrollToBottom()
    const request = mouthV2.chat(prompt, {
      threadId: this.threadId,
      debugMode: this.data.debugEnabled,
    })
    this.currentRequest = request

    try {
      const result = await request.promise
      this.applyAgentResult(result)
    } catch (error) {
      if (this.abortRequested || /abort/i.test(error.message)) {
        this.pushMessage({ role: 'assistant', text: '对话已被中断。' })
      } else {
        this.setData({ error: error.message || '请求失败，请稍后重试' })
      }
    } finally {
      this.currentRequest = null
      this.setData({ isLoading: false })
      this.refreshCanReassess()
      this.scrollToBottom()
    }
  },

  async handleReassess(isAutomatic) {
    if (this.data.isLoading) {
      return
    }

    const lastUserMessage = [...this.data.messages]
      .reverse()
      .find((message) => message.role === 'user' && message.text.trim())
    if (!isAutomatic && !lastUserMessage) {
      return
    }

    const prompt = lastUserMessage ? lastUserMessage.text.trim() : DEFAULT_REASSESS_PROMPT
    this.threadId = createUuid()
    this.resetSlotState()
    this.abortRequested = false
    this.setData({ isLoading: true, error: '', canReassess: false })
    this.scrollToBottom()

    const request = mouthV2.reassess(prompt, {
      threadId: this.threadId,
      debugMode: this.data.debugEnabled,
    })
    this.currentRequest = request

    try {
      const result = await request.promise
      this.applyAgentResult(result)
      this.hasReassessed = true
    } catch (error) {
      if (this.abortRequested || /abort/i.test(error.message)) {
        this.pushMessage({ role: 'assistant', text: '对话已被中断。' })
      } else {
        this.setData({ error: error.message || '重新评估失败，请稍后重试' })
      }
    } finally {
      this.currentRequest = null
      this.setData({ isLoading: false })
      this.refreshCanReassess()
      this.scrollToBottom()
    }
  },

  handleReassessTap() {
    if (!this.data.canReassess || this.data.isLoading) {
      return
    }
    this.handleReassess(false)
  },

  applyAgentResult(result) {
    if (this.data.debugEnabled) {
      this.updateSlotState(result.slotUpdate, result.triageResult)
    }

    this.pushMessage({
      role: 'assistant',
      text: result.reply,
      options: result.options,
      optionsConfig: result.optionsConfig,
      decisionLogic: result.decisionLogic,
      videoUrl: result.videoUrl,
      videoPassword: result.videoPassword,
    })
  },

  pushMessage(message) {
    this.messageSequence += 1
    const optionsConfig = message.optionsConfig || {}
    const options = Array.isArray(message.options) ? message.options : []
    const nextMessage = {
      id: `message-${this.messageSequence}`,
      role: message.role,
      isAssistant: message.role === 'assistant',
      text: message.text,
      timestamp: formatTime(new Date()),
      options,
      hasOptions: options.length > 0,
      multiSelect: optionsConfig.multiSelect === true,
      maxSelect: optionsConfig.maxSelect || null,
      confirmButtonText: optionsConfig.confirmButtonText || '确认选择',
      selectedKeys: [],
      selectedCount: 0,
      selectionSummary: optionsConfig.maxSelect ? `已选择 0 / ${optionsConfig.maxSelect} 项` : '已选择 0 项',
      decisionLogic: message.decisionLogic || '',
      videoUrl: message.videoUrl || '',
      videoPassword: message.videoPassword || '',
      isDirectVideo: /\.(mp4|m3u8)(?:\?|$)/i.test(message.videoUrl || ''),
    }
    const messages = this.data.messages.concat(nextMessage)
    const newMessageIndex = messages.length - 1
    this.hasReassessed = false
    this.setData({ messages })
    this.refreshCanReassess()
    this.scrollToBottom()
    this.preloadOptionImages(newMessageIndex)
  },

  preloadOptionImages(messageIndex) {
    const message = this.data.messages[messageIndex]
    if (!message || !Array.isArray(message.options)) {
      return
    }
    message.options.forEach((option, optionIndex) => {
      const remoteUrl = option.imageUrl
      if (!remoteUrl || option.localImageUrl || option.imageLoading) {
        return
      }
      this.setOptionField(messageIndex, optionIndex, { imageLoading: true })
      const task = wx.downloadFile({
        url: remoteUrl,
        success: (res) => {
          if (res.statusCode === 200 && res.tempFilePath) {
            this.setOptionField(messageIndex, optionIndex, {
              localImageUrl: res.tempFilePath,
              imageLoading: false,
              imageError: false,
            })
          } else {
            this.setOptionField(messageIndex, optionIndex, {
              imageLoading: false,
              imageError: true,
            })
          }
        },
        fail: () => {
          this.setOptionField(messageIndex, optionIndex, {
            imageLoading: false,
            imageError: true,
          })
        },
      })
    })
  },

  setOptionField(messageIndex, optionIndex, patch) {
    const messages = this.data.messages.slice()
    const message = messages[messageIndex]
    if (!message || !message.options || !message.options[optionIndex]) {
      return
    }
    message.options = message.options.map((option, index) => (
      index === optionIndex ? { ...option, ...patch } : option
    ))
    messages[messageIndex] = { ...message }
    this.setData({ messages })
  },

  handleOptionTap(event) {
    if (this.data.isLoading) {
      return
    }
    const messageIndex = Number(event.currentTarget.dataset.messageIndex)
    const optionIndex = Number(event.currentTarget.dataset.optionIndex)
    const message = this.data.messages[messageIndex]
    const option = message && message.options[optionIndex]
    if (!message || !option || option.disabled) {
      return
    }

    if (message.multiSelect) {
      this.toggleOption(messageIndex, optionIndex)
      return
    }

    if (isOtherOption(option)) {
      this.openOtherDialog(messageIndex, option)
      return
    }

    this.clearMessageOptions(messageIndex)
    this.pushMessage({ role: 'user', text: option.label.trim() || option.key.trim() })
    this.executePrompt(option.label.trim() || option.key.trim(), true)
  },

  toggleOption(messageIndex, optionIndex) {
    const messages = this.data.messages.slice()
    const message = { ...messages[messageIndex] }
    const options = message.options.map((option) => ({ ...option }))
    options[optionIndex].selected = !options[optionIndex].selected
    const selectedCount = options.filter((option) => option.selected).length

    options.forEach((option) => {
      option.disabled = Boolean(message.maxSelect
        && selectedCount >= message.maxSelect
        && !option.selected)
    })

    message.options = options
    message.selectedKeys = options.filter((option) => option.selected).map((option) => option.key)
    message.selectedCount = selectedCount
    message.selectionSummary = message.maxSelect
      ? `已选择 ${selectedCount} / ${message.maxSelect} 项`
      : `已选择 ${selectedCount} 项`
    messages[messageIndex] = message
    this.setData({ messages })
  },

  handleMultiSelectConfirm(event) {
    if (this.data.isLoading) {
      return
    }
    const messageIndex = Number(event.currentTarget.dataset.messageIndex)
    const message = this.data.messages[messageIndex]
    if (!message || !message.selectedKeys.length) {
      return
    }

    const selectedOptions = message.options.filter((option) => option.selected)
    const selectedKeys = selectedOptions.map((option) => option.key).sort()
    const selectedLabels = selectedKeys
      .map((key) => selectedOptions.find((option) => option.key === key).label)
      .join('、')

    this.clearMessageOptions(messageIndex)
    this.pushMessage({ role: 'user', text: `选择: ${selectedLabels}` })
    this.executePrompt(selectedKeys.join(','), true)
  },

  clearMessageOptions(messageIndex) {
    const messages = this.data.messages.slice()
    messages[messageIndex] = {
      ...messages[messageIndex],
      options: [],
      hasOptions: false,
      selectedKeys: [],
      selectedCount: 0,
      selectionSummary: messages[messageIndex].maxSelect
        ? `已选择 0 / ${messages[messageIndex].maxSelect} 项`
        : '已选择 0 项',
    }
    this.setData({ messages })
  },

  openOtherDialog(messageIndex, option) {
    const normalizedLabel = option.label.replace(/[：:]/g, '').trim()
    this.pendingOther = { messageIndex }
    let title = '请输入详细描述'
    let hint = '请详细描述'
    if (normalizedLabel === '其他表现') {
      title = '请描述其他表现'
      hint = '请详细描述患者的具体表现'
    } else if (normalizedLabel === '其他选择') {
      title = '请描述其他选择'
      hint = '请详细描述您的选择'
    }
    this.setData({
      showOtherDialog: true,
      otherDialogTitle: title,
      otherDialogHint: hint,
      otherInput: '',
      otherCanSubmit: false,
    })
  },

  closeOtherDialog() {
    this.pendingOther = null
    this.setData({ showOtherDialog: false, otherInput: '', otherCanSubmit: false })
  },

  submitOtherInput() {
    const input = this.data.otherInput.trim()
    if (!input || !this.pendingOther) {
      return
    }
    const messageIndex = this.pendingOther.messageIndex
    this.pendingOther = null
    this.setData({ showOtherDialog: false, otherInput: '', otherCanSubmit: false })
    this.clearMessageOptions(messageIndex)
    this.pushMessage({ role: 'user', text: input })
    this.executePrompt(input, true)
  },

  updateSlotState(slotUpdate, triageResult) {
    const collectedSlots = {
      ...this.data.collectedSlots,
      ...(slotUpdate || {}),
      ...((triageResult && triageResult.slots) || {}),
    }
    const slotItems = SLOT_DEFINITIONS.map((slot) => {
      const rawValue = collectedSlots[slot.key]
      const value = getSlotValue(rawValue)
      return {
        ...slot,
        filled: Boolean(value),
        valueLabel: value ? (SLOT_VALUE_LABELS[slot.key] || {})[value] || value : '待收集',
      }
    })
    const filledSlotCount = slotItems.filter((slot) => slot.filled).length
    const slotProgress = Math.round((filledSlotCount / SLOT_DEFINITIONS.length) * 100)
    const riskLevel = triageResult && triageResult.risk_level

    this.setData({
      collectedSlots,
      slotItems,
      filledSlotCount,
      slotProgress,
      slotProgressStyle: `width: ${slotProgress}%;`,
      triageVisible: Boolean(triageResult),
      riskLabel: RISK_LABELS[riskLevel] || riskLevel || '',
      riskColor: RISK_COLORS[riskLevel] || '#64748b',
      carePlanId: triageResult && triageResult.care_plan_id ? triageResult.care_plan_id : '',
    })
  },

  resetSlotState() {
    this.setData({
      collectedSlots: {},
      slotItems: SLOT_DEFINITIONS.map((slot) => ({ ...slot, filled: false, valueLabel: '待收集' })),
      filledSlotCount: 0,
      slotProgress: 0,
      slotProgressStyle: 'width: 0%;',
      triageVisible: false,
      riskLabel: '',
      riskColor: '#64748b',
      carePlanId: '',
    })
  },

  refreshCanReassess() {
    const hasUserMessage = this.data.messages.some((message) => message.role === 'user' && message.text.trim())
    this.setData({
      canReassess: hasUserMessage && !this.hasReassessed && !this.data.isLoading,
    })
  },

  scrollToBottom() {
    this.setData({ scrollIntoView: this.data.isLoading ? 'loading-anchor' : 'bottom-anchor' })
  },

  openInlineVideo(event) {
    const url = event.currentTarget.dataset.url
    if (!url) {
      return
    }
    const password = event.currentTarget.dataset.password || ''
    wx.navigateTo({
      url: `/pages/video/video?url=${encodeURIComponent(url)}&password=${encodeURIComponent(password)}`,
    })
  },

  copyVideoPassword(event) {
    const password = event.currentTarget.dataset.password
    if (password) {
      wx.setClipboardData({ data: password })
    }
  },

  stopPropagation() {},
})
