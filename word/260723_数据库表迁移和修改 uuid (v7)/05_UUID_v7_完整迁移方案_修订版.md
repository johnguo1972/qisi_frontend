# UUID v7 完整迁移方案（修订版）

> **版本**：v2.0（修订版，修正旧方案 8 处致命错误）
> **日期**：2026-07-23
> **目标**：将全部业务表主键从 `int8 (BigAutoField)` 改为 `UUID v7`，改造后所有表与接口正常
> **执行顺序**：先本地演练 → 再部署服务器
> **前置文档**：本方案基于对项目 33 个模型、58 条外键、59 张表的实测调研，修正了 `02_UUID_v7_完整迁移方案.md` 的全部技术错误

---

## 一、执行摘要

### 核心结论（先看这 6 条）

1. **PostgreSQL 18.4 原生支持 `uuidv7()`**——可直接 `ALTER COLUMN ... TYPE uuid USING uuidv7()`，无需装扩展。
2. **`default_auto_field` 绝不能改成 UUIDField**——Django 源码强制校验必须是 `AutoField` 子类，改了会启动即崩。正确做法：**保持 `BigAutoField`，每个模型显式声明 `id = UUIDField(...)`**。
3. **Django 无法自动把 int 主键转成 UUID**——`bigint::uuid` 在 PostgreSQL 直接报 `cannot cast type bigint to uuid`，空表也失败。必须手写 `RunSQL`（用 `USING uuidv7()`）或数据迁移。
4. **库选 `uuid-utils>=0.11.0`**——RFC 9562 合规、Rust 实现、自带 `compat` 模块返回标准库 `uuid.UUID`（Django 必需）。旧方案的 `uuid7` 库不符合 RFC 且有争议，禁用。
5. **三类表要分别处理**：① Django 托管表（43 张，IDENTITY 自增）② 原始 SQL 表（14 张，`nextval` 序列，Django 管不到）③ 软引用字段（5 个 `question_id=IntegerField`，Django 迁移视野之外）。
6. **本地业务表全空、生产数据极少**（`user_account` 仅 1 条）→ 推荐走「重建表法」最简单可靠；同时提供「原地迁移法」应对数据量大的情况。

### 风险等级

| 风险 | 等级 | 应对 |
|------|------|------|
| `user_account` 被 16 张表引用，改主键牵连最广 | 🔴 高 | 必须最先迁移，迁移后全面验证登录相关接口 |
| 5 个软引用 `question_id` 易被遗漏 | 🔴 高 | 单独批次处理，专项验证 |
| 9 个模型未显式定义 id（仅改配置无效） | 🟡 中 | 逐个显式声明 `id = UUIDField(...)` |
| 3 处自引用外键（ExamQuestion、CourseTree）| 🟡 中 | 特殊迁移顺序，先置 NULL |
| 生产数据丢失 | 🟡 中 | 迁移前 `pg_dump` 全量备份 + 本地演练 |

---

## 二、现状盘点（实测数据）

### 2.1 技术栈

| 项 | 版本 |
|----|------|
| Django | 5.2.15 |
| Python | 3.13.9（用不了标准库 `uuid7`，需 3.14+；故必须装 `uuid-utils`）|
| PostgreSQL | **18.4**（原生支持 `uuidv7()`）|
| psycopg2 | 2.9.12 |
| `AUTH_USER_MODEL` | `accounts.UserAccount` |
| `DEFAULT_AUTO_FIELD` | `django.db.models.BigAutoField`（全局）|

### 2.2 模型与外键规模

| 指标 | 数值 |
|------|------|
| 含模型的 App | 9（accounts / knowledge / missions / institutions / papers / parser / study / wrongbook / courses）|
| 模型/业务表总数 | **33**（旧方案误报为 30）|
| 真实外键字段 | **53** |
| 数据库外键约束 | **58** 条 |
| **软引用字段**（`question_id=IntegerField`）| **5**（指向 `tiku_exam_question`，Django 管不到）|
| 自引用外键 | **3**（ExamQuestion×2、CourseTree×1）|
| M2M 中间表 | 0（多对多全用手动关联表）|
| `managed=False` 模型 | 0（knowledge_points 已在 0003 改为 True）|
| **未显式定义 id 的模型** | **9**（papers 4 个 + parser 5 个，依赖 default_auto_field）|

### 2.3 被引用最多的核心表（迁移影响面）

| 排名 | 表 | 被引用次数 | 含义 |
|------|-----|:---:|------|
| 1 | `user_account` | **16 张表 / 20 处** | 用户体系核心，必须最先迁 |
| 2 | `tiku_exam_question` | 4 表 + 2 自引用 + 5 软引用 | 题库核心 |
| 3 | `tiku_exam_paper` | 5 | 试卷核心 |
| 4 | `learning_mission` / `class` | 各 4 | |
| 5 | `course` / `mission_level` | 各 3 | |
| - | `knowledge_points` / `tiku_paper_code_counter` / `tiku_question_id_counter` | 0 | 叶子表，最简单 |

### 2.4 数据量（本地实测，生产以服务器为准）

- 本地 59 张表共 238 行，**全部集中在 Django 框架表**（`auth_permission` 152、`django_migrations` 48、`django_content_type` 38）。
- **56 张业务表本地全部为空**。
- 生产（服务器）：`user_account` 1 条，其余业务表数据量待确认（迁移前需 `SELECT COUNT(*)` 核查）。

> **结论**：本地演练零数据风险；生产即便有数据也是少量，主推「重建表法」。

### 2.5 三类自增机制

| 类型 | 机制 | 涉及表 | Django 能否管 |
|------|------|--------|:---:|
| A. Django 托管 | `IDENTITY BY DEFAULT` | 43 张业务表 | ✅ |
| B. 原始 SQL 表 | `nextval('xxx_id_seq')` | 14 张（alert_logs/problems/users/system_config 等）| ❌ 需纯 SQL |
| C. 软引用 | `IntegerField` 无约束 | 5 个 `question_id` 列 | ❌ 需专项处理 |

---

## 三、旧方案（02）的致命错误（逐条）

照搬旧方案会在第一步就崩。逐条修正如下：

| # | 旧方案做法 | 实际情况 | 修正 |
|---|-----------|---------|------|
| 1 | `default_auto_field = 'django.db.models.UUIDField'` | **启动即 ValueError**（`options.py` L278 校验必须是 AutoField 子类）| 保持 `BigAutoField`，模型显式声明 id |
| 2 | `pip install uuid7` | 该库**不符合 RFC 9562**，PEP 541 争议 | 改用 `uuid-utils>=0.11.0` |
| 3 | `default=uuid7.uuid7` | 来自不合规库，且返回类型非 stdlib | 改 `default=uuid_utils.compat.uuid7` |
| 4 | "Django 自动转 int→UUID / 自动更新外键 / 数据不丢失" | **全部错误**。PG 报 `cannot cast bigint to uuid`，空表也失败 | 手写 `RunSQL ... USING uuidv7()` 或数据迁移 |
| 5 | 期望 DB 列 `DEFAULT uuid_generate_v7()` | 该函数在 uuid-ossp 1.1 **不存在**；Django `default=` 也不写 DB DEFAULT | 用 PG18 原生 `uuidv7()` + `db_default` |
| 6 | "改父表主键后 Django 自动同步子表 FK 列类型" | 会生成但同样 cast 报错，全部失败 | 子表 FK 列也用 `RunSQL USING uuidv7()` |
| 7 | "9 apps 约 30 个模型" | 实际 33 个；漏列 parser 的 ExamPage/QuestionOption/QuestionImage 等 | 按本方案完整清单 |
| 8 | 未提 14 张原始 SQL 表 + 5 个软引用 | Django 完全管不到，遗漏则数据失联 | 本方案设独立批次处理 |

---

## 四、技术决策

### 4.1 库选型：`uuid-utils`

```bash
pip install "uuid-utils>=0.11.0"
```

- **理由**：RFC 9562 合规、Rust 实现（比标准库 uuid4 快 ~50×）、维护活跃（2025-05 仍有更新）、自带 `uuid_utils.compat` 返回标准库 `uuid.UUID`（Django `UUIDField` 必需）。
- **禁用** `uuid7`（不合规）、`uuid6`（纯 Python 较慢，备选）。
- **不能用**标准库 `uuid.uuid7()`（需 Python 3.14+，当前 3.13.9）。

`requirements.txt` 追加：
```
uuid-utils>=0.11.0
```

### 4.2 配置：`default_auto_field` 保持不变

```python
# config/settings.py —— 不改
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 各 apps.py —— 也不改
class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'  # 保持
```

> ⚠️ 永远不要把 `default_auto_field` 设为 `UUIDField`。

### 4.3 模型写法：显式声明 id

```python
# 每个模型（包括原本未显式定义 id 的 papers/parser 9 个）
import uuid_utils.compat as uuid_compat
from django.db import models

class UserAccount(AbstractBaseUser):
    id = models.UUIDField(
        primary_key=True,
        default=uuid_compat.uuid7,   # Python 端默认值
        editable=False,
    )
    # ...其余字段不动
```

**为什么不用 `db_default`？** Django 5.0+ 支持 `db_default`（把 `uuidv7()` 写进 DB schema）。可选增强：

```python
from django.db.models.expressions import RawSQL
id = models.UUIDField(
    primary_key=True,
    default=uuid_compat.uuid7,        # 应用层（Django ORM 创建对象时）
    db_default=RawSQL("uuidv7()", []), # DB 层（裸 SQL INSERT 时）
    editable=False,
)
```

**建议**：先用 `default`（应用层）即可跑通；`db_default` 作为增强项，待流程验证后再加。

### 4.4 PostgreSQL 原生 `uuidv7()`

PG18 内置（无需扩展）：
```sql
SELECT uuidv7();
-- 019f8edc-58d4-7ee5-8e46-bd603cad4742  （版本位=7，正确）
```

类型转换的正确写法（关键）：
```sql
-- ✅ 正确：用 USING uuidv7() 让 PG 重新生成 UUID 值
ALTER TABLE user_account ALTER COLUMN id TYPE uuid USING uuidv7();

-- ❌ 错误：会报 cannot cast type bigint to uuid
ALTER TABLE user_account ALTER COLUMN id TYPE uuid USING id::uuid;
```

---

## 五、迁移总体策略

### 5.1 三类表分别处理

```
A. Django 托管表（43 张）
   → 改模型 → makemigrations 生成骨架 → 改成 RunSQL（USING uuidv7()）→ migrate

B. 原始 SQL 表（14 张：alert_logs/problems/users/...）
   → 纯 SQL 脚本（nextval 序列 → uuid default uuidv7()），Django 管不到

C. 软引用字段（5 个 question_id）
   → 专项：ALTER TYPE uuid USING uuidv7() + 数据映射（如有数据）
```

### 5.2 两条路径（按数据量选择）

| 路径 | 适用 | 做法 | 数据保留 | 难度 |
|------|------|------|:---:|:---:|
| **路径 A：重建表法** | 业务数据少（<1000 条）或可重新生成 | 改模型 → 删业务表 → migrate 重建 → 按需导回数据 | ❌ 旧 id 不保留 | ⭐ 低 |
| **路径 B：原地迁移法** | 业务数据多、必须保留 | Saleor 式多步：加 uuid 列→建映射→回填 FK→切主键→删旧列 | ✅ 保留外键关系 | ⭐⭐⭐ 高 |

> **本项目推荐路径 A**（本地全空、生产数据极少）。路径 B 作为数据多时的备选，见第八章。

### 5.3 迁移顺序：拓扑分批（先父后子）

按「被引用最多的父表最先迁」，分 **5 批**：

| 批次 | 表 | 说明 |
|:---:|-----|------|
| **1** | `user_account` | 16 张表引用，最先迁，迁后验证登录 |
| **2** | `tiku_exam_question`（含 2 自引用）→ `tiku_exam_paper` → `tiku_exam_page` | 题库核心链 |
| **3** | `learning_mission` → `mission_level` → `class` → `institution` → `course` → `course_tree`（自引用）| 组织/任务核心 |
| **4** | 所有叶子关联表（引用前三批的）：mission_question_rel、student_mission_progress、student_level_progress、answer_attempt、institution_member、class_teacher、class_student、class_join_request、student_parent_bind、tiku_parse_task、tiku_ai_parse_result、tiku_question_option、tiku_question_image、course_material、course_question_link、course_variant_task、tiku_favorite、ai_guidance_session、wrong_book_item、mastery_record | 跟随父表 |
| **5** | 叶子表（无引用）+ B/C 类 | knowledge_points、tiku_paper_code_counter、tiku_question_id_counter + 14 张原始 SQL 表 + 5 个软引用字段 |

每批完成后：跑冒烟测试（关键接口），确认无误再进下一批；可随时回滚到该批备份。

---

## 六、路径 A：重建表法（推荐）

> 适用：本地（全空）、生产（数据少）。**这是本项目主推路径。**

### 6.1 思路

```
1. 全量备份（pg_dump）
2. 改 33 个模型为显式 UUIDField 主键（第四章写法）
3. 清空 django_migrations 中相关 app 记录
4. DROP 所有业务表（CASCADE）
5. makemigrations + migrate（用 UUID 结构重建表）
6. 按需把备份数据导回（少量，id 重新生成或手动映射）
7. 验证接口
```

### 6.2 优缺点

- ✅ 最简单可靠，不用处理复杂的 FK 类型转换
- ✅ 一把 `migrate` 重建全部表，结构干净
- ❌ 旧 int 主键值丢失（UUID 本就不兼容旧 id）
- ❌ 若有大量数据，导回工作量大

### 6.3 详细步骤

#### 步骤 A1：备份

```bash
# 本地
docker exec app-pgsql pg_dump -U appuser appdb > appdb_before_uuid_$(date +%Y%m%d).sql

# 生产
docker exec app-pgsql pg_dump -U appuser appdb > /mnt/datadisk0/qisi/backups/appdb_before_uuid_$(date +%Y%m%d).sql
```

#### 步骤 A2：安装 uuid-utils

```bash
pip install "uuid-utils>=0.11.0"
# 同步加到 requirements.txt
```

#### 步骤 A3：改造模型（见第七章完整清单）

为 33 个模型显式声明 `id = UUIDField(...)`。

#### 步骤 A4：清空迁移记录 + 删表重建

写一个迁移脚本（`rebuild_with_uuid.py`）：

```python
"""
重建表法：清空业务表迁移记录 → 删业务表 → 用 UUID 结构重建
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connection

# 33 张 Django 托管的业务表（A 类）
DJANGO_TABLES = [
    'user_account', 'student_parent_bind',
    'knowledge_points',
    'learning_mission', 'mission_level', 'mission_question_rel',
    'institution', 'institution_member', 'class', 'class_teacher',
    'class_student', 'class_join_request',
    'tiku_exam_paper', 'tiku_parse_task', 'tiku_paper_code_counter', 'tiku_question_id_counter',
    'tiku_exam_page', 'tiku_ai_parse_result', 'tiku_exam_question',
    'tiku_question_option', 'tiku_question_image',
    'student_mission_progress', 'student_level_progress', 'answer_attempt',
    'tiku_favorite', 'ai_guidance_session',
    'wrong_book_item', 'mastery_record',
    'course', 'course_material', 'course_tree', 'course_question_link', 'course_variant_task',
]

with connection.cursor() as cur:
    connection.autocommit = True
    # 1. 删除这些表（CASCADE 连带外键）
    for t in DJANGO_TABLES:
        cur.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE;')
    # 2. 清空这些 app 的迁移记录（按 app 分组删）
    apps = ['accounts','knowledge','missions','institutions','papers','parser','study','wrongbook','courses']
    for a in apps:
        cur.execute(f"DELETE FROM django_migrations WHERE app='{a}';")
print("[OK] 业务表已清空，迁移记录已重置")
```

#### 步骤 A5：重新迁移

```bash
# 因为模型已改成 UUID，makemigrations 会生成 initial 迁移（UUID 主键）
python manage.py makemigrations
python manage.py migrate
```

此时 Django 用全新的 UUID 结构创建 33 张表，主键即 `uuid DEFAULT uuidv7()`（若用了 `db_default`）或应用层 `default`。

#### 步骤 A6：导回数据（如有备份且需要）

数据量少时，可从备份 SQL 里提取 `INSERT` 语句，但 **id 列要改为 uuidv7() 生成**（旧 int id 无法直接用）。或用脚本逐表导。

> 本项目生产数据极少，建议评估后决定是否导回；若可重新生成（如重建测试用户）则跳过。

---

## 七、模型改造指南（33 个模型完整清单）

### 7.1 建议抽一个抽象基类（可选，减少重复）

```python
# apps/common/models.py
import uuid_utils.compat as uuid_compat
from django.db import models

class UUIDPrimaryKeyModel(models.Model):
    """统一 UUID v7 主键的抽象基类"""
    id = models.UUIDField(
        primary_key=True,
        default=uuid_compat.uuid7,
        editable=False,
    )
    class Meta:
        abstract = True
```

> ⚠️ `UserAccount` 继承 `AbstractBaseUser`，保持各自显式声明 id，不强制走基类（避免继承冲突）。其余模型可继承 `UUIDPrimaryKeyModel`。**也可不抽基类，每个模型直接显式声明 id（改动最小，最安全）**。

### 7.2 完整改造清单（每个模型都要显式加 id）

| App | 模型 | db_table | 原状态 | 改造 |
|-----|------|----------|:---:|------|
| accounts | UserAccount | user_account | 已显式 | 改 id 类型 |
| accounts | StudentParentBind | student_parent_bind | 已显式 | 改 id 类型 |
| knowledge | KnowledgePoint | knowledge_points | 已显式 | 改 id 类型 |
| missions | LearningMission | learning_mission | 已显式 | 改 id 类型 |
| missions | MissionLevel | mission_level | 已显式 | 改 id 类型 |
| missions | MissionQuestionRel | mission_question_rel | 已显式 | 改 id 类型 |
| institutions | Institution | institution | 已显式 | 改 id 类型 |
| institutions | InstitutionMember | institution_member | 已显式 | 改 id 类型 |
| institutions | Class | class | 已显式 | 改 id 类型 |
| institutions | ClassTeacher | class_teacher | 已显式 | 改 id 类型 |
| institutions | ClassStudent | class_student | 已显式 | 改 id 类型 |
| institutions | ClassJoinRequest | class_join_request | 已显式 | 改 id 类型 |
| **papers** | ExamPaper | tiku_exam_paper | **未显式** | **新增 id 声明** |
| **papers** | ParseTask | tiku_parse_task | **未显式** | **新增 id 声明** |
| **papers** | PaperCodeCounter | tiku_paper_code_counter | **未显式** | **新增 id 声明** |
| **papers** | QuestionIDCounter | tiku_question_id_counter | **未显式** | **新增 id 声明** |
| **parser** | ExamPage | tiku_exam_page | **未显式** | **新增 id 声明** |
| **parser** | AIParseResult | tiku_ai_parse_result | **未显式** | **新增 id 声明** |
| **parser** | ExamQuestion | tiku_exam_question | **未显式** | **新增 id 声明** |
| **parser** | QuestionOption | tiku_question_option | **未显式** | **新增 id 声明** |
| **parser** | QuestionImage | tiku_question_image | **未显式** | **新增 id 声明** |
| study | StudentMissionProgress | student_mission_progress | 已显式 | 改 id 类型 |
| study | StudentLevelProgress | student_level_progress | 已显式 | 改 id 类型 |
| study | AnswerAttempt | answer_attempt | 已显式 | 改 id 类型 |
| study | Favorite | tiku_favorite | 已显式 | 改 id 类型 |
| study | AIGuidanceSession | ai_guidance_session | 已显式 | 改 id 类型 |
| wrongbook | WrongBookItem | wrong_book_item | 已显式 | 改 id 类型 |
| wrongbook | MasteryRecord | mastery_record | 已显式 | 改 id 类型 |
| courses | Course | course | 已显式 | 改 id 类型 |
| courses | CourseMaterial | course_material | 已显式 | 改 id 类型 |
| courses | CourseTree | course_tree | 已显式 | 改 id 类型 |
| courses | CourseQuestionLink | course_question_link | 已显式 | 改 id 类型 |
| courses | VariantTask | course_variant_task | 已显式 | 改 id 类型 |

### 7.3 改造示例

**已显式 id 的模型**（24 个）：
```python
# 修改前
id = models.BigAutoField(primary_key=True)
# 修改后
id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
```

**未显式 id 的模型**（papers/parser 9 个）：
```python
# 修改前：无 id 字段（依赖 default_auto_field）
# 修改后：显式添加
id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
```

**外键字段：无需改代码**——Django 的 `ForeignKey` 会自动使用目标模型的主键类型（UUID）。改完父表，`makemigrations` 会自动为子表 FK 列生成类型变更迁移（但需改成 RunSQL，见第八章）。

### 7.4 db_column 命名陷阱（写裸 SQL 时注意）

以下 FK 字段名以 `_id` 结尾且未设 `db_column`，**真实列名是 `xxx_id_id`（双后缀）**：

| 模型 | 字段名 | 真实列名 |
|------|--------|---------|
| StudentParentBind | student_user_id | student_user_id_id |
| StudentParentBind | parent_user_id | parent_user_id_id |
| LearningMission | creator_teacher_id | creator_teacher_id_id |
| StudentMissionProgress / StudentLevelProgress / AnswerAttempt / AIGuidanceSession / WrongBookItem / MasteryRecord | student_user_id | student_user_id_id |

> 写迁移 SQL 时务必按真实列名，否则报 `column does not exist`。

---

## 八、路径 B：原地迁移法（数据多时备选）

> 适用：生产有大量必须保留的数据。Saleor 式多步迁移，保留外键关系。

### 8.1 单表迁移模板（以 user_account 为例，被 16 张表引用）

```sql
-- 假设要把 user_account.id 从 bigint 改 uuid，并同步更新所有引用

BEGIN;

-- 1. 父表：加新 uuid 列并回填
ALTER TABLE user_account ADD COLUMN new_id uuid DEFAULT uuidv7() NOT NULL;

-- 2. 建旧 id → 新 uuid 的映射（临时表）
CREATE TEMP TABLE _user_map AS
  SELECT id AS old_id, new_id FROM user_account;

-- 3. 对每张引用 user_account 的子表，加新 FK 列并用映射回填
--    （此处以 student_parent_bind.student_user_id_id 为例，实际要对 16 张表都做）
ALTER TABLE student_parent_bind ADD COLUMN new_student_user_id uuid;
UPDATE student_parent_bind sp
  JOIN _user_map m ON sp.student_user_id_id = m.old_id
  SET sp.new_student_user_id = m.new_id;
-- ...其余 15 张表同理（institution_member.user_id、class.creator_teacher_id 等）

-- 4. 切换父表主键
ALTER TABLE user_account DROP CONSTRAINT user_account_pkey;
ALTER TABLE user_account DROP COLUMN id;
ALTER TABLE user_account RENAME COLUMN new_id TO id;
ALTER TABLE user_account ALTER COLUMN id DROP DEFAULT;
ALTER TABLE user_account ALTER COLUMN id SET DEFAULT uuidv7();
ALTER TABLE user_account ADD PRIMARY KEY (id);

-- 5. 切换子表：删旧 FK 列，重命名新列，重建外键约束
ALTER TABLE student_parent_bind DROP COLUMN student_user_id_id;
ALTER TABLE student_parent_bind RENAME COLUMN new_student_user_id TO student_user_id_id;
ALTER TABLE student_parent_bind
  ADD CONSTRAINT student_user_fk FOREIGN KEY (student_user_id_id) REFERENCES user_account(id);
-- ...其余 15 张表同理

COMMIT;
```

### 8.2 自引用外键特殊处理

**ExamQuestion**（parent_question、original_question 指向自己）和 **CourseTree**（parent）：

```sql
-- ExamQuestion 自引用：先把自引用列置 NULL，改完主键再用映射回填
ALTER TABLE tiku_exam_question ADD COLUMN new_id uuid DEFAULT uuidv7() NOT NULL;
CREATE TEMP TABLE _q_map AS SELECT id AS old_id, new_id FROM tiku_exam_question;

ALTER TABLE tiku_exam_question ADD COLUMN new_parent uuid, ADD COLUMN new_original uuid;
UPDATE tiku_exam_question q
  JOIN _q_map m1 ON q.parent_question_id = m1.old_id
  SET q.new_parent = m1.new_id;
UPDATE tiku_exam_question q
  JOIN _q_map m2 ON q.original_question_id = m2.old_id
  SET q.new_original = m2.new_id;
-- 切主键（同 8.1 step4），再替换 parent_question_id / original_question_id 列
```

### 8.3 软引用字段（5 个 question_id）

这些列无外键约束，但有数据时需用映射回填：

```sql
-- 5 张表：mission_question_rel / answer_attempt / tiku_favorite / ai_guidance_session / wrong_book_item
-- 都有 question_id 列（int）指向 tiku_exam_question.id
-- tiku_exam_question 改 uuid 后，用映射表回填：

ALTER TABLE mission_question_rel ALTER COLUMN question_id TYPE uuid
  USING (SELECT new_id FROM _q_map WHERE _q_map.old_id = mission_question_rel.question_id);
-- 其余 4 张表同理
```

> ⚠️ 软引用列改完类型后，建议补建外键约束，或至少建索引。

### 8.4 Django 迁移文件配合（路径 B）

路径 B 用纯 SQL 改完表结构后，要让 Django 迁移状态对齐：

```python
# migrations/xxxx_uuid_pk.py
from django.db import migrations, models
import uuid_utils.compat as uuid_compat

class Migration(migrations.Migration):
    dependencies = [('accounts', '0001_initial')]
    operations = [
        migrations.RunSQL(
            sql="<上面 8.1 的 SQL>",
            reverse_sql="...",
            state_operations=[
                migrations.AlterField(
                    'accounts', 'UserAccount', 'id',
                    models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False),
                ),
                # 所有子表 FK 的 state_operations...
            ],
        ),
    ]
```

> 路径 B 工作量巨大（58 个外键约束逐个处理）。**强烈建议优先评估能否走路径 A**。

---

## 九、B 类表（14 张原始 SQL 表）处理

这些表 Django 管不到（`alert_logs/problems/users/system_config` 等），用纯 SQL：

```sql
-- 模板：nextval 序列表 → uuid 主键
-- 以 alert_logs 为例
ALTER TABLE alert_logs DROP CONSTRAINT IF EXISTS alert_logs_pkey;
ALTER TABLE alert_logs ALTER COLUMN id TYPE uuid USING uuidv7();
ALTER TABLE alert_logs ALTER COLUMN id SET DEFAULT uuidv7();
ALTER TABLE alert_logs ADD PRIMARY KEY (id);
DROP SEQUENCE IF EXISTS alert_logs_id_seq;
-- 其余 13 张同理
```

完整 14 张：`alert_logs, api_task_logs, dlq_messages, gemini_results, llm_audit, monitoring_metrics, problem_results, problems, retry_queue, rollback_logs, system_config, task_outbox, test_connection, users`

> ⚠️ `test_connection` 已是 uuid 主键（迁移时建的），跳过。`users` 是旧表，确认是否还在用。

---

## 十、本地执行步骤（先演练）

> 本地业务表全空，走**路径 A（重建表法）**演练全流程。

```bash
cd D:\yangtze\project\2026\qisi\qisi_frontend

# 1. 安装 uuid-utils
pip install "uuid-utils>=0.11.0"

# 2. 备份本地数据库
docker exec app-pgsql pg_dump -U appuser appdb > appdb_before_uuid_local.sql

# 3. 改造 33 个模型（第七章清单，逐个加 id = UUIDField(...)）
#    同步 requirements.txt 加 uuid-utils

# 4. 跑改造脚本：删业务表 + 清迁移记录（第六章 A4 脚本）
python rebuild_with_uuid.py

# 5. 重新迁移（UUID 结构）
python manage.py makemigrations
python manage.py migrate

# 6. 验证表结构（id 应为 uuid 类型）
docker exec app-pgsql psql -U appuser -d appdb -c "\d user_account"
# 期望：id | uuid | not null | default uuidv7()

# 7. 处理 14 张原始 SQL 表（第九章 SQL）

# 8. 处理 5 个软引用字段（第八章 8.3）

# 9. 启动本地服务，冒烟测试
python manage.py runserver
# 测试：注册/登录、知识点树、试卷、任务等关键接口

# 10. 本地全绿后，准备上传服务器
```

---

## 十一、服务器部署步骤

> 生产走与本地相同的路径（数据少时路径 A，数据多时路径 B）。

```bash
# === 本地准备 ===
# 1. 确认本地已验证通过
# 2. 打包后端代码（含改好的模型 + 迁移文件）
cd D:\yangtze\project\2026\qisi\qisi_frontend
tar --exclude=venv --exclude=node_modules --exclude=.git --exclude=__pycache__ \
    --exclude=*.pyc --exclude=.env --exclude=*.tar.gz --exclude=word \
    --exclude=uniapp --exclude=src --exclude=.claude \
    -czf qisi_backend.tar.gz .

# 3. 上传
scp qisi_backend.tar.gz ubuntu@42.194.195.78:/mnt/datadisk0/qisi/backend/

# === 服务器执行 ===
ssh ubuntu@42.194.195.78
cd /mnt/datadisk0/qisi/backend
tar -xzf qisi_backend.tar.gz && rm qisi_backend.tar.gz

# 4. 【关键】全量备份生产数据库（务必！）
docker exec app-pgsql pg_dump -U appuser appdb \
  > /mnt/datadisk0/qisi/backups/appdb_before_uuid_prod_$(date +%Y%m%d_%H%M%S).sql
ls -lh /mnt/datadisk0/qisi/backups/appdb_before_uuid_prod_*

# 5. 统计生产各业务表数据量（决定走路径 A 还是 B）
docker exec app-pgsql psql -U appuser -d appdb -c "
SELECT relname, n_live_tup FROM pg_stat_user_tables 
WHERE schemaname='public' AND n_live_tup > 0 ORDER BY n_live_tup DESC;"
# → 若业务表数据都很少（如 <1000 行），走路径 A；否则走路径 B

# 6. 安装 uuid-utils
source venv/bin/activate
pip install "uuid-utils>=0.11.0"

# 7. 执行迁移（路径 A：删表重建）
python rebuild_with_uuid.py        # 删业务表 + 清迁移记录
python manage.py makemigrations
python manage.py migrate

# 8. 处理 14 张原始 SQL 表 + 5 个软引用（第九、八章 SQL）
docker exec -i app-pgsql psql -U appuser -d appdb < migrate_raw_tables_uuid.sql
docker exec -i app-pgsql psql -U appuser -d appdb < migrate_soft_refs_uuid.sql

# 9. 重启服务
sudo systemctl restart qisi-gunicorn qisi-celery qisi-celery-beat

# 10. 验证（第十二章清单）
```

---

## 十二、验证清单

### 12.1 表结构验证

```sql
-- 所有业务表主键应为 uuid
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='public' AND column_name='id'
  AND table_name NOT IN ('django_session','django_migrations')
ORDER BY data_type, table_name;
-- 期望：全部 data_type = 'uuid'（除 django_session.session_key 是 varchar）
```

### 12.2 接口冒烟测试（生产）

```bash
# 登录（涉及 user_account）
curl -s -o /dev/null -w "%{http_code}\n" https://qisi.chengxuelu.com/api/v1/auth/login
# 知识点树
curl -s -o /dev/null -w "%{http_code}\n" "https://qisi.chengxuelu.com/api/v1/teacher/knowledge-tree/?subject=数学&stage=高中"
# 任务列表（涉及 learning_mission、mission_level）
curl -s -o /dev/null -w "%{http_code}\n" https://qisi.chengxuelu.com/api/v1/missions/list/
# 试卷（涉及 tiku_exam_paper、tiku_exam_question）
curl -s -o /dev/null -w "%{http_code}\n" https://qisi.chengxuelu.com/api/v1/papers/
```

> 401 = 未登录但路由正常（说明表正常）；200 = 完全正常；500 = 有问题。

### 12.3 功能验证（用真实账号登录后）

- [ ] 登录 / 注册
- [ ] 知识点树加载
- [ ] 试卷解析（tiku 链路）
- [ ] 任务下发与进度（mission 链路）
- [ ] 班级/课程（institution + courses 链路）
- [ ] 错题本 / 收藏（wrongbook + favorite，含软引用 question_id）
- [ ] AI 辅导（ai_guidance_session，含软引用）

---

## 十三、回滚方案

### 13.1 迁移前必备

- 全量 `pg_dump` 备份（生产 + 本地各一份）
- 记录当前 `django_migrations` 状态

### 13.2 回滚操作

```bash
# 停服务
sudo systemctl stop qisi-gunicorn qisi-celery qisi-celery-beat

# 恢复数据库（迁移前的备份）
docker exec -i app-pgsql psql -U appuser appdb \
  < /mnt/datadisk0/qisi/backups/appdb_before_uuid_prod_YYYYMMDD_HHMMSS.sql

# 代码回退（git checkout 到 UUID 改造前的 commit）
cd /mnt/datadisk0/qisi/backend
git checkout <pre-uuid-commit>

# 重启
sudo systemctl start qisi-gunicorn qisi-celery qisi-celery-beat
```

### 13.3 分批回滚

走路径 B 分批迁移时，每批后都打一个 git tag + 数据库备份点，失败时回退到最近一个成功点，不必全量回滚。

---

## 十四、风险与注意事项

1. **生产数据量必须先核查**（第十一章步骤 5）。数据多就走路径 B，不要盲目重建。
2. **JWT / 已签发 token**：UserAccount.id 改 UUID 后，旧 token 里的 int user_id 失效，所有用户需重新登录。**迁移窗口选低峰期**。
3. **前端**：若前端缓存了 int 类型的 id，需清理。URL 里的 id（如 `/api/papers/123/`）会变成 UUID 格式 `/api/papers/019f8edc-.../`，确认前端路由/正则兼容。
4. **第三方 / 外部存储**：OSS 文件路径、Celery 任务参数里若含旧 int id，需排查。
5. **14 张原始 SQL 表**：Django 迁移管不到，必须单独 SQL，且部分（如 `users`）可能是旧表，确认是否还在用。
6. **5 个软引用 `question_id`**：最易遗漏，迁移后若发现"题目打不开"类问题，优先查这些列。
7. **`db_default=uuidv7()`**：若启用，确保迁移文件里带了，否则裸 SQL INSERT 会报 null。
8. **不要在生产直接 `migrate` 未经验证的迁移**——先本地演练，再服务器。

---

## 十五、FAQ

**Q1：为什么不直接用标准库 `uuid.uuid7()`？**
A：标准库 3.14 才有，当前 Python 3.13.9 用不了。用 `uuid-utils` 的 `compat.uuid7` 返回标准库 `uuid.UUID`，Django 兼容。

**Q2：UUID 主键性能比 int 差很多吗？**
A：UUID v7 是时间有序的（不像 v4 随机），B-tree 索引友好，性能接近自增 int。存储 16 字节 vs int 8 字节，索引略大，中小规模可忽略。

**Q3：路径 A 会丢数据吗？**
A：会丢旧 int 主键值（UUID 本就不兼容 int），但业务数据（非 id 列）可从备份导回（id 重新生成）。本项目数据少，影响可控。

**Q4：迁移期间要停服吗？**
A：建议维护窗口（低峰期），因为涉及表结构变更 + 用户需重新登录。预估停机：路径 A 15-30 分钟，路径 B 1-3 小时（视数据量）。

**Q5：能不能分 app 渐进迁移（部分表 UUID，部分 int）？**
A：不推荐。跨 app 外键会导致 int/UUID 混用，类型不匹配报错。建议一次性全改。

**Q6：`question_id` 软引用为什么不建成真外键？**
A：历史设计选择（可能为了解耦或避免删除级联）。本次迁移顺带可补建外键，但需评估业务影响。

---

## 十六、参考资料

- [Django Ticket #32577 – UUIDAutoField](https://code.djangoproject.com/ticket/32577)
- [uuid-utils (PyPI)](https://pypi.org/project/uuid-utils/)
- [PostgreSQL 18 UUIDv7 支持](https://www.thenile.dev/blog/uuidv7)
- [Saleor – UUID Migration in Django with PostgreSQL](https://dev.to/saleor/uuid-migration-in-django-with-postgresql-4p3m)
- [Migrating Integer ID to UUID in Django Without Data Loss](https://medium.com/@mohammadwow24/migrating-from-integer-id-to-uuid-in-django-without-data-loss-postgresql-d4f21c3b4477)
- 本项目调研报告：代码层（33 模型 / 53 外键 / 5 软引用）、数据库层（PG18 / 58 约束 / 14 原始表）

---

## 附录 A：完整外键依赖图（迁移顺序依据）

```
user_account (被16表引用) ──┐
                            ├── student_parent_bind×2
                            ├── institution, institution_member, class, class_teacher/student/join_request×2
                            ├── learning_mission, tiku_exam_paper
                            └── study/courses/wrongbook 等所有含 user FK 的表

tiku_exam_question (4表+2自引用+5软引用) ──┐
    ├── tiku_parse_task, tiku_question_option, tiku_question_image
    ├── course_question_link, course_variant_task
    ├── parent_question/original_question (自引用)
    └── 软引用: mission_question_rel/answer_attempt/tiku_favorite/ai_guidance_session/wrong_book_item

tiku_exam_paper (5) → tiku_parse_task, tiku_exam_page, tiku_ai_parse_result, tiku_exam_question, tiku_question_image
learning_mission (4) → mission_level, mission_question_rel, student_mission_progress, answer_attempt
class (4) → learning_mission, class_teacher/student, class_join_request
mission_level (3) → mission_question_rel, student_mission_progress/level_progress
course (3) → course_material, course_tree, course_question_link
course_tree (2+自引用) → course_tree(parent), course_question_link
institution (2) → institution_member, class
tiku_exam_page (2) → tiku_ai_parse_result, tiku_question_image
```

---

## 附录 B：本地演练实战记录（2026-07-23 已验证）

本地按路径 A 完整演练**全部通过**（49 张业务表 id 全部 UUID v7）。以下实战细节，服务器部署务必遵循：

### B.1 路径 A 精确执行顺序

```bash
# 1. 删 9 个业务 app 旧迁移文件（保留 __init__.py）
find apps -path "*/migrations/0*.py" -delete

# 2. 删业务表 + 清迁移记录（脚本已实现）
python rebuild_with_uuid.py
#    → DROP 33 张业务表 + django_admin_log（CASCADE）
#    → DELETE django_migrations WHERE app IN (9个业务app + admin)  ← admin 必须清，否则 django_admin_log 重建失败

# 3. 生成全新 UUID 结构迁移
python manage.py makemigrations
#    → papers/parser 循环依赖 + 自引用外键，Django 自动拆成 0001+0002，正常

# 4. 建表
python manage.py migrate
```

### B.2 C 类软引用（5 个 question_id）迁移踩坑

`makemigrations` 生成的 `AlterField(integer→uuid)` **会失败**（`cannot cast integer to uuid`），需手改成 `RunSQL`：

```python
operations = [
    migrations.RunSQL(
        sql="ALTER TABLE xxx ALTER COLUMN question_id TYPE uuid USING uuidv7();",
        reverse_sql="ALTER TABLE xxx ALTER COLUMN question_id TYPE integer USING NULL::integer;",
        state_operations=[
            # ⚠️ AlterField 签名是 (model_name, name, field)，第一个参数不要传 app_label！
            migrations.AlterField("ModelName", "question_id", models.UUIDField()),
        ],
    ),
]
```

**踩坑**：state_operations 若误写 `AlterField("app_label", "Model", ...)` → `KeyError: ('app','app')`。

### B.3 B 类表处理顺序（关键，易错）

nextval 序列表与 IDENTITY 列处理顺序**不同**，必须按序：

```
1. DROP CONSTRAINT 主键 CASCADE
2. DROP IDENTITY    （仅 IDENTITY 列；用 try/except，非 identity 会报错忽略）
3. DROP DEFAULT     （nextval 序列表必须先删，否则报 "default cannot be cast to uuid"）
4. ALTER COLUMN id TYPE uuid USING uuidv7()
5. ALTER COLUMN id SET DEFAULT uuidv7()
6. ADD PRIMARY KEY (id)
7. DROP SEQUENCE IF EXISTS
```

- **13 张 nextval 序列表**（alert_logs/problems/users 等）：步骤 3 必须，否则 `default cannot be cast to uuid`
- **2 张 IDENTITY 表**（tiku_teacher_favorite/profile）：步骤 2 必须，否则 `identity column type must be smallint/integer/bigint`

脚本 `migrate_b_tables_uuid.py` 已实现上述顺序，直接复用。

### B.4 本地验证结果

| 验证项 | 结果 |
|--------|------|
| 49 张业务表 id 类型 | 全部 uuid（0 张非 uuid）✅ |
| Django check | 0 issues ✅ |
| makemigrations | No changes detected（迁移与模型一致）✅ |
| UUID v7 主键生成 | `019f8f0d-107a-71f3-...`（版本位 7）✅ |
| 外键跟随 | creator_teacher_id 等自动变 uuid ✅ |
| `uuidv7()` 函数 | PG18.4 原生可用 ✅ |

### B.5 服务器部署可直接复用的脚本

- `rebuild_with_uuid.py`：删业务表 + 清迁移记录（路径 A 第 2 步）
- `migrate_b_tables_uuid.py`：B 类 15 张表 id → uuid（含 IDENTITY 处理）
- C 类迁移文件（study/missions/wrongbook 的 0002 RunSQL）：随代码上传即可

---

**✅ 方案要点回顾**：保持 `BigAutoField`、显式 `UUIDField` 主键、用 `uuid-utils`、PG18 原生 `uuidv7()`、手写 RunSQL（`USING uuidv7()`）、三类表分别处理、拓扑分批、本地先演练。**数据少走路径 A（重建表），数据多走路径 B（原地 Saleor 式）。**
