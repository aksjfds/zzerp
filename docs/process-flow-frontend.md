# Process-flow frontend boundaries

- `domain/types.ts`: stable API and application-domain types; it has no LogicFlow field names.
- `logicflow/adapter.ts`: the only data conversion between the business graph and LogicFlow graph data.
- `logicflow/commands.ts`: imperative editor commands such as adding part, process, and assembly nodes.
- `composables/useLogicFlowInstance.ts`: creates and destroys the LogicFlow instance and translates events.
- `components/ProcessFlowCanvas.vue`: thin canvas API exposed to its coordinator.
- `components/ProcessNodePalette.vue`: BOM and node creation controls.
- `components/ProcessPropertyPanel.vue`: process and assembly property editing.
- `components/ProcessFlowEditor.vue`: coordinates the components and exposes business-level save/reload methods.

LogicFlow-native camelCase properties must stay inside the adapter, commands, canvas, and instance composable.
API clients, stores, views, and the database use the versioned snake_case business graph.
Schema version 2 contains only `part`, `process`, and `assembly` nodes. Edges represent normal
macro-process transitions and do not carry QC outcomes or rework routes. Whether completed work is
sent to QC is selected during production rather than configured in the product flow. QC records quantities only;
there is no qualified-product destination control.
Process nodes select macro `procedure` definitions only. The property panel has no substep-route editor, because
substep order is decided during production and is not global product configuration.

The standard-production workspace has two levels:

1. The left parent production/repository column lists one selected component at each exact macro-process position. It does
   not repeat the same component once for repository input and again for every internal substep stock row. Its only
   production action is `出货`.
2. The right execution area places a horizontal substep bar above the work-order area. The bar appears after a parent
   card is selected, begins with `未{工艺名}`, and then shows one card for
   every substep actually used by that component, such as a single `粗1` card containing `粗1进行中`, `粗1待检`, and
   `粗1完`. Only `开工单` lives on these cards. The work-order area below shows the selected substep's details and
   history. Direct completion
   and `送检` are actions on the exact open work-order card. Direct completion always adds to the current substep's
   completed quantity.

Substep quantities must not overlap. `未{工艺名}` is repository quantity minus open-order reservations;
`{substep}进行中` is the remaining quantity of open work orders targeting that substep; `{substep}待检` is the
submitted quantity in pending QC batches; `{substep}完` is stage-stock quantity minus reservations held by later
open work orders. A reserved quantity therefore moves visually from the source card's completed amount to the target
card's processing amount instead of appearing twice. The unprocessed card is always first. Other cards come from
current stock, pending QC, and all non-cancelled work orders whose immutable `source_flow_node_id` snapshot matches the selected
parent position. An actually used substep therefore remains visible as a zero-quantity card after active state is
exhausted. Used substeps are ordered by their first work-order ID, not by the reusable suggestion dictionary.

`开工单` uses the clicked card as the source. The unprocessed card supplies its repository ID; a completed-substep
card supplies its stage-stock ID. The dialog accepts a free-form target substep name, quantity, and worker, and may
show reusable names as suggestions. `送检` is shown on each open work-order card; clicking it only asks for the
quantity because the work order is already unambiguous. There is no `配置路线` button, stage-range slider, fixed
next-step picker, or automatically created next order.

Selecting a parent sends its production-item, flow-node, and source-flow IDs to both the substep-card and work-order
queries. Selecting a substep adds its ID to the work-order query. The work-order response's nullable
`source_flow_node_id` is the stable source-position snapshot: substep orders always provide it and assembly orders do
not. This keeps the three columns aligned even after the source repository or stage-stock row has been consumed.

The QC inspection dialog contains worker, result quantities, and defect reason only. Qualified standard-process
quantity returns to the same substep card's completed amount; rework returns to the recorded source; scrap and loss
leave production. It has no `合格品去向` or next-substep fields.

The parent card's `出货` dialog lists completed substep positions with unreserved stock, selects one source and a
positive quantity, and calls `POST /procedure-stage-stocks/{stage_stock_id}/dispatches`. Dispatch advances that stock
along the macro process's normal edge. The action is disabled when no completed substep has available stock, and the
unprocessed repository position cannot be used to bypass the procedure. Purchase-receipt and assembly workspaces keep
their existing specialized behavior.

Internal-substep stock remains production execution state and is not editable in the process-flow designer.
Complete process-flow validation is owned by the backend domain service. The frontend only
enforces editor interaction constraints and displays structured validation errors returned by
the save API, preventing a second rule implementation from drifting over time.
