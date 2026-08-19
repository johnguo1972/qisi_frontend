# 微信网页扫码与小程序可信绑定 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不使用短信回退的前提下，让 H5 网页扫码登录通过小程序可信手机号授权完成首次绑定，已绑定用户可直接扫码登录。

**Architecture:** 网页 OAuth 只验证 OpenID/UnionID；state、网页登录票据和绑定完成票据均绑定发起浏览器会话，300 秒过期且一次性消费。小程序从已认证的服务端身份取得可信手机号，关联网页身份后向原浏览器签发绑定完成票据；令牌由统一登录服务签发。

**Spec:** `docs/superpowers/specs/2026-08-19-wechat-web-qr-login-design.md`

## 全局约束

- 仅修改 `./front`；不修改或提交 `.env`、密钥和授权凭据。
- 保留手机验证码与 `MP-WEIXIN` 现有登录路径。
- 网页 OAuth 不得假定返回手机号；浏览器提交的手机号永不作为可信身份。
- OAuth code、token、手机号授权凭据与 AppSecret 不得写入日志、URL 或响应。
- 缓存异常、会话不匹配、票据过期/重放、身份冲突必须失败关闭；不得降级短信。

## Task 1: 修复网页 OAuth 状态边界

**Files:** `apps/accounts/wechat_web.py`、`apps/accounts/tests/test_wechat_web_login.py`

**Produces:** `create_web_login_state(requested_role, browser_session_id)`、`consume_web_login_state(state, browser_session_id)`、只返回 OpenID/UnionID 的 `exchange_web_identity(code)`。

- [ ] 写失败测试：不同浏览器消费 state 被拒绝；标准 OAuth 仅返回 OpenID/UnionID 时可生成网页身份；缓存 get/set/delete 异常受控失败；日志不包含 code/token。
- [ ] 运行 `python -m pytest apps/accounts/tests/test_wechat_web_login.py -k 'browser or standard_oauth or cache or log' -q`，确认 RED。
- [ ] 最小实现：state 缓存内容含 `browser_session_id`，消费时先删除后比较会话；网页身份交换不解析手机号字段；缓存异常抛受控认证错误。
- [ ] 重跑同一命令确认 GREEN，并提交：`git commit -m "fix(auth): secure web wechat oauth state"`。

## Task 2: 小程序可信绑定票据与统一登录

**Files:** `apps/accounts/wechat_web.py`、`apps/accounts/services.py`、`apps/accounts/serializers.py`、`apps/accounts/views.py`、`apps/accounts/urls.py`、`apps/accounts/tests/test_wechat_web_login.py`

**Produces:** `bind_web_identity_from_miniprogram(web_session_id, authenticated_user)` 和 `complete_web_binding(ticket, browser_session_id, requested_role)`；路由 `binding-session`、`binding-status`、`binding-complete`。

- [ ] 写失败测试：小程序绑定端点忽略/拒绝 posted `mobile`；绑定票据不能跨浏览器消费或重放；student/parent 首次创建可用，teacher/admin 首次创建拒绝；角色、微信身份、手机号冲突失败；SMS 方法未调用。
- [ ] 运行 `python -m pytest apps/accounts/tests/test_wechat_web_login.py -k 'binding or replay or trusted_mobile or sms' -q`，确认 RED。
- [ ] 最小实现：仅从已认证小程序服务端用户读取受信手机号；关联 `WechatWebIdentity`，创建绑定浏览器的一次性票据；完成端点复用统一可信登录服务，保持既有 JWT/用户/角色响应信封。
- [ ] 运行 `python -m pytest apps/accounts/tests/test_role_auth.py apps/accounts/tests/test_roles.py apps/accounts/tests/test_wechat_web_login.py -q`，确认 GREEN，并提交：`git commit -m "feat(auth): add miniprogram web login binding"`。

## Task 3: H5 扫码与小程序绑定引导

**Files:** `uniapp/src/api/wechat-web.ts`、`uniapp/src/api/index.ts`、`uniapp/src/pages/login/index.vue`、`tests/test_wechat_web_login_ui_contract.py`

**Produces:** `createSession`、`bindingStatus`、`complete` API；H5 二维码、未绑定的小程序授权引导、已绑定完成登录。

- [ ] 写失败 UI 契约测试：包含“微信扫码登录”和“请在微信小程序完成手机号授权”；同时保留 `#ifdef H5`、`#ifdef MP-WEIXIN`、`persistSession` 和 `routeForRole`。
- [ ] 运行 `python -m pytest tests/test_wechat_web_login_ui_contract.py -q`，确认 RED。
- [ ] 最小实现：H5 仅创建会话、展示授权地址、轮询状态、消费短期票据；不采集手机号。绑定未完成时显示小程序授权引导；成功后复用现有会话持久化和角色跳转。
- [ ] 运行 `python -m pytest tests/test_wechat_web_login_ui_contract.py -q; npm run build:h5`，确认 GREEN，并提交：`git commit -m "feat(login): guide h5 wechat qr binding"`。

## Task 4: 全链路验证与验收记录

**Files:** `apps/accounts/tests/test_wechat_web_login.py`、`docs/superpowers/specs/2026-08-19-wechat-web-qr-login-design.md`

- [ ] 写失败测试：回调/绑定重定向不含 JWT、code 或敏感参数；所有票据重放均失败。
- [ ] 运行 `python manage.py check; python manage.py makemigrations --check; python -m pytest apps/accounts/tests/test_role_auth.py apps/accounts/tests/test_roles.py apps/accounts/tests/test_wechat_web_login.py tests/test_wechat_web_login_ui_contract.py -q; npm run build:h5`。
- [ ] 在设计文档记录每条命令的实际结果；若 DB、依赖或微信平台阻塞，记录精确原因而不宣称通过。
- [ ] 记录生产验证：配置 HTTPS 回调域名、测试账号网页扫码、同一浏览器中完成小程序手机号授权并登录。提交：`git commit -m "test(auth): verify web binding login flow"`。

## 自检

四项任务覆盖浏览器会话防 CSRF、标准 OAuth 身份、小程序可信手机号、票据防重放、无短信、角色安全、H5 引导和真实生产验证；不再包含网页 OAuth 直接取手机号的非标准假设。
