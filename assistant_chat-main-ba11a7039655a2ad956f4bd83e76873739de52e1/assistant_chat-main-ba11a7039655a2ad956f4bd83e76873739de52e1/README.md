# Assistant Chat

口腔小程序 Server，负责微信账号登录、JWT 鉴权和 Agent 请求转发。

## 快速开始

### 1. 后端服务
1. 可选：创建虚拟环境并安装依赖
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. 复制并填写环境变量
   ```bash
   test -f .env || cp .env.example .env
   ```
3. 创建或升级 MySQL 表
   ```bash
   alembic upgrade head
   ```
4. 启动 FastAPI 服务
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8001 --reload
   ```

### 2. 前端界面
1. 安装依赖（首次执行即可）
   ```bash
   cd web
   npm install
   ```
2. 启动开发服务器
   ```bash
   npm run dev
   ```
3. 当前 Web 用户名密码登录已停用，账号入口以微信小程序为准。

## 配置说明
- 微信账号和 JWT：
  - `WECHAT_APPID` / `WECHAT_SECRET`：小程序登录配置，Secret 只能保存在 Server。
  - `AUTH_SECRET_KEY`：JWT 签名密钥，生产环境必须使用随机强密钥。
  - `AUTH_ISSUER` / `AUTH_AUDIENCE`：JWT 签发方和受众。
- MySQL：
  - `DATABASE_URL`：SQLAlchemy MySQL URL，必须使用 `mysql+pymysql://`。
  - Docker Compose 部署还需配置 `MYSQL_ROOT_PASSWORD`、`MYSQL_DATABASE`、`MYSQL_USER`、`MYSQL_PASSWORD`。
- Agent 转发：
  - `CHAT_BASE_URL`：Agent 服务地址（若不同 Agent 地址相同，可统一配置）
  - `CHAT_DISNEY_BASE_URL` / `CHAT_MOUTH_BASE_URL`：为不同 Agent 指定独立服务地址
  - `CHAT_DISNEY_API_KEY` / `CHAT_MOUTH_API_KEY`：为不同 Agent 指定密钥

## Docker Compose 部署

```bash
test -f .env || cp .env.example .env
# 编辑现有 .env，补齐微信、JWT、MySQL 和 Agent 配置
docker compose build --no-cache backend
docker compose up -d mysql
docker compose up -d backend frontend
docker compose ps
curl -fsS https://sanora.linkwe-inc.com/health
```

Backend 容器启动时会先执行 `alembic upgrade head`，迁移成功后再启动 Uvicorn。MySQL 数据保存在 `mysql_data` 命名卷中。

## 目录结构
- `chat_client.py` / `oral_cavity_client.py`：Agent 客户端示例
- `server.py`：FastAPI 身份网关和 Agent 代理
- `account_models.py` / `user_repository.py`：MySQL 账号模型和仓储
- `wechat_client.py`：微信 code2Session 客户端
- `migrations/`：Alembic 数据库迁移
- `web/`：Vue + Tailwind 前端项目
- `requirements.txt`：Python 依赖
- `AGENTS.md`：贡献指南
