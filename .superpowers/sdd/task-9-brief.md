# Task 9: 集成测试

## 测试清单

### 后端测试

1. **模型测试**（Task 1 已完成）
   - `python -m pytest apps/courses/tests/test_models.py -v`

2. **校验器测试**（Task 3 已完成）
   - `python -m pytest apps/courses/tests/test_validator.py -v`

3. **Django 检查**
   - `python manage.py check`

### 前端测试

4. **TypeScript 检查**
   - `cd uniapp && npx tsc --noEmit`

5. **H5 Build 测试**
   - `cd uniapp && npm run build:h5`

### 端到端手动测试清单

6. **课程列表功能**
   - 老师登录 → 左侧菜单显示"课程列表"
   - 点击"课程列表" → 显示卡片网格
   - 新建课程 → 卡片显示
   - 删除课程 → 确认弹窗 → 卡片消失

7. **课程资料功能**
   - 点击"课程资料" → 进入资料页
   - 上传 PDF/Word/图片 → 列表显示
   - 下载/预览/删除 → 功能正常

8. **课程练习功能**
   - 点击"课程练习" → 左侧空目录树
   - 右键新建根节点 → 子节点 → 多层嵌套
   - 从题库引入题目 → 习题列表显示
   - 新增习题（拍照/上传）→ 保存到指定节点
   - AI 处理单题 → 轮询结果
   - 生成变式题 → Celery 任务 → 结果入库（待确认）
   - 确认/驳回变式题
   - 批量操作：批量AI处理、批量生成变式题、批量移除

## 约束
- 仅修改 ./front 目录
- 所有测试通过才算完成
