# Engineering product API contract

## Error response

Product-domain and request-validation failures use one response shape:

```json
{
  "detail": {
    "code": "bom_part_no_conflict",
    "message": "BOM 配件编号重复：Z8412-01",
    "path": "bom_items.1.part_no"
  }
}
```

`code` is stable for programmatic handling. `message` is user-facing. `path` is optional and identifies the
invalid request field or domain object.

## Write boundaries

- `POST /products`: create product base information and its initial BOM.
- `PUT /products/{product_id}`: update product base information only.
- `PUT /products/{product_id}/bom`: replace the complete ordered BOM.
- `PUT /products/{product_id}/process-flow`: replace the complete process flow.
- `DELETE /products/{product_id}`: delete the product, BOM and process flow.

Product responses include a business `version` and an integer `revision`. Every update body must send the
latest revision as `expected_revision`. Delete sends it as the `expected_revision` query parameter. Each
successful write increments `revision`; creating a product version increments the business `version`. A stale
write is rejected with `product_version_conflict` instead of overwriting another user's changes.

Product versions are persisted in the `product_version` registry. BOM rows, process-flow documents, and customer
order items reference `(product_id, product_version)` through database foreign keys, so an order cannot reference
a version that does not exist.

The split prevents newly inserted BOM rows and their generated IDs from being mixed with stale process-flow
references in one request.

Once any customer order references a product, its shared base information is frozen so historical orders do not
silently display renamed products or factory codes. BOM and process-flow data are frozen per business version;
create a new product version before changing either section.

## Process-flow version

Every process-flow document must contain:

```json
{
  "schema_version": 2,
  "nodes": [],
  "edges": []
}
```

The persisted JSON is the stable business graph contract for schema version 2. Unsupported versions are rejected.
LogicFlow's native camelCase graph data is converted at the frontend boundary and is not used as the API or
database contract.

Node types are `part`, `process`, and `assembly`. Every edge represents a normal macro-process transition;
QC outcomes and rework routes are not part of the product flow. Whether completed substep work is sent to QC is
chosen during production, but QC never receives a configurable qualified-product destination. Validation errors may
include `element_id`, allowing the editor to focus the invalid node or edge.

A `process` node references a macro `procedure`. Its reusable `procedure_substep` names and internal-substep stock
are production dictionary/state data and are deliberately not embedded in the product flow document.

Substeps are chosen when work orders are opened:

- `GET /procedures/{procedure_id}/substeps` returns reusable name suggestions for the selected procedure.
- `POST /work-orders` accepts `substep_name` together with exactly one source ID, quantity, and optional worker.
  The service trims the name, reuses an existing same-procedure row, or creates a new dictionary row atomically.
  It also copies that source row's `source_flow_node_id` into the work order as an immutable provenance snapshot;
  assembly work orders expose null because they combine multiple sources.
- There is no route-configuration `PUT`: substeps have no fixed order, active state, stage range, or configured next
  step. Customer-order confirmation therefore does not depend on a preconfigured first substep.

`POST /work-orders/{work_order_id}/submissions` accepts `quantity` and
`completion_action = direct | qc`; it does not accept `continuation_action` or `next_substep_name`:

- For a standard procedure, `direct` always creates or increases internal stock whose `completed_substep_id` is the
  current work order's substep. It does not leave the macro process and does not create another work order.
- For `qc`, the submission creates a pending batch and stores the source node and nullable source substep needed for
  later rework. The client supplies no qualified destination.
- Purchase-receipt work orders retain their fixed destination: direct receipt advances immediately to the normal
  macro target, and qualified receipt advances there after QC. Assembly remains direct-only.

`POST /qc/work-order-batches/{batch_id}/inspection` accepts only the QC worker, qualified/rework/scrap/lost
quantities, and optional defect reason. For a standard procedure, qualified quantity always joins the current work
order substep's completed stock. Rework returns to the exact source recorded by the batch; scrap and loss leave
production. No next work order is created by QC.

Selecting a parent production card loads its execution positions through:

`GET /departments/{department_code}/production-items/{production_item_id}/substep-cards?flow_node_id={node_id}&source_flow_node_id={source_node_id}`

The response begins with a virtual `未{工艺名}` position and then returns substeps evidenced at the requested macro
position by current stock, pending QC, or any non-cancelled historical work order carrying the same immutable source snapshot.
Consequently, a substep used at that position remains as a zero-quantity card after its active quantities are
exhausted. Used substeps are ordered by their first work-order ID, with substep ID as the fallback for stock that has
no order. The envelope is `{ "data": [...] }`. Each card contains
`card_key`, production/flow/procedure identity, nullable `substep_id`, `repository_id`, and `stage_stock_id`,
`substep_name`, `available_quantity`, `processing_quantity`, `pending_qc_quantity`, `completed_quantity`,
`can_create_work_order`, `can_submit_qc`, and `open_work_orders`. Completed availability excludes quantities reserved
by later open work orders. Each open-order summary contains its ID, number, worker identity, total quantity, and
processing quantity for status projection. The actual `送检` action is rendered on the corresponding work-order card,
so its submission calls the selected work-order ID directly. The unprocessed card has null substep/stage-stock IDs
and the display name `未{工艺名}`.

The work-order list can be isolated to the same selected parent position through:

`GET /departments/{department_code}/work-orders?production_item_id={item_id}&flow_node_id={node_id}&source_flow_node_id={source_node_id}&substep_id={substep_id}`

All filters are optional. `source_flow_node_id` filters the immutable source snapshot, rather than a repository or
stage-stock reference that may have been released. Every work-order response includes `source_flow_node_id`: it is
non-null for a substep order and null for an assembly order. The parent-card, substep-card, and work-order queries
therefore use the same exact production position without mixing otherwise identical arrivals from different sources.
Stage-stock arrival dates are likewise ranked within the snapshot source position; QC rework uses its batch source
snapshot.

Leaving a standard macro procedure is explicit:

`POST /procedure-stage-stocks/{stage_stock_id}/dispatches`

```json
{
  "quantity": 12
}
```

The selected stage stock must belong to the caller's department, represent completed stock at a standard procedure,
and have enough unreserved quantity. The service consumes it, follows the process node's normal target, and records a
standalone `procedure_dispatch` movement without work-order or QC-batch references. Raw `未{工艺名}` repository
quantity cannot be dispatched, so the action cannot bypass the macro procedure. The response reports stage-stock,
production-item, and substep identity, dispatched quantity, and nullable target node/department identity.

For a non-empty flow:

- each part node references a valid BOM row, and a BOM row appears at most once;
- each part node connects directly to exactly one first process node;
- all nodes belong to one connected graph;
- edges form a directed acyclic graph;
- assembly nodes have at least two inputs.

An empty flow remains valid while the product is still a draft.
