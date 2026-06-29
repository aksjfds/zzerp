# 后端认证与授权

## 会话安全

- 登录会话使用 `HttpOnly` Cookie，数据库只保存会话令牌哈希。
- 写请求必须携带与会话绑定的 `X-CSRF-Token`。
- `ALLOWED_ORIGINS` 必须配置明确的可信前端源。

## 业务权限

| 接口 | 权限 | 数据范围 |
| --- | --- | --- |
| `GET /products` | 公开 | 无需登录，只读查看全部产品库存 |
| `GET /records` | 公开 | 无需登录，只读查看产品流转记录 |
| `POST /products` | `product:add` | 管理员创建订单产品和全局部门流程 |
| `GET /work-orders/{department}` | `task:view` | 当前部门 |
| 配置工艺、维护工人、开工单 | `task:assign` | 当前部门 |
| 送检、直接报工 | `task:complete` | 当前部门工单 |
| `GET /qc/submissions/pending` | `task:view` | 仅 QC 或管理员 |
| 分配送检批次给 QC 工人 | `task:assign` | 仅 QC 或管理员 |
| 提交 QC 结果 | `task:complete` | 仅 QC 或管理员 |

## QC 不可变规则

- 每个送检批次只能提交一次 QC 结果。
- 送检批次必须先分配给有效的 QC 工人，之后才能录入结果。
- QC 结果必须满足 `送检 = OK + 返修 + 报废 + 遗失`。
- 完成后的批次没有修改或删除接口。
- 数据库触发器禁止更新已完成批次，并禁止删除任何工单批次。

## 部署配置

- HTTPS 环境保持 `COOKIE_SECURE=true`。
- 跨站部署使用 `COOKIE_SAMESITE=none`；同站部署优先使用 `lax`。
