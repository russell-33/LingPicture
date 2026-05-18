const PREFIX = 'yunpicture:agent:session'

function normalizeSpaceId(spaceId?: string | number | null): string {
  const raw = spaceId === undefined || spaceId === null || String(spaceId).trim() === ''
    ? 'global'
    : String(spaceId).trim()
  return raw
}

export function getAgentSessionStorageKey(spaceId?: string | number | null): string {
  return `${PREFIX}:${normalizeSpaceId(spaceId)}`
}

export function getOrCreateAgentSessionId(spaceId?: string | number | null): string {
  const key = getAgentSessionStorageKey(spaceId)
  const existing = window.localStorage.getItem(key)
  if (existing) return existing
  const id = `agent_${normalizeSpaceId(spaceId)}_${Date.now()}_${Math.random().toString(16).slice(2)}`
  window.localStorage.setItem(key, id)
  return id
}

export function resetAgentSessionId(spaceId?: string | number | null): string {
  const key = getAgentSessionStorageKey(spaceId)
  window.localStorage.removeItem(key)
  return getOrCreateAgentSessionId(spaceId)
}
