# 齐思 · A自习室（Qisi / A-Study-Room）

一个面向 K12 教育场景的 **AI 驱动智能学习平台**。平台将传统试卷（Word / PDF）通过 AI 解析为结构化题库，教师基于题库创建分层学习任务并布置给班级，学生完成任务、获取 AI 苏格拉底式辅导、自动整理错题本并追踪成长曲线。

本仓库为**前后端一体化仓库（Monorepo）**，包含：

- **后端**：Django 5 + DRF + Celery 的 REST API 服务
- **前端**：uni-app（Vue 3）多端应用，当前主要面向 H5

---

## 一、技术栈

### 后端（根目录）

| 分类 | 技术 |
| --- | --- |
| Web 框架 | Django 5.x、Django REST Framework 3.14 |
| 认证 | djangorestframework-simplejwt（JWT，Access 24h / Refresh 30d） |
| 异步任务 | Celery 5.x + Redis |
| 缓存 | Redis |
| 数据库 | PostgreSQL（psycopg2） |
| 文档处理 | PyMuPDF（PDF）、python-docx（Word） |
| AI 服务 | 通义千问 Qwen（httpx 调用，定位用 qwen3.6-plus，结构化用 qwen3-vl-plus） |
| 云服务 | 腾讯云 SMS（短信验证码）、阿里云 OSS（对象存储） |
| 部署 | gunicorn |
| 测试 | pytest、pytest-django、factory-boy、Faker、Playwright |

### 前端（`uniapp/`）

| 分类 | 技术 |
| --- | --- |
| 框架 | uni-app 3.0（Vue 3.4.21） |
| 构建 | Vite 5.2.8 + TypeScript 5.3.3 |
| UI 组件 | @dcloudio/uni-ui 1.5.6 |
| 状态管理 | Pinia 2.2.6 |
| 路由 | vue-router 4.4.4 |
| 目标平台 | H5（主要）、App（次要） |

---

## 二、目录结构

```text
qisi_frontend/
├── apps/                     # Django 业务应用（后端核心）
│   ├── accounts/             # 用户与认证（手机号 + 短信验证码 + JWT，多角色）
│   ├── institutions/         # 机构 / 班级 / 成员管理（多租户）
│   ├── knowledge/            # 知识体系（学科×学段×年级×章节 知识树）
│   ├── missions/             # 学习任务（分层任务 + 关卡 + 题目编排）
│   ├── papers/               # 试卷管理（上传、转 PDF、解析任务编排）
│   ├── parser/               # AI 试卷解析引擎（核心，11 步流水线）★
│   ├── review/               # 教师审校与编辑（质检、AI 生成答案、裁图）
│   ├── study/                # 学生学习（进度、作答、收藏、AI 辅导）
│   ├── wrongbook/            # 错题本（错题归集、变式推荐、掌握度、PDF 导出）
│   └── common/               # 公共工具与基础类
│
├── config/                   # Django 项目配置
│   ├── settings.py           # 全局配置（DB / Redis / JWT / OSS / SMS / CORS）
│   ├── urls.py               # API 路由总入口（/api/v1/...）
│   ├── celery.py             # Celery 异步任务配置
│   ├── wsgi.py / asgi.py     # 部署入口
│   └── __init__.py
│
├── uniapp/                   # uni-app 前端（H5/App 多端）
│   └── src/
│       ├── pages/            # 页面（按角色组织：login / student / teacher / admin）
│       ├── api/              # 接口封装（带 JWT 拦截器的 HTTP 客户端）
│       ├── store/            # Pinia 状态管理
│       ├── components/       # 公共组件
│       ├── utils/            # 工具函数
│       ├── App.vue           # 应用根组件
│       ├── main.ts           # 应用入口
│       ├── manifest.json     # 应用配置（名称：A自习室，H5 端口 5173）
│       └── pages.json        # 路由与页面注册（35+ 页面）
│
├── tests/                    # 测试套件
│   ├── conftest.py           # pytest 公共 fixtures
│   ├── factories.py          # 测试数据工厂（factory-boy）
│   ├── test_ai_pipeline.py   # AI 解析流水线测试
│   ├── test_integration.py   # 通用集成测试
│   ├── test_models_quick.py  # 模型校验测试
│   ├── integration/          # 功能模块集成测试（auth / papers / missions …）
│   └── e2e/                  # Playwright 端到端测试
│
├── docs/                     # 项目文档
│   ├── architecture/         # 系统架构（含 11 步解析流水线说明）
│   ├── superpowers/          # 功能设计与规划
│   └── student-requirements-v1.md  # 学生端需求（分 4 期）
│
├── src/                      # 演示 / 调试用前端组件（独立，非主前端）
│   ├── components/
│   └── pages/
│
├── media/                    # 用户上传文件（试卷、题目图片）本地存储
├── manage.py                 # Django 管理命令入口
├── requirements.txt          # Python 依赖
├── pytest.ini                # pytest 配置
├── .env.example              # 环境变量模板
└── .env                      # 本地环境变量（不提交）
```

---

## 三、功能模块说明

### 后端业务应用（`apps/`）

| 应用 | 职责 |
| --- | --- |
| **accounts** | 自定义用户模型 `UserAccount`，支持教师 / 学生 / 家长 / 管理员多角色；手机号 + 短信验证码登录；JWT 鉴权。 |
| **institutions** | 多租户机构体系：`Institution` / `Class` / `InstitutionMember`，班级邀请码、教师学生关联、入班审批。 |
| **knowledge** | 结构化知识树 `KnowledgePoint`，按 学科 × 学段 × 年级 × 学期 × 章节 多维分类。 |
| **missions** | 学习任务 `LearningMission`，含多难度关卡 `MissionLevel`（练习 / 复习 / 重做 / 变式 / 检测），题目编排与排序。 |
| **papers** | 试卷上传与解析编排：`ExamPaper` / `ParseTask`，Word→PDF 转换、解析状态跟踪、自动编号（如 M90001）。 |
| **parser** ★ | **核心 AI 解析引擎**。11 步流水线：Word→PDF→低清出图→AI 定位→高清出图→AI 结构化解析→后处理→裁切→入库；跨页题目合并、LaTeX 校验、失败重试。 |
| **review** | 教师审校：题目质检工作流（待审→通过/驳回）、AI 6 步生成答案、bbox 重新裁图、批量处理。 |
| **study** | 学生学习：任务 / 关卡进度、作答提交与判别、教师收藏、AI 辅导会话（B/C 苏格拉底式辅导模式）。 |
| **wrongbook** | 错题本：自动归集错题、变式题推荐、`MasteryRecord` 掌握度（间隔复习）、PDF 导出。 |

### 后端 API 路由（`/api/v1/`）

```text
/api/v1/auth/            认证（登录、刷新、短信验证码）
/api/v1/profile/me       当前用户资料
/api/v1/institutions/    机构、班级、成员
/api/v1/papers/          试卷管理
/api/v1/questions/       题库与检索
/api/v1/missions/        学习任务
/api/v1/student/         学生专属接口
/api/v1/dicts/           字典 / 参考数据
/api/v1/teacher/         教师专属接口
```

### 前端页面（`uniapp/src/pages/`，35+ 页面，按角色分组）

- **登录**：`login/` 统一登录 + 角色选择。
- **学生端（12 页）**：今日任务、加入班级、任务闯关、拍照作答、AI 辅导、错题本、变式练习、成长曲线、知识图谱、PDF 导出 等。
- **教师端（16 页）**：工作台、试卷导入、题库（知识树）、收藏、OCR 审校、审校列表、题目编辑、新建题目、拍照建题、任务创建、任务详情、关卡预览、我的班级、班级创建/编辑/详情、入班审批 等。
- **管理端（5 页）**：管理首页、机构管理、机构创建/编辑/详情。

---

## 四、环境准备

### 1. 依赖服务

- **Python 3.10+**
- **Node.js 18+** 与 **pnpm / npm**
- **PostgreSQL**（数据库名默认 `qisi_ai_tutor`）
- **Redis**（Celery Broker + 缓存）

### 2. 必需的外部服务密钥

- 通义千问（Qwen）API Key —— AI 解析与辅导的核心依赖
- 腾讯云 SMS —— 短信验证码登录
- 阿里云 OSS（可选）—— 对象存储

---

## 五、本地启动

### 5.1 配置环境变量

复制模板并填写真实值：

```bash
cp .env.example .env
```

按需修改 `.env` 中的数据库、Redis、`QWEN_API_KEY`、腾讯云 SMS 等配置（字段说明见 `.env.example`）。

### 5.2 启动依赖服务

确保 PostgreSQL 和 Redis 已运行：

```bash
# PostgreSQL（Docker 容器）
docker start qisi-postgres

# Redis（本地）
redis-server --port 6379 --requirepass "Redis_2026_StrongPwd"
```

### 5.3 启动后端（Django）

```bash
# 1. 创建并激活虚拟环境
python -m venv venv
source venv/Scripts/activate     # Windows (Git Bash)
# venv\Scripts\activate          # Windows (CMD)

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据库（PostgreSQL 中需先建好库与用户，见 .env）
python manage.py migrate

# 4. （可选）创建超级用户
python manage.py createsuperuser

# 5. 启动开发服务器（默认 http://127.0.0.1:8000）
python manage.py runserver
```

### 5.4 启动 Celery Worker（AI 解析等异步任务需要）

新开一个终端，激活同一虚拟环境后：

```bash
celery -A config worker -l info
```

> 试卷 AI 解析走异步流水线，不启动 Celery 将导致解析任务卡住。

### 5.5 启动前端（uni-app H5）

```bash
cd uniapp

# 1. 安装依赖
npm install

# 2. 启动 H5 开发服务器（默认 http://localhost:5273）
npm run dev:h5
```

#### 切换 API 后端地址

前端通过 Vite 代理转发 API 请求，默认指向本地后端。可通过以下方式切换：

**方式一：使用默认模式（访问本地后端）**

```bash
npm run dev:h5
```

自动加载 `uniapp/.env.development`，代理到 `http://localhost:8001`。

**方式二：使用生产模式（访问远程服务器）**

```bash
npm run dev:h5 -- --mode production
```

自动加载 `uniapp/.env.production`，代理到 `https://qisi.chengxuelu.com/study`。

**方式三：临时覆盖（自定义地址）**

```bash
# Windows (CMD)
set VITE_API_TARGET=https://your-domain.com/study && npm run dev:h5

# Windows (Git Bash / PowerShell)
VITE_API_TARGET=https://your-domain.com/study npm run dev:h5
```

**方式四：直接修改配置文件**

编辑 `uniapp/.env.development`（本地）或 `uniapp/.env.production`（生产）中的 `VITE_API_TARGET` 值：

```env
# 本地后端
VITE_API_TARGET=http://localhost:8001

# 远程服务器
VITE_API_TARGET=https://qisi.chengxuelu.com/study
```

> 前端默认端口为 5273，后端默认端口为 8001，可在 `uniapp/vite.config.ts` 的 `server.port` 中修改。

---

## 六、运行测试

测试基于 pytest，配置见 `pytest.ini`（`DJANGO_SETTINGS_MODULE=config.settings`）。

```bash
# 运行全部测试（含覆盖率）
pytest

# 仅跑快速 / 单元测试，跳过慢测试
pytest -m "not slow"

# 运行端到端测试（需先安装 Playwright 浏览器：playwright install）
pytest -m e2e
```

测试结果会输出到根目录 `test-report.json`。可用的 marker：`slow`、`integration`、`e2e`。

---

## 七、部署

### 7.1 后端生产部署

推荐使用 **gunicorn + Celery + systemd / supervisor** 的组合，前置 Nginx。

1. **生产环境变量**：将 `.env` 中
   - `DJANGO_DEBUG=False`
   - 替换 `DJANGO_SECRET_KEY` 与 `JWT_SECRET_KEY` 为强随机值
   - `ALLOWED_HOSTS` 设置为真实域名
   - `CORS_ALLOWED_ORIGINS` 设置为前端真实地址

2. **收集静态文件**：

   ```bash
   python manage.py collectstatic --noinput
   ```

3. **使用 gunicorn 启动**：

   ```bash
   gunicorn config.wsgi:application --workers 4 --bind 0.0.0.0:8000
   ```

4. **后台异步任务**（必备）：

   ```bash
   celery -A config worker -l info
   ```

5. **Nginx** 反向代理至 gunicorn（8000），并托管 `media/`、`static/` 目录。

### 7.2 前端生产部署

```bash
cd uniapp
npm run build:h5      # 产物输出到 uniapp/dist/build/h5
```

将 `dist/build/h5` 部署至任意静态服务器 / CDN，或交由 Nginx 托管。注意把前端的 API 基地址指向生产后端域名。

### 7.3 打包 App（可选）

```bash
cd uniapp
npm run dev:app       # 开发
npm run build:app     # 构建 App 产物，使用 HBuilderX 进一步打包
```

---

## 八、相关文档

- 系统架构与解析流水线：[docs/architecture/](docs/architecture/)
- 学生端需求（分 4 期）：[docs/student-requirements-v1.md](docs/student-requirements-v1.md)
- 功能设计与规划：[docs/superpowers/](docs/superpowers/)
