# Process-flow frontend boundaries

- `domain/types.ts`: stable API and application-domain types; it has no LogicFlow field names.
- `logicflow/adapter.ts`: the only data conversion between the business graph and LogicFlow graph data.
- `logicflow/commands.ts`: imperative editor commands such as adding nodes and changing QC routes.
- `composables/useLogicFlowInstance.ts`: creates and destroys the LogicFlow instance and translates events.
- `components/ProcessFlowCanvas.vue`: thin canvas API exposed to its coordinator.
- `components/ProcessNodePalette.vue`: BOM and node creation controls.
- `components/ProcessPropertyPanel.vue`: process, assembly and QC-edge property editing.
- `components/ProcessFlowEditor.vue`: coordinates the components and exposes business-level save/reload methods.

LogicFlow-native camelCase properties must stay inside the adapter, commands, canvas, and instance composable.
API clients, stores, views, and the database use the versioned snake_case business graph.
Complete process-flow validation is owned by the backend domain service. The frontend only
enforces editor interaction constraints and displays structured validation errors returned by
the save API, preventing a second rule implementation from drifting over time.
