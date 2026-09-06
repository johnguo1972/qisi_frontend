<template>
  <view class="create-page">

    <!-- 右侧内容区 -->
    <view class="main">
      <!-- Step 1: 基本信息 -->
      <view v-if="step === 1" class="form">
        <view class="form-item">
          <text class="label">题目来源</text>
          <view class="target-mode-group">
            <view
              v-for="item in sourceTypeOptions"
              :key="item.value"
              class="target-mode"
              :class="{ active: sourceType === item.value }"
              @click="sourceType = item.value"
            >{{ item.label }}</view>
          </view>
        </view>
        <view class="form-title">作业信息</view>
        <view class="form-item">
          <text class="label">作业名称 *</text>
          <view class="name-builder">
            <text class="name-prefix">{{ selectedClassName || '选择班级' }} {{ assignmentDate }}</text>
            <input v-model="assignmentTitle" placeholder="作业" class="name-input" />
          </view>
        </view>
        <view class="form-item">
          <text class="label">作业类型</text>
          <view class="target-mode-group">
            <view class="target-mode" :class="{ active: missionKind === 'regular' }" @click="missionKind = 'regular'">普通作业</view>
            <view class="target-mode" :class="{ active: missionKind === 'drill' }" @click="missionKind = 'drill'">教师精练</view>
          </view>
        </view>
        <view class="form-item">
          <text class="label">选择班级 *</text>
          <view class="class-picker" @click="showClassDropdown = !showClassDropdown">
            <text class="class-value">{{ selectedClassName || '请选择班级（可多选）' }}</text>
            <text class="class-arrow">📋</text>
          </view>
          <!-- 班级下拉框 -->
          <view v-if="showClassDropdown" class="class-dropdown">
            <view v-for="cls in classList" :key="cls.id"
                  :class="['class-option', {active: form.class_ids.includes(String(cls.id))}]"
                  @click="toggleClass(cls)">
              <text class="class-opt-name">{{ cls.class_name }}</text>
              <text v-if="form.class_ids.includes(String(cls.id))" class="class-opt-check">✓</text>
            </view>
            <view v-if="classList.length === 0" class="class-empty">
              <text>暂无班级，请先创建班级</text>
            </view>
          </view>
        </view>
        <view class="form-item">
          <text class="label">作业说明</text>
          <textarea
            v-model="form.goal_text"
            class="form-textarea"
            placeholder="请输入作业说明（可选）"
            maxlength="255"
          />
        </view>
        <view class="form-item">
          <text class="label">开始日期（自动）</text>
          <view class="date-picker readonly-date-picker">
            <text class="date-value">{{ editMode && form.start_at ? formatDateOnly(form.start_at) : assignmentDate }}</text>
            <text class="date-hint">布置作业当天</text>
          </view>
        </view>
        <view class="form-item">
          <text class="label">完成日期 *</text>
          <view class="date-picker" @click="openDatePicker">
            <text class="date-value">{{ formatDateOnly(form.end_at, '') || '请选择截止时间' }}</text>
            <text class="date-arrow">📅</text>
          </view>
        </view>
        <view class="form-item target-students-item">
          <text class="label">布置对象</text>
          <view class="target-mode-group">
            <view class="target-mode" :class="{ active: targetMode === 'class' }" @click="setTargetMode('class')">全班</view>
            <view
              class="target-mode"
              :class="{ active: targetMode === 'students', disabled: !form.class_id || form.class_ids.length !== 1 }"
              @click="setTargetMode('students')"
            >指定学生</view>
          </view>
          <text v-if="!form.class_id" class="target-hint">请先选择班级，才能指定学生</text>
          <text v-else-if="form.class_ids.length > 1" class="target-hint">多班级作业暂不支持指定学生，请布置给全班</text>
        </view>
        <view v-if="form.class_id && targetMode === 'students'" class="form-item target-students-item">
          <text class="label">选择需要精练的学生</text>
          <view class="target-students">
            <view v-for="student in classStudents" :key="student.student || student.id"
                  :class="['target-student', { selected: targetStudentIds.includes(String(student.student || student.id)) }]"
                  @click="toggleTargetStudent(String(student.student || student.id))">
              <text>{{ student.student_name || student.display_name || student.student_mobile || student.mobile }}</text>
              <text>{{ targetStudentIds.includes(String(student.student || student.id)) ? '✓' : '' }}</text>
            </view>
            <text v-if="!classStudents.length" class="target-empty">该班级暂无学生</text>
          </view>
        </view>
        <button class="next-btn" @click="nextStep">下一步：选择题目</button>
      </view>

      <!-- Step 2: 选择题目 -->
      <view v-if="step === 2" class="step2-container">
        <!-- 左侧知识树 -->
        <view class="knowledge-tree">
          <text class="tree-title">知识树</text>
          <picker class="subject-picker" :range="subjectOptions" range-key="label" @change="onSubjectChange">
            <view class="subject-picker-value">学科：{{ subjectLabel }}</view>
          </picker>
          <view v-if="treeLoading" class="tree-loading">加载中...</view>
          <view v-else class="tree-content">
            <view v-for="grade in treeData" :key="grade.name" class="tree-grade">
              <view class="tree-node" @click="grade.expanded = !grade.expanded">
                <text class="arrow">{{ grade.expanded ? '▼' : '▶' }}</text>
                <text class="tree-label">{{ grade.name }}</text>
              </view>
              <view v-if="grade.expanded" class="tree-children">
                <view v-for="sem in grade.semesters" :key="sem.name" class="tree-semester">
                  <view class="tree-node" @click="sem.expanded = !sem.expanded">
                    <text class="arrow">{{ sem.expanded ? '▼' : '▶' }}</text>
                    <text class="tree-label">{{ sem.name }}</text>
                  </view>
                  <view v-if="sem.expanded" class="tree-children">
                    <view v-for="ch in sem.chapters" :key="ch.name" class="tree-chapter">
                      <view class="tree-node" @click="ch.expanded = !ch.expanded">
                        <text class="arrow">{{ ch.expanded ? '▼' : '▶' }}</text>
                        <text class="tree-label">{{ ch.name }}</text>
                      </view>
                      <view v-if="ch.expanded" class="tree-children">
                        <view v-for="kp in ch.knowledge_points" :key="kp.id"
                              :class="['tree-kp', {active: filterKpIds.includes(kp.id)}]"
                              @click.stop="toggleKpFromTree(kp)">
                          <text class="kp-name">{{ kp.name }}</text>
                        </view>
                      </view>
                    </view>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </view>

        <!-- 右侧区域 -->
        <view class="right-panel">
          <!-- 综合筛选区 -->
          <view class="filter-section">
            <view class="filter-row">
              <view class="filter-item filter-kp-item">
                <text class="filter-label">知识点</text>
                <view class="kp-input-row">
                  <input v-model="kpSearchText" placeholder="输入知识点名称搜索" class="kp-search-input" @focus="showKpDropdown = true" @blur="onKpInputBlur" />
                  <text v-if="filterKpIds.length > 0" class="kp-count-badge">{{ filterKpIds.length }}</text>
                </view>
                <!-- 知识点下拉框 -->
                <view v-if="showKpDropdown" class="kp-dropdown" @mousedown.prevent>
                  <view class="kp-dropdown-header">
                    <text class="kp-dropdown-title">选择知识点（可多选）</text>
                    <text class="kp-dropdown-clear" @click="clearKpSelection">清空</text>
                  </view>
                  <scroll-view scroll-y class="kp-dropdown-list">
                    <view v-for="kp in filteredKpList" :key="kp.id"
                          :class="['kp-option', {selected: filterKpIds.includes(kp.id)}]"
                          @click="toggleFilterKp(kp)">
                      <text class="kp-check">{{ filterKpIds.includes(kp.id) ? '☑' : '☐' }}</text>
                      <text class="kp-label">{{ kp.name }}</text>
                    </view>
                    <view v-if="filteredKpList.length === 0" class="kp-dropdown-empty">
                      <text>无匹配的知识点</text>
                    </view>
                  </scroll-view>
                </view>
              </view>
              <view class="filter-item">
                <text class="filter-label">难度</text>
                <view class="diff-buttons">
                  <view v-for="d in [1,2,3,4,5]" :key="d"
                        :class="['diff-btn', {active: filterDifficulty.includes(d)}]"
                        @click="toggleDifficulty(d)">
                    <text>{{ '★'.repeat(d) }}</text>
                  </view>
                </view>
              </view>
              <view class="filter-item filter-stage-item">
                <text class="filter-label">年级学期</text>
                <view class="multi-select" @click="showStageDropdown = !showStageDropdown">
                  <text class="multi-select-text">
                    {{ selectedStages.length > 0 ? `已选 ${selectedStages.length} 个学期` : '全部学期' }}
                  </text>
                  <text class="dropdown-arrow">▼</text>
                </view>
                <view v-if="showStageDropdown" class="stage-dropdown" @mousedown.prevent>
                  <view v-for="s in allStages" :key="s"
                        :class="['stage-option', {selected: selectedStages.includes(s)}]"
                        @click="toggleStage(s)">
                    <text class="stage-check">{{ selectedStages.includes(s) ? '☑' : '☐' }}</text>
                    <text class="stage-label">{{ s }}</text>
                  </view>
                </view>
              </view>
              <view class="filter-item filter-type-item">
                <text class="filter-label">题型</text>
                <picker
                  mode="selector"
                  :range="questionTypeRange"
                  :value="questionTypeIndex"
                  @change="onQuestionTypeChange"
                >
                  <view class="multi-select type-select">
                    <text class="multi-select-text">{{ questionTypeLabel }}</text>
                    <text class="dropdown-arrow">▼</text>
                  </view>
                </picker>
              </view>
            </view>
            <view class="filter-row">
              <view class="filter-item">
                <text class="filter-label">错误率</text>
                <view class="range-inputs">
                  <input v-model.number="filterErrorMin" type="number" placeholder="最小%" class="range-input" />
                  <text class="range-sep">~</text>
                  <input v-model.number="filterErrorMax" type="number" placeholder="最大%" class="range-input" />
                </view>
              </view>
              <view class="filter-item">
                <text class="filter-label">关键词</text>
                <input v-model="searchQuery" placeholder="输入关键字（可多个）" class="search-input" />
              </view>
              <view class="filter-item">
                <text class="filter-label">题号（UUID）</text>
                <input v-model="questionUuid" placeholder="输入 UUID 或片段" class="search-input" />
              </view>
              <view class="filter-item">
                <text class="filter-label">标签</text>
                <picker mode="selector" :range="tagPickerRange" :value="tagPickerIndex" @change="onTagChange">
                  <view class="multi-select type-select">
                    <text class="multi-select-text">{{ tagFilterLabel }}</text>
                    <text class="dropdown-arrow">▼</text>
                  </view>
                </picker>
                <button size="mini" class="tag-refresh-btn" :loading="tagLoading" @click="loadTags">刷新标签</button>
              </view>
              <view class="filter-actions">
                <button class="filter-btn" @click="applyFilters">🔍 筛选</button>
                <button class="reset-btn" @click="resetFilters">↻ 重置</button>
              </view>
            </view>
          </view>

          <!-- 操作栏 -->
          <view class="action-bar">
            <view class="action-left">
              <view class="select-all-row" @click="toggleSelectAll">
                <text>{{ isAllSelected ? '☑ 取消全选' : '☐ 全选' }}</text>
              </view>
              <button class="batch-add-btn" @click="batchAddSelected">批量加入列表</button>
              <button class="back-btn step2-back-btn" @click="prevStep">上一步：创建作业</button>
              <button v-if="selectedIds.length > 0" class="create-task-btn" @click="goToStep3">
                下一步：编排序号并创建作业 ({{ selectedIds.length }}题)
              </button>
            </view>
            <view class="action-right">
              <button class="list-btn" @click="showSelectedModal = true">
                📋 题目列表
                <text v-if="selectedIds.length > 0" class="list-badge">{{ selectedIds.length }}</text>
              </button>
            </view>
          </view>

          <!-- 题目列表表格 -->
          <view v-if="loading" class="table-loading">加载中...</view>
          <view v-else-if="filteredQuestions.length === 0" class="table-empty">
            <text>暂无题目，请选择知识点或使用筛选条件</text>
          </view>
          <view v-else class="question-table">
            <view class="table-header">
              <text class="col col-check">☐</text>
              <text class="col col-no">序号</text>
              <text class="col col-stem">题干预览</text>
              <text class="col col-type">题型</text>
              <text class="col col-diff">难度</text>
              <text class="col col-kp">知识点</text>
              <text class="col col-attempts">做题数</text>
              <text class="col col-errors">错误数</text>
              <text class="col col-error-rate">错误率</text>
              <text class="col col-actions">操作</text>
            </view>
            <scroll-view scroll-y class="table-body">
              <view v-for="(q, idx) in paginatedQuestions" :key="q.id"
                    :class="['table-row', { 'row-selected': isSelected(q.id) }]">
                <view class="col col-check" @click.stop="toggleSelect(q.id)">
                  <text>{{ isSelected(q.id) ? '☑' : '☐' }}</text>
                </view>
                <text class="col col-no">{{ (currentPage - 1) * pageSize + idx + 1 }}</text>
                <text class="col col-stem" @click.stop="showQuestionDetail(q)">{{ q.stem_preview || '(无预览)' }}</text>
                <text class="col col-type">{{ questionTypeText(q) }}</text>
                <text :class="['col col-diff', 'diff-' + getDifficultyInt(q)]">
                  {{ '★'.repeat(getDifficultyInt(q)) }}
                  <text v-if="q.difficulty" class="diff-score">{{ Number(q.difficulty).toFixed(1) }}</text>
                </text>
                <text class="col col-kp">{{ q.knowledge_points_count || 0 }}</text>
                <text class="col col-attempts">{{ q.attempt_count || 0 }}</text>
                <text class="col col-errors">{{ q.wrong_count || 0 }}</text>
                <text :class="['col col-error-rate', getErrorRateClass(q)]">
                  {{ q.attempt_count > 0 ? ((q.wrong_count || 0) / q.attempt_count * 100).toFixed(1) + '%' : '-' }}
                </text>
                <view class="col col-actions">
                  <text class="action-link" @click.stop="showQuestionDetail(q)">查看</text>
                  <text v-if="!isSelected(q.id)" class="action-link action-add" @click.stop="addToSelected(q)">加入</text>
                  <text v-else class="action-link action-added" @click.stop="removeFromSelected(q.id)">✓ 已加入</text>
                </view>
              </view>
            </scroll-view>
            <!-- 分页 -->
            <view class="pagination">
              <text class="page-total">共 {{ totalCount }} 题</text>
              <view class="page-controls">
                <button size="mini" :disabled="currentPage <= 1" @click="prevPage">上一页</button>
                <picker mode="selector" :range="pageRangeLabels" :value="currentPage - 1" @change="selectPage"><view class="page-picker">{{ pageOptionLabel(currentPage) }}</view></picker>
                <button size="mini" :disabled="currentPage >= totalPages" @click="nextPage">下一页</button>
                <text class="page-size-label">每页</text>
                <picker mode="selector" :range="pageSizeRange" :value="pageSizeOptions.indexOf(pageSize)" @change="changePageSize"><view class="page-size-select">{{ pageSize }} 条</view></picker>
                <input v-model.number="jumpPage" class="jump-page-input" type="number" min="1" :max="totalPages" placeholder="页码" @confirm="goToPage" />
                <button size="mini" @click="goToPage">跳转</button>
                <text class="page-info">{{ currentPage }}/{{ totalPages }}页</text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- Step 3: 编排题目序号 -->
      <view v-if="step === 3" class="step3-container">
        <!-- 题目编排区 -->
        <view class="step3-section">
          <view class="section-header">
            <text class="section-title">题目编排 ({{ orderedQuestions.length }}题)</text>
            <text class="section-hint">拖拽调整顺序，点击序号可编辑</text>
          </view>
          <scroll-view scroll-y class="ordered-question-list">
            <view v-for="(q, idx) in orderedQuestions" :key="q.id" class="ordered-item"
                  draggable="true" @dragstart="onDragStart(idx)" @dragover.prevent @drop="onDrop(idx)">
              <view class="drag-handle">⠿</view>
              <input :value="q.sort_no" @input="setSortNo(q.id, $event)" type="number" class="sort-input" placeholder="序号" />
              <text class="ordered-stem">{{ (q.stem_preview || '').substring(0, 50) }}{{ (q.stem_preview || '').length > 50 ? '...' : '' }}</text>
              <text class="ordered-diff">{{ '★'.repeat(getDifficultyInt(q)) }}</text>
              <text class="ordered-remove" @click="removeFromOrdered(q.id)">✕</text>
            </view>
          </scroll-view>
        </view>

        <view class="step3-section flat-assignment-hint">
          <text class="section-title">作业题目</text>
          <text class="section-hint">已取消关卡设置，所有题目将按当前顺序组成一份作业。</text>
        </view>

        <view class="nav-btns">
          <button class="back-btn" @click="prevStep">上一步：选择题目</button>
          <button class="next-btn" @click="nextStep">下一步：预览发布</button>
        </view>
      </view>

      <!-- 历史关卡分配弹窗（保留兼容，不在新流程中展示） -->
      <view v-if="false && showQuestionAssign" class="assign-modal" @click="closeQuestionAssign">
        <view class="assign-panel" @click.stop>
          <view class="assign-header">
            <text class="assign-title">为"{{ levels[currentAssignLevel]?.name }}"分配题目</text>
            <text class="assign-close" @click="closeQuestionAssign">✕</text>
          </view>
          <view class="assign-actions">
            <text class="assign-select-all" @click="selectAllForLevel">全选已选题目</text>
            <text class="assign-clear" @click="clearLevelQuestions">清空</text>
          </view>
          <scroll-view scroll-y class="assign-list">
            <view v-for="q in selectedQuestions" :key="q.id"
                  :class="['assign-item', {assigned: isQuestionAssignedForLevel(q.id)}]"
                  @click="toggleQuestionForLevel(q.id)">
              <text class="assign-check">{{ isQuestionAssignedForLevel(q.id) ? '☑' : '☐' }}</text>
              <text class="assign-no">#{{ getQuestionSortNo(q.id) }}</text>
              <text class="assign-stem">{{ (q.stem_preview || '').substring(0, 60) }}</text>
              <text class="assign-diff">{{ '★'.repeat(getDifficultyInt(q)) }}</text>
            </view>
          </scroll-view>
          <view class="assign-footer">
            <text class="assign-count">已选 {{ (levels[currentAssignLevel]?.questionIds || []).length }} 道</text>
            <button class="assign-confirm" @click="closeQuestionAssign">确定</button>
          </view>
        </view>
      </view>

      <!-- Step 4: 预览 + 发布 -->
      <view v-if="step === 4" class="preview">
        <view class="form-title">预览</view>
        <view class="preview-card">
          <text class="preview-name">{{ previewMissionName }}</text>
          <view class="preview-row"><text class="preview-label">题目数量</text><text class="preview-value">{{ orderedQuestions.length }} 道</text></view>
          <view class="preview-row"><text class="preview-label">布置对象</text><text class="preview-value">{{ assignmentTargetLabel }}</text></view>
          <view class="preview-row"><text class="preview-label">截止日期</text><text class="preview-value">{{ formatDateOnly(form.end_at, '未设置') }}</text></view>
          <!-- 题目序号预览 -->
          <view class="preview-questions">
            <text class="preview-questions-title">题目列表：</text>
            <view v-for="q in orderedQuestions" :key="q.id" class="preview-question-item">
              <text class="preview-q-no">第{{ q.sort_no }}题</text>
              <text class="preview-q-stem">{{ (q.stem_preview || '').substring(0, 40) }}</text>
              <text class="preview-q-diff">{{ '★'.repeat(getDifficultyInt(q)) }}</text>
            </view>
          </view>
        </view>
        <view class="nav-btns">
          <button class="back-btn" @click="prevStep">上一步</button>
          <button class="save-btn" @click="saveDraft">保存草稿</button>
          <button class="publish-btn" @click="publish">保存并发布</button>
        </view>
      </view>
    </view>

    <!-- 日期选择弹窗 -->
    <view v-if="showDatePicker" class="date-modal" @click="showDatePicker = false">
      <view class="date-panel" @click.stop>
        <view class="date-panel-header">
          <text class="date-close-btn" @click="showDatePicker = false">取消</text>
          <text class="date-confirm-btn" @click="confirmDate">确定</text>
        </view>
        <picker mode="date" :value="tempDate" @change="onDateChange">
          <view class="date-picker-input">
            <text class="date-picker-label">完成日期</text>
            <text class="date-picker-value">{{ tempDate }}</text>
          </view>
        </picker>
      </view>
    </view>

    <!-- 已选题目弹窗 -->
    <view v-if="showSelectedModal" class="selected-modal" @click="showSelectedModal = false">
      <view class="selected-panel" @click.stop>
        <view class="selected-header">
          <text class="selected-title">已选题目列表 ({{ selectedIds.length }}题)</text>
          <view class="selected-header-actions">
            <text class="selected-clear" @click="clearSelected">清空全部</text>
            <text class="selected-close-btn" @click="showSelectedModal = false">✕ 关闭</text>
          </view>
        </view>
        <view v-if="selectedQuestions.length === 0" class="selected-empty">
          <text>尚未加入任何题目</text>
        </view>
        <scroll-view v-else scroll-y class="selected-list">
          <view v-for="(q, idx) in selectedQuestions" :key="q.id" class="selected-item">
            <text class="selected-no">{{ idx + 1 }}.</text>
            <text class="selected-stem">{{ (q.stem_preview || '').substring(0, 60) }}{{ (q.stem_preview || '').length > 60 ? '...' : '' }}</text>
            <text class="selected-remove" @click="removeFromSelected(q.id)">✕ 移除</text>
          </view>
        </scroll-view>
        <!-- 统计信息 -->
        <view v-if="selectedQuestions.length > 0" class="selected-stats">
          <text class="stat-item">难度均值: {{ avgDifficulty }}</text>
          <text class="stat-item">知识点覆盖: {{ uniqueKpCount }} 个</text>
        </view>
      </view>
    </view>

    <!-- 题目详情弹窗 -->
    <view v-if="showDetailModal" class="detail-modal" @click="showDetailModal = false">
      <view class="detail-panel" @click.stop>
        <view class="detail-header">
          <text class="detail-title">题目 #{{ currentQuestion?.id }}</text>
          <text class="detail-close" @click="showDetailModal = false">✕ 关闭</text>
        </view>
        <scroll-view scroll-y class="detail-body" v-if="currentQuestion">
          <view class="detail-section">
            <text class="detail-section-title">【题干】</text>
            <text class="detail-stem">{{ currentQuestion.stem || currentQuestion.stem_preview || '暂无题干' }}</text>
          </view>
          <view class="detail-section" v-if="currentQuestion.options">
            <text class="detail-section-title">【选项】</text>
            <text class="detail-options-text">{{ currentQuestion.options }}</text>
          </view>
          <view class="detail-section">
            <text class="detail-section-title">【答案】</text>
            <text class="detail-answer">{{ currentQuestion.answer || '暂无答案' }}</text>
          </view>
          <view class="detail-section">
            <text class="detail-section-title">【解析】</text>
            <text class="detail-explanation">{{ currentQuestion.explanation || '暂无解析' }}</text>
          </view>
          <view class="detail-section">
            <text class="detail-section-title">【知识点】</text>
            <text class="detail-kp">{{ currentQuestion.knowledge_points_list || '暂无知识点' }}</text>
          </view>
          <view class="detail-section">
            <text class="detail-section-title">【年级/学期】</text>
            <text class="detail-stage">{{ currentQuestion.stage || '未设置' }}</text>
          </view>
          <view class="detail-section">
            <text class="detail-section-title">【难度】</text>
            <text class="detail-difficulty">
              {{ '★'.repeat(getDifficultyInt(currentQuestion)) }}
              ({{ Number(currentQuestion.difficulty).toFixed(1) || '-' }}/5)
            </text>
          </view>
          <view class="detail-section" v-if="currentQuestion.ai_answer_a">
            <text class="detail-section-title">【AI答案 - A模式】引导式</text>
            <text class="detail-ai">{{ currentQuestion.ai_answer_a }}</text>
          </view>
          <view class="detail-section" v-if="currentQuestion.ai_answer_b">
            <text class="detail-section-title">【AI答案 - B模式】逐步拆解</text>
            <text class="detail-ai">{{ currentQuestion.ai_answer_b }}</text>
          </view>
          <view class="detail-section" v-if="currentQuestion.ai_answer_c">
            <text class="detail-section-title">【AI答案 - C模式】直接解答</text>
            <text class="detail-ai">{{ currentQuestion.ai_answer_c }}</text>
          </view>
          <view class="detail-section">
            <text class="detail-section-title">【统计】</text>
            <text class="detail-stats">
              已做: {{ currentQuestion.attempt_count || 0 }}人 |
              错题本: {{ currentQuestion.wrong_count || 0 }}次 |
              错误率: {{ currentQuestion.attempt_count > 0 ? ((currentQuestion.wrong_count || 0) / currentQuestion.attempt_count * 100).toFixed(1) : 0 }}%
            </text>
          </view>
        </scroll-view>
        <view class="detail-footer">
          <button class="detail-add-btn" @click="if (currentQuestion) addToSelected(currentQuestion); showDetailModal = false">
            {{ currentQuestion && isSelected(currentQuestion.id) ? '✓ 已在列表中' : '加入列表' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { missionApi } from '@/api/index.ts'
import { getTagList, questionApi } from '@/api/questions.ts'
import { knowledgeApi } from '@/api/knowledge.ts'
import { classApi } from '@/api/institutions.ts'
import { useUserStore } from '@/store/index.ts'
import { formatDateOnly } from '@/utils/display-format'
import { buildMissionQuestionFilterParams } from './mission-question-filters'
import { QUESTION_TYPE_OPTIONS, getQuestionTypeLabel } from '@/constants/question-types'

const userStore = useUserStore()

const step = ref(1)

const editMode = ref(false)
const editMissionId = ref<string>('')

const form = ref({ mission_name: '', goal_text: '', start_at: '', end_at: '', class_id: null as string | null, class_ids: [] as string[] })
const missionKind = ref<'regular' | 'drill'>('regular')
type SourceType = 'question_bank' | 'handout' | 'wrongbook' | 'ai_recommendation'
const sourceType = ref<SourceType>('question_bank')
const sourceTypeOptions: Array<{ value: SourceType; label: string }> = [
  { value: 'question_bank', label: '题库' },
  { value: 'handout', label: '讲义' },
  { value: 'wrongbook', label: '错题本' },
  { value: 'ai_recommendation', label: 'AI推荐' },
]
const assignmentTitle = ref('作业')
const targetMode = ref<'class' | 'students'>('class')
const courseId = ref<number | null>(null)
const pendingFavoriteQuestionIds = ref<Array<string | number>>([])
const levels = ref([{ name: '基础练习', type: 'practice', mode: 'block_a', questionIds: [] as string[] }])
const subjectOptions = [
  { value: 'physics', label: '物理' },
  { value: 'math', label: '数学' },
]
const questionTypeOptions = [{ value: '', label: '全部题型' }, ...QUESTION_TYPE_OPTIONS]
const selectedSubject = ref(String(userStore.userInfo?.subject || 'physics'))
const selectedQuestionType = ref('')
const questionTypeRange = questionTypeOptions.map(item => item.label)
const questionTypeIndex = computed(() => Math.max(0, questionTypeOptions.findIndex(item => item.value === selectedQuestionType.value)))
const questionTypeLabel = computed(() => questionTypeOptions[questionTypeIndex.value]?.label || '全部题型')
const sortNos = ref<Record<string, number>>({})
const draggingIndex = ref(-1)
const searchQuery = ref('')
const questionUuid = ref('')
const filterTag = ref('')
const allTags = ref<any[]>([])
const tagLoading = ref(false)
const showDatePicker = ref(false)
const tempDate = ref('')
const showStartDatePicker = ref(false)
const tempStartDate = ref('')

// 班级选择
const classList = ref<any[]>([])
const showClassDropdown = ref(false)
const selectedClassName = ref('')
const classStudents = ref<any[]>([])
const targetStudentIds = ref<string[]>([])

function localDateString(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const assignmentDate = computed(() => localDateString())
const previewMissionName = computed(() => {
  if (editMode.value && form.value.mission_name) return form.value.mission_name
  return `${selectedClassName.value || '指定学生'} ${assignmentDate.value} ${assignmentTitle.value.trim() || '作业'}`
})
const assignmentTargetLabel = computed(() => {
  if (targetMode.value === 'students' && targetStudentIds.value.length) {
    return `${selectedClassName.value}（指定 ${targetStudentIds.value.length} 人）`
  }
  return selectedClassName.value || '指定学生'
})

// === Step 2: 知识树 ===
const treeData = ref<any[]>([])
const treeLoading = ref(false)

// === Step 2: 筛选条件 ===
const showKpDropdown = ref(false)
const showStageDropdown = ref(false)
const kpSearchText = ref('')
const filterKpIds = ref<Array<string | number>>([])
const filterDifficulty = ref<number[]>([])
const selectedStages = ref<string[]>([])
const filterErrorMin = ref<number | null>(null)
const filterErrorMax = ref<number | null>(null)

// === Step 2: 题目列表 ===
const allQuestions = ref<any[]>([])
const filteredQuestions = ref<any[]>([])
const totalCount = ref(0)
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)
const jumpPage = ref(1)
const pageSizeOptions = [10, 20, 30, 50]

// === Step 2: 已选列表 ===
const selectedIds = ref<string[]>([])
const showSelectedModal = ref(false)

// === Step 2: 题目详情 ===
const showDetailModal = ref(false)
const currentQuestion = ref<any>(null)

// 获取知识点扁平列表
const flatKpList = computed(() => {
  const list: any[] = []
  for (const grade of treeData.value) {
    for (const sem of grade.semesters || []) {
      for (const ch of sem.chapters || []) {
        for (const kp of ch.knowledge_points || []) {
          list.push({ id: kp.id, name: kp.name, chapter: ch.name, semester: sem.name, grade: grade.name })
        }
      }
    }
  }
  return list
})

// 所有年级学期列表
const allStages = computed(() => {
  const stages: string[] = []
  for (const grade of treeData.value) {
    for (const sem of grade.semesters || []) {
      stages.push(`${grade.name} ${sem.name}`)
    }
  }
  return stages
})

// 已选知识点名称
const selectedKpNames = computed(() => {
  return filterKpIds.value.map(id => {
    const kp = flatKpList.value.find(k => k.id === id)
    return kp ? kp.name : ''
  }).filter(Boolean)
})

// 知识点下拉列表（按搜索文本过滤）
const filteredKpList = computed(() => {
  if (!kpSearchText.value.trim()) return flatKpList.value
  const q = kpSearchText.value.trim().toLowerCase()
  return flatKpList.value.filter(kp => kp.name.toLowerCase().includes(q))
})

const tagPickerRange = computed(() => [
  '全部标签',
  ...allTags.value.map((tag: any) => `${tag.name}（${tag.question_count ?? 0}）`),
])
const tagPickerIndex = computed(() => {
  if (!filterTag.value) return 0
  const index = allTags.value.findIndex((tag: any) => tag.name === filterTag.value)
  return index >= 0 ? index + 1 : 0
})
const tagFilterLabel = computed(() => filterTag.value || '全部标签')

// 已选题目的详细信息
const selectedQuestions = computed(() => {
  return selectedIds.value.map(id => allQuestions.value.find(q => String(q.id) === String(id))).filter(Boolean)
})

// Step 3: 已选题目（带序号）
const orderedQuestions = computed(() => {
  return selectedQuestions.value.map((q, idx) => ({
    ...q,
    sort_no: sortNos.value[String(q.id)] || q.sort_no || (idx + 1),
  }))
})

// 全选状态
const isAllSelected = computed(() => {
  return paginatedQuestions.value.length > 0 && paginatedQuestions.value.every(q => isSelected(q.id))
})

// 分页
const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageNumbers = computed(() => Array.from({ length: totalPages.value }, (_, index) => index + 1))
const pageRangeLabels = computed(() => pageNumbers.value.map(pageOptionLabel))
const pageSizeRange = pageSizeOptions.map((size) => `${size} 条`)
const paginatedQuestions = computed(() => {
  return filteredQuestions.value
})

// 已选题目统计
const avgDifficulty = computed(() => {
  if (selectedQuestions.value.length === 0) return '-'
  const values = selectedQuestions.value.map(q => Number(q.difficulty)).filter(Number.isFinite)
  return values.length ? (values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1) : '-'
})

const uniqueKpCount = computed(() => {
  return new Set(selectedQuestions.value.flatMap(q => extractQuestionKnowledgePointIds(q))).size
})

function extractQuestionKnowledgePointIds(q: any): string[] {
  const result: string[] = []
  const add = (value: any) => {
    if (value == null || value === '') return
    if (Array.isArray(value)) return value.forEach(add)
    if (typeof value === 'object') return add(value.id || value.code || value.name || value.module)
    result.push(String(value))
  }
  for (const key of ['knowledge_point_ids', 'knowledge_ids', 'knowledge_points_display', 'knowledge_points']) {
    let value = q?.[key]
    if (typeof value === 'string') { try { value = JSON.parse(value) } catch { value = [] } }
    add(value)
  }
  let enriched = q?.ai_knowledge_enrichment
  if (typeof enriched === 'string') { try { enriched = JSON.parse(enriched) } catch { enriched = null } }
  add(enriched?.points || enriched?.knowledge_points || (Array.isArray(enriched) ? enriched : []))
  return result
}

const subjectLabel = computed(() => subjectOptions.find(item => item.value === selectedSubject.value)?.label || selectedSubject.value)
function isSelected(id: string | number) { return selectedIds.value.includes(String(id)) }

// 日期选择
function openDatePicker() {
  const now = new Date()
  if (form.value.end_at) {
    tempDate.value = form.value.end_at.split('T')[0]
  } else {
    tempDate.value = now.toISOString().split('T')[0]
  }
  showDatePicker.value = true
}

function openStartDatePicker() {
  const now = new Date()
  if (form.value.start_at) {
    tempStartDate.value = form.value.start_at.split('T')[0]
  } else {
    tempStartDate.value = now.toISOString().split('T')[0]
  }
  showStartDatePicker.value = true
}

function confirmStartDate() {
  if (tempStartDate.value) {
    form.value.start_at = `${tempStartDate.value}T00:00:00`
  }
  showStartDatePicker.value = false
}

function onDateChange(e: any) {
  tempDate.value = e.detail.value
}

function onStartDateChange(e: any) {
  tempStartDate.value = e.detail.value
}

function confirmDate() {
  if (tempDate.value) {
    form.value.end_at = `${tempDate.value}T23:59:59`
  }
  showDatePicker.value = false
}

// Step 导航
function nextStep() {
  if (step.value === 1) {
    if (!form.value.class_ids.length) {
      uni.showToast({ title: '请先选择班级', icon: 'none' })
      return
    }
    if (!form.value.end_at) {
      uni.showToast({ title: '请先选择完成日期', icon: 'none' })
      return
    }
    if (targetMode.value === 'students' && targetStudentIds.value.length === 0) {
      uni.showToast({ title: '请至少选择一名指定学生', icon: 'none' })
      return
    }
  }
  if (step.value === 2 && selectedIds.value.length === 0) {
    uni.showToast({ title: '请先选择至少一道题目', icon: 'none' })
    return
  }
  if (step.value < 4) step.value++
}
function prevStep() { if (step.value > 1) step.value-- }

function goToStep3() {
  if (selectedIds.value.length === 0) {
    uni.showToast({ title: '请先选择至少一道题目', icon: 'none' })
    return
  }
  step.value = 3
}

// 知识树加载
async function loadKnowledgeTree() {
  treeLoading.value = true
  try {
    const res: any = await knowledgeApi.getTree({ subject: selectedSubject.value })
    const grades = res.data?.grades || res.data || []
    treeData.value = grades.map((g: any) => ({
      ...g,
      expanded: false,
      semesters: (g.semesters || []).map((s: any) => ({
        ...s,
        expanded: false,
        chapters: (s.chapters || []).map((c: any) => ({
          ...c,
          expanded: false,
        })),
      })),
    }))
  } catch (e) {
    console.error('加载知识树失败:', e)
  } finally {
    treeLoading.value = false
  }
}

function onSubjectChange(e: any) {
  selectedSubject.value = subjectOptions[Number(e.detail.value)]?.value || selectedSubject.value
  filterKpIds.value = []
  selectedStages.value = []
  kpSearchText.value = ''
  loadKnowledgeTree()
  loadQuestions()
}

// 题目加载
async function loadQuestions() {
  loading.value = true
  try {
    const params = buildMissionQuestionFilterParams({
      page: currentPage.value,
      pageSize: pageSize.value,
      subject: selectedSubject.value,
      knowledgePointIds: filterKpIds.value,
      difficulties: filterDifficulty.value,
      stages: selectedStages.value,
      questionType: selectedQuestionType.value,
      keyword: searchQuery.value,
      questionUuid: questionUuid.value,
      tag: filterTag.value,
      errorRateMin: filterErrorMin.value,
      errorRateMax: filterErrorMax.value,
    })

    const res: any = await questionApi.list(params)
    const data = res.data || {}
    const items = data.items || []
    filteredQuestions.value = items
    totalCount.value = Number(data.total || items.length)

    const loaded = new Map(allQuestions.value.map(q => [String(q.id), q]))
    items.forEach((q: any) => loaded.set(String(q.id), q))
    allQuestions.value = Array.from(loaded.values())
    jumpPage.value = currentPage.value
  } catch (e) {
    console.error('加载题目失败:', e)
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  currentPage.value = 1
  jumpPage.value = 1
  loadQuestions()
}

function prevPage() { if (currentPage.value > 1) { currentPage.value--; loadQuestions() } }
function nextPage() { if (currentPage.value < totalPages.value) { currentPage.value++; loadQuestions() } }
function selectPage(event?: any) { currentPage.value = Math.max(1, Math.min(totalPages.value, Number(event?.detail?.value ?? currentPage.value - 1) + 1)); jumpPage.value = currentPage.value; loadQuestions() }
function changePageSize(event?: any) { const index = Number(event?.detail?.value ?? pageSizeOptions.indexOf(pageSize.value)); pageSize.value = pageSizeOptions[index] || pageSizeOptions[0]; currentPage.value = 1; jumpPage.value = 1; loadQuestions() }
function goToPage() { const target = Math.max(1, Math.min(totalPages.value, Number(jumpPage.value) || 1)); currentPage.value = target; jumpPage.value = target; loadQuestions() }
function pageOptionLabel(page: number) { return page === currentPage.value ? `${page} / ${totalPages.value} 页` : `第 ${page} 页` }

function resetFilters() {
  filterKpIds.value = []
  filterDifficulty.value = []
  selectedStages.value = []
  selectedQuestionType.value = ''
  filterErrorMin.value = null
  filterErrorMax.value = null
  searchQuery.value = ''
  questionUuid.value = ''
  filterTag.value = ''
  applyFilters()
}

async function loadTags() {
  tagLoading.value = true
  try {
    const response: any = await getTagList()
    const data = Array.isArray(response.data) ? response.data : (response.data?.items || [])
    allTags.value = data
    if (filterTag.value && !allTags.value.some((tag: any) => tag.name === filterTag.value)) {
      filterTag.value = ''
    }
  } catch (error) {
    console.error('加载标签失败:', error)
    uni.showToast({ title: '加载标签失败，请检查网络', icon: 'none' })
  } finally {
    tagLoading.value = false
  }
}

function onTagChange(event: any) {
  const index = Number(event?.detail?.value ?? 0)
  filterTag.value = index > 0 ? (allTags.value[index - 1]?.name || '') : ''
  applyFilters()
}

// 知识点选择
function onKpInputBlur() {
  // 延迟关闭，让点击选项的事件先触发
  setTimeout(() => { showKpDropdown.value = false }, 200)
}

function toggleFilterKp(kp: any) {
  const idx = filterKpIds.value.findIndex(id => String(id) === String(kp.id))
  if (idx >= 0) filterKpIds.value.splice(idx, 1)
  else filterKpIds.value.push(kp.id)
}

function clearKpSelection() {
  filterKpIds.value = []
}

function toggleKpFromTree(kp: any) {
  toggleFilterKp(kp)
  // 点击知识树节点自动筛选
  applyFilters()
}

// 难度选择
function toggleDifficulty(d: number) {
  const idx = filterDifficulty.value.indexOf(d)
  if (idx >= 0) filterDifficulty.value.splice(idx, 1)
  else filterDifficulty.value.push(d)
}

// 年级学期选择
function toggleStage(s: string) {
  const idx = selectedStages.value.indexOf(s)
  if (idx >= 0) selectedStages.value.splice(idx, 1)
  else selectedStages.value.push(s)
  // 选择后自动关闭
  setTimeout(() => { showStageDropdown.value = false }, 150)
}

// 题目选择
function toggleSelect(id: string | number) {
  const normalized = String(id)
  const idx = selectedIds.value.indexOf(normalized)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(normalized)
}

function addToSelected(q: any) {
  if (!isSelected(q.id)) selectedIds.value.push(String(q.id))
}

function removeFromSelected(id: string | number) {
  const idx = selectedIds.value.indexOf(String(id))
  if (idx >= 0) {
    selectedIds.value.splice(idx, 1)
    delete sortNos.value[String(id)]
  }
}

function removeFromOrdered(id: number) {
  removeFromSelected(id)
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    // 取消当前页全选
    for (const q of paginatedQuestions.value) {
      const idx = selectedIds.value.indexOf(String(q.id))
      if (idx >= 0) selectedIds.value.splice(idx, 1)
    }
  } else {
    // 当前页全选
    for (const q of paginatedQuestions.value) {
      if (!isSelected(q.id)) selectedIds.value.push(String(q.id))
    }
  }
}

// 批量加入
function batchAddSelected() {
  if (selectedIds.value.length === 0) {
    uni.showToast({ title: '请先勾选题目', icon: 'none' })
    return
  }
  uni.showToast({ title: `已将 ${selectedIds.value.length} 题加入列表`, icon: 'success' })
}

function clearSelected() {
  selectedIds.value = []
}

// 错误率样式
function getErrorRateClass(q: any): string {
  const rate = q.attempt_count > 0 ? (q.wrong_count || 0) / q.attempt_count * 100 : 0
  if (rate >= 70) return 'error-rate-high'
  if (rate >= 40) return 'error-rate-mid'
  return 'error-rate-low'
}

// 难度转整数（后端 difficulty 是 Decimal，如 1.00, 3.00）
function getDifficultyInt(q: any): number {
  return q.difficulty != null ? Math.round(Number(q.difficulty)) : 1
}

function onQuestionTypeChange(event: any) {
  const index = Number(event?.detail?.value)
  selectedQuestionType.value = questionTypeOptions[index]?.value || ''
}

function questionTypeText(q: any): string {
  return q?.question_type_label || getQuestionTypeLabel(q?.question_type)
}

// 题目详情
function showQuestionDetail(q: any) {
  currentQuestion.value = q
  showDetailModal.value = true
}

const levelTypes = [
  { value: 'practice', label: '练习' }, { value: 'review', label: '复习' },
  { value: 'retry', label: '重做' }, { value: 'variant', label: '变式' }, { value: 'check', label: '检查' },
]
const modePolicies = [
  { value: 'block_a', label: 'A模式分块' }, { value: 'allow_a', label: '允许A模式' },
  { value: 'require_guidance', label: '需要引导' }, { value: 'free_practice', label: '自由练习' },
]
function levelTypeText(value: string) { return levelTypes.find(item => item.value === value)?.label || value }
function modePolicyText(value: string) { return modePolicies.find(item => item.value === value)?.label || value }

function onDragStart(index: number) { draggingIndex.value = index }
function onDrop(index: number) {
  if (draggingIndex.value < 0 || draggingIndex.value === index) return
  const next = [...selectedIds.value]
  const [moved] = next.splice(draggingIndex.value, 1)
  next.splice(index, 0, moved)
  selectedIds.value = next
  draggingIndex.value = -1
}
function setSortNo(id: string | number, event: any) {
  const value = Number(event?.detail?.value ?? event?.target?.value)
  if (Number.isFinite(value) && value > 0) sortNos.value[String(id)] = Math.floor(value)
}

function addLevel() { levels.value.push({ name: '', type: 'practice', mode: 'block_a', questionIds: [] }) }
function removeLevel(i: number) { if (levels.value.length > 1) levels.value.splice(i, 1) }

// === 题目分配 ===
const showQuestionAssign = ref(false)
const currentAssignLevel = ref(0)

function openQuestionAssign(levelIndex: number) {
  currentAssignLevel.value = levelIndex
  showQuestionAssign.value = true
}

function closeQuestionAssign() {
  showQuestionAssign.value = false
}

function isQuestionAssignedForLevel(qid: string | number): boolean {
  const level = levels.value[currentAssignLevel.value]
  return level?.questionIds?.some(id => String(id) === String(qid)) || false
}

function toggleQuestionForLevel(qid: string | number) {
  const level = levels.value[currentAssignLevel.value]
  if (!level) return
  if (!level.questionIds) level.questionIds = []
  const normalized = String(qid)
  const idx = level.questionIds.findIndex(id => String(id) === normalized)
  if (idx >= 0) level.questionIds.splice(idx, 1)
  else level.questionIds.push(normalized)
}

function selectAllForLevel() {
  const level = levels.value[currentAssignLevel.value]
  if (!level) return
  level.questionIds = [...selectedIds.value]
}

function clearLevelQuestions() {
  const level = levels.value[currentAssignLevel.value]
  if (!level) return
  level.questionIds = []
}

function removeQuestionFromLevel(qid: string | number, levelIndex: number) {
  const level = levels.value[levelIndex]
  if (!level) return
  const idx = level.questionIds?.findIndex(id => String(id) === String(qid))
  if (idx !== undefined && idx >= 0) level.questionIds.splice(idx, 1)
}

// 移动题目顺序（direction: -1=上移, 1=下移）
function moveQuestion(levelIndex: number, questionIndex: number, direction: number) {
  const level = levels.value[levelIndex]
  if (!level || !level.questionIds) return
  const newIndex = questionIndex + direction
  if (newIndex < 0 || newIndex >= level.questionIds.length) return
  // 交换位置
  const temp = level.questionIds[questionIndex]
  level.questionIds[questionIndex] = level.questionIds[newIndex]
  level.questionIds[newIndex] = temp
}

function getQuestionSortNo(qid: string | number): number {
  const q = orderedQuestions.value.find(q => String(q.id) === String(qid))
  return q?.sort_no || 0
}

function getQuestionPreview(qid: string | number): string {
  const q = orderedQuestions.value.find(q => String(q.id) === String(qid))
  const preview = q?.stem_preview || ''
  return preview.length > 40 ? preview.substring(0, 40) + '...' : preview
}

async function publish() {
  // Keep the publish request explicit: an empty start value is sent as null
  // and the backend applies the assignment date as the default.
  const createForPublish = (payload: any) => missionApi.create({
    ...payload,
    start_at: form.value.start_at || null,
  })
  await saveMission(true, createForPublish)
}

async function saveDraft() {
  await saveMission(false)
}

async function saveMission(
  shouldPublish: boolean,
  createMission: (payload: any) => Promise<any> = (payload) => missionApi.create(payload),
) {
  if (!form.value.class_ids.length && targetStudentIds.value.length === 0) {
    uni.showToast({ title: '请选择班级或指定学生', icon: 'none' })
    step.value = 1
    return
  }
  if (targetMode.value === 'students' && targetStudentIds.value.length === 0) {
    uni.showToast({ title: '请选择至少一名学生', icon: 'none' })
    step.value = 1
    return
  }
  if (!form.value.end_at) {
    uni.showToast({ title: '请选择完成日期', icon: 'none' })
    step.value = 1
    return
  }
  if (selectedIds.value.length === 0) {
    uni.showToast({ title: '请先选择至少一道题目', icon: 'none' })
    step.value = 2
    return
  }

  const fullName = editMode.value && form.value.mission_name
    ? form.value.mission_name
    : `${selectedClassName.value || '指定学生'} ${assignmentDate.value} ${assignmentTitle.value.trim() || '作业'}`
  const orderedIds = orderedQuestions.value
    .sort((a: any, b: any) => Number(a.sort_no) - Number(b.sort_no))
    .map((question: any) => String(question.id))

  try {
    uni.showLoading({ title: shouldPublish ? '发布中...' : '保存中...' })
    let missionId: string
    const payload = {
      mission_name: fullName,
      goal_text: form.value.goal_text,
      start_at: form.value.start_at || new Date().toISOString(),
      end_at: form.value.end_at,
      class_id: form.value.class_id,
      class_ids: form.value.class_ids,
      course_id: courseId.value,
      target_student_ids: targetMode.value === 'students' ? targetStudentIds.value : [],
      assignment_mode: 'flat',
      mission_kind: missionKind.value,
      source_type: sourceType.value,
    }

    if (editMode.value) {
      missionId = editMissionId.value
      await missionApi.update(missionId, payload)
    } else {
      const res = await createMission(payload)
      missionId = res.data?.id
      if (!missionId) throw new Error('作业创建失败')
      if (pendingFavoriteQuestionIds.value.length) {
        await missionApi.addFavorites(missionId, pendingFavoriteQuestionIds.value)
      }
    }

    await missionApi.saveQuestions(missionId, orderedIds)
    if (shouldPublish) await missionApi.publish(missionId)

    uni.hideLoading()
    uni.showToast({ title: shouldPublish ? '发布成功' : '草稿已保存', icon: 'success' })
    setTimeout(() => uni.navigateTo({ url: '/pages/teacher/layout' }), 1200)
  } catch (e: any) {
    uni.hideLoading()
    console.error('保存作业失败:', e)
    const msg = e?.data?.message || e?.message || '保存失败，请重试'
    uni.showToast({ title: msg, icon: 'none' })
  }
}

onMounted(async () => {
  form.value.start_at = new Date().toISOString()
  // 先加载班级列表（编辑模式需要用到）
  await loadClasses()

  const pages = getCurrentPages()
  const page = pages[pages.length - 1] as any
  const id = String(page.options?.id || '')
  courseId.value = page.options?.courseId ? String(page.options.courseId) : null
  if (page.options?.favoriteQuestionIds) {
    pendingFavoriteQuestionIds.value = String(page.options.favoriteQuestionIds).split(',').filter(Boolean)
  }

  if (id) {
    // 编辑模式：加载已有作业数据
    editMode.value = true
    editMissionId.value = id
    await loadMissionData(id)
  }

  await Promise.all([loadKnowledgeTree(), loadTags()])
  await loadQuestions()
})

// 加载已有作业数据（编辑模式）
async function loadMissionData(id: string) {
  try {
    const res: any = await missionApi.detail(id)
    const data = res.data
    if (!data) return

    form.value.mission_name = data.mission_name || ''
    form.value.goal_text = data.goal_text || ''
    form.value.start_at = data.start_at || ''
    form.value.end_at = data.end_at || ''
    form.value.class_id = data.class_obj || null
    form.value.class_ids = (data.class_ids || (data.class_obj ? [data.class_obj] : [])).map((value: any) => String(value))
    missionKind.value = data.mission_kind === 'drill' ? 'drill' : 'regular'
    sourceType.value = (data.source_type || 'question_bank') as SourceType
    targetStudentIds.value = (data.target_student_ids || []).map((value: any) => String(value))
    targetMode.value = targetStudentIds.value.length ? 'students' : 'class'
    assignmentTitle.value = data.mission_name || '作业'
    if (form.value.class_ids.length === 1) await loadClassStudents(form.value.class_ids[0])

    // 加载班级名称（此时 classList 已加载）
    selectedClassName.value = classList.value
      .filter((c: any) => form.value.class_ids.includes(String(c.id)))
      .map((c: any) => c.class_name).join('、')

    // 平铺读取题目，兼容历史作业的关卡关联顺序。
    try {
      const qRes: any = await missionApi.questions(id)
      const questions = Array.isArray(qRes.data) ? qRes.data : []
      allQuestions.value = questions
      selectedIds.value = questions.map((q: any) => String(q.id))
    } catch (e) {
      console.error('加载作业题目失败:', e)
    }
  } catch (e) {
    console.error('加载作业数据失败:', e)
  }
}

// 加载班级列表
async function loadClasses() {
  try {
    const res: any = await classApi.simpleList()
    classList.value = res.data?.data || res.data || []
  } catch (e) {
    console.error('加载班级列表失败:', e)
  }
}

function selectClass(cls: any) {
  form.value.class_id = cls.id
  selectedClassName.value = cls.class_name
  showClassDropdown.value = false
  targetMode.value = 'class'
  targetStudentIds.value = []
  loadClassStudents(cls.id)
}

function toggleClass(cls: any) {
  const id = String(cls.id)
  const index = form.value.class_ids.indexOf(id)
  if (index >= 0) form.value.class_ids.splice(index, 1)
  else form.value.class_ids.push(id)
  form.value.class_id = form.value.class_ids[0] || null
  selectedClassName.value = classList.value
    .filter(item => form.value.class_ids.includes(String(item.id)))
    .map(item => item.class_name).join('、')
  showClassDropdown.value = false
  if (form.value.class_ids.length === 1) loadClassStudents(form.value.class_ids[0])
  else {
    classStudents.value = []
    targetMode.value = 'class'
    targetStudentIds.value = []
  }
}

function setTargetMode(mode: 'class' | 'students') {
  if (mode === 'students' && (!form.value.class_id || form.value.class_ids.length !== 1)) {
    uni.showToast({ title: '请先选择班级', icon: 'none' })
    return
  }
  targetMode.value = mode
  if (mode === 'class') targetStudentIds.value = []
}

async function loadClassStudents(classId: number) {
  try {
    const res: any = await classApi.students(classId)
    classStudents.value = res.data?.items || []
  } catch (e) {
    classStudents.value = []
    console.error('加载班级学生失败:', e)
  }
}

function toggleTargetStudent(studentId: string) {
  const index = targetStudentIds.value.indexOf(studentId)
  if (index >= 0) targetStudentIds.value.splice(index, 1)
  else targetStudentIds.value.push(studentId)
}
</script>

<style scoped>
.create-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 0;
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
  padding: 30rpx 40rpx;
}
.target-students { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.target-student { display: flex; gap: 8px; align-items: center; padding: 6px 10px; border: 1px solid #dcdfe6; border-radius: 4px; color: #606266; cursor: pointer; }
.target-student.selected { color: #409eff; border-color: #409eff; background: #ecf5ff; }
.target-empty { color: #909399; font-size: 12px; }
.target-mode-group { display: flex; gap: 12px; margin-top: 8px; }
.target-mode { padding: 8px 18px; border: 1px solid #dcdfe6; border-radius: 6px; color: #606266; background: #fff; cursor: pointer; }
.target-mode.active { color: #409eff; border-color: #409eff; background: #ecf5ff; }
.target-mode.disabled { color: #c0c4cc; border-color: #ebeef5; background: #f5f7fa; cursor: not-allowed; }
.target-hint { display: block; margin-top: 8px; color: #909399; font-size: 24rpx; }
.name-builder { display: flex; align-items: center; gap: 8px; }
.name-prefix { color: #606266; white-space: nowrap; }
.name-input { flex: 1; }
.save-btn { background: #909399; color: #fff; }
.flat-assignment-hint { display: flex; flex-direction: column; gap: 12px; }
.form-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
  margin-bottom: 30rpx;
}
.form-item {
  margin-bottom: 24rpx;
  position: relative;
}
.label {
  font-size: 26rpx;
  color: #333;
  margin-bottom: 8rpx;
  display: block;
}
input, .form-textarea {
  width: 100%;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  padding: 24rpx 16rpx;
  font-size: 28rpx;
  background: #fff;
  box-sizing: border-box;
  min-height: 88rpx;
  line-height: 40rpx;
}
.form-textarea {
  min-height: 120rpx;
}
.date-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  padding: 24rpx 16rpx;
  font-size: 28rpx;
  background: #fff;
  box-sizing: border-box;
  min-height: 88rpx;
  cursor: pointer;
}
.readonly-date-picker { cursor: default; background: #f5f7fa; }
.date-hint { color: #909399; font-size: 24rpx; }
.class-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  padding: 24rpx 16rpx;
  font-size: 28rpx;
  background: #fff;
  box-sizing: border-box;
  min-height: 88rpx;
  cursor: pointer;
  position: relative;
}
.class-picker:hover { border-color: #409eff; background: #f5f9ff; }
.class-value { color: #333; font-size: 28rpx; flex: 1; }
.class-value:empty::before { content: '请选择班级'; color: #999; }
.class-arrow { font-size: 36rpx; margin-left: 12rpx; }
.class-dropdown {
  background: #fff;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.1);
  z-index: 100;
  max-height: 400rpx;
  overflow-y: auto;
  margin-top: 8rpx;
}
.class-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20rpx 16rpx;
  border-bottom: 1rpx solid #f0f0f0;
  cursor: pointer;
}
.class-option:hover { background: #f5f9ff; }
.class-option.active { background: #ecf5ff; }
.class-opt-name { font-size: 26rpx; color: #333; }
.class-opt-check { font-size: 26rpx; color: #409eff; margin-left: 12rpx; }
.class-empty {
  text-align: center;
  padding: 30rpx;
  color: #999;
  font-size: 24rpx;
}
.date-picker:hover {
  border-color: #409eff;
  background: #f5f9ff;
}
.date-value {
  color: #333;
  font-size: 28rpx;
  flex: 1;
}
.date-value:empty::before {
  content: '请选择截止时间';
  color: #999;
}
.date-arrow {
  font-size: 36rpx;
  margin-left: 12rpx;
}
.date-modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}
.date-panel {
  width: 80%;
  max-width: 500px;
  background: #fff;
  border-radius: 16rpx;
  padding: 0 30rpx 30rpx;
  box-shadow: 0 8rpx 30rpx rgba(0, 0, 0, 0.15);
}
.date-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 30rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
  margin-bottom: 30rpx;
}
.date-close-btn, .date-confirm-btn {
  font-size: 30rpx;
  padding: 10rpx 20rpx;
}
.date-close-btn { color: #999; }
.date-confirm-btn { color: #409eff; font-weight: bold; }
.date-picker-input {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 16rpx;
  margin-bottom: 20rpx;
  background: #f8f8f8;
  border-radius: 8rpx;
  cursor: pointer;
}
.date-picker-label { font-size: 28rpx; color: #666; }
.date-picker-value { font-size: 30rpx; color: #333; font-weight: 500; }

/* ====== Step 2: 知识树+筛选 ====== */
.step2-container {
  display: flex;
  gap: 20rpx;
  width: 100%;
  height: calc(100vh - 120rpx);
  min-height: 0;
  min-width: 0;
}

/* 知识树 */
.knowledge-tree {
  width: 240px;
  box-sizing: border-box;
  background: #fff;
  border-radius: 12rpx;
  padding: 20rpx;
  overflow-y: auto;
  flex-shrink: 0;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.05);
  min-height: 75vh;
}
.tree-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 16rpx;
}
.tree-loading, .tree-empty {
  color: #999;
  font-size: 24rpx;
  padding: 20rpx 0;
}
.tree-content { }
.tree-node {
  display: flex;
  align-items: center;
  padding: 8rpx 4rpx;
  cursor: pointer;
  border-radius: 4rpx;
}
.tree-node:hover { background: #f5f5f5; }
.arrow { font-size: 20rpx; color: #999; margin-right: 6rpx; width: 24rpx; }
.tree-label { font-size: 24rpx; color: #333; flex: 1; }
.tree-children { padding-left: 16rpx; }
.tree-kp {
  display: flex;
  align-items: center;
  padding: 6rpx 8rpx;
  cursor: pointer;
  border-radius: 4rpx;
  margin: 2rpx 0;
}
.tree-kp:hover { background: #ecf5ff; }
.tree-kp.active { background: #ecf5ff; }
.kp-name { font-size: 22rpx; color: #555; }

/* 右侧面板 */
.right-panel {
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.05);
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

/* 筛选区 */
.filter-section {
  background: #f8f9fa;
  border-radius: 8rpx;
  padding: 16rpx;
  margin-bottom: 16rpx;
  box-sizing: border-box;
  max-width: 100%;
}
.filter-row {
  display: flex;
  gap: 16rpx;
  min-width: 0;
  margin-bottom: 12rpx;
  align-items: flex-end;
  flex-wrap: wrap;
}
.filter-row:last-child { margin-bottom: 0; }
.filter-item {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  min-width: 0;
  max-width: 100%;
  position: relative;
}
.filter-kp-item {
  position: relative;
}
.filter-stage-item {
  position: relative;
}
.filter-type-item { flex: 0 0 auto; }
.type-select { width: 220rpx; }
.filter-label {
  font-size: 22rpx;
  color: #666;
}
.kp-input-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
  min-width: 0;
  max-width: 100%;
}
.kp-search-input {
  width: 320rpx;
  max-width: 100%;
  box-sizing: border-box;
  flex: 1 1 240rpx;
  height: 56rpx;
  min-height: 56rpx;
  padding: 0 12rpx;
  border: 1rpx solid #ddd;
  border-radius: 4rpx;
  font-size: 22rpx;
  background: #fff;
  line-height: 54rpx;
}
.kp-search-input:focus {
  border-color: #409eff;
}
.kp-count-badge {
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  padding: 2rpx 10rpx;
  font-size: 18rpx;
  min-width: 28rpx;
  text-align: center;
}
.multi-select {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10rpx 16rpx;
  background: #fff;
  border: 1rpx solid #ddd;
  border-radius: 6rpx;
  width: 200rpx;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  cursor: pointer;
  font-size: 24rpx;
}
.multi-select:hover { border-color: #409eff; }
.multi-select-text { color: #333; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dropdown-arrow { font-size: 20rpx; color: #999; margin-left: 8rpx; }

/* 知识点下拉 */
.kp-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  width: 360rpx;
  max-width: calc(100vw - 40rpx);
  max-height: 400rpx;
  background: #fff;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.15);
  z-index: 200;
  margin-top: 4rpx;
}
.kp-dropdown-header {
  display: flex;
  justify-content: space-between;
  padding: 12rpx 16rpx;
  border-bottom: 1rpx solid #eee;
}
.kp-dropdown-title { font-size: 24rpx; font-weight: bold; color: #333; }
.kp-dropdown-clear { font-size: 22rpx; color: #409eff; cursor: pointer; }
.kp-dropdown-list { max-height: 300rpx; }
.kp-option {
  display: flex;
  align-items: center;
  padding: 8rpx 16rpx;
  cursor: pointer;
}
.kp-option:hover { background: #f5f5f5; }
.kp-option.selected { background: #ecf5ff; }
.kp-check { font-size: 24rpx; margin-right: 8rpx; width: 28rpx; }
.kp-label { font-size: 22rpx; color: #333; }
.kp-dropdown-empty {
  text-align: center;
  padding: 20rpx;
  color: #999;
  font-size: 22rpx;
}

/* 学期下拉 */
.stage-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  width: 260rpx;
  max-height: 500rpx;
  background: #fff;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.15);
  z-index: 200;
  margin-top: 4rpx;
  overflow-y: auto;
}
.stage-option {
  display: flex;
  align-items: center;
  padding: 10rpx 16rpx;
  cursor: pointer;
  min-height: 44rpx;
}
.stage-option:hover { background: #f5f5f5; }
.stage-option.selected { background: #ecf5ff; }
.stage-check { font-size: 24rpx; margin-right: 8rpx; }
.stage-label { font-size: 22rpx; color: #333; }

/* 难度按钮 */
.diff-buttons {
  display: flex;
  gap: 6rpx;
}
.diff-btn {
  padding: 8rpx 12rpx;
  background: #fff;
  border: 1rpx solid #ddd;
  border-radius: 6rpx;
  cursor: pointer;
  font-size: 20rpx;
  color: #999;
}
.diff-btn:hover, .diff-btn.active {
  background: #fff3e0;
  border-color: #ff9800;
  color: #ff9800;
}

/* 范围输入 */
.range-inputs {
  display: flex;
  align-items: center;
  gap: 4rpx;
}
.range-input {
  width: 80rpx;
  box-sizing: border-box;
  height: 56rpx;
  min-height: 56rpx;
  padding: 0 8rpx;
  border: 1rpx solid #ddd;
  border-radius: 4rpx;
  font-size: 22rpx;
  text-align: center;
  background: #fff;
  line-height: 54rpx;
}
.range-sep { color: #999; font-size: 22rpx; }
.tag-refresh-btn {
  margin-top: 6rpx;
  padding: 4rpx 12rpx;
  font-size: 20rpx;
  line-height: 1.4;
}
.search-input {
  width: 240rpx;
  max-width: 100%;
  box-sizing: border-box;
  flex: 0 1 240rpx;
  display: block;
  height: 56rpx !important;
  min-height: 56rpx !important;
  max-height: 56rpx;
  padding: 0 12rpx;
  border: 1rpx solid #ddd;
  border-radius: 4rpx;
  font-size: 22rpx;
  background: #fff;
  line-height: 54rpx;
}

/* 筛选按钮 */
.filter-actions {
  display: flex;
  gap: 8rpx;
  align-items: center;
  flex-wrap: wrap;
}
.filter-btn, .reset-btn {
  padding: 10rpx 20rpx;
  font-size: 22rpx;
  border-radius: 6rpx;
  height: auto;
  line-height: normal;
}
.filter-btn { background: #409eff; color: #fff; }
.reset-btn { background: #f0f0f0; color: #666; }

/* 操作栏 */
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12rpx 0;
  margin-bottom: 12rpx;
  border-bottom: 1rpx solid #eee;
}
.action-left { display: flex; gap: 12rpx; align-items: center; }
.select-all-row {
  padding: 8rpx 12rpx;
  font-size: 24rpx;
  color: #409eff;
  cursor: pointer;
  border: 1rpx solid #409eff;
  border-radius: 6rpx;
}
.batch-add-btn {
  padding: 10rpx 24rpx;
  background: #4caf50;
  color: #fff;
  border-radius: 6rpx;
  font-size: 24rpx;
  height: auto;
  line-height: normal;
}
.create-task-btn {
  padding: 10rpx 24rpx;
  background: #ff9800;
  color: #fff;
  border-radius: 6rpx;
  font-size: 24rpx;
  height: auto;
  line-height: normal;
}
.step2-back-btn {
  flex: 0 0 auto;
  margin: 0;
  padding: 10rpx 24rpx;
  background: #909399;
  color: #fff;
  border-radius: 6rpx;
  font-size: 24rpx;
  height: auto;
  line-height: normal;
}
.list-btn {
  padding: 10rpx 20rpx;
  background: #fff;
  border: 1rpx solid #409eff;
  color: #409eff;
  border-radius: 6rpx;
  font-size: 24rpx;
  display: flex;
  align-items: center;
  gap: 8rpx;
  height: auto;
  line-height: normal;
}
.list-badge {
  background: #f44336;
  color: #fff;
  border-radius: 50%;
  padding: 2rpx 10rpx;
  font-size: 20rpx;
  min-width: 32rpx;
  text-align: center;
}

/* 题目表格 */
.question-table { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.table-header {
  display: flex;
  align-items: center;
  padding: 12rpx 8rpx;
  background: #f5f7fa;
  border-radius: 6rpx;
  font-size: 22rpx;
  font-weight: bold;
  color: #666;
  flex-shrink: 0;
}
.table-body {
  flex: 1;
  min-height: 0;
  height: 0;
  overflow-y: auto;
}
.table-row {
  display: flex;
  align-items: center;
  padding: 12rpx 8rpx;
  border-bottom: 1rpx solid #f0f0f0;
  font-size: 22rpx;
  min-height: 68rpx;
}
.table-row:hover { background: #f9f9f9; }
.table-row.row-selected { background: #e8f5e9; }
.col { padding: 0 8rpx; box-sizing: border-box; flex-shrink: 0; }
.col-check {
  width: 64rpx;
  min-height: 44rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  cursor: pointer;
  font-size: 36rpx;
  line-height: 1;
}
.col-no { width: 72rpx; text-align: center; color: #999; font-size: 22rpx; }
.col-stem { flex: 1 1 auto; min-width: 0; color: #333; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-stem:hover { color: #409eff; }
.col-type { width: 140rpx; text-align: center; color: #606266; white-space: nowrap; }
.col-diff { width: 160rpx; text-align: center; }
.diff-1 { color: #4caf50; }
.diff-2 { color: #8bc34a; }
.diff-3 { color: #ff9800; }
.diff-4 { color: #f44336; }
.diff-5 { color: #9c27b0; }
.diff-score { font-size: 18rpx; color: #999; margin-left: 4rpx; }
.col-kp { width: 110rpx; text-align: center; color: #666; font-size: 22rpx; }
.col-attempts { width: 120rpx; text-align: center; color: #666; font-size: 22rpx; }
.col-errors { width: 120rpx; text-align: center; color: #666; font-size: 22rpx; }
.col-error-rate { width: 140rpx; text-align: center; font-weight: bold; font-size: 22rpx; }
.error-rate-high { color: #f44336; }
.error-rate-mid { color: #ff9800; }
.error-rate-low { color: #4caf50; }
.col-actions { width: 240rpx; display: flex; gap: 16rpx; justify-content: center; align-items: center; flex-wrap: nowrap; white-space: nowrap; }
.action-link { flex: 0 0 auto; color: #409eff; cursor: pointer; font-size: 22rpx; padding: 4rpx 8rpx; border-radius: 4rpx; white-space: nowrap; }
.action-link:hover { background: #ecf5ff; }
.action-add { color: #4caf50; }
.action-added { color: #999; cursor: default; }

/* 分页 */
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20rpx;
  padding: 18rpx 0;
  margin-top: 12rpx;
  border-top: 1rpx solid #eee;
}
.page-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10rpx;
  margin-left: auto;
}
.page-controls button {
  min-width: 76rpx;
  height: 48rpx;
  padding: 0 14rpx;
  font-size: 22rpx;
  background: #fff;
  border: 1rpx solid #dcdfe6;
  border-radius: 6rpx;
  line-height: 46rpx;
}
.page-controls button:disabled { opacity: 0.5; }
.page-info, .page-total, .page-size-label { font-size: 22rpx; color: #606266; white-space: nowrap; }
.page-picker, .page-size-select, .jump-page-input { height: 48rpx; box-sizing: border-box; border: 1rpx solid #dcdfe6; border-radius: 6rpx; background: #fff; color: #303133; font-size: 22rpx; }
.page-picker, .page-size-select { display: flex; align-items: center; justify-content: center; min-width: 0; line-height: 1.2; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.page-picker { width: 190rpx; padding: 0 10rpx; }
.page-size-select { width: 124rpx; padding: 0 10rpx; }
.jump-page-input {
  width: 88rpx;
  height: 48rpx !important;
  min-height: 48rpx !important;
  max-height: 48rpx;
  padding: 0 10rpx;
  line-height: 46rpx;
  text-align: center;
  margin: 0;
}

@media screen and (max-width: 900px) {
  .pagination { align-items: flex-start; flex-direction: column; }
  .page-controls { width: 100%; justify-content: flex-start; margin-left: 0; }
}

.table-loading, .table-empty {
  text-align: center;
  padding: 80rpx;
  color: #999;
  font-size: 26rpx;
}

/* 已选题目弹窗 */
.selected-modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}
.selected-panel {
  width: 80%;
  max-width: 700px;
  background: #fff;
  border-radius: 16rpx;
  padding: 0 0 20rpx;
  box-shadow: 0 8rpx 30rpx rgba(0,0,0,0.15);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.selected-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24rpx;
  border-bottom: 1rpx solid #eee;
}
.selected-title { font-size: 28rpx; font-weight: bold; color: #333; }
.selected-header-actions { display: flex; gap: 16rpx; align-items: center; }
.selected-clear { font-size: 24rpx; color: #f44336; cursor: pointer; }
.selected-close-btn { font-size: 32rpx; color: #999; cursor: pointer; }
.selected-empty { text-align: center; padding: 60rpx; color: #999; font-size: 26rpx; }
.selected-list { flex: 1; max-height: 50vh; padding: 0 24rpx; }
.selected-item {
  display: flex;
  align-items: center;
  padding: 12rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
  gap: 12rpx;
}
.selected-no { font-size: 22rpx; color: #999; width: 40rpx; flex-shrink: 0; }
.selected-stem { flex: 1; font-size: 24rpx; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.selected-stem { white-space: normal; overflow-wrap: anywhere; word-break: break-word; }
.selected-remove { font-size: 22rpx; color: #f44336; cursor: pointer; flex-shrink: 0; white-space: nowrap; }
.selected-stats {
  display: flex;
  gap: 24rpx;
  padding: 16rpx 24rpx;
  background: #f8f8f8;
  border-top: 1rpx solid #eee;
}
.stat-item { font-size: 22rpx; color: #666; }

/* 题目详情弹窗 */
.detail-modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}
.detail-panel {
  width: 80%;
  max-width: 700px;
  background: #fff;
  border-radius: 16rpx;
  box-shadow: 0 8rpx 30rpx rgba(0,0,0,0.15);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24rpx;
  border-bottom: 1rpx solid #eee;
}
.detail-title { font-size: 28rpx; font-weight: bold; color: #333; }
.detail-close { font-size: 32rpx; color: #999; cursor: pointer; }
.detail-body { flex: 1; padding: 0 24rpx; max-height: 60vh; }
.detail-section {
  padding: 16rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
}
.detail-section-title {
  font-size: 24rpx;
  font-weight: bold;
  color: #409eff;
  display: block;
  margin-bottom: 8rpx;
}
.detail-stem, .detail-options-text, .detail-answer, .detail-explanation,
.detail-kp, .detail-stage, .detail-difficulty, .detail-ai, .detail-stats {
  font-size: 24rpx;
  color: #333;
  line-height: 1.6;
  display: block;
}
.detail-footer {
  padding: 16rpx 24rpx;
  border-top: 1rpx solid #eee;
  text-align: center;
}
.detail-add-btn {
  padding: 12rpx 40rpx;
  background: #4caf50;
  color: #fff;
  border-radius: 8rpx;
  font-size: 26rpx;
  height: auto;
  line-height: normal;
}

/* 通用 */
.nav-btns { display: flex; gap: 20rpx; margin-top: 30rpx; }
.back-btn { background: #eee; color: #333; flex: 1; }
.next-btn { background: #409eff; color: #fff; flex: 2; }
.publish-btn { background: #4caf50; color: #fff; flex: 2; }
.preview-card { background: #fff; border-radius: 12rpx; padding: 30rpx; margin-bottom: 20rpx; }
.preview-name { font-size: 32rpx; font-weight: bold; display: block; margin-bottom: 20rpx; }
.preview-row { display: flex; justify-content: space-between; padding: 12rpx 0; border-bottom: 1rpx solid #f0f0f0; }
.preview-label { color: #666; font-size: 24rpx; }
.preview-value { font-size: 24rpx; color: #333; font-weight: bold; }
.preview-questions { margin-top: 20rpx; }
.preview-questions-title { font-size: 24rpx; font-weight: bold; color: #333; display: block; margin-bottom: 12rpx; }
.preview-question-item {
  display: flex;
  align-items: center;
  padding: 8rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
  gap: 12rpx;
  font-size: 22rpx;
}
.preview-q-no { color: #409eff; width: 60rpx; flex-shrink: 0; }
.preview-q-stem { flex: 1; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.preview-q-diff { color: #ff9800; width: 60rpx; text-align: center; flex-shrink: 0; }
/* ====== Step 3: 编排题目 + 配置关卡 ====== */
.step3-container {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}
.step3-section {
  background: #fff;
  border-radius: 12rpx;
  padding: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.05);
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.section-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
}
.section-hint {
  font-size: 22rpx;
  color: #999;
}
.ordered-question-list {
  max-height: 400rpx;
  margin-bottom: 16rpx;
}
.ordered-item {
  display: flex;
  align-items: center;
  padding: 10rpx 8rpx;
  border-bottom: 1rpx solid #f0f0f0;
  gap: 8rpx;
  font-size: 22rpx;
}
.ordered-item:hover {
  background: #f9f9f9;
}
.drag-handle {
  color: #ccc;
  font-size: 28rpx;
  cursor: grab;
  width: 32rpx;
  text-align: center;
  flex-shrink: 0;
}
.sort-input {
  width: 60rpx;
  height: 44rpx;
  padding: 4rpx 8rpx;
  border: 1rpx solid #ddd;
  border-radius: 4rpx;
  font-size: 20rpx;
  text-align: center;
  background: #fff;
  min-height: auto;
  line-height: normal;
  flex-shrink: 0;
}
.ordered-stem {
  flex: 1;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.subject-picker { margin: 16rpx 0; }
.subject-picker { display: block; width: 100%; max-width: 100%; }
.subject-picker-value { display: flex; align-items: center; justify-content: center; width: 100%; min-width: 0; box-sizing: border-box; padding: 12rpx 16rpx; border: 1rpx solid #dcdfe6; border-radius: 6rpx; color: #409eff; background: #fff; font-size: 24rpx; line-height: 1.2; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ordered-diff {
  width: 80rpx;
  text-align: center;
  color: #ff9800;
  flex-shrink: 0;
}
.ordered-remove {
  color: #f44336;
  cursor: pointer;
  font-size: 24rpx;
  flex-shrink: 0;
  padding: 4rpx;
}
.level-list { max-height: 350px; margin-bottom: 16rpx; }
.level-config { background: #fff; border: 1rpx solid #ddd; padding: 16rpx; margin-bottom: 12rpx; border-radius: 8rpx; }
.level-header { display: flex; justify-content: space-between; margin-bottom: 12rpx; }
.level-title { font-weight: bold; font-size: 26rpx; }
.remove-btn { color: #f44336; font-size: 24rpx; cursor: pointer; }
.level-options { display: flex; gap: 16rpx; margin-top: 12rpx; }
.level-options picker { flex: 1; min-width: 0; }
.picker-display { display: flex; align-items: center; justify-content: center; width: 100%; min-width: 0; box-sizing: border-box; padding: 12rpx; background: #f8f8f8; border-radius: 4rpx; font-size: 24rpx; line-height: 1.2; text-align: center; color: #666; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 关卡题目分配区 */
.level-questions { margin-top: 16rpx; padding-top: 12rpx; border-top: 1rpx solid #eee; }
.level-q-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8rpx; }
.level-q-title { font-size: 22rpx; color: #666; }
.level-q-assign-btn { font-size: 22rpx; color: #409eff; cursor: pointer; }
.level-q-list { max-height: 200rpx; overflow-y: auto; }
.level-q-item { display: flex; align-items: center; padding: 6rpx 4rpx; gap: 6rpx; font-size: 20rpx; }
.level-q-no { color: #409eff; width: 36rpx; flex-shrink: 0; text-align: center; }
.level-q-stem { flex: 1; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.level-q-actions { display: flex; align-items: center; gap: 4rpx; flex-shrink: 0; }
.level-q-move {
  color: #409eff; cursor: pointer; font-size: 22rpx;
  width: 36rpx; height: 36rpx;
  display: flex; align-items: center; justify-content: center;
  border-radius: 6rpx;
  background: #f0f4ff;
  border: 1rpx solid #d0d9f5;
  transition: all 0.15s;
  font-weight: bold;
}
.level-q-move:hover { background: #dce4ff; border-color: #409eff; }
.level-q-move.disabled { color: #ddd; cursor: not-allowed; background: #f5f5f5; border-color: #eee; }
.level-q-move.disabled:hover { background: #f5f5f5; border-color: #eee; }
.level-q-remove { color: #f44336; cursor: pointer; font-size: 20rpx; padding: 2rpx 6rpx; border-radius: 4rpx; }
.level-q-remove:hover { background: #ffebee; }
.level-q-empty { text-align: center; padding: 16rpx; color: #999; font-size: 22rpx; }

/* 题目分配弹窗 */
.assign-modal {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 999;
}
.assign-panel {
  width: 80%; max-width: 700px; background: #fff; border-radius: 16rpx;
  box-shadow: 0 8rpx 30rpx rgba(0,0,0,0.15); max-height: 80vh;
  display: flex; flex-direction: column;
  overflow: hidden;
}
.assign-header { display: flex; justify-content: space-between; align-items: center; padding: 24rpx; border-bottom: 1rpx solid #eee; }
.assign-title { font-size: 26rpx; font-weight: bold; color: #333; }
.assign-close { font-size: 32rpx; color: #999; cursor: pointer; }
.assign-actions { display: flex; gap: 24rpx; padding: 12rpx 24rpx; background: #f8f8f8; }
.assign-select-all { font-size: 22rpx; color: #409eff; cursor: pointer; }
.assign-clear { font-size: 22rpx; color: #f44336; cursor: pointer; }
.assign-list { flex: 1; max-height: 50vh; padding: 0; overflow: hidden; }
.assign-item {
  display: flex; align-items: center; padding: 12rpx 32rpx; border-bottom: 1rpx solid #f0f0f0;
  gap: 12rpx; cursor: pointer; font-size: 22rpx;
}
.assign-item.assigned { background: #e8f5e9; padding: 12rpx 32rpx; border-radius: 0; }
.assign-check { font-size: 24rpx; width: 28rpx; flex-shrink: 0; }
.assign-no { color: #409eff; width: 36rpx; flex-shrink: 0; }
.assign-stem { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.assign-diff { color: #ff9800; flex-shrink: 0; padding-left: 16rpx; padding-right: 32rpx; }
.assign-item.assigned { background: #e8f5e9; padding: 12rpx 32rpx; border-radius: 0; }
.assign-check { font-size: 24rpx; width: 28rpx; flex-shrink: 0; }
.assign-no { color: #409eff; width: 36rpx; flex-shrink: 0; }
.assign-stem { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.assign-footer { display: flex; justify-content: space-between; align-items: center; padding: 16rpx 24rpx; border-top: 1rpx solid #eee; }
.assign-count { font-size: 22rpx; color: #666; }
.assign-confirm { padding: 12rpx 40rpx; background: #4caf50; color: #fff; border-radius: 8rpx; font-size: 24rpx; height: auto; line-height: normal; }

/* 小屏适配 */
@media (max-width: 768px) {
  .main { margin-left: 60px; padding: 20rpx; }
  .step2-container { flex-direction: column; }
  .knowledge-tree { width: auto; max-height: 30vh; }
  .filter-row { flex-direction: column; }
}
</style>
