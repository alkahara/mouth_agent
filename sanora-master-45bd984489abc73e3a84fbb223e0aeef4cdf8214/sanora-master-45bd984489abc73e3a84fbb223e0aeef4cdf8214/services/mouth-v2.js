const request = require('./request')
const normalizeAgentResponse = require('../utils/response-normalizer')

function requestChat(path, message, context, resetState) {
  const requestTask = request(path, {
    method: 'POST',
    data: {
      message,
      agent: 'mouth_v2',
      thread_id: context.threadId,
      debug_mode: context.debugMode,
      ...(resetState ? { reset_state: true } : {}),
    },
  })
  return {
    promise: requestTask.promise.then(normalizeAgentResponse),
    abort() {
      requestTask.abort()
    },
  }
}

function chat(message, context) {
  return requestChat('/api/chat', message, context, false)
}

function reassess(message, context) {
  return requestChat('/api/chat/reassess', message, context, true)
}

module.exports = {
  chat,
  reassess,
}
