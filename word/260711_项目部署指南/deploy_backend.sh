#!/bin/bash
# ============================================================
# 齐思 · A自习室 后端一键部署脚本（v3.0）
# 在服务器上执行：bash deploy_backend.sh
# 前置条件: 后端代码已上传到 /mnt/datadisk0/qisi/backend
# 注意:
#   - 使用端口 8001（避开已占用的 8000）
#   - Gunicorn 绑定 0.0.0.0（Docker Nginx 可访问）
#   - 数据库/Redis 通过 localhost 连接（端口已发布到宿主机）
#   - 部署路径使用 /mnt/datadisk0/（与现有项目一致）
# ============================================================
set -e

PROJECT_DIR="/mnt/datadisk0/qisi"
BACKEND_DIR="$PROJECT_DIR/backend"
LOGS_DIR="$PROJECT_DIR/logs"
VENV_DIR="$BACKEND_DIR/venv"

echo "============================================================"
echo "  齐思 · A自习室 后端一键部署脚本 v3.0"
echo "  后端端口: 8001（绑定 0.0.0.0）"
echo "  数据库: localhost:5432 (qisi-postgres)"
echo "  Redis: localhost:6379 (qisi-redis)"
echo "  部署路径: /mnt/datadisk0/qisi/"
echo "============================================================"
echo ""

# ---- 检查是否以 ubuntu 用户运行 ----
if [ "$(whoami)" != "ubuntu" ]; then
    echo "[ERROR] 请以 ubuntu 用户运行此脚本"
    exit 1
fi

# ---- 1. 创建目录 ----
echo "[1/9] 创建目录..."
mkdir -p $BACKEND_DIR
mkdir -p $BACKEND_DIR/media
mkdir -p $BACKEND_DIR/staticfiles
mkdir -p $LOGS_DIR
mkdir -p $PROJECT_DIR/frontend-h5
mkdir -p $PROJECT_DIR/backups

# ---- 2. 创建虚拟环境 & 安装依赖 ----
echo "[2/9] 创建 Python 虚拟环境并安装依赖..."
cd $BACKEND_DIR
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ---- 3. 创建 .env 文件 ----
echo "[3/9] 配置环境变量..."
if [ ! -f ".env" ]; then
    cat > .env << 'ENVEOF'
# Django
DJANGO_SECRET_KEY=qisi_jwt_secret_key_2026_development
DJANGO_DEBUG=False
ALLOWED_HOSTS=127.0.0.1,localhost,42.194.195.78,qisi.chengxuelu.com

# Database - 使用已有的 qisi-postgres 容器（端口已发布到宿主机）
DB_NAME=qisi_ai_tutor
DB_USER=qisi_admin
DB_PASSWORD=qisi_pg_2026_StrongPwd
DB_HOST=localhost
DB_PORT=5432

# Redis / Celery - 使用已有的 qisi-redis 容器（端口已发布到宿主机）
# 使用 DB 1/2/3 避免与已有项目（tiku 使用 DB 0）冲突
CELERY_BROKER_URL=redis://:Redis_2026_StrongPwd@localhost:6379/1
CELERY_RESULT_BACKEND=redis://:Redis_2026_StrongPwd@localhost:6379/2
CACHE_URL=redis://:Redis_2026_StrongPwd@localhost:6379/3
CELERY_TASK_ALWAYS_EAGER=False
REDIS_PASSWORD=Redis_2026_StrongPwd
REDIS_HOST=localhost
REDIS_PORT=6379

# AI Providers
QWEN_API_KEY=sk-6a5be1cc8fc84ac18836619ffe86fa2e
AI_MODEL=qwen3.6-plus

# Aliyun OSS
ALIYUN_OSS_ACCESS_KEY_ID=LTAI5t9LrNmrcXd8BB53sUu2
ALIYUN_OSS_ACCESS_KEY_SECRET=3vZFeXev1gNHC0rRL6fLtoc7Jxl7Rj
ALIYUN_OSS_BUCKET=oss-pai-q69568m1rpn68fpbj7-cn-shanghai
ALIYUN_OSS_REGION=cn-shanghai
ALIYUN_OSS_ENDPOINT=https://oss-cn-shanghai.aliyuncs.com

# JWT
JWT_SECRET_KEY=qisi_jwt_secret_key_2026_development
JWT_ACCESS_EXPIRE_HOURS=24
JWT_REFRESH_EXPIRE_DAYS=30

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://qisi.chengxuelu.com

# Tencent Cloud SMS
SMS_DEV_MODE=0
TENCENT_SMS_SECRET_ID=AKIDnUuGRQq57CC4wl09A3kGbputmaGlKpCV
TENCENT_SMS_SECRET_KEY=CC3jDZn3tdEeuzsZ5PX9dw43rdEg8dDd
TENCENT_SMS_SDK_APP_ID=1400878428
TENCENT_SMS_SIGN_NAME=深圳市优途致远信息
TENCENT_SMS_LOGIN_TEMPLATE_ID=2028981
TENCENT_SMS_REGISTER_TEMPLATE_ID=2028979
TENCENT_SMS_REGION=ap-guangzhou
ENVEOF
    echo "  .env 文件已创建（localhost 连接数据库/Redis）"
else
    echo "  .env 文件已存在，跳过"
fi

# ---- 4. 修改 settings.py 添加 FORCE_SCRIPT_NAME ----
echo "[4/9] 检查 Django settings.py 部署配置..."
cd $BACKEND_DIR
source venv/bin/activate

# 检查是否已添加 FORCE_SCRIPT_NAME
if ! grep -q "FORCE_SCRIPT_NAME" config/settings.py; then
    echo "  添加 FORCE_SCRIPT_NAME 和 STATIC_URL/MEDIA_URL 配置..."
    cat >> config/settings.py << 'PYEOF'

# ========== 部署配置（/study 子路径前缀） ==========
FORCE_SCRIPT_NAME = '/study'
STATIC_URL = '/study/static/'
MEDIA_URL = '/study/media/'
PYEOF
    echo "  ✓ 已添加部署配置到 config/settings.py"
else
    echo "  ✓ FORCE_SCRIPT_NAME 已存在，跳过"
fi

# ---- 5. 数据库迁移 ----
echo "[5/9] 运行数据库迁移..."
python manage.py migrate

# ---- 6. 收集静态文件 ----
echo "[6/9] 收集静态文件..."
python manage.py collectstatic --noinput

# ---- 7. 创建 systemd 服务 ----
echo "[7/9] 配置 systemd 服务（端口 8001，绑定 0.0.0.0）..."

# Gunicorn - 绑定 0.0.0.0:8001 以便 Docker Nginx 可访问
sudo tee /etc/systemd/system/qisi-gunicorn.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=Qisi Django Gunicorn Service
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/mnt/datadisk0/qisi/backend
Environment="PATH=/mnt/datadisk0/qisi/backend/venv/bin"
ExecStartPre=/bin/sleep 5
ExecStart=/mnt/datadisk0/qisi/backend/venv/bin/gunicorn config.wsgi:application \
  --workers 4 \
  --bind 0.0.0.0:8001 \
  --timeout 120 \
  --access-logfile /mnt/datadisk0/qisi/logs/gunicorn-access.log \
  --error-logfile /mnt/datadisk0/qisi/logs/gunicorn-error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Celery Worker
sudo tee /etc/systemd/system/qisi-celery.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=Qisi Celery Worker Service
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/mnt/datadisk0/qisi/backend
Environment="PATH=/mnt/datadisk0/qisi/backend/venv/bin"
ExecStart=/mnt/datadisk0/qisi/backend/venv/bin/celery -A config worker -l info \
  --logfile=/mnt/datadisk0/qisi/logs/celery-worker.log \
  --pidfile=/mnt/datadisk0/qisi/logs/celery-worker.pid
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Celery Beat
sudo tee /etc/systemd/system/qisi-celery-beat.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=Qisi Celery Beat Service
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/mnt/datadisk0/qisi/backend
Environment="PATH=/mnt/datadisk0/qisi/backend/venv/bin"
ExecStart=/mnt/datadisk0/qisi/backend/venv/bin/celery -A config beat -l info \
  --logfile=/mnt/datadisk0/qisi/logs/celery-beat.log \
  --pidfile=/mnt/datadisk0/qisi/logs/celery-beat.pid
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

# ---- 8. 启动服务 ----
echo "[8/9] 启动服务..."
sudo systemctl daemon-reload
sudo systemctl enable qisi-gunicorn
sudo systemctl enable qisi-celery
sudo systemctl enable qisi-celery-beat
sudo systemctl start qisi-gunicorn
sudo systemctl start qisi-celery
sudo systemctl start qisi-celery-beat

# ---- 9. 验证 ----
echo "[9/9] 验证后端服务..."
sleep 3
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/v1/auth/login 2>/dev/null || echo "000")
echo "  后端 API 响应码: $HTTP_CODE"

echo ""
echo "============================================================"
echo "  后端部署完成！"
echo "  后端端口: 8001（绑定 0.0.0.0）"
echo "  服务状态:"
sudo systemctl is-active qisi-gunicorn qisi-celery qisi-celery-beat
echo ""
echo "  下一步操作:"
echo "  1. 修改 /opt/qisi/nginx.conf 添加 /study/ 路由"
echo "  2. 重建 Nginx 容器添加新目录挂载"
echo "  3. 平滑重载 Nginx: sudo docker exec qisi-nginx nginx -s reload"
echo "  详细步骤见部署指南 v3.0"
echo "============================================================"