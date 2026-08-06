# UUID 主键类型混用排查与修复方案

日期：2026-08-05  
范围：`D:\yangtze\project\2026\qisi\qisi_frontend`

## 实施结果（2026-08-05）

本方案已实施。后端 UUID 校验、任务/班级/课程/题目相关序列化器、学生班级筛选、照片题知识点筛选和核心前端 API 类型契约均已更新。实现不改变接口路径、字段名称、外键关系、权限判断或业务状态流转。

验证结果：

- `python manage.py check`：通过；
- `python manage.py makemigrations --check --dry-run`：通过；
- `npm run build:h5`：通过；
- `python manage.py test apps.institutions apps.missions`：22 项通过；
- `python manage.py test apps.courses`：37 项通过；
- UUID 序列化校验：班级、课程、任务、关卡、题目、AI 状态字段均可正确读写 UUID。

注：`npx tsc --noEmit` 仍有 3 项既有问题（条件编译产生的 `UPLOAD_BASE`/`BASE_URL` 重复声明，以及既有上传参数联合类型问题），与本次 UUID 修改无关；H5 构建不受影响。

## 1. 背景与目标

系统的班级、机构、课程、任务、关卡、题目、用户、知识点、标签等核心实体已使用 UUID 作为主键。部分后端序列化器、接口实现和前端 TypeScript 声明仍按整数 ID 处理，可能造成：

- 请求校验返回 400，例如 `class_id` 被要求填写合法整数；
- 接口内部执行 `int(uuid)` 后产生 500；
- 返回数据序列化失败；
- 前端类型提示错误，后续维护时容易重新引入同类问题；
- 按班级、知识点、题目等条件筛选时失效或被静默忽略。

本方案目标是统一 UUID 类型契约，同时保持现有业务含义、接口路径、数据结构和权限流程不变。

## 2. 已完成修复

### 2.1 创建任务接口的班级 UUID 校验

问题：`POST /api/v1/missions/` 的 `class_id` 被 `IntegerField` 校验，传入班级 UUID 时返回 400。

已调整的文件：

- `apps/missions/serializers.py`
- `uniapp/src/api/missions.ts`

已完成内容：

- `CreateMissionSerializer.class_id` 改为 UUID 校验；
- `CreateMissionSerializer.course_id` 改为 UUID 校验；
- 任务详情中的 `class_obj` 改为 UUID 输出；
- 创建关卡题目关联所用 `level_id`、`question_ids` 改为 UUID 校验；
- 使用实际班级 ID `019fcf88-937c-7ad0-9692-abb985480140` 对任务创建序列化器进行验证，校验通过，类型为 `UUID`。

业务影响：无。任务仍然通过同一 `class_obj` 外键关联班级，课程、目标学生、任务创建人及默认状态逻辑均不变。

## 3. 待修复问题清单

### 3.1 学生提交入班申请

涉及文件：

- `apps/institutions/serializers.py`
- `uniapp/src/api/institutions.ts`

现状：`CreateJoinRequestSerializer.class_id` 是 `IntegerField`，而 `institutions.Class.id` 为 UUID。

风险：学生从班级列表提交加入申请时，会收到与创建任务相同的 400 整数校验错误。

建议优化：

1. 将 `class_id` 改为 `serializers.UUIDField()`；
2. 将前端 `studentClassApi.submitJoinRequest` 的 `class_id` 改为 `string`（或统一 UUID 类型）；
3. 保留原有的班级存在性、重复申请、已加入班级校验逻辑。

验证：使用有效 UUID 班级 ID 调用 `/api/v1/classes/join-request`，应返回创建成功或现有业务校验结果，不应出现“请填写合法的整数值”。

### 3.2 学生首页按班级筛选任务

涉及文件：

- `apps/study/student_views.py`
- `uniapp/src/api/student.ts`

现状：学生首页接口对查询参数执行 `int(class_id)`。

风险：学生选择 UUID 班级进行任务筛选时会触发 `ValueError`，存在 500 风险。

建议优化：

1. 删除 `int(class_id)` 和大于零判断；
2. 仅在 `class_id` 非空时直接传入 ORM 的 `mission__class_obj_id=class_id` 过滤；
3. 如需格式校验，使用 UUID 解析并对非法 UUID 返回 400；
4. 前端 `studentApi.home` 的 `class_id` 改为 `string`。

验证：学生分别使用“全部班级”和一个有效 UUID 班级访问首页；前者返回全部可见任务，后者只返回该班级任务，均不出现 500。

### 3.3 任务详情中的创建教师 ID

涉及文件：

- `apps/missions/serializers.py`
- `uniapp/src/api/missions.ts`

现状：`MissionDetailSerializer.creator_teacher` 使用 `IntegerField`，但 `UserAccount.id` 为 UUID。

风险：任务详情接口序列化创建教师 ID 时可能失败。

建议优化：

1. 改为 `serializers.UUIDField(source='creator_teacher_id.id', read_only=True)`；
2. 前端 `Mission.creator_teacher_id` 改为 UUID 字符串类型；
3. 不更改教师名称、任务归属和权限校验。

验证：创建一条带教师的任务后访问 `/api/v1/missions/<mission_id>/`，确认 `creator_teacher` 返回 UUID 字符串且详情页可正常展示。

### 3.4 课程习题列表的题目和目录节点 ID

涉及文件：

- `apps/courses/serializers.py`
- `uniapp/src/api/courses.ts`
- `uniapp/src/pages/teacher/course-practice.vue`

现状：`CourseQuestionLinkSerializer.question_id` 和 `tree_node_id` 使用 `IntegerField`，但 `ExamQuestion.id`、`CourseTree.id` 均为 UUID。

风险：课程习题列表返回数据时可能发生序列化错误；前端再进行批量移动、删除或跳转时也容易产生错误类型约束。

建议优化：

1. 两个序列化字段改为 `UUIDField`；
2. 前端课程、习题、目录节点相关 ID 均使用 UUID 字符串；
3. 不改变课程习题关联表、目录归属、软删除和排序逻辑。

验证：创建课程目录并引入至少一题，调用课程习题列表、按目录筛选、批量移动、批量删除；各接口应正确返回 UUID，且原有业务结果保持一致。

### 3.5 课程习题触发 AI 处理

涉及文件：

- `apps/courses/views.py`
- `uniapp/src/api/courses.ts`
- 课程习题页面中调用 AI 的相关组件

现状：`question_ai_process` 对请求体内的 `question_id` 执行 `int(question_id)`。

风险：课程习题使用 UUID 时，点击 AI 处理会直接失败。

建议优化：

1. 移除 `int(question_id)`；
2. 直接使用 UUID 查询 `CourseQuestionLink`；
3. 对非法 UUID 返回明确的 400，而不是运行时异常；
4. 保留“题目必须属于当前课程”的权限与归属校验。

验证：在课程习题页选择一条 UUID 题目发起 AI 处理，确认能创建异步任务；使用不属于当前课程的题目时仍返回原有的“不属于课程”错误。

### 3.6 照片题目页面的知识点筛选

涉及文件：

- `apps/study/photo_views.py`

现状：照片题目列表仅将知识点 ID 当作整数处理。知识点当前为 UUID。

风险：以 UUID 知识点筛选时不会报错，但筛选条件会被忽略，导致用户看到错误的题目列表。

建议优化：

1. 继续保留 `-1` 代表“未分类”的特殊语义；
2. 对其他值按 UUID 查询知识点；
3. 使用 `knowledge_points` JSON 中的 ID 和模块名称兼容过滤；
4. 与题库管理页的人工知识点筛选保持同一规则。

验证：为照片题绑定一个 UUID 知识点后，使用该知识点筛选应只返回已关联题目；选择未分类时仍只返回空知识点题目。

### 3.7 预留 AI 状态序列化器

涉及文件：

- `apps/review/serializers.py`

现状：`AIStatusSerializer.question_id`、`AIProcessResultSerializer.question_id` 为 `IntegerField`。当前未发现实际接口调用这些序列化器。

风险：后续启用时会在 UUID 题目上产生返回序列化错误。

建议优化：两个字段统一改为 `UUIDField`。

验证：为对应序列化器增加最小单元测试，以 UUID 题目 ID 进行序列化和反序列化，均应通过。

### 3.8 前端 UUID 类型契约不统一

涉及文件（重点）：

- `uniapp/src/api/student.ts`
- `uniapp/src/api/institutions.ts`
- `uniapp/src/api/missions.ts`
- `uniapp/src/api/courses.ts`
- `uniapp/src/pages/student/**`
- `uniapp/src/pages/teacher/**`
- `uniapp/src/components/**`

现状：部分前端 API、组件 Props 和页面函数仍将任务、班级、课程、题目、关卡、错题本等 UUID 类型写为 `number`。

风险：TypeScript 无法发现 UUID 与整数混用；开发者可能在后续代码中加入 `Number()` 或 `parseInt()`，再次造成接口错误。

建议优化：

1. 在公共类型文件中定义 `type UUID = string`；
2. 为核心实体定义 `MissionId`、`ClassId`、`CourseId`、`QuestionId`、`LevelId` 等别名；
3. API 入参、返回值、页面路由参数和组件 Props 使用同一类型；
4. 纯显示场景允许 `string | number` 仅作为过渡兼容，写接口和查询时一律使用 UUID；
5. 不修改接口 URL 和字段名称，只收紧类型声明。

验证：运行前端类型检查和 H5 构建；以 UUID 路由参数打开班级、任务、题目、课程页面并执行主要操作。

## 4. 兼容性与业务逻辑保护原则

修复时必须遵守以下原则：

1. 不更改数据库中已有 UUID 主键，不重建或迁移业务数据；
2. 不更改 API 路径、请求字段名或响应业务字段；
3. 不改变班级成员关系、任务发布、题目关联、知识点筛选、标签筛选和权限判定；
4. 对原先使用字符串传 UUID 的前端调用保持兼容；
5. 对非法 ID 返回明确 400/404，不让 `int()` 转换产生 500；
6. 每项修复配套最小接口测试，覆盖有效 UUID、非法 UUID、无权限和不存在对象四类情况。

## 5. 建议实施顺序

1. 先修复班级加入申请、学生首页班级筛选、任务详情创建教师；
2. 再修复课程习题列表和课程 AI 处理；
3. 修复照片题知识点筛选与预留 AI 状态序列化器；
4. 最后统一前端 UUID 类型定义，并清理 `number` 类型声明；
5. 每完成一组接口执行回归验证，确认业务行为不变后再进行下一组。

## 6. 验证清单

完成代码修改后执行：

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
cd uniapp
npm run build:h5
```

并进行以下接口与页面回归：

- 创建任务：传 UUID 班级、空课程、指定目标学生；
- 查看任务详情、添加关卡、关联 UUID 题目；
- 学生按 UUID 班级筛选任务；
- 提交并审批入班申请；
- 课程习题的列表、目录筛选、导入、移动、删除及 AI 处理；
- 题库、我的精选、照片题目的知识点筛选；
- H5 页面中班级、任务、课程、题目相关路由跳转。

通过标准：所有有效 UUID 请求成功；非法 UUID 得到明确 400；不存在资源得到 404；无权限保持原有拒绝逻辑；不出现“请填写合法的整数值”、`ValueError` 或 UUID 序列化错误。
