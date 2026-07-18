# Database design notes

## Process and execution hierarchy

- `procedure` remains the macro process definition referenced by `flow_json` process nodes. It answers which
  department owns a process, but it is no longer the unit used to open a work order.
- `procedure_substep` is a small reusable name dictionary under a procedure. It has no code, active flag, stage
  interval, or configured successor. When opening a work order, the operator may enter any non-empty substep name;
  the service reuses the same-procedure name when it exists and creates it when it does not.
- `procedure_stage_stock` stores quantities that completed one custom substep but have not left the macro process.
  It keeps the production item, macro flow position, source-flow provenance, department, `completed_substep_id`, and
  quantity. The completed substep identifies the current display position and the source that may be used to open a
  later substep work order or dispatch from the macro process. Its procedure is obtained through
  `procedure_substep` rather than copied into the stock row.
- `repository` continues to represent quantities at macro flow nodes. Internal-substep quantities are kept in
  `procedure_stage_stock`, so `repository` and `production_movement` need no additional substep columns.

## Work-order ownership and completion

- `work_order` is substep-centric. The former procedure columns are reused as `substep_id`, `work_order_type`, and
  `work_order_name`. A normal work order consumes exactly one source while open: either a repository row or a
  procedure-stage stock row. `source_flow_node_id` is an immutable provenance snapshot copied from that source when
  the work order is opened. Once the order is no longer open, its repository/stage-stock reference may be cleared so
  an exhausted positive-quantity source row can be removed, while the snapshot continues to identify the exact
  `(production_item_id, flow_node_id, source_flow_node_id)` execution position. Assembly orders keep both substep and
  source-flow snapshots null because they combine multiple material positions.
- `work_order_name` snapshots a display name such as `粗光-粗1`. Historical work orders therefore remain readable
  after procedure or substep names change.
- `work_order_batch.source_flow_node_id` copies the work order's source-flow snapshot when quantity is submitted.
  `work_order_batch.source_substep_id` is null for repository input and snapshots the completed substep for internal
  stock input. Together they retain enough provenance to restore QC rework after the consumed source row is removed.
- `flow_json` schema version 2 contains only `part`, `process`, and `assembly` nodes. A process node references the
  macro `procedure`; QC nodes, QC edges, and outcome routes are not stored in the graph.
- For a standard procedure, direct completion always adds the completed quantity to
  `procedure_stage_stock` under the work order's own `substep_id`. It neither leaves the macro process nor opens
  another work order. A later substep is opened manually from that completed-stock position, with a new custom
  substep name, quantity, and worker selection.
- QC submission creates a pending inspection batch without any qualified-destination setting. For a standard
  procedure, qualified quantity always joins the same current-substep completed stock as direct completion. Rework
  returns to the repository input or exact prior `source_substep_id` recorded by the batch; scrap and loss leave
  production. Purchase-receipt routing remains fixed to its normal macro target, and assembly work orders remain
  direct-only.
- Leaving a standard macro procedure is a separate `procedure_dispatch` action. It consumes an explicitly selected
  `procedure_stage_stock` row and sends that quantity to the process node's normal target. The movement has no work
  order or QC batch because dispatch consumes completed stock rather than executing a substep. Its source stage-stock
  ID is command context and is not copied into `production_movement`.

## Production-card projection

- The first production column has one parent card per production item and exact macro position
  `(flow_node_id, source_flow_node_id, department_id)`. Repository input and all completed-substep stock at that
  position are not rendered as duplicate parent cards.
- Selecting a parent card loads a second column of substep cards. `未{工艺名}` is the unreserved repository input.
  Every substep actually used by that production item and flow node has one card that keeps its processing and
  completed quantities together. A separate pending-QC quantity remains visible because it is neither processing
  stock nor qualified completed stock.
- Quantities are non-overlapping: unprocessed is repository quantity minus open-work-order reservations; a substep's
  processing quantity is the remaining quantity of its open work orders; pending QC is the submitted quantity of its
  unrecorded batches; completed is its stage-stock quantity minus reservations held by later open work orders. A
  reservation removed from one card's completed count appears in the target substep's processing count.
- Substep cards are derived from current repository/stage stock, pending QC, and every non-cancelled substep work order whose
  immutable source snapshot matches the selected production position. They are not expanded from every reusable name
  under the procedure. `未{工艺名}` is always first. Every substep actually used at that exact position remains as a
  zero-quantity card after its stock, open order, and pending batch are exhausted, and used substeps are ordered by
  their first work-order ID (then substep ID for a stock-only fallback).
- `开工单` belongs to the substep column: the unprocessed card supplies a repository source and a completed-substep
  card supplies a stage-stock source. `送检` belongs to each open work-order card so the submitted order is
  unambiguous. The parent card's `出货` action selects completed stage stock and quantity, then performs
  `procedure_dispatch`.

## Integrity boundaries

- `product_version` is the registry for every product business version.
- BOM, process-flow, and customer-order references use composite product-version foreign keys.
- BOM sort positions are unique per product version and checked at transaction commit.
- Work orders snapshot `work_order_name`, `work_order_type`, and—only for substep orders—`source_flow_node_id` for
  historical stability and exact production-position filtering.
- Composite foreign keys require a work order or assembly material to reference a repository owned by the same
  production item. The work-order service validates that a selected substep belongs to the macro procedure being
  executed; assembly orders remain valid with a null substep ID.
- When a repository position is exhausted, all work-order and material-allocation references to that row are
  released before deletion. Immutable production movements remain the historical source-of-truth.
- QC batches reference the inspecting worker by ID and retain the worker name as a display snapshot.
- Production items store their locked product ID/version. Composite foreign keys require both the order item and
  optional BOM row to match that same version, without cross-table validation triggers or concurrency windows.
- QC-batch movements use `(batch_id, work_order_id)` as a composite reference. Submission quantity must match the
  batch, and QC result totals must match immutable movement history. The service owns the exact qualified/rework
  destination rule; the client does not configure a qualified destination.
- Submission movements require an open work order, and completed QC batches reject any later movement. Each
  assembly material has exactly one input movement whose quantity matches its allocation.
- Production movement fields follow an exact matrix for initial, submission, assembly-input, QC-output,
  procedure-dispatch, scrap, and loss records. Standard direct and qualified results always remain as current-substep
  stock; rework returns to its recorded source; only `procedure_dispatch` advances completed stock through the normal
  macro edge. A dispatch requires source node/department, requires target node/department to be both present or both
  absent, and forbids work-order and batch references. Execution movements cannot be updated or deleted; initial rows
  may be cascade-deleted only together with their production item so an unstarted customer order can still be
  cancelled.
- Once movements exist, work-order substep/source snapshots, batch source node/substep fields, completed QC results,
  and assembly material identity/quantity are frozen. A QC batch's source node is validated against the work-order
  snapshot rather than a source row that may already have been deleted; its nullable source substep is still validated
  against the referenced stage stock. Trigger reads lock work order, then batch/material rows in that order; composite
  foreign keys cover repository/stage-stock and batch ownership. The work-order service resolves or creates the custom
  substep under the macro procedure before creation, avoiding a separate procedure snapshot field.

## Time

Persisted timestamps use `TIMESTAMPTZ`. Services write UTC values and API presenters convert them to
`Asia/Shanghai`. Database triggers use the actual wall-clock time to maintain `updated_at` for products, BOM rows,
process flows, and customer orders, including changes made outside SQLAlchemy.

## Search and operational indexes

Product and BOM-part substring search uses PostgreSQL `pg_trgm` GIN indexes. Operational indexes cover product-version
references, reusable procedure-substep names, non-empty internal-substep stock, open work orders, worker activity time,
pending QC batches, exact work-order production positions with their first-used substeps, and latest movement at a
production position. The pending-QC index starts with descending batch ID to match global pagination. Work-order and batch
movement indexes exclude null references, and a partial unique index permits only one submission movement per QC
batch. Another partial unique index permits one assembly-input movement per work order and production item. Unique
BOM sort-order enforcement also serves version-and-order lookups, so it is not duplicated by a second index.
The same operational and search indexes are declared in both `zzerp.sql` and SQLAlchemy metadata.

Production-card source queries push arrival-date and product/part keyword filters into PostgreSQL. Parent positions
distinguish production item, target node, and source node, so normal and rework arrivals cannot overwrite one another.
Repository, stage-stock, open-work-order, and pending-batch quantities are projected into non-overlapping substep-card
counts as described above. Work-order snapshots keep parent cards, work-order lists, and substep history isolated by
that same exact source position even after an exhausted source row is removed. Stage-stock arrival timestamps use the
work-order source snapshot (or the QC batch snapshot for rework), so equal item/node/substep combinations arriving
from different sources do not share an arrival time. Historical latest-movement ranking is restricted to candidate
production positions, including source-flow provenance, before card hydration. Completed substep stock waiting for
dispatch remains an active `processing` position for status filtering. Assembly filters run only after complete material groups are formed;
incomplete source sets cannot open an assembly order, and the frontend sends filters and page state to the API instead
of loading a fixed 10,000-row snapshot. Final status filtering and assembly grouping remain in the service because
they depend on live work orders and process-flow structure. Status queries skip historical hydration for active-state
filters and skip ordinary current inventory for completed-only filters.

## Rebuild policy

The current project policy remains a destructive rebuild from `zzerp.sql`. The script runs schema and seed changes
inside one transaction. Existing data must be exported separately if it needs to be retained.
