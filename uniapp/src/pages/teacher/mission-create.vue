<template>
  <view class="create-page">
    <TeacherSidebar activeItem="missions" />

    <!-- 右侧内容区 -->
    <view class="main">
      <!-- Step 1: 基本信息 -->
      <view v-if="step === 1" class="form">
        <view class="form-title">基本信息</view>
        <view class="form-item">
          <text class="label">任务名称 *</text>
          <input v-model="form.mission_name" placeholder="如：二次函数练习" />
        </view>
        <view class="form-item">
          <text class="label">选择班级 *</text>
          <view class="class-picker" @click="showClassDropdown = !showClassDropdown">
            <text class="class-value">{{ selectedClassName || '请选择班级' }}</text>
            <text class="class-arrow">📋</text>
          </view>
          <!-- 班级下拉框 -->
          <view v-if="showClassDropdown" class="class-dropdown">
            <view v-for="cls in classList" :key="cls.id"
                  :class="['class-option', {active: form.class_id === cls.id}]"
                  @click="selectClass(cls)">
              <text class="class-opt-name">{{ cls.class_name }}</text>
              <text v-if="form.class_id === cls.id" class="class-opt-check">✓</text>
            </view>
            <view v-if="classList.length === 0" class="class-empty">
              <text>暂无班级，请先创建班级</text>
            </view>
          </view>
        </view>
        <view class="form-item">
          <text class="label">任务目标</text>
          <textarea v-model="form.goal_text" placeholder="描述任务目标..." class="form-textarea" />
        </view>
        <view class="form-item">
          <text class="label">开始时间</text>
          <view class="date-picker" @click="openStartDatePicker">
            <text class="date-value">{{ form.start_at || '请选择开始时间' }}</text>
            <text class="date-arrow">📅</text>
          </view>
        </view>
        <view class="form-item">
          <text class="label">截止时间 *</text>
          <view class="date-picker" @click="openDatePicker">
            <text class="date-value">{{ form.end_at || '请选择截止时间' }}</text>
            <text class="date-arrow">📅</text>
          </view>
        </view>
        <button class="next-btn" @click="nextStep">下一步：选择题目</button>
      </view>

      <!-- Step 2: 选择题目 -->
      <view v-if="step === 2" class="step2-container">
        <!-- 左侧知识树 -->
        <view class="knowledge-tree">
          <text class="tree-title">知识树</text>
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
            </view>
            <view class="filter-row">
              <view class="filter-item">
                <text class="filter-label">知识点数</text>
                <view class="range-inputs">
                  <input v-model.number="filterKpCountMin" type="number" placeholder="最小" class="range-input" />
                  <text class="range-sep">~</text>
                  <input v-model.number="filterKpCountMax" type="number" placeholder="最大" class="range-input" />
                </view>
              </view>
              <view class="filter-item">
                <text class="filter-label">做题人数</text>
                <view class="range-inputs">
                  <input v-model.number="filterAttemptMin" type="number" placeholder="最小" class="range-input" />
                  <text class="range-sep">~</text>
                  <input v-model.number="filterAttemptMax" type="number" placeholder="最大" class="range-input" />
                </view>
              </view>
              <view class="filter-item">
                <text class="filter-label">错误率</text>
                <view class="range-inputs">
                  <input v-model.number="filterErrorMin" type="number" placeholder="最小%" class="range-input" />
                  <text class="range-sep">~</text>
                  <input v-model.number="filterErrorMax" type="number" placeholder="最大%" class="range-input" />
                </view>
              </view>
              <view class="filter-item">
                <text class="filter-label">题号搜索</text>
                <input v-model="searchQuery" placeholder="输入题号关键词" class="search-input" />
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
              <button v-if="selectedIds.length > 0" class="create-task-btn" @click="goToStep3">
                下一步：编排序号并创建任务 ({{ selectedIds.length }}题)
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
              <text class="col col-diff">难度</text>
              <text class="col col-kp">知识点</text>
              <text class="col col-attempts">做题数</text>
              <text class="col col-errors">错误数</text>
              <text class="col col-error-rate">错误率</text>
              <text class="col col-actions">操作</text>
            </view>
            <scroll-view scroll-y class="table-body">
              <view v-for="(q, idx) in paginatedQuestions" :key="q.id"
                    :class="['table-row', { 'row-selected': selectedIds.includes(q.id) }]">
                <view class="col col-check" @click.stop="toggleSelect(q.id)">
                  <text>{{ selectedIds.includes(q.id) ? '☑' : '☐' }}</text>
                </view>
                <text class="col col-no">{{ (currentPage - 1) * pageSize + idx + 1 }}</text>
                <text class="col col-stem" @click.stop="showQuestionDetail(q)">{{ q.stem_preview || '(无预览)' }}</text>
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
                  <text v-if="!selectedIds.includes(q.id)" class="action-link action-add" @click.stop="addToSelected(q)">加入</text>
                  <text v-else class="action-link action-added" @click.stop="removeFromSelected(q.id)">✓ 已加入</text>
                </view>
              </view>
            </scroll-view>
            <!-- 分页 -->
            <view class="pagination">
              <text class="page-info">第 {{ currentPage }}/{{ totalPages }} 页，共 {{ filteredQuestions.length }} 题</text>
              <view class="page-controls">
                <button :disabled="currentPage <= 1" @click="currentPage--">‹ 上一页</button>
                <button :disabled="currentPage >= totalPages" @click="currentPage++">下一页 ›</button>
                <view class="page-size-selector">
                  <text>每页</text>
                  <picker :range="[10, 20, 50]" @change="pageSize = [10, 20, 50][$event.detail.value]; currentPage = 1">
                    <view class="page-size-value">{{ pageSize }}条</view>
                  </picker>
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- Step 3: 编排题目序号 + 配置关卡 -->
      <view v-if="step === 3" class="step3-container">
        <!-- 题目编排区 -->
        <view class="step3-section">
          <view class="section-header">
            <text class="section-title">题目编排 ({{ orderedQuestions.length }}题)</text>
            <text class="section-hint">拖拽调整顺序，点击序号可编辑</text>
          </view>
          <scroll-view scroll-y class="ordered-question-list">
            <view v-for="(q, idx) in orderedQuestions" :key="q.id" class="ordered-item">
              <view class="drag-handle">⠿</view>
              <input v-model="q.sort_no" type="number" class="sort-input" placeholder="序号" />
              <text class="ordered-stem">{{ (q.stem_preview || '').substring(0, 50) }}{{ (q.stem_preview || '').length > 50 ? '...' : '' }}</text>
              <text class="ordered-diff">{{ '★'.repeat(getDifficultyInt(q)) }}</text>
              <text class="ordered-remove" @click="removeFromOrdered(q.id)">✕</text>
            </view>
          </scroll-view>
        </view>

        <!-- 关卡配置区 -->
        <view class="step3-section">
          <view class="section-header">
            <text class="section-title">配置关卡</text>
            <text class="section-hint">为每个关卡分配不同的题目，难度递进</text>
          </view>
          <scroll-view scroll-y class="level-list">
            <view v-for="(level, i) in levels" :key="i" class="level-config">
              <view class="level-header">
                <text class="level-title">第 {{ i + 1 }} 关</text>
                <text class="remove-btn" @click="removeLevel(i)">删除</text>
              </view>
              <input v-model="level.name" placeholder="关卡名称" />
              <view class="level-options">
                <picker :range="levelTypes" @change="level.type = levelTypes[$event.detail.value]">
                  <view class="picker-display">类型: {{ level.type || 'practice' }}</view>
                </picker>
                <picker :range="modePolicies" @change="level.mode = modePolicies[$event.detail.value]">
                  <view class="picker-display">模式: {{ level.mode || 'block_a' }}</view>
                </picker>
              </view>
              <!-- 题目分配区 -->
              <view class="level-questions">
                <view class="level-q-header">
                  <text class="level-q-title">题目 ({{ level.questionIds?.length || 0 }}道)</text>
                  <text class="level-q-assign-btn" @click="openQuestionAssign(i)">分配题目</text>
                </view>
                <view v-if="level.questionIds && level.questionIds.length > 0" class="level-q-list">
                  <view v-for="qid in level.questionIds" :key="qid" class="level-q-item">
                    <text class="level-q-no">#{{ getQuestionSortNo(qid) }}</text>
                    <text class="level-q-stem">{{ getQuestionPreview(qid) }}</text>
                    <text class="level-q-remove" @click="removeQuestionFromLevel(qid, i)">✕</text>
                  </view>
                </view>
                <view v-else class="level-q-empty">
                  <text>点击"分配题目"为该关卡选择题目</text>
                </view>
              </view>
            </view>
          </scroll-view>
          <button @click="addLevel" class="add-level-btn">+ 添加关卡</button>
        </view>

        <view class="nav-btns">
          <button class="back-btn" @click="prevStep">上一步：选择题目</button>
          <button class="next-btn" @click="nextStep">下一步：预览发布</button>
        </view>
      </view>

      <!-- 题目分配弹窗 -->
      <view v-if="showQuestionAssign" class="assign-modal" @click="closeQuestionAssign">
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
          <text class="preview-name">{{ form.mission_name || '未命名任务' }}</text>
          <view class="preview-row"><text class="preview-label">题目数量</text><text class="preview-value">{{ orderedQuestions.length }} 道</text></view>
          <view class="preview-row"><text class="preview-label">关卡数量</text><text class="preview-value">{{ levels.length }} 个</text></view>
          <view class="preview-row"><text class="preview-label">截止时间</text><text class="preview-value">{{ form.end_at || '未设置' }}</text></view>
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
          <button class="publish-btn" @click="publish">发布任务</button>
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
            <text class="date-picker-label">截止日期</text>
            <text class="date-picker-value">{{ tempDate }}</text>
          </view>
        </picker>
      </view>
    </view>

    <!-- 开始日期选择弹窗 -->
    <view v-if="showStartDatePicker" class="date-modal" @click="showStartDatePicker = false">
      <view class="date-panel" @click.stop>
        <view class="date-panel-header">
          <text class="date-close-btn" @click="showStartDatePicker = false">取消</text>
          <text class="date-confirm-btn" @click="confirmStartDate">确定</text>
        </view>
        <picker mode="date" :value="tempStartDate" @change="onStartDateChange">
          <view class="date-picker-input">
            <text class="date-picker-label">开始日期</text>
            <text class="date-picker-value">{{ tempStartDate }}</text>
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
            {{ selectedIds.includes(currentQuestion?.id) ? '✓ 已在列表中' : '加入列表' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { missionApi } from '@/api/index.ts'
import { questionApi } from '@/api/questions.ts'
import { knowledgeApi } from '@/api/knowledge.ts'
import { classApi } from '@/api/institutions.ts'
import { useUserStore } from '@/store/index.ts'
import TeacherSidebar from '@/components/TeacherSidebar.vue'

const userStore = useUserStore()

const step = ref(1)

const form = ref({ mission_name: '', goal_text: '', start_at: '', end_at: '', class_id: null as number | null })
const levels = ref([{ name: '基础练习', type: 'practice', mode: 'block_a', questionIds: [] as number[] }])
const searchQuery = ref('')
const showDatePicker = ref(false)
const tempDate = ref('')
const showStartDatePicker = ref(false)
const tempStartDate = ref('')

// 班级选择
const classList = ref<any[]>([])
const showClassDropdown = ref(false)
const selectedClassName = ref('')

// === Step 2: 知识树 ===
const treeData = ref<any[]>([])
const treeLoading = ref(false)

// === Step 2: 筛选条件 ===
const showKpDropdown = ref(false)
const showStageDropdown = ref(false)
const kpSearchText = ref('')
const filterKpIds = ref<number[]>([])
const filterDifficulty = ref<number[]>([])
const selectedStages = ref<string[]>([])
const filterKpCountMin = ref<number | null>(null)
const filterKpCountMax = ref<number | null>(null)
const filterAttemptMin = ref<number | null>(null)
const filterAttemptMax = ref<number | null>(null)
const filterErrorMin = ref<number | null>(null)
const filterErrorMax = ref<number | null>(null)

// === Step 2: 题目列表 ===
const allQuestions = ref<any[]>([])
const filteredQuestions = ref<any[]>([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(10)

// === Step 2: 已选列表 ===
const selectedIds = ref<number[]>([])
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

// 已选题目的详细信息
const selectedQuestions = computed(() => {
  return allQuestions.value.filter(q => selectedIds.value.includes(q.id))
})

// Step 3: 已选题目（带序号）
const orderedQuestions = computed(() => {
  return selectedQuestions.value.map((q, idx) => ({
    ...q,
    sort_no: q.sort_no || (idx + 1),
  }))
})

// 全选状态
const isAllSelected = computed(() => {
  return paginatedQuestions.value.length > 0 && paginatedQuestions.value.every(q => selectedIds.value.includes(q.id))
})

// 分页
const totalPages = computed(() => Math.max(1, Math.ceil(filteredQuestions.value.length / pageSize.value)))
const paginatedQuestions = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredQuestions.value.slice(start, start + pageSize.value)
})

// 已选题目统计
const avgDifficulty = computed(() => {
  if (selectedQuestions.value.length === 0) return '-'
  const sum = selectedQuestions.value.reduce((acc, q) => acc + (q.difficulty || 1), 0)
  return (sum / selectedQuestions.value.length).toFixed(1)
})

const uniqueKpCount = computed(() => {
  const ids = new Set<number>()
  for (const q of selectedQuestions.value) {
    // Try different field names the backend might use
    const kpIds = q.knowledge_point_ids || q.knowledge_ids || []
    if (Array.isArray(kpIds)) {
      for (const id of kpIds) ids.add(id)
    }
    // Also try knowledge_points as array of objects
    if (q.knowledge_points && Array.isArray(q.knowledge_points)) {
      for (const kp of q.knowledge_points) {
        if (kp.id) ids.add(kp.id)
      }
    }
  }
  return ids.size
})

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
    form.value.start_at = `${tempStartDate.value}T00:00`
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
    form.value.end_at = `${tempDate.value}T23:59`
  }
  showDatePicker.value = false
}

// Step 导航
function nextStep() {
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
    const subject = userStore.userInfo?.subject || ''
    const stages = userStore.userInfo?.stages
    const stageList = Array.isArray(stages) && stages.length > 0 ? stages.join(',') : ''
    const res: any = await knowledgeApi.getTree({ subject, stages: stageList })
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

// 题目加载
async function loadQuestions() {
  loading.value = true
  try {
    const res = await questionApi.list({ page: 1, page_size: 200 })
    allQuestions.value = res.data?.items || []
    applyFilters()
  } catch (e) {
    console.error('加载题目失败:', e)
  } finally {
    loading.value = false
  }
}

// 筛选应用
function applyFilters() {
  let list = [...allQuestions.value]

  // 知识点筛选 (or关系：题目包含任一选中的知识点即可)
  if (filterKpIds.value.length > 0) {
    list = list.filter(q => {
      let qKpIds: number[] = []

      // 从 ai_knowledge_enrichment JSON 中提取知识点ID
      if (q.ai_knowledge_enrichment) {
        try {
          const enriched = typeof q.ai_knowledge_enrichment === 'string'
            ? JSON.parse(q.ai_knowledge_enrichment)
            : q.ai_knowledge_enrichment
          if (Array.isArray(enriched)) {
            qKpIds = enriched.map((kp: any) => kp.id).filter(Boolean)
          } else if (enriched.knowledge_points && Array.isArray(enriched.knowledge_points)) {
            qKpIds = enriched.knowledge_points.map((kp: any) => kp.id).filter(Boolean)
          }
        } catch {}
      }

      // 从 knowledge_points JSON 中提取
      if (qKpIds.length === 0 && q.knowledge_points) {
        try {
          const kps = typeof q.knowledge_points === 'string'
            ? JSON.parse(q.knowledge_points)
            : q.knowledge_points
          if (Array.isArray(kps)) {
            qKpIds = kps.map((kp: any) => kp.id).filter(Boolean)
          }
        } catch {}
      }

      // 从 knowledge_point_ids / knowledge_ids 中提取（兼容旧字段）
      if (qKpIds.length === 0) {
        if (q.knowledge_point_ids && Array.isArray(q.knowledge_point_ids)) {
          qKpIds = q.knowledge_point_ids
        } else if (q.knowledge_ids && Array.isArray(q.knowledge_ids)) {
          qKpIds = q.knowledge_ids
        }
      }

      return filterKpIds.value.some(id => qKpIds.includes(id))
    })
  }

  // 难度筛选：difficulty 是 Decimal（如 1.00, 3.00），需要转成整数比较
  if (filterDifficulty.value.length > 0) {
    list = list.filter(q => {
      const diff = q.difficulty != null ? Math.round(Number(q.difficulty)) : 0
      return filterDifficulty.value.includes(diff)
    })
  }

  // 年级学期筛选
  if (selectedStages.value.length > 0) {
    list = list.filter(q => {
      const qStage = q.stage || q.subject || ''
      return selectedStages.value.some(s => qStage.includes(s))
    })
  }

  // 知识点数筛选
  if (filterKpCountMin.value != null) list = list.filter(q => (q.knowledge_points_count || 0) >= filterKpCountMin.value!)
  if (filterKpCountMax.value != null) list = list.filter(q => (q.knowledge_points_count || 0) <= filterKpCountMax.value!)

  // 做题人数筛选
  if (filterAttemptMin.value != null) list = list.filter(q => (q.attempt_count || 0) >= filterAttemptMin.value!)
  if (filterAttemptMax.value != null) list = list.filter(q => (q.attempt_count || 0) <= filterAttemptMax.value!)

  // 错误率筛选
  list = list.filter(q => {
    const rate = q.attempt_count > 0 ? (q.wrong_count || 0) / q.attempt_count * 100 : -1
    if (filterErrorMin.value != null && rate < filterErrorMin.value!) return false
    if (filterErrorMax.value != null && rate > filterErrorMax.value!) return false
    return true
  })

  // 题号搜索
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(item => {
      const no = item.question_no || item.system_id || ''
      return no.toLowerCase().includes(q)
    })
  }

  filteredQuestions.value = list
  currentPage.value = 1
}

function resetFilters() {
  filterKpIds.value = []
  filterDifficulty.value = []
  selectedStages.value = []
  filterKpCountMin.value = null
  filterKpCountMax.value = null
  filterAttemptMin.value = null
  filterAttemptMax.value = null
  filterErrorMin.value = null
  filterErrorMax.value = null
  searchQuery.value = ''
  applyFilters()
}

// 知识点选择
function onKpInputBlur() {
  // 延迟关闭，让点击选项的事件先触发
  setTimeout(() => { showKpDropdown.value = false }, 200)
}

function toggleFilterKp(kp: any) {
  const idx = filterKpIds.value.indexOf(kp.id)
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
function toggleSelect(id: number) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}

function addToSelected(q: any) {
  if (!selectedIds.value.includes(q.id)) selectedIds.value.push(q.id)
}

function removeFromSelected(id: number) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
}

function removeFromOrdered(id: number) {
  removeFromSelected(id)
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    // 取消当前页全选
    for (const q of paginatedQuestions.value) {
      const idx = selectedIds.value.indexOf(q.id)
      if (idx >= 0) selectedIds.value.splice(idx, 1)
    }
  } else {
    // 当前页全选
    for (const q of paginatedQuestions.value) {
      if (!selectedIds.value.includes(q.id)) selectedIds.value.push(q.id)
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

// 题目详情
function showQuestionDetail(q: any) {
  currentQuestion.value = q
  showDetailModal.value = true
}

const levelTypes = ['practice', 'review', 'retry', 'variant', 'check']
const modePolicies = ['block_a', 'allow_a', 'require_guidance', 'free_practice']

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

function isQuestionAssignedForLevel(qid: number): boolean {
  const level = levels.value[currentAssignLevel.value]
  return level?.questionIds?.includes(qid) || false
}

function toggleQuestionForLevel(qid: number) {
  const level = levels.value[currentAssignLevel.value]
  if (!level) return
  if (!level.questionIds) level.questionIds = []
  const idx = level.questionIds.indexOf(qid)
  if (idx >= 0) level.questionIds.splice(idx, 1)
  else level.questionIds.push(qid)
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

function removeQuestionFromLevel(qid: number, levelIndex: number) {
  const level = levels.value[levelIndex]
  if (!level) return
  const idx = level.questionIds?.indexOf(qid)
  if (idx !== undefined && idx >= 0) level.questionIds.splice(idx, 1)
}

function getQuestionSortNo(qid: number): number {
  const q = orderedQuestions.value.find(q => q.id === qid)
  return q?.sort_no || 0
}

function getQuestionPreview(qid: number): string {
  const q = orderedQuestions.value.find(q => q.id === qid)
  const preview = q?.stem_preview || ''
  return preview.length > 40 ? preview.substring(0, 40) + '...' : preview
}

async function publish() {
  // 校验任务名称
  if (!form.value.mission_name.trim()) {
    uni.showToast({ title: '请填写任务名称', icon: 'none' })
    step.value = 1
    return
  }

  // 校验班级
  if (!form.value.class_id) {
    uni.showToast({ title: '请选择班级', icon: 'none' })
    step.value = 1
    return
  }

  // 校验截止时间
  if (!form.value.end_at) {
    uni.showToast({ title: '请选择截止时间', icon: 'none' })
    step.value = 1
    return
  }

  // 校验题目数量
  if (selectedIds.value.length === 0) {
    uni.showToast({ title: '请先选择至少一道题目', icon: 'none' })
    step.value = 2
    return
  }

  // 校验每个关卡都有题目
  for (let i = 0; i < levels.value.length; i++) {
    const level = levels.value[i]
    if (!level.questionIds || level.questionIds.length === 0) {
      uni.showToast({ title: `请为"${level.name || `第${i+1}关`}"分配至少一道题目`, icon: 'none' })
      step.value = 3
      return
    }
  }

  try {
    uni.showLoading({ title: '发布中...' })

    // 1. 创建任务
    const res = await missionApi.create({
      mission_name: form.value.mission_name,
      goal_text: form.value.goal_text,
      start_at: form.value.start_at,
      end_at: form.value.end_at,
      class_id: form.value.class_id,
    })
    const missionId = res.data?.id
    if (!missionId) {
      uni.hideLoading()
      uni.showToast({ title: '任务创建失败', icon: 'none' })
      return
    }

    // 2. 批量创建关卡和题目（一次请求完成）
    await missionApi.addLevelsBatch(missionId, {
      levels: levels.value.map((level, i) => ({
        name: level.name || `第${i + 1}关`,
        type: level.type,
        mode: level.mode,
        questionIds: level.questionIds || [],
      })),
    })

    // 3. 发布
    await missionApi.publish(missionId)

    uni.hideLoading()
    uni.showToast({ title: '发布成功', icon: 'success' })
    setTimeout(() => uni.navigateTo({ url: '/pages/teacher/workbench' }), 1500)
  } catch (e: any) {
    uni.hideLoading()
    console.error('发布任务失败:', e)
    const msg = e?.data?.message || e?.message || '发布失败，请重试'
    uni.showToast({ title: msg, icon: 'none' })
  }
}

onMounted(async () => {
  await loadClasses()
  await loadKnowledgeTree()
  await loadQuestions()
})

// 加载班级列表
async function loadClasses() {
  try {
    const res = await classApi.simpleList()
    classList.value = res.data || []
  } catch (e) {
    console.error('加载班级列表失败:', e)
  }
}

function selectClass(cls: any) {
  form.value.class_id = cls.id
  selectedClassName.value = cls.class_name
  showClassDropdown.value = false
}
</script>

<style scoped>
.create-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 240px;
  flex: 1;
  padding: 30rpx 40rpx;
}
.form-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
  margin-bottom: 30rpx;
}
.form-item {
  margin-bottom: 24rpx;
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
  position: absolute;
  top: 100%;
  left: 0; right: 0;
  margin-top: 4rpx;
  background: #fff;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.1);
  z-index: 100;
  max-height: 400rpx;
  overflow-y: auto;
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
  min-height: 70vh;
}

/* 知识树 */
.knowledge-tree {
  width: 240px;
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
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.05);
  min-height: 75vh;
}

/* 筛选区 */
.filter-section {
  background: #f8f9fa;
  border-radius: 8rpx;
  padding: 16rpx;
  margin-bottom: 16rpx;
}
.filter-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 12rpx;
  align-items: flex-end;
  flex-wrap: wrap;
}
.filter-row:last-child { margin-bottom: 0; }
.filter-item {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  position: relative;
}
.filter-kp-item {
  position: relative;
}
.filter-stage-item {
  position: relative;
}
.filter-label {
  font-size: 22rpx;
  color: #666;
}
.kp-input-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.kp-search-input {
  width: 200rpx;
  height: 56rpx;
  padding: 6rpx 12rpx;
  border: 1rpx solid #ddd;
  border-radius: 4rpx;
  font-size: 22rpx;
  background: #fff;
  min-height: auto;
  line-height: normal;
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
  min-width: 200rpx;
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
  width: 240rpx;
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
  height: 56rpx;
  padding: 6rpx 8rpx;
  border: 1rpx solid #ddd;
  border-radius: 4rpx;
  font-size: 22rpx;
  text-align: center;
  background: #fff;
  min-height: auto;
  line-height: normal;
}
.range-sep { color: #999; font-size: 22rpx; }
.search-input {
  width: 160rpx;
  height: 56rpx;
  padding: 6rpx 12rpx;
  border: 1rpx solid #ddd;
  border-radius: 4rpx;
  font-size: 22rpx;
  background: #fff;
  min-height: auto;
  line-height: normal;
}

/* 筛选按钮 */
.filter-actions {
  display: flex;
  gap: 8rpx;
  align-items: center;
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
.question-table { flex: 1; display: flex; flex-direction: column; }
.table-header {
  display: flex;
  align-items: center;
  padding: 12rpx 8rpx;
  background: #f5f7fa;
  border-radius: 6rpx;
  font-size: 22rpx;
  font-weight: bold;
  color: #666;
}
.table-body {
  flex: 1;
}
.table-row {
  display: flex;
  align-items: center;
  padding: 12rpx 8rpx;
  border-bottom: 1rpx solid #f0f0f0;
  font-size: 22rpx;
}
.table-row:hover { background: #f9f9f9; }
.table-row.row-selected { background: #e8f5e9; }
.col { padding: 0 6rpx; }
.col-check { width: 40rpx; text-align: center; cursor: pointer; font-size: 24rpx; }
.col-no { width: 40rpx; text-align: center; color: #999; font-size: 22rpx; }
.col-stem { flex: 2; color: #333; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-stem:hover { color: #409eff; }
.col-diff { width: 90rpx; text-align: center; }
.diff-1 { color: #4caf50; }
.diff-2 { color: #8bc34a; }
.diff-3 { color: #ff9800; }
.diff-4 { color: #f44336; }
.diff-5 { color: #9c27b0; }
.diff-score { font-size: 18rpx; color: #999; margin-left: 4rpx; }
.col-kp { width: 50rpx; text-align: center; color: #666; font-size: 22rpx; }
.col-attempts { width: 60rpx; text-align: center; color: #666; font-size: 22rpx; }
.col-errors { width: 60rpx; text-align: center; color: #666; font-size: 22rpx; }
.col-error-rate { width: 70rpx; text-align: center; font-weight: bold; font-size: 22rpx; }
.error-rate-high { color: #f44336; }
.error-rate-mid { color: #ff9800; }
.error-rate-low { color: #4caf50; }
.col-actions { width: 110rpx; display: flex; gap: 6rpx; justify-content: center; }
.action-link { color: #409eff; cursor: pointer; font-size: 22rpx; padding: 4rpx 6rpx; border-radius: 4rpx; }
.action-link:hover { background: #ecf5ff; }
.action-add { color: #4caf50; }
.action-added { color: #999; cursor: default; }

/* 分页 */
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 0;
  margin-top: 8rpx;
  border-top: 1rpx solid #eee;
}
.page-info { font-size: 22rpx; color: #666; }
.page-controls { display: flex; gap: 8rpx; align-items: center; }
.page-controls button {
  padding: 8rpx 16rpx;
  font-size: 22rpx;
  background: #fff;
  border: 1rpx solid #ddd;
  border-radius: 4rpx;
  height: auto;
  line-height: normal;
}
.page-controls button:disabled { opacity: 0.5; }
.page-size-selector {
  display: flex;
  align-items: center;
  gap: 6rpx;
  font-size: 22rpx;
  color: #666;
}
.page-size-value {
  padding: 4rpx 12rpx;
  background: #f5f5f5;
  border-radius: 4rpx;
  font-size: 22rpx;
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
.picker-display { flex: 1; padding: 12rpx; background: #f8f8f8; border-radius: 4rpx; font-size: 24rpx; color: #666; }

/* 关卡题目分配区 */
.level-questions { margin-top: 16rpx; padding-top: 12rpx; border-top: 1rpx solid #eee; }
.level-q-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8rpx; }
.level-q-title { font-size: 22rpx; color: #666; }
.level-q-assign-btn { font-size: 22rpx; color: #409eff; cursor: pointer; }
.level-q-list { max-height: 200rpx; overflow-y: auto; }
.level-q-item { display: flex; align-items: center; padding: 6rpx 4rpx; gap: 8rpx; font-size: 20rpx; }
.level-q-no { color: #409eff; width: 32rpx; flex-shrink: 0; }
.level-q-stem { flex: 1; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.level-q-diff { color: #ff9800; width: 48rpx; text-align: center; flex-shrink: 0; }
.level-q-remove { color: #f44336; cursor: pointer; font-size: 20rpx; flex-shrink: 0; padding: 4rpx; }
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
}
.assign-header { display: flex; justify-content: space-between; align-items: center; padding: 24rpx; border-bottom: 1rpx solid #eee; }
.assign-title { font-size: 26rpx; font-weight: bold; color: #333; }
.assign-close { font-size: 32rpx; color: #999; cursor: pointer; }
.assign-actions { display: flex; gap: 24rpx; padding: 12rpx 24rpx; background: #f8f8f8; }
.assign-select-all { font-size: 22rpx; color: #409eff; cursor: pointer; }
.assign-clear { font-size: 22rpx; color: #f44336; cursor: pointer; }
.assign-list { flex: 1; max-height: 50vh; padding: 0 24rpx; }
.assign-item {
  display: flex; align-items: center; padding: 12rpx 0; border-bottom: 1rpx solid #f0f0f0;
  gap: 12rpx; cursor: pointer; font-size: 22rpx;
}
.assign-item.assigned { background: #e8f5e9; padding: 12rpx 8rpx; border-radius: 4rpx; }
.assign-check { font-size: 24rpx; width: 28rpx; flex-shrink: 0; }
.assign-no { color: #409eff; width: 36rpx; flex-shrink: 0; }
.assign-stem { flex: 1; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.assign-diff { color: #ff9800; width: 48rpx; text-align: center; flex-shrink: 0; }
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
