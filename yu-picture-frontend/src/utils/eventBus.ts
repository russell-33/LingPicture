type Handler = (...args: any[]) => void

const listeners: Record<string, Set<Handler>> = {}

export function on(event: string, handler: Handler) {
  if (!listeners[event]) listeners[event] = new Set()
  listeners[event].add(handler)
}

export function off(event: string, handler: Handler) {
  listeners[event]?.delete(handler)
}

export function emit(event: string, ...args: any[]) {
  listeners[event]?.forEach((handler) => handler(...args))
}
