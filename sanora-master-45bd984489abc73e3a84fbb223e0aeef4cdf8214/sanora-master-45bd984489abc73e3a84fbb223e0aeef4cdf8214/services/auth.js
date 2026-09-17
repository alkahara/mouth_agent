const TOKEN_STORAGE_KEY = 'assistant_chat_access_token'

function getToken() {
  return wx.getStorageSync(TOKEN_STORAGE_KEY) || ''
}

function setToken(token) {
  wx.setStorageSync(TOKEN_STORAGE_KEY, token)
}

function clearToken() {
  wx.removeStorageSync(TOKEN_STORAGE_KEY)
}

module.exports = {
  getToken,
  setToken,
  clearToken,
}
