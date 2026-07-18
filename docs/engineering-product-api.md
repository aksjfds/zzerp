# 生产标记接口

`flow_json` 只配置宏观工艺节点和正常流向，不配置 QC、标记或标记顺序。

## 标记与横栏

- `GET /procedures/{procedure_id}/tags`：返回工艺下已有的标记名称建议。
- `GET /departments/{department_code}/production-items/{production_item_id}/tag-cards?flow_node_id={node_id}&source_flow_node_id={source_node_id}`：返回所选配件当前位置的标记组合横栏。

横栏返回 `tag_set_id`、`tag_ids`、`tag_names`、`tag_set_name`、具体来源库存 ID，以及加工中、质检中和已完成数量。未打标记卡片的 `tag_set_id` 为空。

## 工单

`POST /work-orders` 接收且只接收一个来源：

- 未打标记来源：`repository_id`；
- 已有组合来源：`procedure_tag_stock_id`。

标准工艺还必须提交非空 `tag_names: string[]`、正整数数量和可选工人；一张工单最多新增 20 个标记。服务会先去除首尾空白和重复名称，再复用或创建标记，将这些标记保存为本次新增集合，并生成“来源集合 ∪ 本次新增集合”的目标集合。任一新增标记已在来源组合中时拒绝开单。外购入库提交空数组。

`GET /departments/{department_code}/work-orders` 可用 `production_item_id`、`flow_node_id`、`source_flow_node_id` 和 `target_tag_set_id` 筛选目标组合工单。

标准生产工单通过 `POST /work-orders/{id}/submissions` 和 `completion_action = qc` 创建首次送检批次，送检不会自动结单。`POST /work-order-batches/{batch_id}/rework-submissions` 把该 QC 批次尚未处理的返工数量重新送检，并在原工单下创建关联子批次。`POST /work-orders/{id}/complete` 由生产部门主动结单；存在待检或待返工数量时拒绝，尚未首次送检的剩余数量按无需 QC 直接完成。

## QC 与出货

QC 不在产品流程中配置。合格数量进入目标组合；标准生产工单的返工数量回到原工单加工中，不进入公共库存，也不改变工单状态；报废和遗失离开生产。

`POST /procedure-tag-stocks/{tag_stock_id}/dispatches` 从一个非空已完成标记组合出货，并沿宏观工艺的正常边进入下一节点。未打标记数量不能出货。
