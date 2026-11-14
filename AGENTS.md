# AI 开发约束

## 阅读入口

- README.md：项目介绍、目录与命令。
- openspec/specs/mes/spec.md：当前业务基线。
- openspec/specs/development-workflow/spec.md：开发和架构规范。
- openspec/changes/<change>/：当前变更的 proposal.md、design.md、tasks.md 和规范差量。

以当前用户明确要求为准。只保留现行规则，避免另建重复业务说明或历史整改长文。

## 编码实现

1. 先阅读真实代码、调用方和现有公共接口，确认需求及影响范围。
2. 新功能、跨模块/跨层修改、数据库或公共接口变更使用 OpenSpec；先完成提案、规范、设计和任务，再按任务实现。用户已授权的范围直接推进，不重复请求确认。
3. 小型修复沿用已有实现，直接修改并说明原因；业务规则变化仍需更新规范。
4. 小范围修改、复用已有代码、明确命名与副作用。函数和组件职责单一，复杂流程按业务步骤组织。
5. 不添加无实际用途的抽象、依赖、兼容层、静默回退或临时绕过；不顺便重构无关代码。
   跨模块数据使用明确值类型；命令、分页查询、序列化与纯算法保持职责清晰。Ruff 复杂度上限使用默认10，前端启用未使用声明检查，不按现有实现放宽规则。
6. 不引入自动化测试、测试框架、测试目录或测试任务；OpenSpec Scenario 只描述预期行为。
7. 用无缓存静态检查和代码审查核对实现；范围内问题全部解决且证据齐备后，才能勾选任务完成。缺少条件如实说明。
8. 完成后同步当前规范，按 OpenSpec 归档变更；最终说明修改内容、原因和代码规范/低耦合/稳定性审查结论。

OpenSpec 命令通过 pnpm run spec 调用：new change <name> 建立变更，instructions <artifact> --change <name> --json 获取 proposal/specs/design/tasks 指引，instructions apply --change <name> --json 获取实施任务。完成后 validate <name> --strict，再 archive <name> --yes；归档不跳过规范同步。

## 模块边界

- 后端位于 backend/src/zzerp。单模块入口：HTTP Router → Database.query/command → modules/<name>/api.py → 模块内部 → 数据库。
- 跨模块入口：HTTP Router → Database.query/command → application → 各模块 api.py。契约从 contracts.py 导入，不经多种旁路端口。
- 表归属由 modules/ownership.py 声明。只由所属模块构造或修改 ORM，不导入其他模块 persistence。业务函数显式接收 Session，事务由执行器提交或回滚；不创建全局会话、引擎或读取应用配置。
- engineering 拥有产品、共用BOM、命名外观、各外观图和当前投影；planning 拥有计划、产品/外观明细、工单、流水和交接；organization 拥有部门；sales 拥有客户；identity 拥有账号与会话。
- application/engineering.py 注入 planning 引用查询，避免 engineering → planning 反向依赖。
- 所属模块 api 可提供有明确列类型的只读标量 Select，供同库子查询组合；不导出 ORM 类/实例，不在调用方修改查询所有者的表。部门/产品筛选不得先加载全局数据再构造 Python IN 集合。
- 纯规则与契约归属业务模块；纯规则不依赖框架、数据库或配置，业务模块不得反向依赖 HTTP 或 application。应用工厂管理资源生命周期。
- 前端跨 feature 经目标 index.ts；shared 不依赖业务 feature、不持有部门或配件业务状态；路由是组合根。
- 不恢复旧顶层 services/repositories/models、旧扁平导入或重复模块注册元数据。工程页面拥有自己的草稿，请求取消与分页由 shared/query 统一处理。
- zzerp.sql 是唯一开发重建基线；优先关系与简单数量约束，SQL 不解析流程图、不复制完整业务状态机。

## 检查与操作权限

- 允许读取、搜索、修改项目文件以及无外部连接、无缓存和无持久化副作用的静态审查。
- 开发环境就绪后，可执行 pnpm run check 或其中独立检查；它们不包含构建、服务、数据库和测试。
- 不使用自动修复/格式化命令，除非用户当前请求明确授权；根据检查结果手动做必要修改。
- 安装依赖、其他项目脚本、构建、启动/停止服务、数据库、网络或 Git 写操作，须有当前用户明确授权。引入指定工具的授权仅覆盖所需开发依赖与官方资料，不扩大到其他操作。
- 不修改本轮无关改动，不读取或输出密钥，不将真实数据库用于检查。
- 检查失败必须解决或如实报告；不得增加广泛忽略、禁用规则或把本轮问题转交下一轮。
