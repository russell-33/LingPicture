import myAxios from '../request'

const API_BASE_URL = myAxios.defaults.baseURL || ''

export type AutoTagResult = {
  name?: string
  category?: string
  tags?: string[]
  introduction?: string
}

/** 获取 Agent 消息历史 */
export function getAgentMessages(sessionId: string) {
  return myAxios.get('/api/ai/agent/messages', { params: { sessionId } })
}

/** Agent 流式执行 */
export function agentRunStream(
  sessionId: string,
  task: string,
  spaceId: string | number,
  maxSteps = 6,
  signal?: AbortSignal,
) {
  return fetch(`${API_BASE_URL}/api/ai/agent/run/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, task, space_id: String(spaceId), max_steps: maxSteps }),
    credentials: 'include',
    signal,
  })
}

/** 自动标注 */
export function autoTag(pictureId: string | number, imageUrl?: string, spaceId?: string | number) {
  return myAxios.post(`/api/ai/picture/auto-tag/${pictureId}`, {
    image_url: imageUrl || '',
    space_id: spaceId !== undefined && spaceId !== null && String(spaceId) !== '' ? String(spaceId) : undefined,
  })
}

export function unwrapAutoTagResult(raw: any): AutoTagResult {
  const data = typeof raw === 'string' ? JSON.parse(raw) : raw
  const candidates = [
    data,
    data?.data,
    data?.result,
    data?.data?.result,
    data?.payload,
  ]
  for (const candidate of candidates) {
    if (hasAutoTagContent(candidate)) {
      return candidate
    }
  }
  const rawText = safeStringify(data)
  throw new Error(data?.message || data?.msg || data?.detail || `AI 标注未返回有效内容：${rawText}`)
}

export function hasAutoTagContent(data: any): data is AutoTagResult {
  return Boolean(
    data?.category ||
    data?.introduction ||
    (Array.isArray(data?.tags) && data.tags.length > 0)
  )
}

function safeStringify(data: any): string {
  try {
    const text = JSON.stringify(data)
    return text.length > 200 ? `${text.slice(0, 200)}...` : text
  } catch {
    return String(data)
  }
}
