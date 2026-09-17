const agentConfig = require('../config/agent')
const auth = require('./auth')

function redirectToLogin() {
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1]
  if (!currentPage || currentPage.route !== 'pages/login/login') {
    wx.reLaunch({ url: '/pages/login/login' })
  }
}

function request(path, options = {}) {
  let requestTask

  const promise = new Promise((resolve, reject) => {
    const token = auth.getToken()
    const header = {
      'Content-Type': 'application/json',
      ...(options.header || {}),
    }
    if (options.auth !== false && token) {
      header.Authorization = `Bearer ${token}`
    }

    requestTask = wx.request({
      url: `${agentConfig.baseUrl.replace(/\/$/, '')}${path}`,
      method: options.method || 'GET',
      timeout: options.timeout || agentConfig.timeout,
      header,
      data: options.data,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data)
          return
        }

        if (options.auth !== false && (response.statusCode === 401 || response.statusCode === 403)) {
          auth.clearToken()
          redirectToLogin()
        }

        const detail = response.data && (response.data.detail || response.data.message)
        reject(new Error(detail || `请求失败（${response.statusCode}）`))
      },
      fail(error) {
        reject(new Error(error.errMsg || '无法连接服务器，请稍后重试'))
      },
    })
  })

  return {
    promise,
    abort() {
      if (requestTask) {
        requestTask.abort()
      }
    },
  }
}

module.exports = request
