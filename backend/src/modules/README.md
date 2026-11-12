# Module boundaries

Routers call primary api.py surfaces. Cross-module collaboration uses descriptor-declared narrow *_api.py ports; only the owner constructs or writes its ORM.

- identity owns users and sessions.
- sales owns customers.
- organization owns the nine production departments.
- engineering owns products, versions, BOM, drawings and the current product_department_route and product_route_component projections.
- planning owns production plans, department_work_order and immutable department_work_order_movement records.

application/engineering.py injects planning.reference_api to protect referenced node pairs without creating an engineering -> planning dependency. Planning reads engineering.route_api and organization.read_api within its own transaction.

Schema 8 drawings contain explicit part and department nodes, without grouping. Formal JSON is authoritative; the current projection indexes each material-origin/department node pair and its current BOM constituents. Drafts do not generate tasks. Version copies preserve node IDs and remap BOM references.

Each plan/material-origin/department pair has at most one work order. Laser and assembly merges create assembly identities at the merge node and flatten constituent names. Parts use production quantity times BOM requirement; assemblies use production quantity from the merge onward. Branches deduplicate the same material, ambiguous overlapping inputs or assembly cycles are rejected. Work orders contain no part, department, route, BOM-unit or version snapshots. Live references protect existing tasks during engineering changes. Plan state supplies cancellation/completion display.

Shared frontend geometry does not own engineering business state. Do not restore removed execution, inventory or legacy top-level services/repositories/models layers.

Production users have a department_code foreign key and department:work-order:view/operate. Identity serializes membership for login and sessions; planning reads actor names only through identity.read_api. Central authorization restricts scoped users to work-order access. APIs must pass authenticated department_scope; queries enforce it before count/pagination and mutations reject unscoped or different departments. Planners retain read access across departments but cannot register movements.

Receipts and issues are independent positive-integer entries without business caps or automatic downstream transfers. Only confirmed plans accept entries; all commands share the parent-plan lock. Per-order UUIDs make retries idempotent. SQL protects append-only history and recorded work-order identity/quantity; plans with entries cannot be withdrawn, rebuilt or deleted. Totals derive from entries and are transported as exact decimal strings. Public login names do not grant data access.
