## Why

现有 Markdown 文档重复记录业务与历史整改，AI 容易读取过期规则；质量检查缺少统一的代码、依赖和架构约束。用户授权删除旧说明，采用精简项目介绍、AGENTS.md、OpenSpec、Ruff、Deptry 和 Import Linter，不引入测试。

## What Changes

- 保留并重写根 README，重写精简 AGENTS.md，删除其余旧 Markdown。
- 用 OpenSpec 当前规范和逐项变更任务替代 MODIFICATION.md；先记录设计，再实施。
- 安装项目本地开发工具，加入统一配置及不构建、不连接数据库的检查入口。
- 保留模块化单体与前端 feature 目录；仅修复新检查发现的必要代码问题。

## Capabilities

### New Capabilities
- `mes`: 保存当前工程、计划、部门与流水业务基线。
- `development-workflow`: 约束 AI 实现流程、仓库边界和静态质量检查。

### Modified Capabilities

无既有 OpenSpec capability。

## Impact

涉及文档、开发依赖、根工具配置、检查脚本和必要的静态问题修正。不增加自动化测试、业务功能或数据库结构；不运行构建、服务、数据库或 Git 写操作，不改变现有部署和重建工作流。
