# Backend module boundary

`modules/<name>/api.py` is the only module surface supported by HTTP routers.
Business modules may additionally use narrowly scoped `*_api.py` collaboration
ports where a single facade would create circular dependencies. Routers may
import schemas, permissions, department registry functions and primary module
APIs, but must not import collaboration ports, implementations, ORM models,
repositories or the database session directly.

Business implementations and data-access repositories live in their owning
module packages. The old top-level `services` and `repositories` source files
have been removed. Static architecture review requires those layers to remain
absent.

ORM class definitions live in each owner's `persistence.py`. Files under the
top-level `models` package have been removed. Owning modules import persistence
classes directly; an exceptional foreign ORM read uses the owner's
`model_api.py`. Static architecture review must verify that the physical file
owner, `TABLE_OWNERS` declaration and public model surfaces agree.

Department packages under `departments/` own department capabilities and
presentation policies. Shared inventory, movement and work-order state remains
owned by `production_core`; department packages delegate to it and must not
create copies of the production state machine.

## Ownership

- `identity`: users, sessions and authentication.
- `organization`: departments, workshops and procedures.
- `engineering`: products, versions, BOM and process flow.
- `sales`: customers and customer orders.
- `production_core`: production items, repositories, movement ledger and shared work-order state.
- `standard_execution`: procedure prices, pay details and standard work-order execution.
- `assembly`: assembly work orders and material allocation.
- `quality`: inspections and QC release.
- `inventory`: temporary warehouse stock and operations, cross-order finished stock and immutable ledgers.
- `workforce`: worker administration, history and pay projections.
- `planning`: production plans, PMC and other cross-module read models.

## Dependency rules

1. Routers call module APIs.
2. Business modules may only import another module through `api.py` or an
   explicitly named `*_api.py` facade.
3. Router-facing use cases return dictionaries, Pydantic contracts or immutable
   DTOs, never SQLAlchemy records or a live database session.
4. Only the owning module constructs its persisted records. Cross-module
   workflows call transaction-aware owner APIs with the current session.
5. Cross-module state changes remain in one application transaction while the
   system is a modular monolith.
6. Department-specific behavior is a policy or adapter; common production
   behavior is not copied into each department.
7. `context_api.py` protocols and owner command ports are internal transaction
   contracts. They may describe objects backed by the shared persistence
   context and are not transport contracts.
8. A future HTTP or message adapter must introduce serializable request,
   response and event DTOs; it must not expose ORM-backed transaction objects.

`modules/ownership.py` declares exactly one authoritative owner for every ORM
table. Static architecture review requires the ownership map to match the
physical ORM definitions, rejects cross-module persistence imports, and checks
that every `model_api.py` is declared by its owning descriptor.

Shared-database read coupling is exceptional and explicit. New collaboration
queries should be owned by the data-owning module and return scalars or
immutable projections. A foreign `model_api.py` import is reserved for an ORM
relationship or a measured joined-query need that cannot yet use such a
contract; it must not be used to write a foreign-owned record.
When an in-transaction workflow must pass an existing runtime object, the owner
publishes a persistence-free structural protocol in `context_api.py`; mutations
still go through an owner command API. These protocol surfaces must remain
independent from SQLAlchemy and persistence modules.

## Registered cross-domain read models

Cross-domain ORM joins are limited to the following read-model owners. These
files may import declared foreign `model_api.py` surfaces for set-based reads;
they may not construct or mutate foreign-owned records.

| Read model | Owner | Purpose |
| --- | --- | --- |
| `planning.department_progress` | planning | ordinary department task list |
| `planning.current_production_cards` / `historical_production_cards` / `production_card_listing` | planning | production workbench card queries and orchestration |
| `planning.production_progress_detail` | planning | department task detail drawer |
| `planning.order_status_view` / `sales_progress_api` | planning | sales order production summaries and flow status |
| `inventory.api` | inventory | temporary warehouse and finished-inventory presentation |
| `inventory.finished_goods_api` | inventory | finished-goods receiving, shipment and presentation |
| `production_core.work_order_queries` / `work_order_presenters` | production_core | owner work-order query and response mapping |
| `quality.workforce_api` | quality | immutable QC activity projection for workforce |
| `workforce.workers` | workforce | worker history and pay projection |

The following transaction paths have registered foreign ORM reads because the
shared SQL transaction must lock or join existing context. They are not foreign
writers: all construction and mutation is delegated to the owning `*_api.py`.

| Transaction path | Foreign read purpose |
| --- | --- |
| `assembly.work_orders` | lock production material allocations and inspect workshop context |
| `planning.plan_builder` / `plan_api` / `route_projection` / `execution_api` | bind the order's immutable product version, validate inventory/production completion and derive its route |
| `production_core.flow` / `lifecycle` / `inventory_api` / `assembly_api` | resolve immutable order-version flow and initialize owner production records |
| `production_core.repositories` / `work_order_commands` / `work_order_support` | validate source, workshop and procedure context before owner writes |
| `production_core.operation_undo` | lock the source order context while reversing owner movements |
| `quality.inspection_api` / `submission_api` | no direct ORM dependency remains; QC batch reads and writes go through `production_core.qc_api` |

Any new foreign ORM construction or attribute mutation is a boundary violation,
even if the class was imported through `model_api.py`.

`production_route_task` is a planning-owned deterministic projection of
`production_plan_item` onto the bound product-version flow. It stores only the
route node, workshop and order within the route; department remains derived
from the workshop owner. Planned quantity,
arrival, completion, work-order and QC state remain in their authoritative
tables. The projection is rebuilt in the same transaction whenever a draft plan
is rebuilt or edited; plan confirmation does not create a second route.
