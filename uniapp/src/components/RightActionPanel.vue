<template>
  <view class="right-panel">
    <button class="action-btn btn-primary" @click="$emit('random')">随机选题</button>
    <button class="action-btn" @click="$emit('query-params')">查询参数</button>
    <button class="action-btn" @click="$emit('refresh')">刷新题目</button>
    <button class="action-btn btn-success" @click="$emit('toggle-answer')">
      {{ allShown ? '关闭答案' : '显示答案' }}
    </button>
    <button class="action-btn" @click="$emit('share-multiple')">分享多题</button>
    <button class="action-btn" @click="$emit('share-history')">分享历史</button>
    <button class="action-btn btn-warning" @click="$emit('basket')">加入篮子</button>
    <button class="action-btn btn-ai" @click="$emit('ai-process')">AI处理</button>
    <view class="basket-count" v-if="basketCount > 0">
      &#128465; 篮子: {{ basketCount }}题
    </view>
  </view>
</template>

<script setup lang="ts">
defineProps<{
  basketCount?: number
  allShown?: boolean
}>()

defineEmits(['random', 'query-params', 'refresh', 'toggle-answer', 'share-multiple', 'share-history', 'basket', 'ai-process'])
</script>

<style scoped>
.right-panel {
  width: 120px; background: #fff;
  border-left: 1px solid #e4e7ed;
  padding: 12px 8px;
  display: flex; flex-direction: column; gap: 8px;
  flex-shrink: 0;
  overflow-y: auto;
}
.action-btn {
  width: 100%; padding: 8px 6px; border-radius: 4px;
  font-size: 12px; border: 1px solid #dcdfe6;
  background: #fff; color: #606266; cursor: pointer;
  line-height: 1.2;
}
.action-btn:hover { background: #f5f7fa; color: #606266; }
.btn-primary { background: #409eff; color: #fff; border-color: #409eff; }
.btn-primary:hover { background: #66b1ff; color: #fff; }
.btn-success { background: #67c23a; color: #fff; border-color: #67c23a; }
.btn-success:hover { background: #85ce61; color: #fff; }
.btn-warning { background: #e6a23c; color: #fff; border-color: #e6a23c; }
.btn-ai { background: #9254de; color: #fff; border-color: #9254de; }
.btn-warning:hover { background: #ebb563; color: #fff; }
.basket-count {
  font-size: 12px; color: #409eff; text-align: center;
  padding: 6px; background: #ecf5ff; border-radius: 4px;
}
</style>
