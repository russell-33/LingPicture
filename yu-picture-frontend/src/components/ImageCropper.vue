<template>
  <a-modal
    class="image-cropper"
    v-model:visible="visible"
    title="编辑图片"
    :footer="false"
    @cancel="closeModal"
  >
    <!-- 图片裁切组件 -->
    <div class="cropper-stage" :class="{ 'remote-action-active': remoteActionTip }">
      <vue-cropper
        ref="cropperRef"
        :img="imageUrl"
        output-type="png"
        :info="true"
        :can-move-box="true"
        :fixed-box="false"
        :auto-crop="true"
        :center-box="true"
      />
      <transition name="remote-action-tip">
        <div v-if="remoteActionTip" class="remote-action-tip">
          {{ remoteActionTip }}
        </div>
      </transition>
    </div>
    <div style="margin-bottom: 16px" />
    <!-- 协同编辑操作 -->
    <div class="image-edit-actions" v-if="isTeamSpace">
      <a-space>
        <a-button v-if="editingUser" disabled>{{ editingUser.userName }} 正在编辑</a-button>
        <a-button v-if="canEnterEdit" type="primary" ghost @click="enterEdit">进入编辑</a-button>
        <a-button v-if="canExitEdit" danger ghost @click="exitEdit">退出编辑</a-button>
      </a-space>
    </div>
    <div style="margin-bottom: 16px" />
    <!-- 图片操作 -->
    <div class="image-cropper-actions">
      <a-space>
        <a-button @click="rotateLeft" :disabled="!canEdit">向左旋转</a-button>
        <a-button @click="rotateRight" :disabled="!canEdit">向右旋转</a-button>
        <a-button @click="changeScale(1)" :disabled="!canEdit">放大</a-button>
        <a-button @click="changeScale(-1)" :disabled="!canEdit">缩小</a-button>
        <a-button type="primary" :loading="loading" :disabled="!canEdit" @click="handleConfirm"
          >确认
        </a-button>
      </a-space>
    </div>
  </a-modal>
</template>

<script lang="ts" setup>
import { computed, onUnmounted, ref, watchEffect } from 'vue'
import { uploadPictureUsingPost } from '../api/pictureController.ts'
import { message } from 'ant-design-vue'
import { useLoginUserStore } from '../stores/useLoginUserStore.ts'
import PictureEditWebSocket from '../utils/pictureEditWebSocket.ts'
import { PICTURE_EDIT_ACTION_ENUM, PICTURE_EDIT_MESSAGE_TYPE_ENUM } from '../constants/picture.ts'
import { SPACE_TYPE_ENUM } from '../constants/space.ts'

interface Props {
  imageUrl?: string
  picture?: API.PictureVO
  spaceId?: number
  space?: API.SpaceVO
  onSuccess?: (newPicture: API.PictureVO) => void
}

const props = defineProps<Props>()

// 是否为团队空间
const isTeamSpace = computed(() => {
  return props.space?.spaceType === SPACE_TYPE_ENUM.TEAM
})

// 获取图片裁切器的引用
const cropperRef = ref()

const EDIT_ACTION_TEXT_MAP: Record<string, string> = {
  [PICTURE_EDIT_ACTION_ENUM.ZOOM_IN]: '放大',
  [PICTURE_EDIT_ACTION_ENUM.ZOOM_OUT]: '缩小',
  [PICTURE_EDIT_ACTION_ENUM.ROTATE_LEFT]: '向左旋转',
  [PICTURE_EDIT_ACTION_ENUM.ROTATE_RIGHT]: '向右旋转',
}

const LEGACY_EDIT_ACTION_MAP: Record<string, string> = {
  放大操作: PICTURE_EDIT_ACTION_ENUM.ZOOM_IN,
  缩小操作: PICTURE_EDIT_ACTION_ENUM.ZOOM_OUT,
  左旋操作: PICTURE_EDIT_ACTION_ENUM.ROTATE_LEFT,
  右旋操作: PICTURE_EDIT_ACTION_ENUM.ROTATE_RIGHT,
}

const remoteActionTip = ref('')
let remoteActionTimer: ReturnType<typeof setTimeout> | undefined

const normalizeEditAction = (editAction?: string) => {
  if (!editAction) {
    return undefined
  }
  return EDIT_ACTION_TEXT_MAP[editAction] ? editAction : LEGACY_EDIT_ACTION_MAP[editAction]
}

const showRemoteActionTip = (userName: string | undefined, action: string) => {
  const actionText = EDIT_ACTION_TEXT_MAP[action] || '编辑'
  remoteActionTip.value = `${userName || '协作者'} 正在${actionText}图片`
  if (remoteActionTimer) {
    clearTimeout(remoteActionTimer)
  }
  remoteActionTimer = setTimeout(() => {
    remoteActionTip.value = ''
  }, 1500)
}

const applyEditAction = (action: string) => {
  switch (action) {
    case PICTURE_EDIT_ACTION_ENUM.ROTATE_LEFT:
      cropperRef.value?.rotateLeft()
      break
    case PICTURE_EDIT_ACTION_ENUM.ROTATE_RIGHT:
      cropperRef.value?.rotateRight()
      break
    case PICTURE_EDIT_ACTION_ENUM.ZOOM_IN:
      cropperRef.value?.changeScale(1)
      break
    case PICTURE_EDIT_ACTION_ENUM.ZOOM_OUT:
      cropperRef.value?.changeScale(-1)
      break
  }
}

// 缩放比例
const changeScale = (num: number) => {
  cropperRef.value?.changeScale(num)
  if (num > 0) {
    editAction(PICTURE_EDIT_ACTION_ENUM.ZOOM_IN)
  } else {
    editAction(PICTURE_EDIT_ACTION_ENUM.ZOOM_OUT)
  }
}

// 向左旋转
const rotateLeft = () => {
  cropperRef.value?.rotateLeft()
  editAction(PICTURE_EDIT_ACTION_ENUM.ROTATE_LEFT)
}

// 向右旋转
const rotateRight = () => {
  cropperRef.value?.rotateRight()
  editAction(PICTURE_EDIT_ACTION_ENUM.ROTATE_RIGHT)
}

// 确认裁切
const handleConfirm = () => {
  cropperRef.value.getCropBlob((blob: Blob) => {
    // blob 为已经裁切好的文件
    const fileName = (props.picture?.name || 'image') + '.png'
    const file = new File([blob], fileName, { type: blob.type })
    // 上传图片
    handleUpload({ file })
  })
}

const loading = ref(false)

/**
 * 上传图片
 * @param file
 */
const handleUpload = async ({ file }: any) => {
  loading.value = true
  try {
    const params: API.PictureUploadRequest = props.picture ? { id: props.picture.id } : {}
    params.spaceId = props.spaceId
    const res = (await uploadPictureUsingPost(params, {}, file)) as any
    if (res.data.code === 0 && res.data.data) {
      message.success('图片上传成功')
      // 将上传成功的图片信息传递给父组件
      props.onSuccess?.(res.data.data)
      closeModal()
    } else {
      message.error('图片上传失败，' + res.data.message)
    }
  } catch (error) {
    console.error('图片上传失败', error)
    const errorMessage = error instanceof Error ? error.message : String(error)
    message.error('图片上传失败，' + errorMessage)
  }
  loading.value = false
}

// 是否可见
const visible = ref(false)

// 打开弹窗
const openModal = () => {
  visible.value = true
}

// 关闭弹窗
const closeModal = () => {
  visible.value = false
  // 断开 WebSocket 连接
  if (websocket) {
    websocket.disconnect()
  }
  editingUser.value = undefined
  remoteActionTip.value = ''
  if (remoteActionTimer) {
    clearTimeout(remoteActionTimer)
    remoteActionTimer = undefined
  }
}

// 暴露函数给父组件
defineExpose({
  openModal,
})

// --------- 实时编辑 ---------
const loginUserStore = useLoginUserStore()
const loginUser = loginUserStore.loginUser

// 正在编辑的用户
const editingUser = ref<API.UserVO>()
// 当前用户是否可进入编辑
const canEnterEdit = computed(() => {
  return !editingUser.value
})
// 正在编辑的用户是本人，可退出编辑
const canExitEdit = computed(() => {
  return editingUser.value?.id === loginUser.id
})
// 可以点击编辑图片的操作按钮
const canEdit = computed(() => {
  // 不是团队空间，默认就可以编辑
  if (!isTeamSpace.value) {
    return true
  }
  // 团队空间，只有编辑者才能协同编辑
  return editingUser.value?.id === loginUser.id
})

// 编写 WebSocket 逻辑
let websocket: PictureEditWebSocket | null

// 初始化 WebSocket 连接，绑定监听事件
const initWebsocket = () => {
  const pictureId = props.picture?.id
  if (!pictureId || !visible.value) {
    return
  }
  // 防止之前的连接未释放
  if (websocket) {
    websocket.disconnect()
  }
  // 创建 websocket 实例
  websocket = new PictureEditWebSocket(pictureId)
  // 建立连接
  websocket.connect()

  // 监听一系列的事件
  websocket.on(PICTURE_EDIT_MESSAGE_TYPE_ENUM.INFO, (msg) => {
    console.log('收到通知消息：', msg)
    message.info(msg.message)
  })

  websocket.on(PICTURE_EDIT_MESSAGE_TYPE_ENUM.ERROR, (msg) => {
    console.log('收到错误通知：', msg)
    message.info(msg.message)
  })

  websocket.on(PICTURE_EDIT_MESSAGE_TYPE_ENUM.ENTER_EDIT, (msg) => {
    console.log('收到进入编辑状态的消息：', msg)
    message.info(msg.message)
    editingUser.value = msg.user
  })

  websocket.on(PICTURE_EDIT_MESSAGE_TYPE_ENUM.EDIT_ACTION, (msg) => {
    console.log('收到编辑操作的消息：', msg)
    message.info(msg.message)
    const editAction = normalizeEditAction(msg.editAction)
    if (!editAction) {
      return
    }
    applyEditAction(editAction)
    showRemoteActionTip(msg.user?.userName, editAction)
  })

  websocket.on(PICTURE_EDIT_MESSAGE_TYPE_ENUM.EXIT_EDIT, (msg) => {
    console.log('收到退出编辑状态的消息：', msg)
    message.info(msg.message)
    editingUser.value = undefined
  })
}

// 监听属性和 visible 变化，初始化 WebSocket 连接
watchEffect(() => {
  // 只有团队空间，才初始化 WebSocket 连接
  if (isTeamSpace.value) {
    initWebsocket()
  }
})

// 组件销毁时，断开 WebSocket 连接
onUnmounted(() => {
  // 断开 WebSocket 连接
  if (websocket) {
    websocket.disconnect()
  }
  editingUser.value = undefined
  if (remoteActionTimer) {
    clearTimeout(remoteActionTimer)
  }
})

// 进入编辑状态
const enterEdit = () => {
  if (websocket) {
    // 发送进入编辑状态的请求
    websocket.sendMessage({
      type: PICTURE_EDIT_MESSAGE_TYPE_ENUM.ENTER_EDIT,
    })
  }
}

// 退出编辑状态
const exitEdit = () => {
  if (websocket) {
    // 发送退出编辑状态的请求
    websocket.sendMessage({
      type: PICTURE_EDIT_MESSAGE_TYPE_ENUM.EXIT_EDIT,
    })
  }
}

// 编辑图片操作
const editAction = (action: string) => {
  if (websocket) {
    // 发送编辑操作的请求
    websocket.sendMessage({
      type: PICTURE_EDIT_MESSAGE_TYPE_ENUM.EDIT_ACTION,
      editAction: action,
    })
  }
}
</script>

<style>
.image-cropper {
  text-align: center;
}

.image-cropper .cropper-stage {
  position: relative;
  border-radius: 4px;
  overflow: hidden;
}

.image-cropper .vue-cropper {
  height: 400px !important;
}

.image-cropper .remote-action-active {
  box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.28);
}

.image-cropper .remote-action-tip {
  position: absolute;
  top: 16px;
  left: 50%;
  z-index: 2;
  transform: translateX(-50%);
  padding: 8px 16px;
  border-radius: 999px;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  background: rgba(22, 119, 255, 0.9);
  box-shadow: 0 8px 20px rgba(22, 119, 255, 0.25);
}

.remote-action-tip-enter-active,
.remote-action-tip-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.remote-action-tip-enter-from,
.remote-action-tip-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}
</style>
