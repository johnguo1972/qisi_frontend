#!/usr/bin/env bash
set -Eeuo pipefail

# 生产环境微信小程序参数和二维码功能发布脚本
#
# 用法：
#   chmod +x 生产环境微信配置与二维码发布.sh
#   sudo ./生产环境微信配置与二维码发布.sh
#
# 可选环境变量：
#   QISI_BACKEND_DIR=/mnt/datadisk0/qisi/backend
#   QISI_FRONTEND_DIR=/mnt/datadisk0/qisi/frontend-h5
#   QISI_PUBLIC_WEB_URL=https://qisi.chengxuelu.com
#   QISI_SKIP_MIGRATE=1       # 仅配置和重启，不执行迁移
#   QISI_SKIP_FRONTEND=1      # 不检查 H5 静态目录

SCRIPT_NAME="$(basename "$0")"
BACKEND_DIR="${QISI_BACKEND_DIR:-/mnt/datadisk0/qisi/backend}"
FRONTEND_DIR="${QISI_FRONTEND_DIR:-/mnt/datadisk0/qisi/frontend-h5}"
PUBLIC_WEB_URL="${QISI_PUBLIC_WEB_URL:-https://qisi.chengxuelu.com}"
ENV_FILE="${BACKEND_DIR}/.env"
VENV_PYTHON="${BACKEND_DIR}/venv/bin/python"

log() { printf '[qisi] %s\n' "$*"; }
fail() { printf '[qisi] ERROR: %s\n' "$*" >&2; exit 1; }

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

[[ -d "${BACKEND_DIR}" ]] || fail "后端目录不存在：${BACKEND_DIR}。可通过 QISI_BACKEND_DIR 覆盖。"
[[ -f "${VENV_PYTHON}" ]] || fail "Python 虚拟环境不存在：${VENV_PYTHON}。"
[[ -f "${BACKEND_DIR}/apps/qrcode/services.py" ]] || fail "服务器后端尚未部署二维码模块，请先上传最新后端代码。"
grep -q "WECHAT_MP_APPID" "${BACKEND_DIR}/config/settings.py" || fail "服务器后端尚未包含微信配置代码，请先上传最新后端代码。"

read -r -p "微信小程序 AppID [wx86647a750a7727cb]: " MP_APPID
MP_APPID="${MP_APPID:-wx86647a750a7727cb}"
[[ "${MP_APPID}" =~ ^wx[[:alnum:]]+$ ]] || fail "AppID 格式不正确。"

read -r -s -p "请输入新的微信小程序 AppSecret（不会显示）： " MP_APPSECRET
printf '\n'
[[ -n "${MP_APPSECRET}" ]] || fail "AppSecret 不能为空。"
read -r -s -p "请再次输入 AppSecret 确认（不会显示）： " MP_APPSECRET_CONFIRM
printf '\n'
[[ "${MP_APPSECRET}" == "${MP_APPSECRET_CONFIRM}" ]] || fail "两次输入的 AppSecret 不一致。"

export QISI_ENV_FILE="${ENV_FILE}"
export QISI_MP_APPID="${MP_APPID}"
export QISI_MP_APPSECRET="${MP_APPSECRET}"
export QISI_PUBLIC_WEB_URL="${PUBLIC_WEB_URL}"

mkdir -p "${BACKEND_DIR}"
touch "${ENV_FILE}"
BACKUP_FILE="${ENV_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
cp -p "${ENV_FILE}" "${BACKUP_FILE}"
chmod 600 "${ENV_FILE}" "${BACKUP_FILE}"
log "已备份原环境文件：${BACKUP_FILE}"

# 使用 Python 按键更新，保留 .env 中其他配置，避免 sed 处理特殊字符出错。
"${VENV_PYTHON}" - <<'PY'
import os
from pathlib import Path

path = Path(os.environ['QISI_ENV_FILE'])
values = {
    'WECHAT_MP_APPID': os.environ['QISI_MP_APPID'],
    'WECHAT_MP_APPSECRET': os.environ['QISI_MP_APPSECRET'],
    'PUBLIC_WEB_URL': os.environ['QISI_PUBLIC_WEB_URL'],
}
lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
seen = set()
updated = []
for line in lines:
    stripped = line.strip()
    key = stripped.split('=', 1)[0].strip() if '=' in stripped and not stripped.startswith('#') else ''
    if key in values:
        if key not in seen:
            updated.append(f'{key}={values[key]}')
            seen.add(key)
        continue
    updated.append(line)
for key, value in values.items():
    if key not in seen:
        updated.append(f'{key}={value}')
path.write_text('\n'.join(updated).rstrip() + '\n', encoding='utf-8')
PY

# 清理当前 shell 中的密钥变量，避免后续命令误输出。
unset MP_APPSECRET MP_APPSECRET_CONFIRM QISI_MP_APPSECRET

cd "${BACKEND_DIR}"
log "检查 Django 配置"
"${VENV_PYTHON}" manage.py check

if [[ "${QISI_SKIP_MIGRATE:-0}" != "1" ]]; then
  log "查看数据库迁移计划"
  "${VENV_PYTHON}" manage.py migrate --plan
  log "执行数据库迁移"
  "${VENV_PYTHON}" manage.py migrate --noinput
else
  log "已跳过数据库迁移（QISI_SKIP_MIGRATE=1）"
fi

log "收集静态文件"
"${VENV_PYTHON}" manage.py collectstatic --noinput

log "验证 Django 已读取微信配置（仅输出 AppID 和是否存在密钥，不输出密钥）"
"${VENV_PYTHON}" manage.py shell -c "from django.conf import settings; print('WECHAT_MP_APPID=' + str(settings.WECHAT_MP_APPID)); print('WECHAT_MP_APPSECRET_CONFIGURED=' + str(bool(settings.WECHAT_MP_APPSECRET))); print('PUBLIC_WEB_URL=' + str(settings.PUBLIC_WEB_URL))"

if [[ "${QISI_SKIP_FRONTEND:-0}" != "1" ]]; then
  [[ -d "${FRONTEND_DIR}" ]] || fail "H5 静态目录不存在：${FRONTEND_DIR}。可通过 QISI_SKIP_FRONTEND=1 跳过检查。"
  log "H5 静态目录存在：${FRONTEND_DIR}"
fi

log "重启后端服务"
systemctl restart qisi-gunicorn
systemctl restart qisi-celery
systemctl restart qisi-celery-beat

log "检查服务状态"
systemctl is-active --quiet qisi-gunicorn || fail "qisi-gunicorn 未运行。"
systemctl is-active --quiet qisi-celery || fail "qisi-celery 未运行。"
systemctl is-active --quiet qisi-celery-beat || fail "qisi-celery-beat 未运行。"

log "检查并重载 Nginx"
nginx -t
systemctl reload nginx

log "验证公网 HTTPS"
curl --fail --silent --show-error --max-time 15 "${PUBLIC_WEB_URL}/health" -o /dev/null
curl --fail --silent --show-error --max-time 15 "${PUBLIC_WEB_URL}/" -o /dev/null

log "完成。未输出 AppSecret；请继续使用真实作业码验证 /api/v1/hw/{code}/url-link 和教师端 wxacode 接口。"
