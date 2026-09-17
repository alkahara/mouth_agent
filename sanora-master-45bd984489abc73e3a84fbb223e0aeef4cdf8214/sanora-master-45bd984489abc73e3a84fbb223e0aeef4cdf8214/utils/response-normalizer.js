function normalizeOptions(kwargs) {
  if (!Array.isArray(kwargs.options)) {
    return []
  }

  return kwargs.options
    .filter((option) => option && typeof option.key === 'string' && typeof option.label === 'string')
    .map((option) => ({
      key: option.key,
      label: option.label,
      imageUrl: typeof option.image_url === 'string' ? option.image_url.trim() : '',
      selected: false,
      disabled: false,
    }))
}

function getDecisionLogic(debugInfo, triageResult) {
  const surgeryDebug = triageResult
    && triageResult.slots
    && triageResult.slots.surgery_type
    && triageResult.slots.surgery_type.debug_info
  if (surgeryDebug && typeof surgeryDebug.final_judgment === 'string') {
    return surgeryDebug.final_judgment
  }

  if (debugInfo && debugInfo.type === 'surgery_type_parse'
      && debugInfo.data && debugInfo.data.final_judgment) {
    return String(debugInfo.data.final_judgment)
  }

  if (debugInfo && debugInfo.slots_collected && debugInfo.slots) {
    const slotKeys = Object.keys(debugInfo.slots)
    for (let index = 0; index < slotKeys.length; index += 1) {
      const key = slotKeys[index]
      const slotDebug = debugInfo.slots[key]
      if (key.endsWith('_debug_info') && slotDebug && slotDebug.final_judgment) {
        return String(slotDebug.final_judgment)
      }
    }
  }

  return debugInfo && debugInfo.decision_logic ? String(debugInfo.decision_logic) : ''
}

function normalizeAgentResponse(response) {
  const optionsConfig = response && response.options_config && typeof response.options_config === 'object'
    ? response.options_config
    : {}
  const options = normalizeOptions({ options: response && response.options })
  const maxSelect = Number(optionsConfig.max_select)
  const triageResult = response && response.triage_result && typeof response.triage_result === 'object'
    ? response.triage_result
    : null
  const debugInfo = response && response.debug_info && typeof response.debug_info === 'object'
    ? response.debug_info
    : {}

  return {
    reply: response && typeof response.reply === 'string' && response.reply.trim()
      ? response.reply.trim()
      : '(Agent 未返回内容)',
    options,
    optionsConfig: options.length ? {
      multiSelect: optionsConfig.multi_select === true,
      maxSelect: maxSelect > 0 ? maxSelect : null,
      confirmButtonText: typeof optionsConfig.confirm_button_text === 'string' && optionsConfig.confirm_button_text.trim()
        ? optionsConfig.confirm_button_text.trim()
        : '确认选择',
    } : null,
    debugInfo,
    decisionLogic: getDecisionLogic(debugInfo, triageResult),
    slotUpdate: response && response.slot_update && typeof response.slot_update === 'object'
      ? response.slot_update
      : null,
    triageResult,
    videoUrl: response && typeof response.video_url === 'string' ? response.video_url.trim() : '',
    videoPassword: response && typeof response.video_password === 'string' ? response.video_password.trim() : '',
  }
}

module.exports = normalizeAgentResponse
