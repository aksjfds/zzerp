# Database design notes

## Integrity boundaries

- `product_version` is the registry for every product business version.
- BOM, process-flow, and customer-order references use composite product-version foreign keys.
- BOM sort positions are unique per product version and checked at transaction commit.
- Work orders snapshot `procedure_name` and `procedure_type` for historical stability.
- Composite foreign keys require a work order or assembly material to reference a repository owned by the same
  production item. A work order's procedure snapshot type must also match its referenced procedure; assembly
  orders remain valid with a null procedure ID.
- When a repository position is exhausted, all work-order and material-allocation references to that row are
  released before deletion. Immutable production movements remain the historical source-of-truth.
- QC batches reference the inspecting worker by ID and retain the worker name as a display snapshot.
- Production items store their locked product ID/version. Composite foreign keys require both the order item and
  optional BOM row to match that same version, without cross-table validation triggers or concurrency windows.
- QC-batch movements use `(batch_id, work_order_id)` as a composite reference. Submission node and quantity must
  match the batch, and QC result nodes and totals must match the immutable movement history.
- Submission movements require an open work order, and completed QC batches reject any later movement. Each
  assembly material has exactly one input movement whose quantity matches its allocation.
- Production movement fields follow an exact matrix for initial, submission, assembly-input, QC-output, scrap,
  and loss records. A qualified QC result may either enter its next node or finish the route; rework always has an
  explicit target. Work-order/QC movement rows cannot be updated or deleted; initial rows may be cascade-deleted
  only together with their production item so an unstarted customer order can still be cancelled.
- Once movements exist, work-order procedure snapshots, batch source fields, completed QC results, and assembly
  material identity/quantity are frozen. Trigger reads lock work order, then batch/material rows in that order;
  composite foreign keys cover repository, procedure-type, and batch ownership without trigger race windows.

## Time

Persisted timestamps use `TIMESTAMPTZ`. Services write UTC values and API presenters convert them to
`Asia/Shanghai`. Database triggers use the actual wall-clock time to maintain `updated_at` for products, BOM rows,
process flows, and customer orders, including changes made outside SQLAlchemy.

## Search and operational indexes

Product and BOM-part substring search uses PostgreSQL `pg_trgm` GIN indexes. Operational indexes cover product-version
references, open work orders, worker activity time, pending QC batches, and latest movement at a production
position. The pending-QC index starts with descending batch ID to match global pagination. Work-order and batch
movement indexes exclude null references, and a partial unique index permits only one submission movement per QC
batch. Another partial unique index permits one assembly-input movement per work order and production item. Unique
BOM sort-order enforcement also serves version-and-order lookups, so it is not duplicated by a second index.
The same operational and search indexes are declared in both `zzerp.sql` and SQLAlchemy metadata.

Production-card source queries push arrival-date and product/part keyword filters into PostgreSQL. Current arrival
positions distinguish production item, target node, and source node, so normal and rework arrivals cannot overwrite
one another. Current cards are `processing` only when their exact repository position has an open work order;
remaining stock is not mislabelled completed because a smaller earlier order closed. Historical latest-movement
ranking is restricted to candidate production positions before card hydration. Assembly filters run only after
complete material groups are formed, incomplete source sets cannot open an assembly order, and the frontend sends
filters and page state to the API instead of loading a fixed 10,000-row snapshot. Final status filtering and
assembly grouping remain in the service because they depend on live work orders and process-flow structure. Status
queries skip historical hydration for active-state filters and skip ordinary current inventory for completed-only
filters.

## Rebuild policy

The current project policy remains a destructive rebuild from `zzerp.sql`. The script runs schema and seed changes
inside one transaction. Existing data must be exported separately if it needs to be retained.
