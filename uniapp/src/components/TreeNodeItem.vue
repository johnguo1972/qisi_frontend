<template>
  <view class="tree-node-wrapper">
    <view
      :class="['tree-node', { active: isSelected }]"
      @click="handleClick"
      @contextmenu.prevent="onRightClick"
    >
      <view class="expand-btn" @click.stop="toggleExpand">
        <text class="expand-arrow">{{ arrow }}</text>
      </view>
      <text class="node-name">{{ node.name || '未命名' }}</text>
      <view class="node-actions">
        <view class="btn-plus" @click.stop="handleAddChild">+</view>
      </view>
    </view>

    <view v-if="isExpanded && hasChildren" class="tree-children">
      <tree-node-item
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :selected-id="selectedId"
        @select="$emit('select', $event)"
        @add-child="$emit('add-child', $event)"
        @rename="$emit('rename', $event)"
        @delete-node="$emit('delete-node', $event)"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface TreeNodeData {
  id: number
  name: string
  children?: TreeNodeData[]
  _expanded?: boolean
  [key: string]: any
}

const props = defineProps<{
  node: TreeNodeData
  selectedId: number | null
}>()

const emit = defineEmits<{
  select: [node: TreeNodeData]
  'add-child': [node: TreeNodeData]
  rename: [node: TreeNodeData]
  'delete-node': [node: TreeNodeData]
}>()

const isSelected = computed(() => props.selectedId === props.node.id)
const hasChildren = computed(() => Array.isArray(props.node.children) && props.node.children.length > 0)
const isExpanded = computed(() => !!props.node._expanded)
const arrow = computed(() => {
  if (!hasChildren.value) return ' '
  return isExpanded.value ? '▼' : '▶'
})

function handleClick() {
  emit('select', props.node)
}

function toggleExpand() {
  if (hasChildren.value) {
    props.node._expanded = !props.node._expanded
  }
}

function handleAddChild() {
  emit('add-child', props.node)
}

function onRightClick(e: any) {
  // Dispatch custom event for context menu
  const evt = new CustomEvent('tree-node-contextmenu', {
    detail: { node: props.node, x: e.clientX || 0, y: e.clientY || 0 },
  })
  window.dispatchEvent(evt)
}
</script>

<style scoped>
.tree-node-wrapper {
  user-select: none;
}

.tree-node {
  display: flex;
  align-items: center;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: 4px;
  margin: 2px 4px;
  font-size: 13px;
  color: #606266;
  transition: background 0.15s;
}

.tree-node:hover {
  background: #f5f7fa;
}

.tree-node.active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 500;
}

.expand-btn {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: pointer;
}

.expand-arrow {
  font-size: 10px;
  color: #909399;
}

.node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin: 0 4px;
}

.node-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.btn-plus {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: #909399;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
}

.btn-plus:hover {
  background: #409eff;
  color: #fff;
}

.tree-children {
  padding-left: 12px;
}
</style>
