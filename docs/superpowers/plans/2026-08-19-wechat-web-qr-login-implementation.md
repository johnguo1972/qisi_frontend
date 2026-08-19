# 微信网页扫码登录 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 H5 登录页提供微信网页扫码登录，基于用户明确的手机号授权完成与短信登录一致的账户、角色与 JWT 会话处理。

**Architecture:** 微信开放平台 OAuth 回调仅由 Django 服务端处理。服务端以 Redis 保存单次 `state` 和短期登录票据，以独立的 `WechatWebIdentity` 保存网页 OpenID/UnionID 到系统账户的映射；手机号验证码与微信授权手机号均进入统一的“按手机号完成登录”服务，后者不调用短信服务。

**Tech Stack:** Django 5.2、Django REST Framework、PostgreSQL、RedisCache、httpx、UniApp Vue 3、SimpleJWT、pytest/pytest-django。

**Spec:** `docs/superpowers/specs/2026-08-19-wechat-web-qr-login-design.md`

## Global Constraints

- 只修改 `./front` 内文件。
- H5 展示网页扫码登录；MP-WEIXIN 保持现有一键登录流程。
- AppSecret 只通过环境变量读取；不得写入源码、测试夹具、日志或 Git。
- 微信扫码必须要求 `phone_authorization_confirmed=true`，且不得调用短信发送或短信校验。
- 扫码和短信登录都必须校验用户在登录页选择的 `requested_role`，不得自动授予角色。
- `state` 和登录票据均为随机、单次消费、5 分钟有效；JWT 不得写入回调 URL。
- 生产验收必须包含真实微信测试号扫码及 HTTPS 回调，模拟测试不替代该项验收。

---

## 文件结构

| 路径 | 责任 |
| --- | --- |
| `apps/accounts/models.py` | `WechatWebIdentity` 持久化身份模型。 |
| `apps/accounts/migrations/0004_wechatwebidentity.py` | 建表与唯一约束。 |
| `apps/accounts/wechat_web.py` | State、票据、微信网页 OAuth 交换与手机号解析的边界服务。 |
| `apps/accounts/services.py` | 统一的可信手机号登录完成服务。 |
| `apps/accounts/serializers.py` | 扫码会话、票据消费请求验证。 |
| `apps/accounts/views.py` | 创建会话、回调、消费票据端点。 |
| `apps/accounts/urls.py` | 网页扫码认证路由。 |
| `apps/accounts/tests/test_wechat_web_login.py` | 后端状态、身份关联、角色与无短信回归测试。 |
| `config/settings.py`、`.env.example` | 无密钥的网页微信配置读取与示例。 |
| `uniapp/src/api/wechat-web.ts` | H5 扫码会话和票据消费 API 客户端。 |
| `uniapp/src/api/index.ts` | 导出网页扫码 API。 |
| `uniapp/src/pages/login/index.vue` | H5 登录方式切换、授权确认、二维码/回调票据处理。 |
| `tests/test_wechat_web_login_ui_contract.py` | H5 登录页及 API 契约静态回归。 |

## Task 1: 网页微信身份模型与迁移

**Files:**
- Modify: `apps/accounts/models.py`
- Create: `apps/accounts/migrations/0004_wechatwebidentity.py`
- Modify: `apps/accounts/tests/test_roles.py`

**Interfaces:**
- Produces: `WechatWebIdentity(user, appid, openid, unionid, last_login_at)`。
- Consumes: `UserAccount`、`uuid_utils.compat.uuid7`。

- [ ] **Step 1: 写失败的模型约束测试**

```python
def test_web_openid_is_unique_per_appid(user):
    WechatWebIdentity.objects.create(user=user, appid='web-app', openid='openid-1')
    with pytest.raises(IntegrityError):
        WechatWebIdentity.objects.create(user=other_user, appid='web-app', openid='openid-1')
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest apps/accounts/tests/test_roles.py -k web_openid -q`

Expected: FAIL，`WechatWebIdentity` 尚不存在。

- [ ] **Step 3: 实现模型和迁移**

```python
class WechatWebIdentity(models.Model):
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name='wechat_web_identities')
    appid = models.CharField(max_length=64)
    openid = models.CharField(max_length=128)
    unionid = models.CharField(max_length=128, blank=True, default='')
    last_login_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['appid', 'openid'], name='uq_wechat_web_appid_openid')]
```

创建迁移，不迁移或修改既有 `WechatIdentity` 数据。

- [ ] **Step 4: 运行模型和迁移测试**

Run: `python manage.py makemigrations --check; python -m pytest apps/accounts/tests/test_roles.py -k web_openid -q`

Expected: 迁移无缺失，测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add apps/accounts/models.py apps/accounts/migrations/0004_wechatwebidentity.py apps/accounts/tests/test_roles.py
git commit -m "feat(auth): add web wechat identity model"
```

## Task 2: 网页 OAuth 状态、票据与微信客户端边界

**Files:**
- Create: `apps/accounts/wechat_web.py`
- Modify: `config/settings.py`
- Modify: `.env.example`
- Test: `apps/accounts/tests/test_wechat_web_login.py`

**Interfaces:**
- Produces: `create_web_login_state(requested_role) -> WebLoginState`、`consume_web_callback(code, state) -> WebAuthorization`、`issue_login_ticket(authorization) -> str`、`consume_login_ticket(ticket) -> WebAuthorization`。
- Consumes: Redis cache、`WECHAT_WEB_APP_ID`、`WECHAT_WEB_APP_SECRET`、`WECHAT_WEB_REDIRECT_URI`。

- [ ] **Step 1: 写状态和票据失败测试**

```python
def test_state_and_ticket_are_single_use(settings):
    state = create_web_login_state(requested_role='teacher')
    assert consume_web_login_state(state.value).requested_role == 'teacher'
    with pytest.raises(WebLoginStateError, match='state_invalid_or_expired'):
        consume_web_login_state(state.value)
```

同时写入 `phone_authorization_confirmed=False` 被拒绝、5 分钟 TTL、回调不记录 `code` 和 token 的测试。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest apps/accounts/tests/test_wechat_web_login.py -k 'state or ticket or confirmation' -q`

Expected: FAIL，模块和接口不存在。

- [ ] **Step 3: 实现最小 OAuth 边界**

```python
def create_web_login_state(*, requested_role: str, redirect_path: str) -> WebLoginState:
    value = secrets.token_urlsafe(32)
    cache.set(f'wechat_web:state:{value}', {'role': requested_role, 'redirect_path': redirect_path}, timeout=300)
    return WebLoginState(value=value, expires_in=300)

def consume_web_login_state(value: str) -> dict:
    payload = cache.get(f'wechat_web:state:{value}')
    cache.delete(f'wechat_web:state:{value}')
    if not payload:
        raise WebLoginStateError('state_invalid_or_expired')
    return payload
```

OAuth 交换采用可注入的 `httpx.Client`；只接受微信服务端返回的手机号及手机号授权成功标识，不读取浏览器提交的手机号。

- [ ] **Step 4: 增加配置并跑通过测试**

在 `settings.py` 读取三个网页微信环境变量；`.env.example` 只加入空值键名。缺失配置返回 `wechat_web_not_configured`，不产生模拟手机号。

Run: `python -m pytest apps/accounts/tests/test_wechat_web_login.py -k 'state or ticket or confirmation or configuration' -q`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add apps/accounts/wechat_web.py apps/accounts/tests/test_wechat_web_login.py config/settings.py .env.example
git commit -m "feat(auth): add secure web wechat oauth boundary"
```

## Task 3: 统一可信手机号登录与网页扫码 API

**Files:**
- Modify: `apps/accounts/services.py`
- Modify: `apps/accounts/serializers.py`
- Modify: `apps/accounts/views.py`
- Modify: `apps/accounts/urls.py`
- Test: `apps/accounts/tests/test_wechat_web_login.py`

**Interfaces:**
- Produces: `complete_trusted_mobile_login(mobile: str, requested_role: str) -> dict`，及 `POST /auth/wechat-web/session`、`GET /auth/wechat-web/callback`、`POST /auth/wechat-web/complete`。
- Consumes: Task 1 的 `WechatWebIdentity`、Task 2 的 `WebAuthorization` 与既有 `generate_tokens`、`serialize_user_session`。

- [ ] **Step 1: 写统一登录失败测试**

```python
def test_web_login_uses_authorized_phone_without_sms(client, mock_wechat):
    session = client.post('/api/v1/auth/wechat-web/session', {
        'requested_role': 'teacher', 'phone_authorization_confirmed': True,
    })
    callback = client.get('/api/v1/auth/wechat-web/callback', {'code': 'one-time-code', 'state': session.data['data']['state']})
    response = client.post('/api/v1/auth/wechat-web/complete', {'ticket': callback_ticket(callback)})
    assert response.data['data']['user']['active_role'] == 'teacher'
    sms_send.assert_not_called()
    sms_verify.assert_not_called()
```

补充：缺失确认、未授予角色、已绑定身份与不同手机号冲突、票据重放、UnionID 多账户歧义、学生/家长首次创建与教师/管理员首次拒绝。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest apps/accounts/tests/test_wechat_web_login.py -k 'web_login or callback or role or sms' -q`

Expected: FAIL，路由和统一完成服务不存在。

- [ ] **Step 3: 抽取统一完成服务并改造短信登录复用它**

```python
def complete_trusted_mobile_login(*, mobile: str, requested_role: str) -> dict:
    user = resolve_or_create_user_for_requested_role(mobile, requested_role)
    tokens = generate_tokens(user, requested_role)
    return {**tokens, 'user': serialize_user_session(user, requested_role)}
```

短信 `login` 在验证码成功后调用该函数；网页扫码回调在取得微信可信手机号后调用同一函数。保持所有现有响应字段与错误码兼容。

- [ ] **Step 4: 实现三条端点与关联规则**

`session` 只创建 state 和二维码地址；`callback` 只处理微信 code/state 并重定向 H5；`complete` 才返回 JWT。微信身份与手机号冲突、未授权角色和无手机号均失败关闭。

- [ ] **Step 5: 运行账户认证回归**

Run: `python -m pytest apps/accounts/tests/test_role_auth.py apps/accounts/tests/test_roles.py apps/accounts/tests/test_wechat_web_login.py -q`

Expected: PASS，且扫码相关测试断言没有调用任何 SMS 方法。

- [ ] **Step 6: 提交**

```bash
git add apps/accounts/services.py apps/accounts/serializers.py apps/accounts/views.py apps/accounts/urls.py apps/accounts/tests/test_wechat_web_login.py
git commit -m "feat(auth): add web wechat qr login endpoints"
```

## Task 4: H5 登录页扫码入口与票据消费

**Files:**
- Create: `uniapp/src/api/wechat-web.ts`
- Modify: `uniapp/src/api/index.ts`
- Modify: `uniapp/src/pages/login/index.vue`
- Create: `tests/test_wechat_web_login_ui_contract.py`

**Interfaces:**
- Consumes: `createSession({ requested_role, phone_authorization_confirmed })` 与 `complete({ ticket })`。
- Produces: H5 登录页面的两种方式切换、二维码展示、回跳票据消费及与短信登录一致的 `persistSession`/`routeForRole` 调用。

- [ ] **Step 1: 写 H5 UI 契约失败测试**

```python
def test_h5_login_requires_phone_authorization_confirmation():
    source = Path('uniapp/src/pages/login/index.vue').read_text(encoding='utf-8')
    assert 'phone_authorization_confirmed' in source
    assert '微信扫码登录' in source
    assert '#ifdef H5' in source
```

测试还必须断言：`requested_role` 使用 `activeTab`、扫码完成调用 `persistSession`、MP-WEIXIN 一键登录分支仍保留。

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest tests/test_wechat_web_login_ui_contract.py -q`

Expected: FAIL，网页扫码 API 和 H5 控件不存在。

- [ ] **Step 3: 实现 API 客户端**

```ts
export const wechatWebApi = {
  createSession: (payload: { requested_role: string; phone_authorization_confirmed: true }) => post('/auth/wechat-web/session', payload),
  complete: (ticket: string) => post('/auth/wechat-web/complete', { ticket }),
}
```

前端不接收、不保存或不发送手机号授权凭证和 AppSecret。

- [ ] **Step 4: 实现 H5 页面交互**

使用 `#ifdef H5` 包裹扫码方式切换、授权确认复选框、二维码 iframe/图片容器、加载/过期/取消提示。回调回到登录页时只读取短期票据，调用 `complete` 后复用现有 `persistSession`、`setUserInfo` 和 `routeForRole`。

- [ ] **Step 5: 运行静态契约和 H5 构建**

Run: `python -m pytest tests/test_wechat_web_login_ui_contract.py -q; npm run build:h5`

Expected: 测试 PASS，H5 构建 exit 0。

- [ ] **Step 6: 提交**

```bash
git add uniapp/src/api/wechat-web.ts uniapp/src/api/index.ts uniapp/src/pages/login/index.vue tests/test_wechat_web_login_ui_contract.py
git commit -m "feat(login): add h5 wechat qr login option"
```

## Task 5: 集成验证、迁移与生产发布清单

**Files:**
- Modify: `docs/superpowers/specs/2026-08-19-wechat-web-qr-login-design.md`
- Test: `apps/accounts/tests/test_wechat_web_login.py`

**Interfaces:**
- Consumes: Tasks 1–4。
- Produces: 可执行的本地与生产验收记录，不将生产密钥写入仓库。

- [ ] **Step 1: 写端到端后端失败场景测试**

```python
def test_callback_ticket_cannot_be_replayed_and_never_exposes_jwt_in_redirect(client, mock_wechat):
    redirect = run_web_callback(client, mock_wechat)
    assert 'access_token' not in redirect['Location']
    ticket = extract_ticket(redirect['Location'])
    assert client.post('/api/v1/auth/wechat-web/complete', {'ticket': ticket}).status_code == 200
    assert client.post('/api/v1/auth/wechat-web/complete', {'ticket': ticket}).status_code == 400
```

- [ ] **Step 2: 运行失败测试**

Run: `python -m pytest apps/accounts/tests/test_wechat_web_login.py -k replay -q`

Expected: FAIL，直到票据消费语义完整实现。

- [ ] **Step 3: 补齐最小实现并运行完整认证回归**

Run: `python manage.py check; python -m pytest apps/accounts/tests/test_role_auth.py apps/accounts/tests/test_roles.py apps/accounts/tests/test_wechat_web_login.py tests/test_wechat_web_login_ui_contract.py -q; npm run build:h5`

Expected: 所有命令 exit 0。

- [ ] **Step 4: 执行本地迁移核验**

Run: `python manage.py makemigrations --check; python manage.py migrate --plan`

Expected: 无未生成迁移；计划只包含新的网页微信身份迁移或已应用状态。

- [ ] **Step 5: 更新设计文档的验收记录并提交**

在设计文档追加已执行的自动化验证命令、结果与未执行的真实微信测试号验收项。

```bash
git add docs/superpowers/specs/2026-08-19-wechat-web-qr-login-design.md apps/accounts/tests/test_wechat_web_login.py
git commit -m "test(auth): verify web wechat qr login flow"
```

- [ ] **Step 6: 生产发布顺序**

1. 在微信开放平台配置生产 HTTPS 回调域名与手机号授权能力。
2. 在生产 `.env` 写入三个网页微信变量；只核验键存在，不输出值。
3. 备份生产 PostgreSQL；发布代码；执行 `python manage.py migrate --noinput`。
4. 重启 Gunicorn；发布 H5 静态资源；使用测试微信号扫码。
5. 验收已绑定多角色账号的四种登录角色，并确认服务端日志不含 code、token、手机号授权凭证或 AppSecret。

## 计划自检

- 规格覆盖：登录方式、授权确认、可信手机号、无短信、角色选择与切换、独立身份表、单次 state/票据、配置、安全、H5 与真实生产验收均已映射到 Tasks 1–5。
- 占位符扫描：已排查未完成占位标记。
- 接口一致性：网页扫码三端点、`complete_trusted_mobile_login`、`WechatWebIdentity` 与 H5 `wechatWebApi` 名称在任务间一致。
