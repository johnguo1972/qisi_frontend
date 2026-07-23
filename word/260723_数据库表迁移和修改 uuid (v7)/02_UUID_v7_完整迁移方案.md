# UUID v7 完整迁移方案

> **目标**：将所有表的主键 ID 从 `BigAutoField`（int8）迁移到 `UUIDField` (UUID v7)  
> **执行时机**：**先于缺失表迁移**执行  
> **数据安全**：迁移过程数据不丢失，支持回滚

---

## 🎯 为什么选择 UUID v7？

### UUID v7 vs BigAutoField 对比

| 特性 | BigAutoField (当前) | UUID v7 |
|------|-------------------|---------|
| **存储** | 8 字节 | 16 字节 |
| **最大值** | 922 亿亿 | 几乎无限 |
| **有序性** | ✅ 自增有序 | ✅ 时间有序（RFC 9562） |
| **性能** | ⭐⭐⭐⭐⭐ 最优 | ⭐⭐⭐ 稍慢（索引大 2 倍） |
| **分布式** | ❌ 单库必须 | ✅ 多库友好 |
| **安全性** | ⚠️ 暴露业务规模 | ✅ 不暴露 |
| **Django 支持** | ✅ 原生 | ✅ 需 uuid7 库 |

### UUID v7 的优势

1. **时间有序**：UUID v7 包含时间戳，天然有序，适合索引
2. **分布式友好**：不需要中心化的 ID 生成器
3. **安全性更好**：不可预测，不暴露业务规模
4. **未来扩展性**：支持多数据中心、数据合并

---

## 📋 迁移范围

### 需要修改的模型（9 个 apps）

| App | 模型数量 | 主要模型 |
|-----|---------|----------|
| accounts | 2 | `UserAccount`, `StudentParentBind` |
| knowledge | 1 | `KnowledgePoint` |
| missions | 3 | `LearningMission`, `MissionLevel`, `MissionQuestionRel` |
| institutions | 5 | `Institution`, `InstitutionMember`, `Class`, `ClassTeacher`, `ClassStudent`, `ClassJoinRequest` |
| papers | 3 | `ExamPaper`, `ExamPage`, `ParseTask` |
| parser | 2 | `AIParseResult`, `ExamQuestion` |
| study | 5 | `Favorite`, `AnswerAttempt`, `StudentLevelProgress`, `StudentMissionProgress` 等 |
| wrongbook | 2 | `WrongBookItem`, `WrongBookQuestion` |
| courses | 5 | `Course`, `CourseMaterial`, `CourseQuestionLink` 等 |

**总计**：约 **30 个模型**需要修改

---

## 🚀 完整迁移方案

### 方案概述

**核心思路**：
1. 修改所有模型定义（`BigAutoField` → `UUIDField`）
2. 生成 Django 迁移文件
3. 执行迁移（Django 自动处理数据转换）

**关键点**：
- 使用 `uuid7` 库（`pip install uuid7`）
- 迁移过程**数据不丢失**
- 支持回滚

---

## 📝 详细步骤

### 步骤 1：安装 uuid7 库

#### 本地（开发环境）

```bash
# 在本地 Git Bash 或 CMD 中执行
cd D:\yangtze\project\2026\qisi\qisi_frontend
pip install uuid7
```

#### 服务器（生产环境）

```bash
# 在服务器执行
cd /mnt/datadisk0/qisi/backend
source venv/bin/activate
pip install uuid7
```

#### 更新 requirements.txt

在 `requirements.txt` 末尾添加：

```
uuid7>=0.1.1
```

---

### 步骤 2：修改所有模型定义

#### 2.1 修改 `apps.py` 配置

每个 app 的 `apps.py` 都要修改：

**修改前**：
```python
class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
```

**修改后**：
```python
import django.db.models
class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.UUIDField'  # 改为 UUIDField
```

**需要修改的文件**：
- `apps/accounts/apps.py`
- `apps/knowledge/apps.py`
- `apps/missions/apps.py`
- `apps/institutions/apps.py`
- `apps/papers/apps.py`
- `apps/parser/apps.py`
- `apps/study/apps.py`
- `apps/wrongbook/apps.py`
- `apps/courses/apps.py`

---

#### 2.2 修改模型 ID 字段

每个模型的 `id` 字段都要修改：

**修改前**：
```python
from django.db import models

class UserAccount(AbstractBaseUser):
    id = models.BigAutoField(primary_key=True)
```

**修改后**：
```python
from django.db import models
import uuid7

class UserAccount(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid7.uuid7, editable=False)
```

**需要修改的文件**（按优先级）：

1. **`apps/accounts/models.py`**（2 个模型）
   - `UserAccount`
   - `StudentParentBind`

2. **`apps/knowledge/models.py`**（1 个模型）
   - `KnowledgePoint`
   - 同时修改 `managed = False` → `managed = True`

3. **`apps/missions/models.py`**（3 个模型）
   - `LearningMission`
   - `MissionLevel`
   - `MissionQuestionRel`

4. **`apps/institutions/models.py`**（6 个模型）
   - `Institution`
   - `InstitutionMember`
   - `Class`
   - `ClassTeacher`
   - `ClassStudent`
   - `ClassJoinRequest`

5. 其他 apps 的模型（类似修改）

---

### 步骤 3：修改外键字段类型

所有外键字段也要改为 `UUIDField`：

**修改前**：
```python
student_user_id = models.ForeignKey(
    UserAccount, on_delete=models.CASCADE
)
```

**修改后**：
```python
student_user_id = models.ForeignKey(
    UserAccount, on_delete=models.CASCADE,
    # Django 会自动使用目标模型的主键类型（UUID）
)
```

**注意**：Django 的 `ForeignKey` 会自动使用关联模型的主键类型，所以**不需要显式指定 `to_field`**。

---

### 步骤 4：生成 Django 迁移文件

#### 4.1 本地生成迁移文件

```bash
# 在本地项目根目录
cd D:\yangtze\project\2026\qisi\qisi_frontend
python manage.py makemigrations
```

这会为所有修改的 app 生成迁移文件：
- `apps/accounts/migrations/0003_alter_useraccount_id.py`
- `apps/knowledge/migrations/0002_alter_knowledgepoint_id.py`
- 等等

#### 4.2 检查迁移文件

查看生成的迁移文件，确认：
- 操作类型是 `AlterField`（修改字段）
- `to` 参数是 `UUIDField`

---

### 步骤 5：测试环境验证

#### 5.1 本地测试

```bash
# 本地执行迁移
python manage.py migrate

# 验证表结构
python manage.py dbshell
\dt
\d user_account
```

#### 5.2 功能测试

- 启动本地服务：`python manage.py runserver`
- 测试登录功能
- 测试知识点树 API
- 确认所有接口正常

---

### 步骤 6：上传到服务器

#### 6.1 打包（排除 .env）

```bash
cd D:\yangtze\project\2026\qisi\qisi_frontend
tar --exclude=venv --exclude=node_modules --exclude=.git --exclude=__pycache__ --exclude=*.pyc --exclude=.env --exclude=*.tar.gz --exclude=word --exclude=uniapp --exclude=src --exclude=.claude -czf qisi_backend.tar.gz .
```

#### 6.2 上传

```bash
scp qisi_backend.tar.gz ubuntu@42.194.195.78:/mnt/datadisk0/qisi/backend/
```

---

### 步骤 7：服务器执行迁移

#### 7.1 解压

```bash
cd /mnt/datadisk0/qisi/backend
tar -xzf qisi_backend.tar.gz
```

#### 7.2 安装 uuid7

```bash
source venv/bin/activate
pip install uuid7
```

#### 7.3 备份数据库（重要！）

```bash
# 备份当前数据库
docker exec app-pgsql pg_dump -U appuser appdb > /mnt/datadisk0/qisi/backups/before_uuid_migration_$(date +%Y%m%d_%H%M%S).sql

# 确认备份文件存在
ls -lh /mnt/datadisk0/qisi/backups/before_uuid_migration_*
```

#### 7.4 执行迁移

```bash
cd /mnt/datadisk0/qisi/backend
source venv/bin/activate
python manage.py migrate
```

**迁移过程说明**：
- Django 会自动修改表结构
- 为每条现有记录生成新的 UUID v7
- 更新所有外键引用
- **数据不会丢失**

迁移输出示例：
```
Running migrations:
  Applying accounts.0003_alter_useraccount_id... OK
  Applying knowledge.0002_alter_knowledgepoint_id... OK
  Applying missions.0004_alter_learningmission_id... OK
  ...
```

---

### 步骤 8：验证迁移成功

#### 8.1 检查表结构

```bash
docker exec app-pgsql psql -U appuser -d appdb -c "\d user_account"
```

**期望输出**：
```
Column  | Type | Collation | Nullable | Default
---------+------+-----------+----------+----------------------------------
id      | uuid |           | not null | uuid_generate_v7()
mobile  | character varying(20) |  | not null
...
```

#### 8.2 检查数据完整性

```bash
# 确认记录数量不变
docker exec app-pgsql psql -U appuser -d appdb -c "SELECT COUNT(*) FROM user_account;"

# 确认所有 ID 都是 UUID 格式
docker exec app-pgsql psql -U appuser -d appdb -c "SELECT id FROM user_account LIMIT 5;"
```

#### 8.3 重启服务

```bash
sudo systemctl restart qisi-gunicorn qisi-celery qisi-celery-beat
```

#### 8.4 功能验证

```bash
# 测试登录接口
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/api/v1/auth/login

# 测试知识点树接口
curl -s "https://qisi.chengxuelu.com/api/v1/teacher/knowledge-tree/?subject=数学&stage=高中"
```

**期望结果**：所有接口正常返回（不是 500）

---

## ⚠️ 风险控制

### 迁移风险

1. **数据丢失风险**：极低（Django 迁移经过充分测试）
2. **性能影响**：索引变大 2 倍，查询稍慢（但可接受）
3. **回滚难度**：需要反向迁移（UUID → int）

### 回滚方案

如果迁移失败，执行回滚：

```bash
# 1. 停止服务
sudo systemctl stop qisi-gunicorn qisi-celery qisi-celery-beat

# 2. 恢复数据库备份
docker exec -i app-pgsql psql -U appuser appdb < /mnt/datadisk0/qisi/backups/before_uuid_migration_YYYYMMDD_HHMMSS.sql

# 3. 代码回退
cd /mnt/datadisk0/qisi/backend
git checkout HEAD~1  # 回退到上一个版本

# 4. 重启服务
sudo systemctl start qisi-gunicorn qisi-celery qisi-celery-beat
```

---

## 📊 性能影响评估

### 存储空间

- **主键索引**：8 字节 → 16 字节（增加 100%）
- **外键字段**：同样增加
- **总体影响**：数据库大小增加约 20-30%

### 查询性能

- **单表查询**：影响很小（< 5%）
- **JOIN 查询**：稍慢（UUID 比较比 int 慢）
- **索引扫描**：影响不大

**结论**：对于中小规模应用（< 100 万用户），性能影响可忽略。

---

## 🎯 执行检查清单

### 迁移前

- [ ] 本地安装 uuid7
- [ ] 服务器安装 uuid7
- [ ] 备份数据库
- [ ] 修改所有 `apps.py` 的 `default_auto_field`
- [ ] 修改所有模型的 `id` 字段
- [ ] 本地生成迁移文件
- [ ] 本地测试通过

### 迁移中

- [ ] 上传代码到服务器
- [ ] 服务器解压
- [ ] 执行 `python manage.py migrate`
- [ ] 确认所有迁移 `OK`

### 迁移后

- [ ] 检查表结构（`id` 是 `uuid` 类型）
- [ ] 检查数据完整性（COUNT 不变）
- [ ] 重启所有服务
- [ ] 功能验证（登录、知识点树等）
- [ ] 监控日志 24 小时

---

## 🔗 相关文档

- **01_缺失表迁移方案.md** - 缺失表迁移方案（在 UUID v7 迁移后执行）
- **public.sql** - 旧库完整表结构参考

---

## 💡 常见问题

### Q1: 迁移需要多长时间？

**A**: 
- 本地测试：5-10 分钟
- 服务器执行：取决于数据量
  - < 1 万记录：< 1 分钟
  - 1-10 万记录：1-5 分钟
  - > 10 万记录：5-30 分钟

### Q2: 迁移期间服务需要停机吗？

**A**: 建议维护窗口，因为：
- 迁移过程会锁表
- 服务可能短暂不可用
- 预计停机时间：5-30 分钟

### Q3: 迁移失败怎么办？

**A**: 立即回滚（见回滚方案），不要继续执行

### Q4: 可以分批次迁移吗？

**A**: 不建议，因为：
- 外键关系复杂
- 部分迁移会导致类型不一致
- 一次性迁移更安全

---

## 📞 支持

迁移过程中如有问题，检查：
1. Django 错误日志：`/mnt/datadisk0/qisi/logs/django-error.log`
2. Gunicorn 日志：`/mnt/datadisk0/qisi/logs/gunicorn-error.log`
3. PostgreSQL 日志：`docker logs app-pgsql`

**祝迁移顺利！**
