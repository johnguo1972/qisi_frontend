@echo off
chcp 65001 >nul

rem ===== 齐思 优途AI辅学系统 —— 一键启动（Docker 版） =====
rem 切换到脚本所在目录（即仓库根目录，可随项目整体移动）
cd /d "%~dp0"

echo ============================================================
echo   齐思 优途AI辅学系统 —— 一键启动
echo ============================================================
echo.

rem ---- 1) PostgreSQL（Docker 容器 qisi-postgres）----
echo [1/4] PostgreSQL ...
docker start qisi-postgres 2>nul || echo 请先执行: docker compose -f "word\260722_项目新部署指南\local\docker-compose.local.yml" up -d
echo.

rem ---- 2) Redis（Docker 容器 qisi-redis）----
echo [2/4] Redis ...
docker start qisi-redis 2>nul
echo [2/4] Redis 就绪（端口 6379）
echo.

rem ---- 3) 后端 Django :8001（已运行则跳过）----
netstat -ano | findstr "LISTENING" | findstr ":8001" >nul && goto backend_done
echo [3/4] 启动后端 Django ...
start "qisi-Backend-8001" cmd /k "venv\Scripts\python.exe manage.py runserver 0.0.0.0:8001"
:backend_done
echo [3/4] 后端就绪 http://localhost:8001/
echo.

rem ---- 4) 前端 uni-app :5273（已运行则跳过）----
netstat -ano | findstr "LISTENING" | findstr ":5273" >nul && goto frontend_done
echo [4/4] 启动前端 uni-app ...
start "qisi-Frontend-5273" cmd /k "cd uniapp && npm run dev:h5"
:frontend_done
echo [4/4] 前端就绪 http://localhost:5273/
echo.

echo ============================================================
echo   全部服务已就绪，浏览器访问：
echo     前端  http://localhost:5273/
echo     后端  http://localhost:8001/
echo   停止：关闭对应窗口；Docker 容器用 docker compose down
echo ============================================================
echo.
echo 按任意键关闭本窗口（已启动的服务窗口不受影响）...
pause >nul
