<template>
  <view class="dir-tree">
    <view class="root-actions">
      <button class="btn-add-root" size="mini" @click="$emit('add-root')">+ 根节点</button>
    </view>
    <view v-if="loading" class="loading">加载中...</view>
    <view v-else-if="nodes.length === 0" class="empty">暂无目录，请点击上方按钮添加</view>
    <view v-else class="tree-list">
      <tree-node-item
        v-for="node in nodes"
        :key="node.id"
        :node="node"
        :selected-id="selectedId"
        @select="handleSelect"
        @add-child="$emit('add-child', $event)"
        @rename="$emit('rename', $event)"
        @delete-node="$emit('delete-node', $event)"
      />
    </view>

    <!-- Context menu -->
    <view v-if="contextVisible" class="ctx-overlay" @click="hideCtx">
      <view class="ctx-menu" :style="{ top: ctxY + 'px', left: ctxX + 'px' }" @click.stop @contextmenu.prevent.stop>
        <view class="ctx-item" @click="doCtx('add')">+ 添加子节点</view>
        <view class="ctx-item" @click="doCtx('rename')">&#9998; 重命名</view>
        <view class="ctx-item danger" @click="doCtx('delete')">&#128465; 删除</view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import TreeNodeItem from './TreeNodeItem.vue'

interface TreeNodeData {
  id: number
  name: string
  children?: TreeNodeData[]
  _expanded?: boolean
  [key: string]: any
}

defineProps<{
  nodes: TreeNodeData[]
  loading?: boolean
}>()

const emit = defineEmits<{
  select: [node: TreeNodeData]
  'add-root': []
  'add-child': [node: TreeNodeData]
  rename: [node: TreeNodeData]
  'delete-node': [node: TreeNodeData]
}>()

const selectedId = ref<number | null>(null)
const contextVisible = ref(false)
const ctxX = ref(0)
const ctxY = ref(0)
const ctxNode = ref<TreeNodeData | null>(null)

function handleSelect(node: TreeNodeData) {
  selectedId.value = node.id
  emit('select', node)
}

function onTreeNodeCtx(e: Event) {
  const detail = (e as CustomEvent).detail
  ctxX.value = detail.x
  ctxY.value = detail.y
  ctxNode.value = detail.node
  contextVisible.value = true
}

function hideCtx() {
  contextVisible.value = false
  ctxNode.value = null
}

function doCtx(action: string) {
  const node = ctxNode.value
  if (!node) return
  hideCtx()
  if (action === 'add') emit('add-child', node)
  else if (action === 'rename') emit('rename', node)
  else if (action === 'delete') emit('delete-node', node)
}

onMounted(() => {
  window.addEventListener('tree-node-contextmenu', onTreeNodeCtx as EventListener)
})

onUnmounted(() => {
  window.removeEventListener('tree-node-contextmenu', onTreeNodeCtx as EventListener)
})
</script>

<style scoped>
.dir-tree {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.root-actions {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.btn-add-root {
  width: 100%;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 12px;
}

.btn-add-root::after {
  border: none;
}

.loading,
.empty {
  text-align: center;
  color: #909399;
  padding: 40px 0;
  font-size: 13px;
}

.tree-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

/* Context menu */
.ctx-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
}

.ctx-menu {
  position: fixed;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  padding: 4px 0;
  min-width: 160px;
  z-index: 10000;
}

.ctx-item {
  padding: 10px 16px;
  font-size: 13px;
  color: #303133;
  cursor: pointer;
  transition: background 0.15s;
}

.ctx-item:hover {
  background: #f5f7fa;
}

.ctx-item.danger {
  color: #f56c6c;
}

.ctx-item.danger:hover {
  background: #fef0f0;
}
</style>
