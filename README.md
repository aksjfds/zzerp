# zzerp MES

面向生产安排与部门交接的 MES，使用 FastAPI、SQLAlchemy、PostgreSQL、Vue 3、TypeScript 和 Element Plus，采用模块化单体。

## 业务范围

- 工程维护产品共用 BOM 和命名外观，每种外观独立维护配件/部门流程图；正式图生成对应外观路线投影，草稿不生成工单。
- 计划按客户与唯一订单号组织产品及外观，同产品不同外观分行填写订单数量和生产数量；按各外观正式路线生成部门工单，交接按外观隔离。
- 九个生产部门独立登录，只能查看和登记本部门工单；内部出料生成交接票，下游按票分批到料。
- 激光/装配汇合形成装配体，数量按 BOM 齐套折算；流水与交接历史只追加。
- 业务账号按订单查看生产进度；不提供库存、QC、工资、车间或收发货功能。

完整现行业务规则见 [MES 规范](openspec/specs/mes/spec.md)。

产品使用命名外观管理，共用 BOM、分别维护流程。旧产品版本数据库与接口已移除，需由用户按当前 `zzerp.sql` 重建；不自动迁移。`revision` 仍用于并发校验，`schema_version` 仍用于图格式，两者均不作为产品版本展示。

## 仓库结构

```text
zzerp/
├── README.md                 # 项目介绍与使用入口
├── AGENTS.md                 # AI 编码与审查约束
├── pyproject.toml            # Ruff、Deptry
├── .importlinter             # Python 架构依赖约束
├── openspec/
│   ├── config.yaml           # 项目上下文与产物规则
│   ├── specs/                # 当前有效规范
│   └── changes/              # 每项变更的提案、设计与任务
├── backend/
│   ├── requirements.txt      # 运行依赖
│   ├── requirements-dev.txt  # 开发检查工具
│   └── src/zzerp/            # 唯一 Python 包，无根目录导入包装
│       ├── app.py            # 应用工厂与资源释放
│       ├── database.py       # 显式查询/命令事务执行器
│       ├── http/             # HTTP 依赖、授权与路由
│       ├── application/      # 跨模块同事务编排
│       └── modules/          # 五业务模块，各有 api/contracts/内部规则及持久化
├── frontend/src/
│   ├── features/             # 身份、工程和生产等业务，经 index.ts 对外协作
│   └── shared/               # 展示、几何、主题、可取消请求与分页，无业务状态
├── scripts/                  # 项目静态检查与显式数据库重建
└── zzerp.sql                  # 唯一开发重建基线
```

## 开发与检查

业务运行环境为 Python 3.12、Node.js 22.22.2+ 或 24.15+、pnpm。开发工具安装在项目本地：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pnpm install --frozen-lockfile
pnpm --dir frontend install --frozen-lockfile
pnpm run check
```

`check` 依次运行 Ruff（格式、导入、现代语法及默认复杂度上限10）、Deptry、Import Linter、后端包/端口及 SQL/ORM 声明检查、前端严格类型/导入边界检查和 OpenSpec 规范校验；不导入后端应用，不连接数据库，不生成构建产物或检查缓存。不包含自动化测试。

数据库检查核对表归属、字段与命名约束、CHECK表达式、外键列/目标/删除及延迟选项、唯一键和索引表达式/顺序/覆盖列/条件；同时检查SQL函数定界和固定search_path。这是静态声明核对，不替代PostgreSQL语法解析、执行计划或数据库并发验收。流水索引对应UTC秒级排序，订单搜索使用trigram；优化生效需按新基线重建数据库。

- 后端开发：`pnpm run b:dev`；前端开发：`pnpm run f:dev`。
- 生产构建独立执行：`pnpm run f:build:prod`。
- OpenSpec：`pnpm run spec --help`；AI 工作流程见 [AGENTS.md](AGENTS.md)。
- 数据库配置参考 `backend/.env.example`；重建由用户显式执行 `pnpm run b:reset-db`，会清空目标数据库。当前代码仅接受哈希密码，旧明文账号不能继续登录，需使用新 SQL 基线重建。开发种子账号密码仍为 `1`，SQL 只保存独立盐哈希。
- 后端使用 `zzerp.app:create_app --factory`，本地命令与 Render 已同步；查询会话、写事务和引擎释放均由应用管理。
- 部署配置见 `render.yaml`、`netlify.toml` 与 `docker-compose.yaml`；GitHub 数据库重建工作流仅允许手动触发。
