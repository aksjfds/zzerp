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
  "schema_version": 1,
  "nodes": [],
  "edges": []
}
```

The persisted JSON is the stable business graph contract for schema version 1. Unsupported versions are rejected.
LogicFlow's native camelCase graph data is converted at the frontend boundary and is not used as the API or
database contract.

Node types are `part`, `process`, `assembly`, and `qc`. Business edges use `route_type` with `normal` or
`rework`; QC outcomes use `approved` and `rejected`. Validation errors may include `element_id`, allowing the
editor to focus the invalid node or edge.

For a non-empty flow:

- each part node references a valid BOM row, and a BOM row appears at most once;
- each part node connects directly to exactly one first process node;
- all nodes belong to one connected graph;
- normal edges form a directed acyclic graph;
- assembly nodes have at least two normal inputs;
- each QC node has exactly one approved output and at most one rejected rework output;
- a rework target is a process or assembly node that reaches the source QC again through normal edges.

An empty flow remains valid while the product is still a draft.
