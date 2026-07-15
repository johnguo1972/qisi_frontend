# Task 6: 前端课程列表页 + 课程卡片组件

**位置**: `uniapp/src/` 前端代码

## 新建文件

### 1. `uniapp/src/components/CourseCard.vue`

课程卡片组件，props: course (id, name, description, subject, grade_level, material_count, question_count)
events: click, materials, practice, delete

- 封面渐变背景（按学科不同颜色）
- 显示：学科、年级、课程名称、简介、资料数、习题数
- 操作按钮：「课程资料」「课程练习」+ 删除图标

### 2. `uniapp/src/pages/teacher/course-list.vue`

课程列表页：
- 左侧 TeacherSidebar（activeItem="course-list"）
- 右侧卡片网格（每行 3 张）
- 右上角「+ 新建课程」按钮 → 弹窗填写名称/学科/年级/简介
- 删除确认弹窗

## 修改文件

### `uniapp/pages.json`
（已在 Task 5 中注册路由，此任务无需修改）

## 约束
- 仅修改 ./front 目录
- 复用 `@/components/TeacherSidebar.vue`
- 样式参考 `uniapp/src/pages/teacher/bank.vue` 的布局模式
