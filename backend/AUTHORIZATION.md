# 后端认证与授权

## 会话

- 登录成功后，服务端生成随机会话令牌；数据库只保存 SHA-256 哈希。
- 原始会话令牌仅写入 `HttpOnly` Cookie。
- 会话默认有效 12 小时，可通过 `SESSION_EXPIRE_HOURS` 调整。
- `/current_user` 从会话确定用户，并轮换同步 CSRF Token。
- 退出登录会撤销数据库会话并删除 Cookie。

## 接口权限

| 接口 | 权限 | 数据范围 |
| --- | --- | --- |
| `POST /login` | 公开 | 不适用 |
| `GET /current_user` | 已登录 | 当前用户 |
| `POST /logout` | 已登录 + CSRF | 当前会话 |
| `GET /products` | `product:view` 或 `task:view` | 系统用户查看全部，部门用户仅查看本部门库存 |
| `POST /products` | `product:add` + CSRF | 系统业务规则 |
| `GET /records` | `record:view` | 非系统用户必须明确指定自己的部门 |
| `GET /tasks/{department}` | `task:view` | 当前部门或 `sys` |
| `POST /tasks` | `task:assign` + CSRF | 当前部门或 `sys` |
| `PATCH /tasks/{id}/complete` | `task:complete` + CSRF | 根据数据库中的任务部门判断 |
| 工人、工艺查询 | `task:view` | 当前部门或 `sys` |
| 新增工艺 | `task:assign` + CSRF | 当前部门或 `sys` |

## 部署要求

- `ALLOWED_ORIGINS` 必须设置为逗号分隔的可信前端源，不能使用 `*`。
- HTTPS 环境保持 `COOKIE_SECURE=true`。
- 跨站部署使用 `COOKIE_SAMESITE=none`；同站部署优先使用 `lax`。
- 浏览器写请求必须同时携带会话 Cookie 和 `X-CSRF-Token`。
