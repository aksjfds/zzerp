## ADDED Requirements

### Requirement: 精简文档与规范驱动实现
项目 SHALL 以 README.md 介绍项目、AGENTS.md 约束 AI 编码、openspec/specs 保存当前规范、openspec/changes 保存变更。新增功能、跨模块/跨层修改、数据库或公共接口变更先阅读代码，再形成 proposal、specs、design、tasks，按任务实现并同步规范；小修复保持最小范围。范围内问题有实际证据后才标记完成，归档只保存该变更必要的结果，不恢复旧整改长文档。

#### Scenario: AI 接到跨模块修改
- **WHEN** 用户授权修改涉及多个业务模块
- **THEN** AI 先记录基于真实代码的目标、非目标、边界、执行顺序、风险和任务，再实现；已授权范围不重复请求批准

### Requirement: 复用现有仓库边界
项目 SHALL 保持模块化单体和现有目录。Router 调用模块 api.py；跨模块应用流程由 application 编排。模块协作使用 descriptor 声明的公开接口，ORM 归属以 ownership.py 为准；禁止跨模块内部导入、构造/修改他人 ORM、循环及模块反向依赖入口。domain 保持纯算法，schemas 保持契约。前端跨 feature 经 index.ts，shared 不依赖 feature。避免无用抽象、重复实现、无关重构和广泛忽略检查。

#### Scenario: 需要工程查询计划引用
- **WHEN** 工程操作需要校验已有计划引用
- **THEN** 复用 application/engineering.py 注入 planning 窄查询接口，避免新增 engineering → planning 依赖

### Requirement: 三类 Python 质量约束
项目 SHALL 使用 Ruff 检查基础错误、无用代码及语句规范；使用 Deptry 检查运行依赖声明；使用 Import Linter 约束领域/契约纯净、模块依赖方向、无循环及 ORM 归属。开发工具独立于运行依赖，使用项目虚拟环境；OpenSpec 使用项目本地 npm 开发依赖。仅对有实际依据的例外精确说明，不用全局禁用绕过违规。

#### Scenario: 引入新的 Python 依赖或模块引用
- **WHEN** 实现增加第三方库或跨模块导入
- **THEN** 依赖与实际用途一致，导入符合已声明接口和架构契约，检查发现问题时必须修正

### Requirement: 静态检查与操作隔离
项目 SHALL 提供统一 check 入口，组合 Ruff、Deptry、Import Linter、项目专用架构/SQL与ORM名称一致性检查、前端类型检查和 OpenSpec 严格校验。检查不导入应用、不读取数据库配置、不连接数据库、不生成构建产物或检查缓存。前端构建、服务、数据库重建分别执行，不因检查自动触发。

SQL/ORM 名称一致性检查 SHALL 明确只核对表/字段/命名约束/索引名称，不宣称验证约束语义或数据库运行行为。项目专用脚本递归检查后端语法与模块依赖，前端允许公共 index.ts 入口并拒绝跨 feature 内部路径。

#### Scenario: 环境没有数据库配置
- **WHEN** 已安装开发依赖，运行静态质量检查
- **THEN** 检查仅分析项目文件，不加载后端应用，不要求数据库可用

### Requirement: 不引入自动化测试
本轮及后续默认开发流程 SHALL 不引入测试框架、测试目录、测试命令或测试阶段。OpenSpec Scenario 为验收描述；交付依据为代码规范、低耦合、稳定性源码审查与实际静态检查结果。构建、数据库并发和运行验收未经执行时不得宣称通过。

#### Scenario: 生成实施任务
- **WHEN** AI 为变更生成任务与完成报告
- **THEN** 列出实现、静态检查和审查证据，不自动添加测试任务，不用静态通过代替运行验证
