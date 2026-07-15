# Task 8 Report: 前端课程练习页（目录树 + 习题列表）

## Status: DONE

## Commits

| SHA | Subject |
|-----|---------|
| `c0270dc` | feat(front): Task 8 课程练习页 - 目录树组件与习题列表页 |

## Summary

创建了 3 个新文件（共 1630 行），实现了课程练习页的完整功能：

### 新建文件

1. **`uniapp/src/components/DirTree.vue`** (176 行)
   - 可编辑目录树容器组件
   - 根节点「+ 根节点」按钮
   - 右键上下文菜单（添加子节点、重命名、删除）
   - 通过 CustomEvent 与子组件通信

2. **`uniapp/src/components/TreeNodeItem.vue`** (163 行)
   - 递归渲染的树节点组件（自引用 `tree-node-item`）
   - 多级展开/折叠（`_expanded` 状态）
   - 选中高亮
   - 右键触发 context menu 事件
   - 内联 `+` 快速添加子节点按钮

3. **`uniapp/src/pages/teacher/course-practice.vue`** (1291 行)
   - 三栏布局：左侧 260px 目录树、中间弹性宽度习题列表、右侧滑入式新增面板
   - 习题列表：多选/全选、批量操作栏、操作列（编辑、AI处理、生成变式、移除）
   - AI 处理轮询（复用 bank.vue 的 `aiPollTimers` 模式）
   - 变式题生成轮询（`variantPollTimers`）
   - 新增习题面板（3 个选项卡）：
     - 拍照/上传 → 跳转现有 `new-question` 页面
     - 从课程资料选择 → 展示资料列表并引入
     - 从题库引入 → 搜索 + 多选引入
   - 节点 CRUD 对话框（添加、重命名）
   - 移动习题对话框（目标节点选择器）

### API 使用

- `treeApi` — list/create/update/remove 目录节点
- `courseQuestionApi` — list/import/batchDelete/batchMove 习题
- `variantApi` — generate/batchGenerate/getStatus 变式题
- `materialApi` — list 课程资料
- `questionApi` — list 题库（从题库引入选项卡）
- `aiProcessQuestion` / `getAiTaskStatus` — AI 处理及轮询

### 构建验证

- `npm run build:h5` — 编译通过（DONE Build complete）
- 修复了前置合并冲突（answer.vue 7处、guidance.vue 1处），与本次提交无关

## Concerns

1. **右键菜单在 H5 平台可用，在小程序/APP 平台需要长按替代** — `@contextmenu.prevent` 在 H5 有效，小程序可能需要 `@longpress` 事件。当前仅实现 H5 版本。
2. **TreeNodeItem 递归组件的 `name` 未显式声明** — 在 Vue 3 `<script setup>` 中通过文件名自动推断（`tree-node-item`），如果编译环境不支持可能需要添加 `defineOptions({ name: 'TreeNodeItem' })`。
3. **customEvent 通过 window 派发** — `tree-node-contextmenu` 事件通过 `window.dispatchEvent` 传递，DirTree 通过 `window.addEventListener` 接收。这是一种解耦方式，但如果页面有多个 DirTree 实例可能会互相干扰。当前场景下只有一个实例，无问题。
