一套完全在 Windows 11 PowerShell + Docker Desktop 中完成的安装方案，不要求在 WSL 终端操作。

Docker Desktop 已经包含 Docker Engine、Docker CLI 和 Docker Compose，因此不需要另外安装 docker-compose。官方镜像当前提供 postgres:18.4-bookworm 和 redis:7.2-bookworm 标签。

一、确认 Docker Desktop 正常运行
1. 启动 Docker Desktop

从 Windows 开始菜单打开：

Docker Desktop

等待左下角或主界面显示 Docker Engine 正常运行。

确认使用的是 Linux 容器。可以右击任务栏右下角 Docker 图标：

如果菜单显示 Switch to Windows containers...，说明当前已经是 Linux 容器模式；
如果显示 Switch to Linux containers...，点击它切换。

PostgreSQL 和 Redis 官方镜像是 Linux 容器镜像。

2. 检查 Docker Desktop 设置

进入：

Docker Desktop
→ Settings
→ General

确认已经启用：

Use the WSL 2 based engine

Docker Desktop 官方推荐在 Windows 上使用 WSL2 后端。

点击：

Apply & Restart
3. 在 PowerShell 中验证

打开普通 PowerShell，不一定要使用管理员权限：

docker version
docker compose version
docker info

正常情况下，docker version 应同时显示：

Client
Server

测试 Docker：

docker run --rm hello-world

如果报错：

Cannot connect to the Docker daemon

通常是 Docker Desktop 尚未启动，或还没有完成初始化。

二、创建部署目录

建议使用一个固定目录，例如：

D:\docker\app-system

在 PowerShell 中执行：

New-Item -ItemType Directory -Force -Path D:\docker\app-system | Out-Null
Set-Location D:\docker\app-system

New-Item -ItemType Directory -Force -Path .\secrets | Out-Null
New-Item -ItemType Directory -Force -Path .\redis\conf | Out-Null
New-Item -ItemType Directory -Force -Path .\backup | Out-Null

检查：

Get-ChildItem

最终目录结构为：

D:\docker\app-system
├── compose.yaml
├── secrets
│   ├── postgres_password.txt
│   └── redis_password.txt
├── redis
│   └── conf
│       └── redis.conf
└── backup

数据库数据采用 Docker 命名卷保存，不直接保存到 Windows 目录中。这样可以减少 Windows 文件系统与 Linux 数据库文件权限、锁和 I/O 兼容性问题。

三、生成 PostgreSQL 和 Redis 密码

不要直接把密码写进 compose.yaml。

在 PowerShell 中执行：

Set-Location D:\docker\app-system

$pgBytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($pgBytes)
$pgPassword = -join ($pgBytes | ForEach-Object { $_.ToString("x2") })
Set-Content -Path .\secrets\postgres_password.txt -Value $pgPassword -NoNewline -Encoding ASCII

$redisBytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($redisBytes)
$redisPassword = -join ($redisBytes | ForEach-Object { $_.ToString("x2") })
Set-Content -Path .\secrets\redis_password.txt -Value $redisPassword -NoNewline -Encoding ASCII

Remove-Variable pgBytes, pgPassword, redisBytes, redisPassword

检查文件：

Get-ChildItem .\secrets

查看密码：

Get-Content .\secrets\postgres_password.txt
Get-Content .\secrets\redis_password.txt

请把密码保存到安全的密码管理工具中。

PostgreSQL 官方镜像支持使用 POSTGRES_PASSWORD_FILE 从文件读取初始化密码。

四、创建 Redis 配置文件

在 PowerShell 中执行：

@'
bind 0.0.0.0
protected-mode yes
port 6379

tcp-backlog 511
timeout 0
tcp-keepalive 300

databases 16

dir /data
dbfilename dump.rdb

save 900 1
save 300 10
save 60 10000

appendonly yes
appendfilename "appendonly.aof"
appenddirname "appendonlydir"
appendfsync everysec
no-appendfsync-on-rewrite no

loglevel notice
'@ | Set-Content -Path .\redis\conf\redis.conf -Encoding ASCII

检查：

Get-Content .\redis\conf\redis.conf

这里启用了：

RDB 快照；
AOF 持久化；
每秒同步一次 AOF；
Redis 保护模式。

Redis 官方镜像使用 /data 保存持久化数据。

五、创建 compose.yaml

在 PowerShell 中执行：

@'
name: app-system

services:
  postgres:
    image: postgres:18.4-bookworm
    container_name: app-pgsql
    hostname: postgres
    restart: unless-stopped

    environment:
      POSTGRES_USER: pgadmin
      POSTGRES_DB: appdb
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
      TZ: Asia/Shanghai
      PGTZ: Asia/Shanghai

    secrets:
      - postgres_password

    ports:
      - "127.0.0.1:5432:5432"

    volumes:
      - postgres_data:/var/lib/postgresql

    shm_size: "512m"

    command:
      - postgres
      - -c
      - max_connections=100
      - -c
      - shared_buffers=512MB
      - -c
      - effective_cache_size=2GB
      - -c
      - work_mem=4MB
      - -c
      - maintenance_work_mem=128MB
      - -c
      - checkpoint_completion_target=0.9
      - -c
      - wal_compression=on
      - -c
      - timezone=Asia/Shanghai
      - -c
      - log_timezone=Asia/Shanghai

    healthcheck:
      test:
        - CMD-SHELL
        - pg_isready -U pgadmin -d appdb
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s

    stop_grace_period: 1m

    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"

    networks:
      - backend

  redis:
    image: redis:7.2-bookworm
    container_name: app-redis
    hostname: redis
    restart: unless-stopped

    environment:
      TZ: Asia/Shanghai

    secrets:
      - redis_password

    ports:
      - "127.0.0.1:6379:6379"

    volumes:
      - redis_data:/data
      - ./redis/conf/redis.conf:/usr/local/etc/redis/redis.conf:ro

    command:
      - /bin/sh
      - -c
      - >
        exec redis-server
        /usr/local/etc/redis/redis.conf
        --requirepass "$$(cat /run/secrets/redis_password)"

    healthcheck:
      test:
        - CMD-SHELL
        - >
          redis-cli
          -a "$$(cat /run/secrets/redis_password)"
          --no-auth-warning
          ping | grep -q PONG
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 10s

    stop_grace_period: 30s

    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"

    networks:
      - backend

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt

  redis_password:
    file: ./secrets/redis_password.txt

volumes:
  postgres_data:
    name: app-system-postgres-data

  redis_data:
    name: app-system-redis-data

networks:
  backend:
    name: app-system-backend
    driver: bridge
'@ | Set-Content -Path .\compose.yaml -Encoding ASCII

检查文件：

Get-Content .\compose.yaml
PostgreSQL 18 的重要变化

PostgreSQL 18 必须使用：

volumes:
  - postgres_data:/var/lib/postgresql

不能使用旧版本常见的：

volumes:
  - postgres_data:/var/lib/postgresql/data

从 PostgreSQL 18 开始，官方镜像的数据目录改成版本专属目录：

/var/lib/postgresql/18/docker

卷挂载点则改为：

/var/lib/postgresql

官方镜像明确要求 PostgreSQL 18 及以后将卷挂载到新位置。

六、检查 Compose 配置

确保当前目录正确：

Set-Location D:\docker\app-system

检查 YAML：

docker compose config

如果没有报错，查看服务：

docker compose config --services

应输出：

postgres
redis

查看镜像：

docker compose config --images

应输出：

postgres:18.4-bookworm
redis:7.2-bookworm

Docker Compose 可以通过一个 YAML 文件定义和运行多个容器服务。

七、拉取 PostgreSQL 和 Redis 镜像

执行：

docker compose pull

也可以分别拉取：

docker pull postgres:18.4-bookworm
docker pull redis:7.2-bookworm

查看镜像：

docker images

验证 PostgreSQL 镜像版本：

docker run --rm postgres:18.4-bookworm postgres --version

应看到类似：

postgres (PostgreSQL) 18.4

验证 Redis 镜像版本：

docker run --rm redis:7.2-bookworm redis-server --version

redis:7.2-bookworm 当前由官方镜像提供；如果希望完全固定补丁版本，可以使用当前明确的 redis:7.2.14-bookworm。

八、启动 PostgreSQL 和 Redis

执行：

Set-Location D:\docker\app-system
docker compose up -d

查看状态：

docker compose ps

初次启动 PostgreSQL 需要初始化数据库，稍等片刻后再执行：

docker compose ps

正常结果应类似：

NAME          IMAGE                    STATUS
app-pgsql     postgres:18.4-bookworm   Up ... (healthy)
app-redis     redis:7.2-bookworm       Up ... (healthy)

也可以在 Docker Desktop 的：

Containers
→ app-system

中看到两个容器。

九、查看日志

查看 PostgreSQL 日志：

docker compose logs --tail=100 postgres

正常日志末尾应包含：

database system is ready to accept connections

查看 Redis 日志：

docker compose logs --tail=100 redis

持续查看全部日志：

docker compose logs -f

按：

Ctrl+C

只会停止日志显示，不会停止容器。

十、验证 PostgreSQL
1. 检查运行状态
docker compose exec postgres pg_isready -U pgadmin -d appdb

应返回：

/var/run/postgresql:5432 - accepting connections
2. 查看版本
docker compose exec postgres psql -U pgadmin -d appdb -c "SELECT version();"
3. 查看实际数据目录
docker compose exec postgres psql -U pgadmin -d appdb -c "SHOW data_directory;"

应显示：

/var/lib/postgresql/18/docker
4. 创建测试表
docker compose exec postgres psql -U pgadmin -d appdb -c "CREATE TABLE IF NOT EXISTS install_test (id BIGSERIAL PRIMARY KEY, message TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW());"

插入测试数据：

docker compose exec postgres psql -U pgadmin -d appdb -c "INSERT INTO install_test(message) VALUES ('PostgreSQL 18.4 installation successful');"

查询：

docker compose exec postgres psql -U pgadmin -d appdb -c "SELECT * FROM install_test;"
十一、验证 Redis

执行：

docker compose exec redis sh -c 'REDISCLI_AUTH="$(cat /run/secrets/redis_password)" redis-cli ping'

应返回：

PONG

测试写入：

docker compose exec redis sh -c 'REDISCLI_AUTH="$(cat /run/secrets/redis_password)" redis-cli SET install:test success'

读取：

docker compose exec redis sh -c 'REDISCLI_AUTH="$(cat /run/secrets/redis_password)" redis-cli GET install:test'

应返回：

success

查看 Redis 版本：

docker compose exec redis sh -c 'REDISCLI_AUTH="$(cat /run/secrets/redis_password)" redis-cli INFO server | grep redis_version'

检查 AOF：

docker compose exec redis sh -c 'REDISCLI_AUTH="$(cat /run/secrets/redis_password)" redis-cli CONFIG GET appendonly'

应返回：

appendonly
yes
十二、从 Windows 软件连接 PostgreSQL

可以使用：

DBeaver；
Navicat；
DataGrip；
pgAdmin；
Windows 应用程序。

连接参数：

主机：127.0.0.1
端口：5432
数据库：appdb
用户：pgadmin
密码：postgres_password.txt 中的内容

在 PowerShell 中查看密码：

Get-Content D:\docker\app-system\secrets\postgres_password.txt

连接字符串格式：

postgresql://pgadmin:密码@127.0.0.1:5432/appdb

如果密码包含特殊字符，直接在数据库客户端的密码输入框中填写，不建议手动拼接 URL。
十三、从 Windows 软件连接 Redis

连接参数：

主机：127.0.0.1
端口：6379
用户名：default
密码：redis_password.txt 中的内容
数据库：0

查看密码：

Get-Content D:\docker\app-system\secrets\redis_password.txt

连接字符串：

redis://default:密码@127.0.0.1:6379/0
十四、端口安全说明

当前配置使用：

ports:
  - "127.0.0.1:5432:5432"

和：

ports:
  - "127.0.0.1:6379:6379"

这表示只有 Windows 本机能够访问数据库，不会直接监听局域网网卡。

检查端口：

Get-NetTCPConnection -State Listen |
    Where-Object {
        $_.LocalPort -eq 5432 -or $_.LocalPort -eq 6379
    } |
    Format-Table LocalAddress, LocalPort, State

应看到：

127.0.0.1  5432  Listen
127.0.0.1  6379  Listen

不要轻易改成：

ports:
  - "5432:5432"

或：

ports:
  - "6379:6379"

因为这可能允许同一网络中的其他设备访问。

十五、应用也是 Docker 容器时

应用容器不要使用：

localhost
127.0.0.1

因为容器内的 localhost 表示应用容器自身。

同一 Docker 网络中的连接地址应为：

PostgreSQL 主机：postgres
PostgreSQL 端口：5432

Redis 主机：redis
Redis 端口：6379

应用服务需要加入：

networks:
  - backend

例如：

services:
  application:
    image: your-application-image
    environment:
      DB_HOST: postgres
      DB_PORT: "5432"
      DB_NAME: appdb
      DB_USER: pgadmin
      REDIS_HOST: redis
      REDIS_PORT: "6379"
    networks:
      - backend

应用也在 Docker 中时，可以删除 PostgreSQL 和 Redis 的 ports: 配置，只保留 Docker 内部网络访问。

十六、停止与重新启动

进入项目目录：

Set-Location D:\docker\app-system

停止容器：

docker compose stop

重新启动：

docker compose start

重启：

docker compose restart

删除容器和网络，但保留数据库数据：

docker compose down

重新创建：

docker compose up -d

查看状态：

docker compose ps
十七、不要误删数据库卷

查看数据卷：

docker volume ls

应看到：

app-system-postgres-data
app-system-redis-data

查看 PostgreSQL 卷：

docker volume inspect app-system-postgres-data

查看 Redis 卷：

docker volume inspect app-system-redis-data

下面的命令会删除容器以及 PostgreSQL、Redis 数据：

docker compose down -v

只有明确需要彻底重建数据库时才能执行。

十八、修改密码需要注意

密码文件只在 PostgreSQL数据卷第一次初始化时用于创建数据库用户。

已经完成初始化后，再修改：

secrets\postgres_password.txt

不会自动修改 PostgreSQL 内部用户密码。

修改已有 PostgreSQL 密码：

docker compose exec postgres psql -U pgadmin -d appdb

进入 psql 后执行：

\password pgadmin

根据提示输入新密码。

然后把同样的新密码写入：

D:\docker\app-system\secrets\postgres_password.txt

PostgreSQL 官方镜像的初始化变量和初始化脚本仅在空数据目录第一次启动时生效。

十九、备份 PostgreSQL

进入目录：

Set-Location D:\docker\app-system

生成备份文件名：

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = ".\backup\appdb_$timestamp.dump"

执行备份：

docker compose exec -T postgres pg_dump -U pgadmin -d appdb -Fc |
    Set-Content -Path $backupFile -AsByteStream

在旧版 Windows PowerShell 中，管道处理二进制数据可能不可靠。更稳妥的方式是在容器中创建备份，然后复制出来：

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

docker compose exec postgres pg_dump `
    -U pgadmin `
    -d appdb `
    -Fc `
    -f "/tmp/appdb_$timestamp.dump"

docker cp "app-pgsql:/tmp/appdb_$timestamp.dump" `
    ".\backup\appdb_$timestamp.dump"

docker compose exec postgres rm "/tmp/appdb_$timestamp.dump"

检查：

Get-ChildItem .\backup
二十、常见问题
PostgreSQL 不断重启

查看日志：

docker logs app-pgsql

如果出现：

there appears to be PostgreSQL data in:
/var/lib/postgresql/data

说明挂载路径使用了旧目录。

正确：

- postgres_data:/var/lib/postgresql

错误：

- postgres_data:/var/lib/postgresql/data

PostgreSQL 18 已更改官方镜像数据目录结构。

5432 端口被占用

检查：

Get-NetTCPConnection -LocalPort 5432 -ErrorAction SilentlyContinue

也可以执行：

netstat -ano | findstr ":5432"

将 Compose 修改为：

ports:
  - "127.0.0.1:15432:5432"

然后 Windows 客户端连接：

127.0.0.1:15432

更新容器：

docker compose up -d --force-recreate postgres
6379 端口被占用

修改成：

ports:
  - "127.0.0.1:16379:6379"

Windows 客户端使用：

127.0.0.1:16379
镜像下载缓慢

先测试：

docker pull postgres:18.4-bookworm
docker pull redis:7.2-bookworm

可以在 Docker Desktop 中检查：

Settings
→ Resources
→ Proxies

如果使用国内镜像加速，应在：

Settings
→ Docker Engine

中配置自己可信的镜像加速地址，不建议使用来源不明的公共镜像站。

二十一、最终验收

依次执行：

Set-Location D:\docker\app-system

docker compose config
docker compose ps
docker images

docker compose exec postgres pg_isready -U pgadmin -d appdb
docker compose exec postgres psql -U pgadmin -d appdb -c "SELECT version();"
docker compose exec postgres psql -U pgadmin -d appdb -c "SHOW data_directory;"

docker compose exec redis sh -c 'REDISCLI_AUTH="$(cat /run/secrets/redis_password)" redis-cli ping'

docker stats --no-stream app-pgsql app-redis

最终应确认：

app-pgsql：healthy
app-redis：healthy
PostgreSQL：18.4
PostgreSQL 数据目录：/var/lib/postgresql/18/docker
Redis：PONG

Windows 本机应用的连接地址为：

PostgreSQL：127.0.0.1:5432
Redis：127.0.0.1:6379