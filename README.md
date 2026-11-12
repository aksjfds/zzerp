# zzerp v6

zzerp MES 是基于 FastAPI、PostgreSQL 和 Vue 的模块化应用，保留工程产品版本、
BOM、流程图与统一生产计划。客户订单和原生产计划已合并：创建计划填写客户、
订单号、订单数量、产品和生产数量，只关联产品，不绑定工程版本。
流程图由配件节点和部门节点组成，连线表达路线。创建计划时按物料路线生成部门工单；
普通配件按生产数量乘 BOM 用量安排，激光/装配汇合后的装配体按生产数量安排并自动命名。
九个生产部门使用独立账号，只能查看和操作各自工单；支持独立分批登记到料/出料、累计数量和流水查询，无任务数或到料限制、不自动转入下游。已有流水不可删除，计划不能再重建工单。新增配件自动填写厂编加递增后缀。不保存配件或路线快照。后端模块通过公开 API 协作。
生产账号用户名为部门代码（stamp、cnc、grinding、outsource、vibration、laser、assembly、purchase、finished），
开发基线初始密码沿用 1。工单范围由后端按认证部门强制限定，工程/业务账号保留原权限。

## AI 与 Agent 项目原则

稳定 + 规范 + 低耦合 + 尽量无性能损失。

所有修改必须基于当前真实代码和实际问题，优先采用可回退、可验证、职责边界
清晰的实现；不得为了局部性能提升破坏稳定性、正确性、兼容性或代码结构。

## 数据库职责

`zzerp.sql` 是开发阶段唯一的破坏性重建基线，负责表结构、关系约束、必要的
并发完整性底线以及初始化数据。SQLAlchemy ORM 必须与其保持一致，但不作为
第二套结构来源。完整业务状态转换由后端领域模块负责，不在数据库触发器中
重复实现。

数据库函数不解析流程图或选择节点。数据库保留关系、数量与格式约束，
触发器维护通用更新时间、流水不可变及已登记工单来源保护；流程图结构、节点引用及可达关系由后端统一校验。

初始化数据分为系统必需基础数据和可删除开发示例数据；数据库重建由用户执行。

## 开发环境

```bash
python3 -m pip install -r backend/requirements.txt
pnpm --dir frontend install
pnpm run check
```

`pnpm run check` 会执行后端架构一致性检查、前端类型检查和生产构建。后端检查会在不连接数据库的前提下核对应用导入、表所有权、模块公开接口、未声明依赖、循环与局部导入、SQL/ORM 的表/字段/约束/索引名称，以及前端 shared 和 feature 导入边界。AI 或 Agent 默认只做代码规范、模块耦合和稳定性审查；只有用户当前请求明确要求时才执行构建或项目脚本。

AI 或 Agent 只有在用户当前请求明确授权后才能执行安装、构建、项目脚本或数据库操作；具体限制以 `AGENTS.md` 为准。

## Docker 开发

```bash
docker compose up -d --build app
docker exec -it app bash
pnpm f
```

Compose 会为容器创建独立的 `frontend/node_modules` 数据卷，并按照容器的
Linux 架构自动安装锁文件中的依赖。不要把宿主机的 `node_modules` 直接共享给
容器；Vite/Rolldown 等工具包含平台相关的原生二进制。开发镜像固定使用
Python 3.12 和 Node 22，并在构建阶段安装 `backend/requirements.txt`；
后端依赖变更后再次执行带 `--build` 的启动命令即可。

## 部署

Render 后端和 Netlify 前端的仓库配置分别见 [render.yaml](render.yaml) 与
[netlify.toml](netlify.toml)。数据库密钥只配置在托管平台环境变量中，不写入仓库。

## 文档入口

- [项目介绍、业务流程与目录职责](PROJECT_OVERVIEW.md)
- [AI 与 Agent 协作规范](AGENTS.md)
- [大型整改方案与执行记录](MODIFICATION.md)
