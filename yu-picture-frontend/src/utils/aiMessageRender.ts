export const MAX_AI_THUMBNAILS = 7

export function renderAiMessageContent(text: string): string {
  if (!text) return ''

  let imageIndex = 0
  let html = escapeHtml(text).replace(
    /!\[([^\]]*)\]\(([^)]+)\)/g,
    (_match, alt: string, url: string) => {
      imageIndex += 1
      const label = alt || '图片'
      if (!/^https?:\/\//i.test(url)) {
        return label
      }
      if (imageIndex > MAX_AI_THUMBNAILS) {
        return `<span class="ai-image-basic-info">${label}</span>`
      }
      return `<a href="${url}" target="_blank"><img src="${url}" alt="${label}" class="ai-chat-image" /></a>`
    },
  )

  html = html.replace(
    /\[([^\]]+)\]\(\/picture\/(\d+)\)/g,
    '<a href="/picture/$2" target="_blank" class="ai-picture-link">$1</a>',
  )

  return html.replace(/\n/g, '<br>')
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
