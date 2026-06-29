# 后端认证与授权

## 会话安全

- 登录会话使用 `HttpOnly` Cookie，数据库只保存会话令牌哈希。
- 写请求必须携带与会话绑定的 `X-CSRF-Token`。
- `ALLOWED_ORIGINS` 必须配置明确的可信前端源。

## 业务权限

| 接口 | 权限 | 数据范围 |
| --- | --- | --- |
| `GET /products` | 公开 | 无需登录，只读查看全部产品库存 |
| `GET /products/{id}/departments/{department}/progress` | 公开 | 仅返回部门工艺数量汇总，不返回工人和工单信息 |
| `GET /records` | `record:view` | 登录后查看产品流转记录 |
| `POST /products` | `product:add` | 管理员创建订单产品和全局部门流程 |
| `GET /work-orders/{department}` | `task:view` | 当前部门 |
| `GET /work-orders/polish/workers/overview` | `task:view` | 磨房或管理员，仅统计已结工单 |
| 配置工艺、维护工人、开工单 | `task:assign` | 当前部门 |
| 维护磨房工艺预设 | `task:assign` | 磨房主管或管理员 |
| 送检、直接报工 | `task:complete` | 当前部门工单 |
| 送洗、确认清洗完成 | `task:complete` | 磨房工单 |
| `GET /qc/submissions/pending` | `task:view` | 仅 QC 或管理员 |
| 分配送检批次给 QC 工人 | `task:assign` | 仅 QC 或管理员 |
| 提交 QC 结果 | `task:complete` | 仅 QC 或管理员 |

## 产品流程规则

- QC 不能作为产品正式部门流程，也不持有正式产品库存。
- QC 只处理其他部门工艺明确要求质检时产生的送检批次。

## QC 不可变规则

- 每个送检批次只能提交一次 QC 结果。
- 送检批次必须先分配给有效的 QC 工人，之后才能录入结果。
- QC 结果必须满足 `送检 = OK + 返修 + 报废 + 遗失`。
- 完成后的批次没有修改或删除接口。
- 数据库触发器禁止更新已完成批次，并禁止删除任何工单批次。

## 部署配置

- HTTPS 环境保持 `COOKIE_SECURE=true`。
- 跨站部署使用 `COOKIE_SAMESITE=none`；同站部署优先使用 `lax`。
