# 微信小程序单二维码设备登录 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 H5 微信登录改造成无 iframe、无网页 OAuth 中间跳转的单个小程序码设备登录，并实现首次手机号授权、后续扫码直接登录。

**Architecture:** H5 创建绑定原浏览器 session 的 Redis 设备会话，后端把不含敏感信息的一次性桥接码生成微信小程序码。小程序扫码后用 `wx.login` 确认 `appid + openid`；已有 `WechatIdentity` 直接完成登录，首次身份通过原生 `getPhoneNumber` 建立绑定，再由 H5 轮询并消费一次性票据。

**Tech Stack:** Django 5.2、Django REST Framework、Redis/Django cache、PostgreSQL、pytest、Vue 3、UniApp、微信 `jscode2session`、微信 `getuserphonenumber`、微信无限小程序码。

**Spec:** `docs/superpowers/specs/2026-08-22-wechat-miniprogram-device-login-design.md`

## Global Constraints

- 仅修改 `./front` 内文件，不修改其他目录。
- H5 扫码入口不得使用 `iframe`、`window.location.assign` 或微信开放平台 `qrconnect` 中间页。
- 二维码只携带不超过 32 字符的随机桥接码，不携带手机号、用户 ID、角色、OpenID 或 JWT。
- 网页会话、桥接码、手机号绑定 token 和完成票据总有效期固定为 300 秒，派生凭据不得延长原绝对期限。
- `wx.login` code、桥接码、手机号 code 和完成票据只能消费一次。
- 首次手机号必须来自微信 `getPhoneNumber` 服务端交换；不得接受浏览器或小程序直接提交的手机号。
- 复用 `WechatIdentity`、统一可信手机号登录和多角色规则，不新增重复身份表，不自动授予管理员或教师角色。
- 旧 `/auth/wechat-web/*` 接口保留一个发布周期作为回滚通道，新 H5 入口不得继续调用它们。
- 日志不得记录手机号、完整 OpenID、微信临时 code、access token、JWT、AppSecret。

---

### Task 1: 设备登录 Redis 状态机

**Files:**
- Create: `apps/accounts/wechat_device.py`
- Create: `apps/accounts/tests/test_wechat_device.py`

**Interfaces:**
- Produces: `DeviceLoginError(code: str)`。
- Produces: `DeviceLoginSession(value: str, expires_in: int)`。
- Produces: `DeviceScanResult(status: str, phone_binding_token: str | None)`。
- Produces: `create_device_login_session(requested_role: str, browser_session_id: str) -> DeviceLoginSession`。
- Produces: `get_or_create_device_bridge(web_session_id: str, browser_session_id: str) -> str`。
- Produces: `confirm_device_identity(bridge_code: str, identity: MiniProgramIdentity) -> DeviceScanResult`。
- Produces: `bind_device_identity_phone(phone_binding_token: str, mobile: str) -> None`。
- Produces: `get_device_login_status(web_session_id: str, browser_session_id: str) -> DeviceLoginStatus`。
- Produces: `complete_device_login(ticket: str, browser_session_id: str, requested_role: str) -> tuple[UserAccount, dict]`。

- [ ] **Step 1: 写入会话、桥接码和浏览器绑定的失败测试**

```python
def test_device_session_and_bridge_are_browser_bound_and_expire_together(monkeypatch):
    # ClockedCache is defined in this test file with set/get/delete/advance;
    # set stores the absolute test deadline and advance moves its fake clock.
    clock = ClockedCache()
    monkeypatch.setattr(wechat_device, "cache", clock)
    session = wechat_device.create_device_login_session("student", "browser-a")
    bridge = wechat_device.get_or_create_device_bridge(session.value, "browser-a")

    assert len(bridge) <= 32
    with pytest.raises(wechat_device.DeviceLoginError) as mismatch:
        wechat_device.get_or_create_device_bridge(session.value, "browser-b")
    assert mismatch.value.code == "DEVICE_BROWSER_MISMATCH"

    clock.advance(301)
    with pytest.raises(wechat_device.DeviceLoginError) as expired:
        wechat_device.get_device_login_status(session.value, "browser-a")
    assert expired.value.code == "DEVICE_SESSION_EXPIRED"
```

- [ ] **Step 2: 运行测试并确认因模块不存在而失败**

Run: `C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests/test_wechat_device.py -q`

Expected: FAIL，提示无法导入 `apps.accounts.wechat_device`。

- [ ] **Step 3: 实现最小会话与桥接状态**

```python
DEVICE_LOGIN_TTL_SECONDS = 300

@dataclass(frozen=True)
class DeviceLoginSession:
    value: str
    expires_in: int

class DeviceLoginError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

def create_device_login_session(requested_role, browser_session_id):
    if requested_role not in VALID_ROLES or not browser_session_id:
        raise DeviceLoginError("DEVICE_SESSION_INVALID")
    value = secrets.token_urlsafe(32)
    expires_at = timezone.now().timestamp() + DEVICE_LOGIN_TTL_SECONDS
    _cache_set(_session_key(value), {
        "requested_role": requested_role,
        "browser_session_id": browser_session_id,
        "status": "pending",
        "expires_at": expires_at,
    }, expires_at)
    return DeviceLoginSession(value=value, expires_in=DEVICE_LOGIN_TTL_SECONDS)
```

实现 `_cache_set`、`_load_session`、绝对过期时间检查、浏览器恒定时间比较和同一会话只生成一个桥接码。

- [ ] **Step 4: 增加扫码状态、手机号 token、完成票据的失败测试**

```python
@pytest.mark.django_db
def test_known_identity_marks_device_session_bound(admin_teacher):
    identity = WechatIdentity.objects.create(
        user=admin_teacher, appid="wx-test", openid="known-openid"
    )
    session = wechat_device.create_device_login_session("teacher", "browser-a")
    bridge = wechat_device.get_or_create_device_bridge(session.value, "browser-a")

    result = wechat_device.confirm_device_identity(
        bridge,
        wechat_device.MiniProgramIdentity(
            appid=identity.appid, openid=identity.openid, unionid=""
        ),
    )
    status = wechat_device.get_device_login_status(session.value, "browser-a")

    assert result.status == "login_confirmed"
    assert status.bound is True
    assert status.ticket

def test_unknown_identity_requires_phone_and_bridge_cannot_replay():
    session = wechat_device.create_device_login_session("student", "browser-a")
    bridge = wechat_device.get_or_create_device_bridge(session.value, "browser-a")
    result = wechat_device.confirm_device_identity(
        bridge,
        wechat_device.MiniProgramIdentity("wx-test", "new-openid", ""),
    )
    assert result.status == "phone_authorization_required"
    assert result.phone_binding_token
    with pytest.raises(wechat_device.DeviceLoginError) as replay:
        wechat_device.confirm_device_identity(
            bridge,
            wechat_device.MiniProgramIdentity("wx-test", "new-openid", ""),
        )
    assert replay.value.code == "DEVICE_BRIDGE_INVALID"
```

- [ ] **Step 5: 实现身份确认、首次绑定和票据消费**

实现要求：

```python
@dataclass(frozen=True)
class MiniProgramIdentity:
    appid: str
    openid: str
    unionid: str

@dataclass(frozen=True)
class DeviceLoginStatus:
    status: str
    bound: bool
    ticket: str | None = None
    error_code: str | None = None
```

- 已有 `WechatIdentity` 时调用统一角色校验，再创建绑定原浏览器的一次性 ticket；
- 未绑定身份时把 AppID/OpenID/UnionID 锁定在服务端 phone token 中；
- `bind_device_identity_phone` 使用 `login_with_trusted_mobile` 取得用户，事务内检查身份冲突并创建 `WechatIdentity`；
- `complete_device_login` 删除 ticket 后再签发 JWT，重复消费返回 `DEVICE_TICKET_INVALID`；
- 家长角色沿用统一可信手机号登录规则，管理员/教师不自动授予。

- [ ] **Step 6: 运行状态机测试**

Run: `C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests/test_wechat_device.py -q`

Expected: PASS，0 failures。

- [ ] **Step 7: 提交状态机**

```bash
git add apps/accounts/wechat_device.py apps/accounts/tests/test_wechat_device.py
git commit -m "feat(login): add wechat device login state machine"
```

---

### Task 2: 微信小程序服务端身份交换边界

**Files:**
- Modify: `apps/accounts/wechat_device.py`
- Modify: `apps/accounts/tests/test_wechat_device.py`

**Interfaces:**
- Produces: `exchange_miniprogram_login_code(login_code: str, http_client=None) -> MiniProgramIdentity`。
- Produces: `exchange_miniprogram_phone_code(phone_code: str, http_client=None) -> str`。
- Consumes: `MiniProgramIdentity`、`DeviceLoginError` from Task 1。

- [ ] **Step 1: 写微信成功、失败和敏感信息不落日志测试**

```python
def test_exchange_login_code_returns_server_verified_identity(settings):
    settings.WECHAT_MP_APPID = "wx-test"
    settings.WECHAT_MP_APPSECRET = "secret"
    client = FakeWechatClient(get_payload={
        "openid": "openid-1", "unionid": "unionid-1", "session_key": "hidden"
    })
    identity = wechat_device.exchange_miniprogram_login_code("one-time", client)
    assert identity == wechat_device.MiniProgramIdentity(
        appid="wx-test", openid="openid-1", unionid="unionid-1"
    )

def test_exchange_phone_code_rejects_wechat_error(settings):
    client = FakeWechatClient(
        get_payload={"access_token": "token"},
        post_payload={"errcode": 40029, "errmsg": "invalid code"},
    )
    with pytest.raises(wechat_device.DeviceLoginError) as error:
        wechat_device.exchange_miniprogram_phone_code("bad-code", client)
    assert error.value.code == "DEVICE_PHONE_AUTHORIZATION_FAILED"
```

- [ ] **Step 2: 运行新增测试并确认失败**

Run: `C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests/test_wechat_device.py -k "exchange" -q`

Expected: FAIL，提示交换函数不存在。

- [ ] **Step 3: 实现微信 API 交换函数**

```python
WECHAT_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
WECHAT_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
WECHAT_PHONE_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"
```

- 所有请求显式设置 10 秒超时；
- AppID/AppSecret 只从 Django settings 读取；
- 微信非 JSON、网络异常、缺少 OpenID/手机号统一转换为受控 `DeviceLoginError`；
- 不记录请求 code、token、手机号或完整 OpenID；
- `jscode2session` 与手机号 code 分别只调用一次。

- [ ] **Step 4: 运行微信边界和状态机测试**

Run: `C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests/test_wechat_device.py -q`

Expected: PASS，0 failures。

- [ ] **Step 5: 提交微信边界**

```bash
git add apps/accounts/wechat_device.py apps/accounts/tests/test_wechat_device.py
git commit -m "feat(login): verify wechat device credentials"
```

---

### Task 3: 设备登录 REST API

**Files:**
- Modify: `apps/accounts/serializers.py`
- Modify: `apps/accounts/views.py`
- Modify: `apps/accounts/urls.py`
- Modify: `apps/accounts/tests/test_wechat_device.py`
- Modify: `apps/qrcode/services.py`
- Modify: `apps/qrcode/tests.py`

**Interfaces:**
- Produces endpoints: `/auth/wechat-device/session`、`qrcode`、`scan`、`phone`、`status`、`complete`。
- Consumes all Task 1 and Task 2 service functions。

- [ ] **Step 1: 写完整 API happy-path 失败测试**

```python
@pytest.mark.django_db
def test_device_api_known_identity_completes_in_original_browser(
    api_client, student_user, monkeypatch, settings
):
    settings.WECHAT_MP_APPID = "wx-test"
    WechatIdentity.objects.create(
        user=student_user, appid="wx-test", openid="known-openid"
    )
    created = api_client.post(
        "/api/v1/auth/wechat-device/session", {"requested_role": "student"}
    )
    assert created.status_code == 200
    session_id = created.data["data"]["web_session_id"]

    captured_qr = {}
    monkeypatch.setattr(
        views,
        "wxacode_image",
        lambda **kwargs: (
            captured_qr.update(kwargs)
            or WechatCodeImage(content=b"jpeg", content_type="image/jpeg")
        ),
    )
    qrcode_response = api_client.get(
        "/api/v1/auth/wechat-device/qrcode",
        {"web_session_id": session_id},
    )
    assert qrcode_response.status_code == 200
    bridge = captured_qr["scene"]
    monkeypatch.setattr(
        views, "exchange_miniprogram_login_code",
        lambda code: MiniProgramIdentity("wx-test", "known-openid", ""),
    )
    scanned = api_client.post(
        "/api/v1/auth/wechat-device/scan",
        {"bridge_code": bridge, "login_code": "wx-code"},
    )
    status = api_client.get(
        "/api/v1/auth/wechat-device/status", {"web_session_id": session_id}
    )
    completed = api_client.post(
        "/api/v1/auth/wechat-device/complete",
        {"ticket": status.data["data"]["ticket"], "requested_role": "student"},
    )

    assert scanned.data["data"]["status"] == "login_confirmed"
    assert completed.status_code == 200
    assert completed.data["data"]["user"]["active_role"] == "student"
```

- [ ] **Step 2: 写首次手机号授权、跨浏览器和重放失败测试**

覆盖以下断言：

```python
assert phone_required.data["data"]["status"] == "phone_authorization_required"
assert "phone_binding_token" in phone_required.data["data"]
assert cross_browser_status.status_code == 400
assert cross_browser_status.data["code"] == "DEVICE_BROWSER_MISMATCH"
assert replay_phone.status_code == 400
assert replay_ticket.status_code == 400
assert not sms_sender.called
```

- [ ] **Step 3: 运行 API 测试并确认路由 404**

Run: `C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests/test_wechat_device.py -k "device_api" -q`

Expected: FAIL，设备登录接口返回 404。

- [ ] **Step 4: 添加 serializers、views 和 urls**

新增序列化器：

```python
class DeviceSessionSerializer(serializers.Serializer):
    requested_role = serializers.ChoiceField(choices=VALID_ROLES)

class DeviceScanSerializer(serializers.Serializer):
    bridge_code = serializers.CharField(max_length=32)
    login_code = serializers.CharField(max_length=256)

class DevicePhoneSerializer(serializers.Serializer):
    phone_binding_token = serializers.CharField(max_length=128)
    phone_code = serializers.CharField(max_length=256)

class DeviceCompleteSerializer(serializers.Serializer):
    ticket = serializers.CharField(max_length=128)
    requested_role = serializers.ChoiceField(choices=VALID_ROLES)
```

新增六个 `AllowAny` view；每个 view 只负责输入校验、调用 service、映射安全错误码和构造统一响应，不在 view 中复制状态机。

- [ ] **Step 5: 修正微信二维码响应的真实 MIME 类型**

在 `apps/qrcode/services.py` 增加并将原 `wxacode_png` 的调用者迁移到新函数：

```python
@dataclass(frozen=True)
class WechatCodeImage:
    content: bytes
    content_type: str

def wxacode_image(
    scene: str,
    page: str,
    width: int = 430,
    check_path: bool = False,
    env_version: str = "release",
) -> WechatCodeImage:
    token_payload = requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={
            "grant_type": "client_credential",
            "appid": settings.WECHAT_MP_APPID,
            "secret": settings.WECHAT_MP_APPSECRET,
        },
        timeout=8,
    ).json()
    access_token = token_payload.get("access_token")
    if not access_token:
        raise RuntimeError("获取微信 access_token 失败")
    response = requests.post(
        "https://api.weixin.qq.com/wxa/getwxacodeunlimit",
        params={"access_token": access_token},
        json={
            "scene": scene[:32],
            "page": page,
            "check_path": check_path,
            "env_version": env_version,
            "width": width,
        },
        timeout=15,
    )
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0]
    if content_type not in {"image/jpeg", "image/png"}:
        raise RuntimeError("生成微信小程序码失败")
    return WechatCodeImage(response.content, content_type)
```

让生成函数把微信响应的 `Content-Type` 与内容一起返回；设备二维码 view 使用真实 `image/jpeg` 或 `image/png`，不再把 JPEG 标记为 PNG。同步调整既有调用和测试。

- [ ] **Step 6: 运行账户与二维码回归测试**

Run: `C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests apps/qrcode/tests.py -q`

Expected: PASS，0 failures。

- [ ] **Step 7: 运行 Django 检查**

Run: `C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py check`

Expected: `System check identified no issues`。

- [ ] **Step 8: 提交 REST API**

```bash
git add apps/accounts/serializers.py apps/accounts/views.py apps/accounts/urls.py apps/accounts/tests/test_wechat_device.py apps/qrcode/services.py apps/qrcode/tests.py
git commit -m "feat(login): expose wechat device login api"
```

---

### Task 4: 小程序扫码确认与首次手机号授权页

**Files:**
- Modify: `uniapp/src/pages/auth/web-binding.vue`
- Create: `uniapp/src/api/wechat-device.ts`
- Create: `uniapp/tests/wechat-device-binding.test.ts`
- Create: `uniapp/vitest.config.ts`
- Modify: `uniapp/package.json`
- Modify: `uniapp/package-lock.json`

**Interfaces:**
- Consumes: `POST /auth/wechat-device/scan` and `POST /auth/wechat-device/phone`。
- Produces: `wechatDeviceApi.scan(bridgeCode, loginCode)`、`wechatDeviceApi.bindPhone(bindingToken, phoneCode)`。

- [ ] **Step 1: 建立可执行的 Vue 测试配置**

在 `package.json` 增加：

```json
{
  "scripts": {
    "test": "vitest run"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.0",
    "@vue/test-utils": "^2.4.6",
    "jsdom": "^24.1.3",
    "vitest": "^1.6.1"
  }
}
```

创建 `vitest.config.ts`：

```ts
import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    clearMocks: true,
  },
})
```

Run: `cd uniapp && npm install`

Expected: exit 0，`package-lock.json` 锁定上述测试依赖。

- [ ] **Step 2: 写小程序页面行为失败测试**

测试用例固定验证：

```ts
it('scans with wx.login and skips phone button for a known identity', async () => {
  mockWxLogin('login-code')
  mockScan({ status: 'login_confirmed' })
  await mountBindingPage({ scene: 'bridge-code' })
  expect(wechatDeviceApi.scan).toHaveBeenCalledWith('bridge-code', 'login-code')
  expect(wrapper.text()).toContain('授权成功，请返回网页端')
  expect(wrapper.find('[open-type="getPhoneNumber"]').exists()).toBe(false)
})

it('shows phone authorization only for an unknown identity', async () => {
  mockScan({
    status: 'phone_authorization_required',
    phone_binding_token: 'binding-token',
  })
  await mountBindingPage({ scene: 'bridge-code' })
  expect(wrapper.find('[open-type="getPhoneNumber"]').exists()).toBe(true)
})
```

- [ ] **Step 3: 运行前端测试并确认失败**

Run: `cd uniapp && npm test -- --run tests/wechat-device-binding.test.ts`

Expected: FAIL，页面尚未调用新的 `wechatDeviceApi.scan`。

- [ ] **Step 4: 实现小程序 API 客户端**

```ts
export const wechatDeviceApi = {
  scan: (bridgeCode: string, loginCode: string) =>
    post<DeviceScanData>('/auth/wechat-device/scan', {
      bridge_code: bridgeCode,
      login_code: loginCode,
    }),
  bindPhone: (bindingToken: string, phoneCode: string) =>
    post<DevicePhoneData>('/auth/wechat-device/phone', {
      phone_binding_token: bindingToken,
      phone_code: phoneCode,
    }),
}
```

- [ ] **Step 5: 重写绑定页状态流**

页面加载后：

1. 读取 `options.scene`；
2. 调用一次 `wx.login`；
3. 调用 `wechatDeviceApi.scan`；
4. `login_confirmed` 显示成功，不显示手机号按钮；
5. `phone_authorization_required` 保存服务端 token 并显示原生手机号按钮；
6. `getPhoneNumber` 只上传 `event.detail.code` 与服务端 token；
7. 拒绝授权、code 缺失、会话过期和网络失败显示可理解的具体文案，不记录敏感值。

- [ ] **Step 6: 运行页面测试和小程序生产构建**

Run: `cd uniapp && npm test -- --run tests/wechat-device-binding.test.ts`

Run: `cd uniapp && npm run build:mp-weixin`

Expected: 测试 PASS；构建 exit 0；产物包含 `pages/auth/web-binding.wxml` 和 `pages/auth/web-binding.js`。

- [ ] **Step 7: 提交小程序绑定页**

```bash
git add uniapp/src/pages/auth/web-binding.vue uniapp/src/api/wechat-device.ts uniapp/tests uniapp/package.json uniapp/package-lock.json
git commit -m "feat(login): confirm device login in miniprogram"
```

---

### Task 5: H5 登录页单二维码交互

**Files:**
- Modify: `uniapp/src/pages/login/index.vue`
- Modify: `uniapp/src/api/wechat-web.ts`
- Create: `uniapp/tests/wechat-device-login.test.ts`

**Interfaces:**
- Consumes: session、qrcode、status、complete endpoints from Task 3。
- Produces: H5 `phone` / `wechat` 两视图切换和自动轮询。

- [ ] **Step 1: 写入口样式与禁止跳转的失败测试**

```ts
it('renders a right-aligned text link below the phone login button', () => {
  const link = wrapper.get('[data-testid="wechat-device-link"]')
  expect(link.text()).toBe('微信扫码登录')
  expect(link.classes()).toContain('wechat-device-link')
  expect(wrapper.find('button.wechat-web-entry').exists()).toBe(false)
})

it('creates and displays an image QR without iframe or page navigation', async () => {
  await wrapper.get('[data-testid="wechat-device-link"]').trigger('click')
  expect(wechatDeviceApi.createSession).toHaveBeenCalledWith('student')
  expect(wrapper.get('img.wechat-device-qr').attributes('src')).toContain(
    '/auth/wechat-device/qrcode'
  )
  expect(wrapper.find('iframe').exists()).toBe(false)
  expect(window.location.assign).not.toHaveBeenCalled()
})
```

- [ ] **Step 2: 运行 H5 页面测试并确认失败**

Run: `cd uniapp && npm test -- --run tests/wechat-device-login.test.ts`

Expected: FAIL，旧按钮仍存在且旧流程调用 `window.location.assign`。

- [ ] **Step 3: 将网页 API 客户端切换为设备登录契约**

保留文件名以减少 import 改动，但导出改为：

```ts
export const wechatDeviceApi = {
  createSession: (requestedRole: string) =>
    post<DeviceSession>('/auth/wechat-device/session', {
      requested_role: requestedRole,
    }),
  status: (webSessionId: string) =>
    get<DeviceStatus>('/auth/wechat-device/status', {
      web_session_id: webSessionId,
    }, { silentError: true }),
  complete: (ticket: string, requestedRole: string) =>
    post<WechatWebLoginSession>('/auth/wechat-device/complete', {
      ticket,
      requested_role: requestedRole,
    }),
}
```

- [ ] **Step 4: 改造登录页模板和状态**

- 把按钮改为登录按钮下一行右对齐 `<text role="link">微信扫码登录</text>`；
- 点击链接立即创建会话并将二维码 URL 赋给 `<img class="wechat-device-qr">`；
- 删除死代码 `v-if="false"`、网页 OAuth URL、callback 恢复和 `window.location.assign`；
- 每 3 秒轮询一次，`bound + ticket` 时消费 ticket、持久化会话并按角色跳转；
- 倒计时到 0 停止轮询并显示“二维码已过期”；
- 角色切换、重新生成、返回手机号页和组件卸载必须清理定时器与旧图片状态；
- 二维码固定正方形、`object-fit: contain`、无滚动容器。

- [ ] **Step 5: 运行 H5 页面测试**

Run: `cd uniapp && npm test -- --run tests/wechat-device-login.test.ts`

Expected: PASS，0 failures。

- [ ] **Step 6: 运行 H5 生产构建**

Run: `cd uniapp && npm run build:h5`

Expected: exit 0；构建产物中登录页不存在 `qrconnect`、`WxLogin` 或登录 iframe。

- [ ] **Step 7: 提交 H5 页面**

```bash
git add uniapp/src/pages/login/index.vue uniapp/src/api/wechat-web.ts uniapp/tests uniapp/package.json uniapp/package-lock.json
git commit -m "feat(login): show single miniprogram login qr"
```

---

### Task 6: 全量回归、文档同步与发布前验证

**Files:**
- Modify: `docs/superpowers/specs/2026-08-19-wechat-web-qr-login-design.md`
- Modify: `docs/superpowers/specs/2026-08-22-wechat-miniprogram-device-login-design.md`
- Modify: `docs/ai_public_component_flow.md` only if it currently documents authentication entry points; otherwise leave unchanged。

**Interfaces:**
- Consumes all previous tasks。
- Produces a release candidate with verified backend, H5 and Mini Program artifacts。

- [ ] **Step 1: 标注旧设计由新设备登录设计取代**

在旧设计开头增加：

```markdown
> 状态：已由 `2026-08-22-wechat-miniprogram-device-login-design.md` 取代。
> 旧网页 OAuth 接口仅作为一个发布周期内的回滚通道。
```

- [ ] **Step 2: 运行账户、二维码及相关认证全量测试**

Run: `C:\Users\johng\miniconda3\envs\ai-tools\python.exe -m pytest apps/accounts/tests apps/qrcode/tests.py -q`

Expected: PASS，0 failures。

- [ ] **Step 3: 运行 Django 检查和迁移一致性检查**

Run: `C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py check`

Run: `C:\Users\johng\miniconda3\envs\ai-tools\python.exe manage.py makemigrations --check --dry-run`

Expected: 系统检查无异常；`No changes detected`。

- [ ] **Step 4: 运行前端测试及两个生产构建**

Run: `cd uniapp && npm test -- --run`

Run: `cd uniapp && npm run build:h5`

Run: `cd uniapp && npm run build:mp-weixin`

Expected: 测试全部 PASS；两个构建 exit 0。

- [ ] **Step 5: 检查构建产物与变更范围**

Run: `rg -n "iframe|qrconnect|window.location.assign" uniapp/dist/build/h5/assets/pages-login-index*.js`

Expected: 无微信登录 iframe、`qrconnect` 或授权页面跳转逻辑。

Run: `git diff --check`

Expected: 无空白符错误。

Run: `git status --short`

Expected: 仅包含本计划明确修改的 `front` 文件；既有用户未跟踪文件保持未修改、未加入提交。

- [ ] **Step 6: 提交文档与最终回归调整**

```bash
git add docs/superpowers/specs/2026-08-19-wechat-web-qr-login-design.md docs/superpowers/specs/2026-08-22-wechat-miniprogram-device-login-design.md
git commit -m "docs(login): supersede web oauth qr flow"
```

- [ ] **Step 7: 生产发布门禁**

发布顺序严格执行：后端接口 → 小程序体验版 → 两条真实链路验收 → 小程序正式版 → H5。体验版只允许体验成员使用，不得把体验版验证结果宣称为普通生产用户可用。

真实验收记录必须包含：

```text
首次身份：session 200 → qrcode 200 → scan phone_required → phone bound → status bound → complete 200
已有身份：session 200 → qrcode 200 → scan login_confirmed → status bound → complete 200
```

未取得上述服务器访问证据和手机端实际页面结果前，只能报告“代码/构建已完成”，不得报告“生产扫码登录已完成”。
