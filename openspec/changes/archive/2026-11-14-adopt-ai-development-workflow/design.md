## Context

项目使用 FastAPI/SQLAlchemy、PostgreSQL、Vue 3/TypeScript。现有 modules/<name>/descriptor.py 声明接口及协作，ownership.py 声明表归属；scripts/check_backend.py 已有项目专用检查，应继续复用。

## Goals / Non-Goals

目标：文档职责唯一、OpenSpec 可用、三个检查工具有实际配置和可执行入口，检查不依赖应用配置或真实数据库，不增加测试。

非目标：迁移业务目录、改写业务规则、批量格式化、增加测试框架、修改部署或数据库重建流程。

## Decisions

1. README 只承担项目介绍、结构与使用入口；AGENTS.md 记录简洁操作规范；正式规范保存在 openspec/specs，变更保存 proposal/design/tasks/specs。删除旧整改和重复说明，无额外历史文档体系。
2. OpenSpec 使用项目本地 npm 开发依赖和 spec-driven schema，以自然语言工作流接入 AGENTS.md，避免安装全局工具或生成多套 AI 工具文件。
3. Ruff/Deptry/Import Linter 放在独立 Python 开发依赖文件和项目虚拟环境。Ruff 从基础错误、无用代码和语句规范开始；不自动格式化全仓库。
4. Deptry 读取唯一运行依赖清单，声明实际本地模块及包名映射；仅豁免通过命令启动的 uvicorn 未导入告警。清理确认无实际用途的依赖，不用全局忽略掩盖问题。
5. Import Linter 约束领域/契约纯净、模块不得反向依赖入口、业务模块无循环、各模块 persistence 只由自身导入。descriptor 专用公开 API 校验继续由现有脚本负责。
6. 现有脚本去除应用导入，递归扫描 Python、校验语法，修正前端公共入口判断。根 check 仅组合静态工具和 OpenSpec 校验；前端类型及构建保持独立命令。

## Risks / Trade-offs

- 文档压缩可能遗漏业务边界：从原项目规则提取当前有效基线，并在删除旧文件前核对。
- 新检查可能发现旧问题：只修复接入所必需的问题，保持业务语义，不添加广泛忽略。
- 依赖安装需要网络；只安装到项目内，不修改全局环境。失败时如实记录实际可用范围。
- 静态检查不能证明实际运行或数据库并发正确性；最终报告必须明确证据范围。

## Implementation Order

1. 记录本方案，编写当前规范和精简项目文档。
2. 加入开发工具、配置和检查入口，修复必要静态问题。
3. 执行无缓存静态检查、OpenSpec 校验及差异审查，更新任务和结果。

## Review

逐项核对文档、命令和工具配置一致；确认业务目录/接口/SQL无无关变化，检查入口不导入应用、不连接数据库。按代码规范、模块耦合和稳定性给出源码及工具检查证据；不增加或运行测试。
