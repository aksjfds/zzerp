## MODIFIED Requirements

### Requirement: 复用现有仓库边界
项目 SHALL 保持模块化单体，但目录与实现可按已授权质量目标重组，不保留旧导入兼容。后端使用zzerp原生包；各业务模块以api.py公开行为、contracts.py公开契约，只有所属模块操作ORM。HTTP经统一执行器调用api或application跨模块编排；命令提交完成后才返回HTTP成功，跨模块流程使用同一Session。纯规则归属所属模块，不依赖HTTP、数据库或应用配置。前端跨feature经index，shared不拥有业务状态；每个页面草稿只有一个拥有者，公共请求负责取消与失效。

#### Scenario: 需要工程查询计划引用
- **WHEN** 工程操作需要校验已有计划引用
- **THEN** application/engineering.py 注入 planning 公开查询接口，避免 engineering 反向依赖 planning

#### Scenario: 跨模块工程命令
- **WHEN** 工程修改需要校验已有计划引用
- **THEN** application在同一Session中调用两模块api，不建立独立嵌套事务，不修改他人ORM

## ADDED Requirements

### Requirement: 显式资源与状态所有权
项目 SHALL 在应用工厂显式建立配置和数据库资源，退出时释放引擎；导入业务模块不创建连接资源或加载环境配置。业务操作显式接收Session，不使用全局SessionLocal。前端工程编辑由页面控制器与草稿模型拥有，列表通过公共可取消分页查询，不建立无消费者详情镜像或复制生命周期代码。Python格式、导入排序和现代语法纳入检查，不放宽复杂度上限。

#### Scenario: 页面切换或命令失败
- **WHEN** 请求未完成时页面切换，或数据库命令提交失败
- **THEN** 旧请求不能写入新页面，失败命令回滚并且不会先返回成功响应
