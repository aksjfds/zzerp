# Render + Netlify + Neon 测试部署

项目采用以下部署结构：

```text
浏览器 -> Netlify /api -> Render FastAPI -> Neon PostgreSQL
```

Netlify 的同源 `/api` 代理可以避免前后端跨站 Cookie 在部分浏览器中被拦截。

## 1. 初始化 Neon 数据库

`zzerp.sql` 会删除并重建 `public` schema，同时写入测试账号和示例数据。仅适合
当前测试阶段，不可用于需要保留数据的数据库。

在本机设置 `DATABASE_URL` 后执行：

```bash
ALLOW_DATABASE_RESET=yes python scripts/reset_database.py
```

也可以在 Neon SQL Editor 中执行 `zzerp.sql`。初始化完成后，访问后端
`/ready` 应返回：

```json
{"status":"ready","database":"ready"}
```

## 2. 部署 Render 后端

仓库根目录的 `render.yaml` 已配置：

- Python 3.12
- 新加坡区域
- 安装 `backend/requirements.txt`
- 启动 `uvicorn main:app`
- 使用 `/health` 作为 Render 健康检查

在 Render 创建 Blueprint，并设置 `DATABASE_URL` 为 Neon 提供的完整连接串。
不要将数据库连接串写入仓库。

部署成功后记录 Render 地址，例如：

```text
https://your-render-service.onrender.com
```

检查：

- `/health`：后端进程正常
- `/ready`：数据库可连接且已初始化

## 3. 部署 Netlify 前端

仓库根目录的 `netlify.toml` 已配置构建目录、Node 22、pnpm 10 和 SPA 路由。

在 Netlify 环境变量中设置：

```text
RENDER_API_URL=https://your-render-service.onrender.com
```

不要在地址末尾添加路径。构建脚本会生成以下代理：

```text
/api/* -> Render /*
/*      -> /index.html
```

前端生产环境默认请求 `/api`。一般不需要设置 `VITE_API_BASE_URL`；设置它会绕过
Netlify 同源代理。

## 4. Render 来源与 Cookie

`render.yaml` 默认允许 `*.netlify.app` 来源，并使用：

```text
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

正式绑定自定义域名后，应将 `ALLOWED_ORIGIN_REGEX` 删除，并把
`ALLOWED_ORIGINS` 设置为唯一前端地址。

## 5. 测试账号与安全限制

当前 `zzerp.sql` 包含开发测试账号，密码以明文方式存储，初始密码也很弱。
因此本方案只适合临时测试部署：

- 不录入真实客户、订单、人员或生产数据；
- 不把测试地址公开给无关人员；
- 测试完成后暂停或删除 Render、Netlify 和 Neon 资源；
- 正式上线前必须改为密码哈希、强密码和可保留数据的迁移方案。

数据库连接串一旦在聊天、日志或其他非密钥渠道中出现，应在 Neon 控制台轮换
数据库密码，并同步更新 Render 的 `DATABASE_URL`。
