<template>
  <div class="ai-chat-panel">
    <!-- 悬浮按钮 -->
    <a-button
      v-if="!visible && showAiButton"
      type="primary"
      shape="circle"
      size="large"
      class="ai-fab"
      @click="openPanel"
    >
      <template #icon><span style="font-size: 20px">AI</span></template>
    </a-button>

    <!-- 聊天抽屉 -->
    <a-drawer
      v-model:open="visible"
      title="AI 助手"
      placement="right"
      :width="420"
      :mask="false"
      :closable="true"
      :getContainer="getDrawerContainer"
      :zIndex="1050"
    >
      <div class="chat-container">
        <div class="chat-messages" ref="messagesRef">
          <div
            v-for="(msg, idx) in displayMessages"
            :key="idx"
            :class="['msg-bubble', msg.role === 'user' ? 'msg-user' : 'msg-ai']"
          >
            <div class="msg-content" v-html="renderContent(msg.content)"></div>
          </div>
          <div v-if="loading" class="msg-bubble msg-ai">
            <div class="msg-content typing">AI 思考中...</div>
          </div>
        </div>
        <div class="chat-input">
          <a-textarea
            v-model:value="input"
            :rows="2"
            placeholder="输入消息，例如：帮我找蓝色背景的图"
            @keydown="handleInputKeydown"
          />
          <a-button type="primary" :loading="loading" @click="sendMessage">发送</a-button>
        </div>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { agentRunStream, getAgentMessages } from '@/api/aiController'
import { getSpaceVoByIdUsingGet } from '@/api/spaceController'
import { getOrCreateAgentSessionId } from '@/utils/aiSession'
import { SPACE_TYPE_ENUM } from '@/constants/space'
import { emit } from '@/utils/eventBus'
import { renderAiMessageContent } from '@/utils/aiMessageRender'

const route = useRoute()
const visible = ref(false)
const getDrawerContainer = () => document.body
const input = ref('')
const loading = ref(false)
const spaceId = ref('')
const AGENT_REQUEST_TIMEOUT_MS = 300000
const messages = ref<{ role: string; content: string; type?: string }[]>([])
function renderContent(text: string): string {
  return renderAiMessageContent(text)
}

const displayMessages = computed(() => {
  const result: { role: string; content: string; type?: string }[] = []
  for (const m of messages.value) {
    if (!m.content || !m.content.trim()) continue
    if (m.type === 'tool_result') continue
    // 和上一条 assistant 消息合并
    const last = result[result.length - 1]
    if (last && last.role === 'assistant' && !last.type && m.role === 'assistant' && !m.type) {
      last.content = last.content.trimEnd() + '\n' + m.content.trimStart()
    } else {
      result.push({ role: m.role, content: m.content.trim(), type: m.type })
    }
  }
  return result
})
const sessionId = ref('')
const messagesRef = ref<HTMLElement>()
const showAiButton = ref(true)
let hasPictureEdit = false

async function checkSpaceAccess() {
  const sid = getSpaceIdFromUrl()
  if (!sid) {
    // 公共图库或非空间页面：不显示 AI 按钮
    showAiButton.value = false
    return
  }
  try {
    // 空间 ID 可能超过 JS Number 安全整数范围，直接传字符串
    const resp = await getSpaceVoByIdUsingGet({ id: sid as unknown as number })
    const space = resp.data?.data
    // 仅在私有空间显示 AI 按钮
    showAiButton.value = space?.spaceType === SPACE_TYPE_ENUM.PRIVATE
  } catch {
    showAiButton.value = false
  }
}

watch(() => route.fullPath, () => {
  checkSpaceAccess()
})

onMounted(() => {
  checkSpaceAccess()
})

// 阻止 Drawer 打开时锁定 body 滚动
// PortalWrapper 的 useScrollLocker 会注入 CSS：html body { overflow-y: hidden; ... }
// 必须用 !important inline style 来覆盖动态注入的 CSS 规则
watch(visible, (val) => {
  if (val) {
    setTimeout(() => {
      document.body.style.setProperty('overflow-y', 'auto', 'important')
      document.body.style.setProperty('width', 'auto', 'important')
    }, 0)
  } else {
    document.body.style.removeProperty('overflow-y')
    document.body.style.removeProperty('width')
  }
})

function getSpaceIdFromUrl(): string {
  const pathId = route.params?.id
  if (pathId) return String(pathId)
  const queryId = route.query?.spaceId
  if (queryId) return String(queryId)
  return ''
}

async function openPanel() {
  visible.value = true
  spaceId.value = getSpaceIdFromUrl()
  sessionId.value = getOrCreateAgentSessionId(spaceId.value)
  const hint = spaceId.value ? `（当前空间: ${spaceId.value}）` : '（未识别到空间，请进入某个空间页面）'
  const defaultMsg = { role: 'assistant', content: `你好！我是 AI 图片管理助手${hint}，可以帮你搜索图片、分析空间。有什么需要？` }
  messages.value = [defaultMsg]
  try {
    const res = await getAgentMessages(sessionId.value)
    const history = res.data?.data?.messages || res.data?.messages || []
    if (history.length > 0) {
      messages.value = history
      scrollToBottom()
    }
  } catch { /* ignore, keep default message */ }
}

async function sendMessage() {
  const text = input.value.trim()
  if (!text || loading.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: text })
  loading.value = true
  hasPictureEdit = false
  scrollToBottom()

  const controller = new AbortController()
  const timeout = setTimeout(() => {
    if (loading.value) {
      controller.abort()
      messages.value.push({ role: 'assistant', content: '请求超时，请稍后重试。' })
    }
  }, AGENT_REQUEST_TIMEOUT_MS)

  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
  try {
    const resp = await agentRunStream(sessionId.value, text, spaceId.value, 6, controller.signal)
    if (!resp.ok) throw new Error('Request failed')
    reader = resp.body?.getReader()
    if (!reader) throw new Error('No stream')
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          switch (event.type) {
            case 'plan':
              break
            case 'tool_call':
              const nameMap: Record<string, string> = {
                search_pictures_by_semantic: '正在语义搜索图片',
                get_picture_detail: '正在获取图片详情',
                analyze_space: '正在分析空间数据',
                edit_picture: '正在批量编辑图片',
              }
              pushProgress(nameMap[event.tool_name] || `正在 ${event.tool_name}...`)
              break
            case 'tool_result':
              if (event.tool_name === 'edit_picture') hasPictureEdit = true
              break
            case 'reasoning':
              const last = messages.value[messages.value.length - 1]
              if (last && last.role === 'assistant' && !last.type) {
                last.content += event.content
              } else {
                messages.value.push({ role: 'assistant', content: event.content })
              }
              break
            case 'final':
              showFinalAnswer(event.answer)
              break
            case 'error':
              messages.value.push({ role: 'assistant', content: event.message || 'AI 处理失败，请稍后重试。' })
              break
          }
        } catch { /* skip malformed */ }
      }
      scrollToBottom()
    }
  } catch (e: any) {
    if (e?.name !== 'AbortError') {
      messages.value.push({ role: 'assistant', content: '抱歉，连接失败，请稍后重试。' })
    }
  } finally {
    clearTimeout(timeout)
    try {
      await reader?.cancel()
    } catch { /* stream already closed */ }
    if (messages.value.length > 100) messages.value = messages.value.slice(-60)
    loading.value = false
    if (hasPictureEdit) {
      emit('ai:refresh-pictures')
    }
  }
}

function handleInputKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    sendMessage()
  }
}

function showFinalAnswer(answer?: string) {
  if (!answer) return
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant' && !last.type) {
    last.content = answer
    return
  }
  messages.value.push({ role: 'assistant', content: answer })
}

function pushProgress(content: string) {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant' && last.type === 'tool_call') {
    last.content = content
    return
  }
  messages.value.push({ role: 'assistant', content, type: 'tool_call' })
}

let scrollTimer = 0
function scrollToBottom() {
  clearTimeout(scrollTimer)
  scrollTimer = setTimeout(() => {
    nextTick(() => {
      if (messagesRef.value) {
        messagesRef.value.scrollTop = messagesRef.value.scrollHeight
      }
    })
  }, 50)
}
</script>

<style scoped>
.ai-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 1000;
  width: 48px;
  height: 48px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}
.chat-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.msg-bubble {
  margin-bottom: 12px;
  max-width: 85%;
}
.msg-user {
  margin-left: auto;
}
.msg-user .msg-content {
  background: #1677ff;
  color: #fff;
  border-radius: 12px 12px 4px 12px;
  padding: 10px 14px;
}
.msg-ai .msg-content {
  background: #f0f0f0;
  border-radius: 12px 12px 12px 4px;
  padding: 10px 14px;
}
.msg-content :deep(.ai-chat-image) {
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  margin: 4px 0;
  display: block;
  cursor: pointer;
}
.msg-content :deep(.ai-picture-link) {
  color: #1677ff;
}
.msg-content :deep(.ai-image-basic-info) {
  font-weight: 500;
  color: #333;
}
.typing {
  color: #999;
  font-style: italic;
}
.chat-input {
  display: flex;
  gap: 8px;
  padding: 8px 0;
  border-top: 1px solid #eee;
}
.chat-input :deep(.ant-btn) {
  align-self: flex-end;
}
</style>
