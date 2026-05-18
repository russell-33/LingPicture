<template>
  <div class="ai-chat-page">
    <a-card title="AI 图片管理助手" style="max-width: 800px; margin: 24px auto; height: calc(100vh - 120px)">
      <div class="chat-body" ref="chatBodyRef">
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          :class="['chat-row', msg.role === 'user' ? 'row-user' : 'row-ai']"
        >
          <a-avatar v-if="msg.role === 'assistant'" style="background: #1677ff; flex-shrink: 0">AI</a-avatar>
          <div :class="['bubble', msg.role === 'user' ? 'bubble-user' : 'bubble-ai']">
            <div v-if="msg.type === 'tool_call'" class="tool-tag">
              <a-tag color="blue">调用工具: {{ msg.toolName }}</a-tag>
            </div>
            <div v-if="msg.type === 'tool_result'" class="tool-tag">
              <a-tag color="green">工具完成: {{ msg.toolName }}</a-tag>
            </div>
            <div class="bubble-text" v-html="renderContent(msg.content)"></div>
          </div>
          <a-avatar v-if="msg.role === 'user'" style="flex-shrink: 0">U</a-avatar>
        </div>
        <div v-if="loading" class="chat-row row-ai">
          <a-avatar style="background: #1677ff; flex-shrink: 0">AI</a-avatar>
          <div class="bubble bubble-ai typing">思考中...</div>
        </div>
      </div>
      <div class="chat-footer">
        <a-space-compact style="width: 100%">
          <a-select v-model:value="spaceId" style="width: 160px" placeholder="选择空间" :options="spaceOptions" />
          <a-textarea
            v-model:value="input"
            :rows="2"
            placeholder="输入任务，例如：帮我把空间里没标签的图片全部标注"
            @keydown="handleInputKeydown"
          />
          <a-button type="primary" :loading="loading" :disabled="!spacesReady" @click="sendMessage">发送</a-button>
        </a-space-compact>
        <div style="margin-top: 8px">
          <a-space>
            <a-tag color="default">试试</a-tag>
            <a-tag color="processing" style="cursor: pointer" @click="quickTask('帮我找蓝色背景的图')">蓝色背景的图</a-tag>
            <a-tag color="processing" style="cursor: pointer" @click="quickTask('帮我分析一下空间的使用情况')">分析空间</a-tag>
          </a-space>
        </div>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { agentRunStream, getAgentMessages } from '../api/aiController'
import { listSpaceVoByPageUsingPost } from '../api/spaceController'
import { getOrCreateAgentSessionId } from '../utils/aiSession'
import { renderAiMessageContent } from '../utils/aiMessageRender'

const input = ref('')
const loading = ref(false)
const spaceId = ref<string>('')
const sessionId = ref(getOrCreateAgentSessionId('global'))
const chatBodyRef = ref<HTMLElement>()
const AGENT_REQUEST_TIMEOUT_MS = 120000
const spaceOptions = ref<{ value: string; label: string }[]>([])
const spacesReady = ref(false)

interface ChatMessage {
  role: string
  content: string
  type?: string
  toolName?: string
}
function renderContent(text: string): string {
  return renderAiMessageContent(text)
}

onMounted(async () => {
  try {
    const res = await listSpaceVoByPageUsingPost({ current: 1, pageSize: 50 })
    const records = res.data?.data?.records || []
    spaceOptions.value = records.map((s: any) => ({ value: String(s.id), label: s.spaceName || `空间${s.id}` }))
    if (records.length > 0) {
      spaceId.value = String(records[0].id)
      sessionId.value = getOrCreateAgentSessionId(spaceId.value)
    }
    spacesReady.value = true
    await loadHistory()
  } catch { /* ignore */ }
})

watch(spaceId, async (newSpaceId) => {
  if (newSpaceId) {
    sessionId.value = getOrCreateAgentSessionId(newSpaceId)
    await loadHistory()
  }
})

const messages = ref<ChatMessage[]>([
  { role: 'assistant', content: '你好！我是 AI 图片管理助手。可以直接告诉我你想做什么，比如：\n\n• 帮我找蓝色背景的简约海报\n• 分析一下我的空间使用情况' }
])

async function loadHistory() {
  try {
    const res = await getAgentMessages(sessionId.value)
    const history = res.data?.data?.messages || res.data?.messages || []
    if (history.length > 0) {
      messages.value = history
      scrollToBottom()
    }
  } catch { /* ignore */ }
}

function quickTask(task: string) {
  input.value = task
  sendMessage()
}

async function sendMessage() {
  const text = input.value.trim()
  if (!text || loading.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: text })
  loading.value = true
  scrollToBottom()

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), AGENT_REQUEST_TIMEOUT_MS)
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
        if (line.startsWith('data: ')) {
          try {
            const parsed = JSON.parse(line.slice(6))
            handleStreamEvent(parsed)
          } catch { /* skip malformed */ }
        }
      }
      scrollToBottom()
    }
  } catch (e: any) {
    clearProgressMessages()
    messages.value.push({
      role: 'assistant',
      content: e?.name === 'AbortError' ? '请求超时，请稍后重试。' : '抱歉，连接失败，请稍后重试。',
    })
  } finally {
    clearTimeout(timeout)
    try {
      await reader?.cancel()
    } catch { /* stream already closed */ }
    clearProgressMessages()
    loading.value = false
  }
}

function handleStreamEvent(event: any) {
  switch (event.type) {
    case 'tool_call':
      if (event.tool_name === 'analyze_space') return
      const toolNames: Record<string, string> = {
        search_pictures_by_semantic: '正在语义搜索图片',
        get_picture_detail: '正在获取图片详情',
        edit_picture: '正在批量编辑图片',
      }
      pushProgress(toolNames[event.tool_name] || `正在 ${event.tool_name}...`, event.tool_name)
      break
    case 'tool_result':
      break
    case 'reasoning':
      // streaming reasoning - update last message or add new
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
      clearProgressMessages()
      messages.value.push({ role: 'assistant', content: event.message || 'AI 处理失败，请稍后重试。' })
      break
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
  clearProgressMessages()
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.role === 'assistant' && !lastMsg.type) {
    lastMsg.content = answer
    return
  }
  messages.value.push({ role: 'assistant', content: answer })
}

function clearProgressMessages() {
  messages.value = messages.value.filter((msg) => msg.type !== 'tool_call')
}

function pushProgress(content: string, toolName?: string) {
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.role === 'assistant' && lastMsg.type === 'tool_call') {
    lastMsg.content = content
    lastMsg.toolName = toolName
    return
  }
  messages.value.push({ role: 'assistant', content, type: 'tool_call', toolName })
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBodyRef.value) {
      chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
    }
  })
}
</script>

<style scoped>
.ai-chat-page {
  height: 100%;
}
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  height: calc(100vh - 320px);
}
.chat-row {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  align-items: flex-start;
}
.row-user {
  flex-direction: row-reverse;
}
.bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
}
.bubble-user {
  background: #1677ff;
  color: #fff;
  border-radius: 12px 12px 4px 12px;
}
.bubble-ai {
  background: #f0f0f0;
  border-radius: 12px 12px 12px 4px;
}
.bubble-text :deep(.ai-chat-image) {
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  margin: 4px 0;
  display: block;
  cursor: pointer;
}
.bubble-text :deep(.ai-picture-link) {
  color: #1677ff;
}
.bubble-text :deep(.ai-image-basic-info) {
  font-weight: 500;
  color: #333;
}
.bubble-text :deep(.ai-report-title) {
  margin: 10px 0 6px;
  font-weight: 700;
  color: #1f1f1f;
}
.bubble-text :deep(.ai-report-row) {
  margin: 3px 0;
  line-height: 1.65;
}
.bubble-text :deep(strong) {
  font-weight: 700;
}
.typing {
  color: #999;
  font-style: italic;
}
.tool-tag {
  margin-bottom: 4px;
}
.chat-footer {
  padding: 12px 0 0;
  border-top: 1px solid #eee;
}
</style>
