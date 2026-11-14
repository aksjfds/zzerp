# Module boundaries

Routers call primary api.py surfaces. Cross-module collaboration uses descriptor-declared narrow *_api.py ports; only the owner constructs or writes its ORM.

- identity owns users and sessions.
- sales owns customers.
- organization owns the nine production departments.
- engineering owns products, versions, BOM, drawings and the current product_department_route and product_route_component projections.
- planning owns production plans, per-product production_plan_item quantities, department_work_order and immutable department_work_order_movement records.

application/engineering.py injects planning.reference_api to protect referenced node pairs without creating an engineering -> planning dependency. Planning reads engineering.route_api and organization.read_api within its own transaction.

Schema 8 drawings contain explicit part and department nodes, without grouping. Formal JSON is authoritative; the current projection indexes each material-origin/department node pair and its current BOM constituents. Drafts do not generate tasks. Version copies preserve node IDs and remap BOM references.

Each plan/product/material-origin/department pair has at most one work order, referencing its product detail through a composite foreign key. Details share the plan customer and carry individual order/production quantities. Plans lock before products; multi-product changes lock old/new products in ID order and rebuild atomically. Handoff candidates and commands require the same plan and product. Laser and assembly merges create assembly identities and flatten constituent names. Parts use their product's production quantity times BOM requirement; assemblies use that production quantity from the merge onward. Branches deduplicate the same material, ambiguous overlapping inputs or assembly cycles are rejected. Work orders contain no part, department, route, BOM-unit or version snapshots. Live references protect existing tasks during engineering changes. Plan state supplies cancellation/completion display.

Shared frontend geometry does not own engineering business state. Do not restore removed execution, inventory or legacy top-level services/repositories/models layers.

Production users have a department_code foreign key and department:work-order:view/operate. Identity serializes membership for login and sessions; planning reads actor names only through identity.read_api. Central authorization restricts scoped users to work-order access. APIs must pass authenticated department_scope; queries enforce it before count/pagination and mutations reject unscoped or different departments. Planners retain read access across departments but cannot register movements.

Only confirmed plans accept positive-integer entries. Cumulative ticket receipts cannot exceed the original issue quantity; application checks and a database ticket-row lock protect this limit. Unattributed receipts require a valid work-order material and a nonblank note. Stamp and purchase are exempt from receipt-based issue limits. Other part issues use received minus issued quantities; assemblies use component-equivalent receipts and the minimum BOM kit count minus previous issues. The shared planning issue_limits helper computes exact integers under plan/product locks; the UI reads the remaining quantity. Issues do not automatically create downstream receipts. Per-order UUIDs make retries idempotent. SQL protects append-only history and work-order identity; plans with entries cannot be rebuilt or deleted.

Planning owns immutable department_handoff_ticket and department_movement_receipt_link records. Internal receipts must reference a ticket targeting the authenticated work order. Engineering provides direct successors and actual work-order material choices through route_api; existing ticket edges are protected via the application-injected planning reference port. Writes lock the plan then product; one issue/ticket/target is atomic and UUID-idempotent. Links do not consume inventory or multiply movement totals. Assembly receipts are grouped by actual input material. All new history is append-only and non-cascading.

Registration does not accept receipt linking. Existing historical links remain readable, and summaries count each original movement once. Unattributed receipts are allowed on any owned confirmed order with mandatory nonblank notes.
