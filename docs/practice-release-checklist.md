# 精练题阶段五灰度发布清单

## 开启灰度

生产环境先保持：

```text
PRACTICE_FEATURE_ENABLED=0
```

确认迁移和服务健康后，仅为测试账号开启：

```text
PRACTICE_FEATURE_ENABLED=1
PRACTICE_BETA_MOBILES=手机号1,手机号2
PRACTICE_RELEASE_VERSION=phase5-rc1
```

手机号白名单匹配登录账号的 `mobile`，家长上下文切换不会绕过白名单。紧急回滚只需将 `PRACTICE_FEATURE_ENABLED` 改为 `0` 并重启 API 服务。

## 发布前检查

```powershell
python manage.py migrate --noinput
python manage.py practice_release_check --strict
python manage.py check
pytest apps/practice apps/wrongbook apps/study apps/qrcode -q
```

健康检查：

```text
GET /api/v1/practice/health
```

阶段五观察 `practice_event=recommendation_insufficient`、`pdf_generation_failed`、`photo_upload_rejected` 和 `photo_submit_rejected` 日志。确认学生、家长、多角色和同账号学生/家长身份均通过后，再逐步扩大 `PRACTICE_BETA_MOBILES`。
