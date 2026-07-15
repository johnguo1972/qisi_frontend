# Task 5: 前端 API 封装 + TeacherSidebar 修改 -- 报告

## 状态: DONE

## 验证结果

### 1. `uniapp/src/api/courses.ts` -- 已存在
- `courseApi`: list, create, detail, update, remove
- `materialApi`: list, upload (FormData + fetch), download (URL返回), preview, remove
- `treeApi`: list, create, update, remove, move
- `courseQuestionApi`: list, import, batchDelete, batchMove
- `variantApi`: generate, batchGenerate, getStatus, confirm, reject

### 2. `uniapp/src/components/TeacherSidebar.vue` -- 已完成
- 第32-35行: "课程列表"菜单项 (在"班级管理"之前)
- 第76行: `goCourseList()` 函数

### 3. `uniapp/src/pages.json` -- 已完成
- 第26行: `pages/teacher/course-list` -- "课程列表"
- 第27行: `pages/teacher/course-materials` -- "课程资料"
- 第28行: `pages/teacher/course-practice` -- "课程练习"

## 结论

所有3个文件均已包含任务简报要求的正确内容。`git status`确认无待提交变更，无需新commit。
