<template>
  <view class="edit-page">
    <TeacherSidebar activeItem="bank" />

    <!-- 右侧内容区 -->
    <view class="main" v-if="question">
      <view class="split-layout">
        <!-- 左侧: 图片查看器 -->
        <view class="image-panel">
          <view v-if="photoImages.length > 0" class="photo-images-section">
            <text class="section-label">试题原图 ({{ photoImages.length }})</text>
            <view class="photo-images-scroll">
              <view v-for="(img, idx) in photoImages" :key="idx" class="photo-image-item">
                <image :src="img.url" mode="widthFix" class="photo-image" @click="previewPhotoImage(img.url)" />
                <text class="photo-image-label">{{ img.description || "图" + (idx+1) }}</text>
              </view>
            </view>
          </view>

          <view class="page-nav-bar">
            <button size="mini" :disabled="currentPage <= 1" @click="prevPage">上页</button>
            <text class="page-label">第 {{ currentPage }} / {{ totalPages }} 页</text>
            <button size="mini" :disabled="currentPage >= totalPages" @click="nextPage">下页</button>
          </view>

          <view class="zoom-controls">
            <button size="mini" @click="zoomOut">-</button>
            <text class="zoom-label">{{ Math.round(zoom * 100) }}%</text>
            <button size="mini" @click="zoomIn">+</button>
            <button size="mini" @click="startCalibration" :type="calibrating ? 'warn' : 'default'">{{ calibrating ? '校准中…点十字' : '校准坐标' }}</button>
            <button size="mini" v-if="(cropOffset.x || cropOffset.y) && !calibrating" @click="resetCalibration">清除({{cropOffset.x}},{{cropOffset.y}})</button>
            <text v-if="(cropOffset.x || cropOffset.y) && !calibrating" class="calib-nudge-label">选框微调</text>
            <button size="mini" v-if="(cropOffset.x || cropOffset.y) && !calibrating" @click="nudgeCalib(0,-5)">↑</button>
            <button size="mini" v-if="(cropOffset.x || cropOffset.y) && !calibrating" @click="nudgeCalib(-5,0)">←</button>
            <button size="mini" v-if="(cropOffset.x || cropOffset.y) && !calibrating" @click="nudgeCalib(5,0)">→</button>
            <button size="mini" v-if="(cropOffset.x || cropOffset.y) && !calibrating" @click="nudgeCalib(0,5)">↓</button>
          </view>

          <view class="image-container" ref="imageContainerRef" @mousedown="onCropStart" @mousemove="onCropMove" @mouseup="onCropEnd" :class="{ 'add-mode': addNewMode, 'calibrating': calibrating }">
            <view class="image-wrap" :style="{ transform: 'scale(' + zoom + ')' }">
              <image
                :src="currentImageSrc"
                mode="widthFix"
                class="page-image"
                @load="onImageLoad"
              />
              <view
                v-if="cropRect"
                class="crop-overlay"
                :style="{ left: cropRect.x + 'px', top: cropRect.y + 'px', width: cropRect.w + 'px', height: cropRect.h + 'px' }"
              >
                <view class="crop-border" :class="{ 'add-border': addNewMode }"></view>
              </view>
            </view>
          </view>
          <view v-if="addNewMode" class="add-mode-actions">
            <button size="mini" type="primary" :disabled="!cropRect" @click="doCropAndRecognize">框选并AI识别</button>
            <button size="mini" @click="cancelAddMode">取消</button>
          </view>
          <view v-if="calibrating" class="calib-crosshair" :style="{ top: calibPos.y + 'px', left: calibPos.x + 'px' }"></view>
          <view v-if="calibrating" class="calib-hint">把鼠标对准上方红色十字中心，点一下完成校准</view>

          <view class="crop-actions">
            <button size="mini" type="primary" :disabled="!cropRect" @click="doCrop">裁剪此区域</button>
            <button size="mini" :disabled="!cropRect" @click="clearCrop">清除选框</button>
          </view>

          <view class="image-list-section">
            <view class="image-list-header">
              <text class="list-title">插图管理 ({{ images.length }})</text>
              <text class="list-hint">划选原图以新增</text>
            </view>
            <view class="image-list-body">
              <view v-for="(img, index) in images" :key="img.id" class="image-list-item">
                <image :src="getImageUrl(img.file_path)" mode="aspectFill" class="thumb-img" />
                <text class="thumb-desc">{{ img.description || '裁剪图' }}</text>
                <view class="thumb-sort">
                  <text class="sort-arrow" @click="moveImageUp(index)" :class="{ disabled: index === 0 }">▲</text>
                  <text class="sort-arrow" @click="moveImageDown(index)" :class="{ disabled: index === images.length - 1 }">▼</text>
                </view>
                <button size="mini" class="thumb-insert" @click="handleInsertImage(img.id)">插入</button>
                <button size="mini" type="warn" class="thumb-delete" @click="handleDeleteImage(img.id)">删除</button>
              </view>
              <view v-if="images.length === 0" class="empty-images">
                <text>暂无插图</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 右侧: 编辑表单 -->
        <view class="edit-panel">
          <view class="form-toolbar">
            <view class="toolbar-left">
              <select v-model="form.question_type" class="form-select-sm">
                <option value="single_choice">单选题</option>
                <option value="multiple_choice">多选题</option>
                <option value="fill_blank">填空题</option>
                <option value="solution">解答题</option>
              </select>
              <view class="info-group">
                <text class="info-label">题号:</text>
                <input v-model="form.question_no" class="form-input-sm info-input" placeholder="题号" />
                <text class="info-label">页码:</text>
                <input v-model.number="form.page_start" type="number" class="form-input-sm info-input-sm" placeholder="起" />
                <text class="info-separator">-</text>
                <input v-model.number="form.page_end" type="number" class="form-input-sm info-input-sm" placeholder="止" />
              </view>
            </view>
            <view class="toolbar-right">
              <view class="diff-badge" :class="'diff-l' + (form.difficulty || 0)">
                难度第{{ ['','一','二','三','四','五'][form.difficulty] || '?' }}级
              </view>
            </view>
          </view>

          <view class="question-actions">
            <button size="mini" @click="handleBackToList">⟵ 返回列表</button>
            <button size="mini" type="info" @click="handlePrevQuestion" :disabled="!paperId">← 上一题</button>
            <button size="mini" type="info" @click="handleNextQuestion" :disabled="!paperId">下一题 →</button>
            <button size="mini" type="danger" @click="handleDeleteQuestion">删除本题</button>
            <button size="mini" type="primary" @click="startAddNewQuestion">框选新增试题</button>
          </view>

          <view class="form-group">
            <text class="form-label">题干</text>
            <textarea id="textarea-stem" class="form-textarea form-textarea-auto" v-model="form.stem" placeholder="输入题干内容" rows="1" @input="onPreviewChange" @focus="activeTextarea = 'stem'" />
            <view class="math-preview" v-html="stemPreview"></view>
          </view>

          <view class="form-group">
            <text class="form-label">答案</text>
            <textarea id="textarea-answer" class="form-textarea form-textarea-auto" v-model="form.answer" placeholder="输入答案" rows="1" @input="onPreviewChange" @focus="activeTextarea = 'answer'" />
            <view class="math-preview" v-html="answerPreview"></view>
          </view>

          <view v-if="form.question_type === 'single_choice' || form.question_type === 'multiple_choice'" class="form-group">
            <text class="form-label">选项</text>
            <view class="options-list">
              <view v-for="(opt, index) in form.options" :key="opt.label" class="option-row">
                <text class="option-label">{{ opt.label }}.</text>
                <view class="option-content-wrapper">
                  <textarea :id="'textarea-option-' + index" v-model="opt.content" class="option-textarea option-textarea-auto" :placeholder="'选项 ' + opt.label + ' 的内容'" rows="1" @input="onPreviewChange" @focus="onOptionFocus(index)" />
                  <view class="math-preview option-preview" v-html="optionPreviews[index] || ''"></view>
                </view>
              </view>
            </view>
          </view>

          <view class="form-group">
            <text class="form-label">知识点</text>
            <view class="kp-selector">
              <input v-model="knowledgeSearch" class="kp-search-input" placeholder="搜索知识点（输入关键词后从下拉列表选择）" />
              <text class="kp-debug">已加载{{ allKpList.length }}条，匹配{{ filteredKpList.length }}条</text>
              <view v-if="knowledgeSearch && filteredKpList.length > 0" class="kp-dropdown">
                <view v-for="kp in filteredKpList.slice(0, 50)" :key="kp.id" class="kp-dropdown-item" @click="toggleKnowledgePoint(kp)">
                  <view class="kp-checkbox"><text v-if="isKnowledgePointSelected(kp.id)">✓</text></view>
                  <text class="kp-item-label">{{ kp.module || kp.label || '未知' }}</text>
                </view>
              </view>
            </view>
            <view v-if="selectedKps.length > 0" class="kp-tags">
              <view v-for="kp in selectedKps" :key="kp.id" class="kp-tag">
                <text>{{ kp.module || kp.label || '未知' }}</text>
                <text class="kp-tag-remove" @click="removeKnowledgePoint(kp.id)">&times;</text>
              </view>
            </view>
            <view v-else class="kp-empty"><text>暂无关联知识点，请在搜索框输入关键词选择</text></view>
          </view>

          <view class="form-group">
            <text class="form-label">解析</text>
            <textarea id="textarea-analysis" class="form-textarea form-textarea-auto" v-model="form.analysis" placeholder="输入解析" rows="1" @input="onPreviewChange" @focus="activeTextarea = 'analysis'" />
            <view class="math-preview" v-html="analysisPreview"></view>
          </view>

          <view class="form-group">
            <text class="form-label">解答</text>
            <textarea id="textarea-solution" class="form-textarea form-textarea-auto" v-model="form.solution" placeholder="输入解答" rows="1" @input="onPreviewChange" @focus="activeTextarea = 'solution'" />
            <view class="math-preview" v-html="solutionPreview"></view>
          </view>

          <view class="form-actions-bar">
            <view class="actions-left"><text class="shortcut-hint">Ctrl+S: 保存 | Ctrl+Enter: 确认</text></view>
            <view class="actions-right">
              <button size="mini" type="warning" @click="handleReparse" :loading="reparseLoading">重解析</button>
              <button size="mini" type="primary" @click="handleSave" :loading="saving" style="background: #1a237e">保存修改</button>
              <button size="mini" type="success" @click="handleConfirm">确认正确</button>
            </view>
          </view>
        </view>
      </view>
    </view>

    <view v-else-if="loading" class="loading"><text>加载中...</text></view>
    <view v-else class="empty"><text>题目不存在</text></view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getQuestionDetail, updateQuestion, confirmQuestion, cropQuestionImage, deleteQuestionImage, getQuestionAssets } from '@/api/questions'
import { renderWithKatex } from '@/utils/katex-renderer'
import { renderImagePlaceholders } from '@/utils/image-placeholder'
import { filterKnowledgePoints, type KnowledgePoint } from '@/utils/knowledge-filter'
import { get } from '@/utils/request'
import TeacherSidebar from '@/components/TeacherSidebar.vue'

const question = ref<any>(null)
const loading = ref(true)
const saving = ref(false)
const reparseLoading = ref(false)
const form = ref({ stem: '', answer: '', analysis: '', solution: '', difficulty: 1, question_type: '', question_no: '', page_start: 1, page_end: 1, options: [{ label: 'A', content: '' }, { label: 'B', content: '' }, { label: 'C', content: '' }, { label: 'D', content: '' }] })
const pages = ref<any[]>([])
const currentPage = ref(1)
const totalPages = ref(1)
const currentImageSrc = ref('')
const zoom = ref(0.7)
const cropRect = ref<{ x: number; y: number; w: number; h: number } | null>(null)
const imgNaturalSize = ref<{ w: number; h: number }>({ w: 0, h: 0 })
const isCropping = ref(false)
const cropStart = ref<{ x: number; y: number } | null>(null)
const addNewMode = ref(false)
const imageContainerRef = ref<HTMLElement | null>(null)
const cropOffset = ref<{ x: number; y: number }>((() => { try { const s = sessionStorage.getItem('cropOffset'); return s ? JSON.parse(s) : { x: 0, y: 0 } } catch { return { x: 0, y: 0 } } })())
const calibrating = ref(false)
const calibPos = ref<{ x: number; y: number }>({ x: 0, y: 0 })
let questionId = 0
const paperId = ref(0)
const questionList = ref<any[]>([])
const currentQuestionIndex = ref(-1)
const images = ref<any[]>([])
const photoImages = ref<any[]>([])
const stemPreview = ref('')
const answerPreview = ref('')
const analysisPreview = ref('')
const solutionPreview = ref('')
const optionPreviews = ref<string[]>([])
const activeTextarea = ref<'stem' | 'answer' | 'analysis' | 'solution' | 'option'>('stem')
const activeOptionIndex = ref(-1)
const knowledgeSearch = ref('')
const allKpList = ref<KnowledgePoint[]>([])
const selectedKps = ref<KnowledgePoint[]>([])
const filteredKpList = computed(() => filterKnowledgePoints(allKpList.value, knowledgeSearch.value))
let previewDebounceTimer: ReturnType<typeof setTimeout> | null = null

function isKnowledgePointSelected(id: number) { return selectedKps.value.some(kp => kp.id === id) }
function toggleKnowledgePoint(kp: KnowledgePoint) { if (isKnowledgePointSelected(kp.id)) removeKnowledgePoint(kp.id); else addKnowledgePoint(kp); knowledgeSearch.value = '' }
function addKnowledgePoint(kp: KnowledgePoint) { if (!selectedKps.value.some(s => s.id === kp.id)) selectedKps.value.push(kp); knowledgeSearch.value = '' }
function removeKnowledgePoint(id: number) { selectedKps.value = selectedKps.value.filter(kp => kp.id !== id) }
function schedulePreviewUpdate() { if (previewDebounceTimer) clearTimeout(previewDebounceTimer); previewDebounceTimer = setTimeout(() => updatePreviews(), 200) }
async function updatePreviews() {
  stemPreview.value = await renderImagePlaceholders(await renderWithKatex(form.value.stem), images.value)
  answerPreview.value = await renderImagePlaceholders(await renderWithKatex(form.value.answer), images.value)
  analysisPreview.value = await renderImagePlaceholders(await renderWithKatex(form.value.analysis), images.value)
  solutionPreview.value = await renderImagePlaceholders(await renderWithKatex(form.value.solution), images.value)
  // Update option previews
  const newOptionPreviews: string[] = []
  for (const opt of form.value.options) {
    newOptionPreviews.push(await renderImagePlaceholders(await renderWithKatex(opt.content), images.value))
  }
  optionPreviews.value = newOptionPreviews
}
function getImageUrl(path: string) { if (!path) return ''; if (path.startsWith('http')) return path; const fixed = path.replace(/\\/g, '/'); return window.location.origin + '/media/' + (fixed.startsWith('/') ? fixed.slice(1) : fixed) }
function previewPhotoImage(url: string) { uni.previewImage({ urls: [url] }) }
function startAddNewQuestion() { addNewMode.value = true; clearCrop(); uni.showToast({ title: '请在原图上框选试题区域', icon: 'none', duration: 2000 }) }
function cancelAddMode() { addNewMode.value = false; clearCrop() }
async function doCropAndRecognize() {
  console.log('[doCrop] triggered, cropRect=', cropRect.value, 'qid=', question.value?.id);
  if (!cropRect.value || !question.value) { uni.showToast({ title: '请先在原图上拖动框选区域', icon: 'none' }); return };
  addNewMode.value = false;
  uni.showLoading({ title: '正在AI识别...' });
  try {
    const _nat = cropToNatural();
    if (!_nat) return;
    const cropRes = await cropQuestionImage(question.value.id, _nat, currentPage.value);
    if (cropRes.code !== 0) { uni.hideLoading(); uni.showToast({ title: '裁剪失败', icon: 'none' }); return }
    const formData = new FormData();
    formData.append('crop_file_path', cropRes.data.file_path);
    formData.append('page_no', String(currentPage.value));
    if (paperId.value) formData.append('paper_id', String(paperId.value));
    const token = uni.getStorageSync('accessToken');
    const aiRes = await fetch('/api/v1/questions/photo-create/', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData,
    });
    const aiData = await aiRes.json();
    uni.hideLoading();
    if (aiData.code === 0 && aiData.data?.question_id) {
      uni.showModal({
        title: 'AI识别成功',
        content: `已识别新题目`,
        showCancel: true,
        cancelText: '继续编辑',
        confirmText: '查看新题',
        success: (res) => {
          if (res.confirm) uni.navigateTo({ url: `/pages/teacher/question-edit?id=${aiData.data.question_id}` })
        },
      })
    } else {
      uni.showToast({ title: aiData.message || 'AI识别失败', icon: 'none' })
    }
  } catch (e: any) {
    uni.hideLoading();
    uni.showToast({ title: e?.message || 'AI识别失败', icon: 'none' })
  }
  clearCrop()
}
async function handleDeleteQuestion() {
  if (!question.value) return;
  uni.showModal({ title: '确认删除', content: `确定要删除题目 "${question.value.question_no}" 吗？`, success: async (res) => {
    if (!res.confirm) return;
    try {
      const { del } = await import('@/utils/request');
      await del(`/review/questions/${question.value.id}/delete/`);
      uni.showToast({ title: '删除成功', icon: 'success' });
      setTimeout(() => { uni.reLaunch({ url: paperId.value ? `/pages/teacher/review-list?paper_id=${paperId.value}` : '/pages/teacher/review-list' }) }, 400);
    } catch (e: any) {
      uni.showToast({ title: e?.message || '删除失败', icon: 'none' });
    }
  } });
}
function getActiveTextareaEl(): HTMLElement | null {
  if (activeTextarea.value === 'option') return activeOptionIndex.value >= 0 ? document.getElementById('textarea-option-' + activeOptionIndex.value) : null
  const m: Record<string, string> = { stem: 'textarea-stem', answer: 'textarea-answer', analysis: 'textarea-analysis', solution: 'textarea-solution' }
  return document.getElementById(m[activeTextarea.value] || 'textarea-stem')
}
function onOptionFocus(index: number) { activeTextarea.value = 'option'; activeOptionIndex.value = index }
function handleInsertImage(imageId: number) {
  const placeholder = `{{image_${imageId}}}`
  let pos: number | undefined
  const el = getActiveTextareaEl()
  if (el) { const native = el.tagName === 'TEXTAREA' ? (el as HTMLTextAreaElement) : (el.querySelector('textarea') as HTMLTextAreaElement | null); if (native) { try { pos = native.selectionStart } catch {} } }
  if (activeTextarea.value === 'option') {
    const opt = form.value.options[activeOptionIndex.value]
    if (!opt) { uni.showToast({ title: '请先点击要插入的选项', icon: 'none' }); return }
    const text = opt.content || ''; const p = pos ?? text.length
    opt.content = text.slice(0, p) + placeholder + text.slice(p)
  } else {
    const field = activeTextarea.value as 'stem' | 'answer' | 'analysis' | 'solution'
    const text = (form.value[field] as string) || ''; const p = pos ?? text.length
    ;(form.value as any)[field] = text.slice(0, p) + placeholder + text.slice(p)
  }
  schedulePreviewUpdate()
}
function moveImageUp(index: number) { if (index <= 0) return; const temp = images.value[index]; images.value[index] = images.value[index - 1]; images.value[index - 1] = temp }
function moveImageDown(index: number) { if (index >= images.value.length - 1) return; const temp = images.value[index]; images.value[index] = images.value[index + 1]; images.value[index + 1] = temp }
async function loadQuestion(id: number) { loading.value = true; try { const res = await getQuestionDetail(id); if (res.success && res.data) { question.value = res.data; const q = res.data; paperId.value = q.paper || 0; if (paperId.value) { try { const { getPaperQuestions } = await import('@/api/questions'); const listRes = await getPaperQuestions(paperId.value); questionList.value = listRes.data?.data || listRes.data || []; currentQuestionIndex.value = questionList.value.findIndex((item: any) => item.id === id) } catch {} } form.value = { stem: q.stem || '', answer: q.answer || '', analysis: q.analysis || '', solution: q.solution || '', difficulty: q.difficulty || 1, question_type: q.question_type || '', question_no: q.question_no || '', page_start: q.page_start || 1, page_end: q.page_end || 1, options: q.options && q.options.length > 0 ? q.options.map((o: any) => ({ label: o.option_label || o.label || '', content: o.content || '' })) : [{ label: 'A', content: '' }, { label: 'B', content: '' }, { label: 'C', content: '' }, { label: 'D', content: '' }] }; images.value = q.images || [] } try { const assetsRes = await getQuestionAssets(id); if (assetsRes.code === 0 && assetsRes.data) { pages.value = assetsRes.data.pages || []; if (pages.value.length > 0) { totalPages.value = pages.value.length; currentPage.value = Math.min(question.value?.page_start || 1, totalPages.value) } if (assetsRes.data.images?.length > 0) images.value = assetsRes.data.images } } catch {} updateCurrentImage(); await updatePreviews() } catch { uni.showToast({ title: '加载失败', icon: 'none' }) } finally { loading.value = false } }
function updateCurrentImage() { const page = pages.value[currentPage.value - 1]; if (page?.image_path) currentImageSrc.value = getImageUrl(page.image_path); clearCrop() }
function prevPage() { if (currentPage.value > 1) { currentPage.value--; updateCurrentImage() } }
function nextPage() { if (currentPage.value < totalPages.value) { currentPage.value++; updateCurrentImage() } }
function zoomIn() { zoom.value = Math.min(3.0, zoom.value + 0.1) }
function zoomOut() { zoom.value = Math.max(0.1, zoom.value - 0.1) }
function onImageLoad(e: any) { const d = e?.detail || {}; imgNaturalSize.value = { w: d.width || 0, h: d.height || 0 }; clearCrop() }
async function loadKnowledgePoints() { try { const params: Record<string, string> = {}; const res = await get('/dicts/knowledge-points', params); allKpList.value = Array.isArray(res.data) ? res.data : []; if (question.value?.knowledge_points && Array.isArray(question.value.knowledge_points)) { selectedKps.value = question.value.knowledge_points.map((kp: any) => { const id = typeof kp === 'object' ? (kp.id || kp.knowledge_point_id) : kp; return allKpList.value.find(p => p.id === id) }).filter(Boolean) } } catch {} }
function getEventPos(e: MouseEvent): { x: number; y: number } { try { const imgEl = document.querySelector('.page-image') as HTMLElement; if (imgEl) { const rect = imgEl.getBoundingClientRect(); return { x: e.clientX - rect.left + cropOffset.value.x, y: e.clientY - rect.top + cropOffset.value.y } } } catch {} return { x: (e.clientX || 0) + cropOffset.value.x, y: (e.clientY || 0) + cropOffset.value.y } }
function cropToNatural(): { x1: number; y1: number; x2: number; y2: number } | null {
  const c = cropRect.value; if (!c) return null;
  const imgEl = document.querySelector('.page-image') as HTMLElement | null;
  if (imgEl && imgNaturalSize.value.w > 0) {
    const rect = imgEl.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      const sx = (imgNaturalSize.value.w / rect.width) * zoom.value;
      const sy = (imgNaturalSize.value.h / rect.height) * zoom.value;
      return { x1: Math.round(c.x * sx), y1: Math.round(c.y * sy), x2: Math.round((c.x + c.w) * sx), y2: Math.round((c.y + c.h) * sy) };
    }
  }
  return { x1: Math.round(c.x), y1: Math.round(c.y), x2: Math.round(c.x + c.w), y2: Math.round(c.y + c.h) };
}
function onCropStart(e: MouseEvent) {
  if (calibrating.value) { cropOffset.value = { x: Math.round(calibPos.value.x - e.clientX), y: Math.round(calibPos.value.y - e.clientY) }; try { sessionStorage.setItem('cropOffset', JSON.stringify(cropOffset.value)) } catch {} calibrating.value = false; uni.showToast({ title: `校准完成 (补偿 ${cropOffset.value.x}, ${cropOffset.value.y})`, icon: 'none', duration: 2000 }); return }
  if ((e.target as HTMLElement)?.closest?.('.add-mode-actions')) return; console.log('[crop] MOUSEDOWN at', e.clientX, e.clientY); isCropping.value = true; const rawPos = getEventPos(e); const pos = { x: rawPos.x / zoom.value, y: rawPos.y / zoom.value }; cropStart.value = pos; cropRect.value = null
}
function onCropMove(e: MouseEvent) { if (!isCropping.value || !cropStart.value) return; const rawPos = getEventPos(e); const pos = { x: rawPos.x / zoom.value, y: rawPos.y / zoom.value }; const start = cropStart.value; const x = Math.min(start.x, pos.x); const y = Math.min(start.y, pos.y); const w = Math.abs(pos.x - start.x); const h = Math.abs(pos.y - start.y); if (w > 5 && h > 5) { cropRect.value = { x, y, w, h } } }
function onCropEnd() { isCropping.value = false }
function startCalibration() { clearCrop(); calibrating.value = true; const el = document.querySelector('.image-container') as HTMLElement | null; if (el) { const r = el.getBoundingClientRect(); calibPos.value = { x: r.left + r.width / 2, y: r.top + r.height / 2 } }; uni.showToast({ title: '请把鼠标对准红色十字中心，点击一次', icon: 'none', duration: 2500 }) }
function resetCalibration() { cropOffset.value = { x: 0, y: 0 }; try { sessionStorage.removeItem('cropOffset') } catch {} uni.showToast({ title: '已清除校准', icon: 'none' }) }
function nudgeCalib(dx: number, dy: number) { cropOffset.value = { x: cropOffset.value.x + dx, y: cropOffset.value.y + dy }; try { sessionStorage.setItem('cropOffset', JSON.stringify(cropOffset.value)) } catch {} }
function clearCrop() { cropRect.value = null; cropStart.value = null }
async function doCrop() {
  if (!cropRect.value || !question.value) return
  const _nat = cropToNatural()
  if (!_nat) return
  const { x1, y1, x2, y2 } = _nat
  try {
    await cropQuestionImage(question.value.id, { x1, y1, x2, y2 }, currentPage.value)
    uni.showToast({ title: '裁剪成功', icon: 'success' })
    const assetsRes = await getQuestionAssets(questionId)
    if (assetsRes.data?.images) images.value = assetsRes.data.images
  } catch (e) {
    uni.showToast({ title: '裁剪失败', icon: 'none' })
  }
  clearCrop()
}
async function handleDeleteImage(imageId: number) {
  if (!question.value || !imageId) return
  uni.showModal({
    title: '确认删除', content: '确定删除此插图？',
    success: async (res) => {
      if (res.confirm) {
        try {
          await deleteQuestionImage(questionId, imageId)
          const assetsRes = await getQuestionAssets(questionId)
          if (assetsRes.data?.images) images.value = assetsRes.data.images
          uni.showToast({ title: '已删除', icon: 'success' })
        } catch (e) {
          uni.showToast({ title: '删除失败', icon: 'none' })
        }
      }
    }
  })
}
function onPreviewChange() { schedulePreviewUpdate() }
async function handleSave() {
  if (!question.value) return
  saving.value = true
  try {
    await updateQuestion(question.value.id, {
      ...form.value,
      knowledge_points: selectedKps.value.map(kp => ({ id: kp.id, module: kp.module }))
    })
    uni.showToast({ title: '保存成功', icon: 'success' })
  } catch (e: any) {
    uni.showToast({ title: e?.message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}
async function handleConfirm() {
  if (!question.value) return
  try {
    await confirmQuestion(question.value.id)
    uni.showToast({ title: '已确认', icon: 'success' })
    handleNextQuestion()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '确认失败', icon: 'none' })
  }
}
async function handleReparse() {
  if (!question.value) return
  uni.showModal({
    title: '确认重解析', content: '确定要重新解析此题目？',
    success: async (res) => {
      if (res.confirm) {
        reparseLoading.value = true
        try {
          const { aiProcessQuestion } = await import('@/api/questions')
          await aiProcessQuestion(questionId)
          uni.showToast({ title: '开始重新解析', icon: 'success' })
        } catch (e) {
          uni.showToast({ title: '重新解析失败', icon: 'none' })
        } finally {
          reparseLoading.value = false
        }
      }
    }
  })
}
function handleBackToList() {
  uni.reLaunch({ url: paperId.value ? `/pages/teacher/review-list?paper_id=${paperId.value}` : '/pages/teacher/review-list' })
}
function handlePrevQuestion() {
  if (currentQuestionIndex.value > 0) {
    uni.redirectTo({ url: `/pages/teacher/question-edit?id=${questionList.value[currentQuestionIndex.value - 1].id}` })
  } else {
    uni.showToast({ title: '已经是第一题了', icon: 'none' })
  }
}
function handleNextQuestion() {
  if (currentQuestionIndex.value >= 0 && currentQuestionIndex.value < questionList.value.length - 1) {
    uni.redirectTo({ url: `/pages/teacher/question-edit?id=${questionList.value[currentQuestionIndex.value + 1].id}` })
  } else {
    uni.showToast({ title: '已经是最后一题了', icon: 'none' })
  }
}
function onKeyDown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); handleSave() }
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); handleConfirm() }
}

onMounted(async () => {
  const pgs = getCurrentPages()
  const pg = pgs[pgs.length - 1] as any
  questionId = Number(pg.options?.id || 0)
  if (!questionId) {
    uni.showToast({ title: '缺少题目ID', icon: 'none' })
    return
  }
  loadQuestion(questionId)
  loadKnowledgePoints()
  window.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  if (previewDebounceTimer) { clearTimeout(previewDebounceTimer); previewDebounceTimer = null }
})
</script>

<style scoped>
.edit-page { display: flex; min-height: 100vh; background: #f0f2f5; }
.main { margin-left: 240px; flex: 1; padding: 0; min-height: 100vh; overflow: hidden; }
.split-layout { display: flex; height: 100%; }
.image-panel { width: 50%; min-width: 300px; background: #fff; display: flex; flex-direction: column; border-right: 1px solid #e4e7ed; overflow: hidden; }
.photo-images-section { margin-bottom: 12px; padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }
.section-label { font-size: 13px; font-weight: 600; color: #606266; margin-bottom: 8px; display: block; }
.photo-images-scroll { display: flex; gap: 8px; overflow-x: auto; }
.photo-image-item { display: flex; flex-direction: column; align-items: center; flex-shrink: 0; }
.photo-image { width: 80px; height: auto; border-radius: 4px; cursor: pointer; }
.photo-image-label { font-size: 11px; color: #909399; margin-top: 4px; }
.page-nav-bar { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 8px; background: #fafafa; border-bottom: 1px solid #eee; }
.page-label { font-size: 13px; color: #606266; }
.zoom-controls { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 4px 8px; background: #fafafa; border-bottom: 1px solid #eee; }
.zoom-label { font-size: 12px; color: #606266; min-width: 40px; text-align: center; }
.image-container { flex: 1; overflow: auto; position: relative; background: #eee; display: flex; align-items: flex-start; justify-content: center; }
.image-container.add-mode { cursor: crosshair; }
.image-wrap { position: relative; width: 100%; transform-origin: top center; }
.page-image { width: 100%; height: auto; display: block; }
.crop-overlay { position: absolute; pointer-events: none; z-index: 10; }
.crop-border { width: 100%; height: 100%; border: 2px solid #409eff; box-sizing: border-box; }
.image-container.calibrating { cursor: crosshair; }
.calib-crosshair { position: fixed; width: 48px; height: 48px; z-index: 9999; pointer-events: none; }
.calib-crosshair::before { content: ''; position: absolute; left: 50%; top: 0; width: 4px; height: 100%; background: #ff0000; transform: translateX(-50%); box-shadow: 0 0 3px #fff, 0 0 3px #fff; }
.calib-crosshair::after { content: ''; position: absolute; top: 50%; left: 0; height: 4px; width: 100%; background: #ff0000; transform: translateY(-50%); box-shadow: 0 0 3px #fff, 0 0 3px #fff; }
.calib-hint { position: fixed; top: 16px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); color: #fff; padding: 8px 16px; border-radius: 4px; font-size: 13px; z-index: 9999; pointer-events: none; }
.calib-nudge-label { font-size: 11px; color: #909399; margin: 0 2px; }
.crop-border.add-border { border-color: #409eff; background: rgba(64, 158, 255, 0.1); }
.add-mode-actions { display: flex; gap: 8px; padding: 8px 12px; background: #fafafa; border-top: 1px solid #eee; justify-content: center; }
.crop-actions { display: flex; gap: 8px; padding: 8px 12px; background: #fafafa; border-top: 1px solid #eee; }
.image-list-section { border-top: 1px solid #eee; padding: 8px 12px; max-height: 200px; overflow-y: auto; }
.image-list-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
.list-title { font-size: 13px; font-weight: 600; color: #606266; }
.list-hint { font-size: 11px; color: #909399; }
.image-list-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid #f0f0f0; }
.thumb-img { width: 80px; height: 80px; border-radius: 4px; object-fit: cover; flex-shrink: 0; }
.thumb-desc { flex: 1; font-size: 12px; color: #606266; min-width: 60px; }
.thumb-sort { display: flex; flex-direction: column; gap: 2px; margin: 0 4px; }
.sort-arrow { font-size: 12px; color: #409eff; cursor: pointer; line-height: 1; padding: 2px; }
.sort-arrow.disabled { color: #ccc; cursor: not-allowed; }
.thumb-insert, .thumb-delete { font-size: 11px; }
.empty-images { text-align: center; padding: 12px; color: #909399; font-size: 12px; }
.edit-panel { width: 50%; min-width: 300px; background: #fff; display: flex; flex-direction: column; overflow-y: auto; padding: 16px; }
.form-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #ebeef5; }
.toolbar-left { display: flex; align-items: center; gap: 8px; }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.form-select-sm { padding: 4px 8px; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 13px; }
.form-input-sm { padding: 4px 8px; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 13px; box-sizing: border-box; }
.info-group { display: flex; align-items: center; gap: 4px; }
.info-label { font-size: 12px; color: #666; }
.info-input { width: 60px; }
.info-input-sm { width: 40px; }
.info-separator { font-size: 12px; color: #999; }
.diff-badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; color: #fff; }
.diff-l0 { background: #909399; } .diff-l1 { background: #67c23a; } .diff-l2 { background: #e6a23c; } .diff-l3 { background: #f56c6c; } .diff-l4 { background: #e63c3c; } .diff-l5 { background: #cc0000; }
.question-actions { display: flex; gap: 8px; padding: 8px 0; border-top: 1px solid #ebeef5; border-bottom: 1px solid #ebeef5; margin-bottom: 12px; flex-wrap: wrap; }
.question-actions button { flex: none; }
.form-group { margin-bottom: 16px; }
.form-label { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 8px; display: block; }
.form-textarea { width: 100%; border: 1px solid #dcdfe6; border-radius: 4px; padding: 8px 12px; font-size: 13px; box-sizing: border-box; resize: vertical; min-height: 32px; line-height: 1.5; }
.form-textarea-auto { height: auto; overflow-y: hidden; }
.form-input { width: 100%; border: 1px solid #dcdfe6; border-radius: 4px; padding: 8px 12px; font-size: 13px; box-sizing: border-box; }
.options-list { display: flex; flex-direction: column; gap: 8px; }
.option-row { display: flex; align-items: flex-start; gap: 6px; margin-bottom: 6px; }
.option-label { font-weight: bold; font-size: 14px; min-width: 20px; color: #409eff; padding-top: 6px; }
.option-content-wrapper { flex: 1; }
.option-textarea { flex: 1; border: 1px solid #dcdfe6; border-radius: 4px; padding: 6px 10px; font-size: 13px; box-sizing: border-box; min-height: 32px; resize: vertical; line-height: 1.5; width: 100%; }
.option-textarea-auto { height: auto; overflow-y: hidden; }
.option-preview { margin-top: 4px; min-height: 18px; }
.kp-selector { position: relative; margin-bottom: 6px; }
.kp-search-input { width: 100%; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 13px; box-sizing: border-box; min-height: 36px; height: auto; }
.kp-debug { display: block; font-size: 11px; color: #999; margin-top: 4px; }
.kp-dropdown { position: absolute; top: 100%; left: 0; right: 0; z-index: 100; background: #fff; border: 1px solid #dcdfe6; border-radius: 4px; max-height: 250px; overflow-y: auto; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-top: 4px; }
.kp-dropdown-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; cursor: pointer; border-bottom: 1px solid #f0f0f0; }
.kp-dropdown-item:hover { background: #ecf5ff; }
.kp-dropdown-item:last-child { border-bottom: none; }
.kp-checkbox { width: 16px; height: 16px; border: 1px solid #dcdfe6; border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 11px; color: #409eff; flex-shrink: 0; }
.kp-item-label { flex: 1; font-size: 13px; color: #303133; }
.kp-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; padding: 8px; min-height: 44px; background: #fafafa; border-radius: 4px; border: 1px dashed #ddd; }
.kp-tag { display: inline-flex; align-items: center; gap: 4px; padding: 6px 10px; background: #ecf5ff; border: 1px solid #b3d8ff; border-radius: 4px; font-size: 13px; color: #409eff; min-height: 32px; }
.kp-tag-remove { cursor: pointer; color: #909399; font-size: 16px; line-height: 1; }
.kp-tag-remove:hover { color: #409eff; }
.kp-empty { margin-top: 8px; font-size: 12px; color: #909399; }
.math-preview { margin-top: 5px; padding: 8px; background: #fafafa; border: 1px dashed #ccc; border-radius: 4px; font-size: 14px; min-height: 24px; white-space: pre-wrap; word-break: break-all; }
.form-actions-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-top: 1px solid #ebeef5; margin-top: 16px; }
.actions-left { font-size: 11px; color: #666; }
.shortcut-hint { font-size: 11px; color: #999; }
.actions-right { display: flex; gap: 8px; }
.loading, .empty { text-align: center; padding: 80rpx; color: #999; }
@media (max-width: 768px) { .main { margin-left: 60px; padding: 20rpx; } .split-layout { flex-direction: column; } .image-panel, .edit-panel { width: 100%; min-width: 0; } }
</style>