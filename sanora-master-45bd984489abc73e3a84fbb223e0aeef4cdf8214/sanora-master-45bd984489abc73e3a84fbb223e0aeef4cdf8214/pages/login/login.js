const request = require('../../services/request')
const auth = require('../../services/auth')

const fourDigits = /^[0-9]{4}$/
const eightDigits = /^[0-9]{8}$/

Page({
  data: {
    mode: 'login',
    loginCode: '',
    idCardLast4: '',
    phoneLast4: '',
    password: '',
    passwordConfirmation: '',
    showPassword: false,
    privacyConsent: false,
    isLoading: false,
    error: '',
    documentTitle: '',
    documentText: '',
  },

  onLoad() {
    if (auth.getToken()) wx.reLaunch({ url: '/pages/index/index' })
  },

  switchMode(event) {
    const mode = event.currentTarget.dataset.mode
    if (mode !== 'login' && mode !== 'register') return
    this.setData({ mode, password: '', passwordConfirmation: '', error: '' })
  },

  handleInput(event) {
    const field = event.currentTarget.dataset.field
    if (!['loginCode', 'idCardLast4', 'phoneLast4', 'password', 'passwordConfirmation'].includes(field)) return
    this.setData({ [field]: String(event.detail.value || ''), error: '' })
  },

  togglePasswordVisibility() {
    this.setData({ showPassword: !this.data.showPassword })
  },

  handleConsentChange(event) {
    const values = event.detail.value || []
    this.setData({ privacyConsent: values.includes('agree'), error: '' })
  },

  getValidationError() {
    const { mode, loginCode, idCardLast4, phoneLast4, password, passwordConfirmation, privacyConsent } = this.data
    if (mode === 'login') {
      if (!eightDigits.test(loginCode)) return '请输入 8 位数字登录识别码'
      if (!password) return '请输入密码'
      return ''
    }
    if (!fourDigits.test(idCardLast4)) return '身份证后 4 位需填写数字'
    if (!fourDigits.test(phoneLast4)) return '手机号后 4 位需填写数字'
    if (password.length < 8) return '密码至少需要 8 位'
    if (password !== passwordConfirmation) return '两次输入的密码不一致'
    if (!privacyConsent) return '请先阅读并同意隐私政策和医疗资料处理说明'
    return ''
  },

  async handleSubmit() {
    if (this.data.isLoading) return
    const validationError = this.getValidationError()
    if (validationError) {
      this.setData({ error: validationError })
      return
    }
    this.setData({ isLoading: true, error: '' })
    try {
      if (this.data.mode === 'register') {
        const result = await request('/api/auth/register', {
          method: 'POST',
          auth: false,
          data: {
            id_card_last4: this.data.idCardLast4,
            phone_last4: this.data.phoneLast4,
            password: this.data.password,
            password_confirmation: this.data.passwordConfirmation,
            privacy_consent: this.data.privacyConsent,
          },
        }).promise
        this.setData({ mode: 'login', loginCode: result.login_code, password: '', passwordConfirmation: '', error: '' })
        wx.showModal({
          title: '注册成功',
          content: `登录识别码：${result.login_code}\n请记住识别码，登录时使用。`,
          showCancel: false,
        })
        return
      }

      const result = await request('/api/auth/login', {
        method: 'POST',
        auth: false,
        data: { login_code: this.data.loginCode, password: this.data.password },
      }).promise
      if (!result || !result.access_token) throw new Error('服务器未返回登录令牌')
      auth.setToken(result.access_token)
      wx.reLaunch({ url: '/pages/index/index' })
    } catch (error) {
      this.setData({ error: error.message || '操作失败，请稍后重试' })
    } finally {
      this.setData({ isLoading: false })
    }
  },

  showPrivacy() {
    this.setData({
      documentTitle: '隐私政策（演示版）',
      documentText: '注册时会保存您填写的身份证后四位、手机号后四位、登录识别码及密码哈希，用于创建和保护平台账号。识别码不能证明真实身份。正式上线前，机构需提供完整的隐私政策。',
    })
  },

  showMedicalNotice() {
    this.setData({
      documentTitle: '医疗资料处理说明（演示版）',
      documentText: '口腔咨询内容会发送至服务端和模型服务以生成回复。当前版本未开放病例图片上传。请勿填写姓名、完整证件号码等不必要的个人信息；智能体回复不能代替医生诊断。',
    })
  },

  closeDocument() {
    this.setData({ documentTitle: '', documentText: '' })
  },

  noop() {},

  showForgotPassword() {
    wx.showModal({ title: '忘记密码', content: '请联系医院工作人员协助处理。', showCancel: false })
  },
})
