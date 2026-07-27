# v5 项目目录与文件职责

本文是项目结构的权威索引。新增目录或改变文件职责时，应在同一个变更中更新
本文和架构测试。

## 根目录

| 路径 | 职责 |
| --- | --- |
| `backend/` | FastAPI 应用、领域规则、模块、传输 Schema 和测试 |
| `frontend/` | Vue 应用、部门页面、权限、路由和前端 API 客户端 |
| `docs/` | 架构、数据库、流程和接口设计 |
| `scripts/` | 本地及 CI 可复用的检查入口 |
| `.github/workflows/verify.yml` | PostgreSQL 契约测试、后端测试、前端检查与构建 |
| `zzerp.sql` | 当前 PostgreSQL 基线结构及初始化数据 |
| `docker-compose.yaml` | 本地应用和 PostgreSQL 容器 |
| `package.json` | 根目录开发、构建和完整验证命令 |

## 后端基础层

| 路径 | 职责 |
| --- | --- |
| `backend/src/main.py` | 创建 FastAPI 应用、异常转换、中间件和 Router 注册 |
| `backend/src/config.py` | 环境文件、数据库、Cookie 和跨域配置 |
| `backend/src/database.py` | SQLAlchemy Engine、Session 工厂和声明基类 |
| `backend/src/auth_dependencies.py` | 当前用户、会话和 CSRF 的 HTTP 依赖 |
| `backend/src/authorization.py` | 权限及部门访问检查 |
| `backend/src/domain/` | 不依赖传输层和持久化层的纯领域类型与规则 |
| `backend/src/schemas/` | REST 请求与响应的 Pydantic 契约 |
| `backend/src/routers/` | HTTP 适配器；只能进入业务模块的 `api.py` |

`routers/` 中的文件按外部资源分工：`auth.py` 处理认证，`products.py` 处理
工程产品，`customers.py` 和 `customer_orders.py` 处理销售，`organization.py`
处理组织资料和部门模块清单，`production.py` 处理部门库存与工人，
`work_orders.py` 处理生产工单，`qc.py` 处理质检，`pmc.py` 处理计划看板，
`procedure_tag_prices.py` 处理计件价格，`admin.py` 处理管理查询。

## 业务模块文件约定

每个 `backend/src/modules/<name>/` 都遵守以下约定：

| 文件名 | 职责 |
| --- | --- |
| `api.py` | Router 和其他模块可使用的主要用例入口 |
| `descriptor.py` | 模块名称、所有权和显式协作关系 |
| `persistence.py` | 该模块拥有的 SQLAlchemy 表定义 |
| `model_api.py` | 仅供显式登记的共享数据库高性能只读投影使用 |
| `context_api.py` | 不依赖 SQLAlchemy 的事务内结构协议 |
| `*_api.py` | 面向特定协作者的窄查询、命令或投影端口 |
| 其他 `.py` 文件 | 模块内部实现，外部禁止直接导入 |

模块具体分工：

| 模块 | 权威数据与业务职责 | 主要公开用例 |
| --- | --- | --- |
| `identity` | 用户、会话、认证 | 登录认证、会话创建/撤销、CSRF |
| `organization` | 部门、车间、工艺 | 组织资料和工艺标签查询 |
| `engineering` | 产品、版本、BOM、流程图 | 产品查询、创建、更新、版本管理 |
| `sales` | 客户、订单、订单明细 | 客户查询、订单增删改、状态转换 |
| `production_core` | 生产项、库存、工单、流转、撤回 | 生产投放、库存卡、工单编排与操作撤回 |
| `standard_execution` | 标签、标签组、库存、计件明细 | 标准工艺执行、标签和计件价格 |
| `purchasing` | 外购执行策略 | 外购工单创建与到货提交 |
| `assembly` | 装配用料和装配执行策略 | 装配开单、提交和返工 |
| `quality` | 质检批次 | 待检查询、检验和合格品放行 |
| `workforce` | 工人 | 工人维护、历史和工资投影 |
| `planning` | 跨模块只读模型 | PMC 配件进度 |

`production_core` 是共享生产状态机和事务编排模块，不代表任何具体部门；
部门差异必须留在 `standard_execution`、`purchasing`、`assembly`、`quality`
或部门门面中。

## 部门模块

`backend/src/departments/<code>/api.py` 是每个部门的独立公开门面。
`departments/contracts.py` 定义能力名称与每项能力必须提供的方法，
`departments/base.py` 只保存部门描述并执行能力守卫，
`departments/capabilities/` 为库存、工单、人员、标准工艺、采购、装配、质检和
打印分别实现可组合能力，
`departments/registry.py` 是唯一注册和解析入口。

| 部门 | 执行模块 | 能力 |
| --- | --- | --- |
| `stamp` | `standard_execution` | 库存、工单、工人、标准执行 |
| `cnc` | `standard_execution` | 库存、工单、工人、标准执行 |
| `polish` | `standard_execution` | 标准能力和专用打印 |
| `warehouse` | `purchasing` | 库存、工单、工人、外购 |
| `assembly` | `assembly` | 库存、工单、工人、装配 |
| `qc` | `quality` | 工人、检验和放行 |

`GET /department-modules` 暴露当前部门、执行模块和能力清单。后端架构测试会
校验每项能力都有公开方法，并校验前后端能力声明完全一致。

## 前端

| 路径 | 职责 |
| --- | --- |
| `frontend/src/router/` | 组合公共路由和部门注册表生成的路由 |
| `frontend/src/permission/` | 登录后默认页面、权限和路由守卫 |
| `frontend/src/features/departments/` | 六个部门的路由、页面入口、权限和能力声明 |
| `frontend/src/features/production/api/` | 生产相关 REST 客户端 |
| `frontend/src/features/production/composables/` | 部门页面状态和用例协调 |
| `frontend/src/features/production/components/` | 库存、工单、质检、打印等组件 |
| `frontend/src/features/production/views/` | 部门页面装配 |
| `frontend/src/features/process-designer/` | 工程产品与流程设计 |
| `frontend/src/features/customer-orders/` | 客户订单 |
| `frontend/src/features/admin/` | 管理和 PMC 看板 |

部门能力现在实际驱动辅助路由、标签价格入口、装配选择策略和专用打印组件，
不再只是静态说明字段。

## 测试与边界清单

| 文件 | 职责 |
| --- | --- |
| `backend/tests/conftest.py` | 建立独立、无需生产配置的测试环境 |
| `test_module_architecture.py` | Router、模块 API、所有权、依赖、循环和前后端能力检查 |
| `test_work_order_progress.py` | 工单进度领域计算 |
| `test_query_boundaries.py` | 工资月份边界和装配批量查询回归 |
| `test_database_contract.py` | 可选 PostgreSQL 物理表与模块所有权契约 |
| `test_postgres_production_flow.py` | 可选 PostgreSQL 标准工艺→QC→装配→QC 全流程及事务回滚 |
| `modules/ownership.py` | 每张 ORM 表唯一所有者 |
| `modules/read_access.py` | 共享数据库联表读取的显式例外清单 |

每个 `descriptor.py` 还登记 `api_version`、主 `public_api` 和全部
`collaboration_apis`。`modules.registry.module_manifests()` 提供机器可读清单，
架构测试会比较清单与磁盘上的 `*_api.py`，漏登记或失效入口都会导致测试失败。
