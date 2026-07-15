# Task 8: 前端课程练习页（目录树 + 习题列表）

**位置**: `uniapp/src/` 前端代码

## 新建文件

### 1. `uniapp/src/components/DirTree.vue`

可编辑目录树组件：
- 多级展开/折叠（递归渲染 children）
- 选中高亮
- 右键菜单：新增下级节点、重命名、删除
- 根节点「+ 根节点」按钮
- props: nodes (嵌套结构), loading
- events: select, add-root, add-child, rename, delete-node

### 2. `uniapp/src/pages/teacher/course-practice.vue`

课程练习页面（三栏布局）：
- 左侧 (260px): DirTree 目录树
- 中间 (flex): 习题列表 + 批量操作栏
- 右侧弹窗: 新增习题面板（三个选项卡：拍照/上传、从课程资料选择、从题库引入）

习题列表功能：
- 多选框 + 全选
- 批量操作：移动节点、从课程移除
- 操作列：编辑、AI处理、生成变式题、移除
- 右上方按钮：新增习题、批量AI处理、批量生成变式题

## 依赖
- Task 5 的 `treeApi`, `courseQuestionApi`, `variantApi`
- Task 5 的 `questionApi`（复用 AI 处理和状态查询）
- `@/components/TeacherSidebar.vue`
- `@/components/DirTree.vue`

## 约束
- 仅修改 ./front 目录
- 习题列表样式参考 `uniapp/src/pages/teacher/bank.vue`
- AI 处理轮询参考 `uniapp/src/pages/teacher/bank.vue` 中的 aiPollTimers 模式
- 新增习题的拍照/上传跳转至现有 `/pages/teacher/new-question` 页面
