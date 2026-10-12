const API_ROOT = '/api'

async function request(path, body) {
  let response
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new Error('Could not reach QueryMind API. Check that the FastAPI backend is running.')
  }

  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = typeof payload.detail === 'string'
      ? payload.detail
      : Array.isArray(payload.detail)
        ? payload.detail.map((item) => item.msg || JSON.stringify(item)).join('; ')
        : `Request failed (${response.status})`
    throw new Error(detail)
  }
  return payload
}

export function testDatabase(connectionString) {
  return request('/database/test', { connection_string: connectionString, schemas: ['public'] })
}

export function askQuery({ question, connectionString, conversationHistory = [] }) {
  return request('/query', {
    question,
    connection_string: connectionString,
    schemas: ['public'],
    conversation_history: conversationHistory.length
      ? conversationHistory.map((item) => `${item.role}: ${item.content}`).join('\n')
      : 'none',
  })
}
