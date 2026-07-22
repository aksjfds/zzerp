# 生产标记接口

## 客户与产品

- `GET /customers?keyword=`：工程部和业务部查询共用客户主数据。
- `POST /products`：提交已有 `customer_id`，或提交空的 `customer_id` 和新 `customer_name`；后一种情况会在创建产品的同一事务中新增客户。
- `GET /products?customer_id=`：按客户筛选产品，业务部创建订单时使用。
- `POST /customer-orders`：必须提交 `customer_id`，且所有订单明细产品必须属于该客户。
- `GET /customer-orders?include_progress=true`：供 PMC 看板返回每个订单产品的总数、完工、报废、遗失、未完工和欠 PO 数量；普通订单列表不请求时不执行进度统计。

产品和订单响应继续返回 `customer_name` 供界面展示，但客户名称以 `customer` 表为唯一来源。

`flow_json` 使用 schema v3 配置配件、工艺、独立 QC、装配、发货节点及正常流向。生产标记及标记顺序不在流程图中配置。BOM 配件节点的首个执行节点可以是工艺节点，也可以直接是装配节点。QC 上游可以是工艺或装配，下游可以是工艺、装配或发货；发货必须是流程终点且上游必须是 QC。跨部门流转和所有标准打标工艺都必须经过 QC。

## 标记与横栏

- `GET /procedures/{procedure_id}/tags`：返回工艺下已有的标记名称建议。
- `GET /departments/{department_code}/production-items/{production_item_id}/tag-cards?flow_node_id={node_id}&source_flow_node_id={source_node_id}`：返回所选配件当前位置的标记组合横栏。

横栏返回 `tag_set_id`、`tag_ids`、`tag_names`、`tag_set_name`、具体来源库存 ID，以及加工中、质检中和已完成数量。未打标记卡片的 `tag_set_id` 为空。

## 工单

`POST /work-orders` 接收且只接收一个来源：

- 未打标记来源：`repository_id`；
- 已有组合来源：`procedure_tag_stock_id`。

标准工艺还必须提交非空 `tag_names: string[]`、正整数数量和可选工人；一张工单最多新增 20 个标记。名称必须属于当前产品版本、配件来源节点在 `procedure_tag_price` 中预先配置的必做标记，装配输出也可作为配件来源。服务去除首尾空白和重复名称后，将这些标记保存为本次新增集合，并生成“来源集合 ∪ 本次新增集合”的目标集合。任一新增标记已在来源组合中或超出预配置集合时拒绝开单。外购入库提交空数组。

`GET /departments/{department_code}/work-orders` 可用 `production_item_id`、`flow_node_id`、`source_flow_node_id`、已有标记 ID 和本次新增标记 ID 筛选工单。

标准生产工单只能通过 `POST /work-orders/{id}/submissions` 和 `completion_action = qc` 创建首次送检批次；流程中缺少独立 QC 节点时拒绝执行，项目不提供绕过 QC 的直接结单接口。非最终标记的合格数量形成目标组合，最终标记的合格数量由 QC 通过 `POST /qc/work-order-batches/{batch_id}/dispatch` 放行。`POST /work-order-batches/{batch_id}/rework-submissions` 把标记或装配返工数量再次送到 QC。全部数量已经处理且没有待检、待返工数量后，系统自动结单。

## QC 与出货

非最终标记工单的合格数量立即进入目标标记组合，不等待工单结单。最终标记工单的合格数量停留在独立 QC 节点，通过 `POST /qc/work-order-batches/{batch_id}/dispatch` 分批放行到 QC 后续节点；放行不依赖工单状态。返工数量回到原工单加工中，报废和遗失离开生产。

`POST /procedure-tag-stocks/{tag_stock_id}/dispatches` 不再允许标准标记库存绕过 QC 出货。QC 放行到 `shipping` 节点时表示实体已发货，不生成新的生产库存。
