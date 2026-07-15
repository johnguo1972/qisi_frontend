# 1. 暂存本地修改，拉取远程
git stash
git pull origin main

# 2. 恢复本地修改
git stash pop
# 此时会提示冲突，手动解决

# 3. 手动编辑 guidance.vue
#    保留本地版本（无需修改，本地版本就是正确的）

# 4. 手动编辑 student_views.py
#    - student_home(): 保留远程的 ClassStudent + 自动创建进度逻辑
#    - class_id 过滤: 用远程的 class_id != '0'（或统一用 int(class_id) > 0）
#    - student_level_detail(): 保留本地的增强字段（answer, analysis, solution, 图片id）
#    - export_pdf + _build_pdf: 保留本地的增强版
#    - 保留本地的 task_progress_stream + PROGRESS_KEY_PREFIX 导入

# 5. 标记冲突已解决，提交
git add .
git commit -m "merge: 合并远程代码，保留本地增强功能"
