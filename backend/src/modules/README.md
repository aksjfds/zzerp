# Backend module boundary

`modules/<name>/api.py` is the only module surface supported by HTTP routers.
Business modules may additionally use narrowly scoped `*_api.py` collaboration
ports where a single facade would create circular dependencies. Routers may
import schemas, permissions, department registry functions and primary module
APIs, but must not import collaboration ports, implementations, ORM models,
repositories or the database session directly.

Business implementations and data-access repositories live in their owning
module packages. The old top-level `services` and `repositories` source files
have been removed. Architecture tests reject legacy imports and require those
layers to remain absent.

ORM class definitions live in each owner's `persistence.py`. Files under the
top-level `models` package have been removed. Owning modules import persistence
classes directly; foreign modules use the owner's `model_api.py` under the
explicit read-access manifest. Architecture tests verify that the physical
file owner, `TABLE_OWNERS` declaration and imports agree.

Department packages under `departments/` own department capabilities and
presentation policies. Shared inventory, movement and work-order state remains
owned by `production_core`; department packages delegate to it and must not
create copies of the production state machine.

## Ownership

- `identity`: users, sessions and authentication.
- `organization`: departments, workshops and procedures.
- `engineering`: products, versions, BOM and process flow.
- `sales`: customers and customer orders.
- `production_core`: production items, inventory, movement ledger and work-order orchestration.
- `standard_execution`: tags, tag sets, piece rates and tagged work orders.
- `purchasing`: purchase receipt work orders.
- `assembly`: assembly work orders and material allocation.
- `quality`: inspections and QC release.
- `workforce`: worker administration, history and pay projections.
- `planning`: PMC and other cross-module read models.

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
table. Architecture tests require the ownership map to remain exhaustive,
reject foreign-owned ORM construction, and ensure every cross-module API
dependency is declared by the caller's descriptor.

Shared-database read coupling is exceptional and explicit:
`modules/read_access.py` lists every foreign table each module currently reads.
Architecture tests require the manifest and actual ORM imports to match exactly.
The same tests build the local Python import graph and reject file-level cycles.
New collaboration queries should be owned by the data-owning module and return
scalars or immutable projections. A `model_api.py` grant is reserved for an ORM
relationship or a measured joined-query need that cannot yet use such a contract.
Only `planning` (cross-domain reporting) and `production_core` (the production
state machine and transaction orchestrator) currently hold grants. Other
modules must request batched projections from each data owner and compose them
without importing foreign ORM tables.
When an in-transaction workflow must pass an existing runtime object, the owner
publishes a persistence-free structural protocol in `context_api.py`; mutations
still go through an owner command API. Architecture tests keep these protocol
surfaces independent from SQLAlchemy and persistence modules.
