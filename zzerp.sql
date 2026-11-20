-- MES 开发数据库唯一破坏性重建基线。
-- 保留工程设计、统一生产计划及账号认证。
-- 配件节点和部门节点通过连线形成当前生产路线。


BEGIN;

DROP SCHEMA public CASCADE;

CREATE SCHEMA public;

GRANT ALL ON SCHEMA public TO CURRENT_USER;

GRANT ALL ON SCHEMA public TO public;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 表结构

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    role TEXT NOT NULL,
    department_code TEXT,
    permissions TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT ck_users_production_department CHECK ((role = 'production') = (department_code IS NOT NULL))
);

CREATE TABLE user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    csrf_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_sessions_token_hash UNIQUE (token_hash)
);

CREATE TABLE customer (
    id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_customer_name UNIQUE (customer_name)
);

CREATE TABLE product (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    product_name TEXT NOT NULL,
    factory_code TEXT NOT NULL,
    customer_code TEXT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    revision INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_factory_code UNIQUE (factory_code),
    CONSTRAINT uq_product_customer_context UNIQUE (id, customer_id),
    CONSTRAINT ck_product_version CHECK (version > 0),
    CONSTRAINT ck_product_revision CHECK (revision > 0)
);

CREATE TABLE product_version (
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    version INT NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, version),
    CONSTRAINT ck_product_version_number CHECK (version > 0),
    CONSTRAINT ck_product_version_value CHECK (length(btrim(value)) BETWEEN 1 AND 100),
    CONSTRAINT uq_product_version_value UNIQUE (product_id, value)
);

CREATE TABLE product_bom (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    product_version INT NOT NULL,
    part_name TEXT NOT NULL,
    part_no TEXT NOT NULL,
    pcs INT NOT NULL,
    remark TEXT,
    sort_order INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_product_bom_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version) ON DELETE CASCADE,
    CONSTRAINT uq_product_bom_product UNIQUE (id, product_id),
    CONSTRAINT uq_product_bom_id_version
        UNIQUE (id, product_id, product_version),
    CONSTRAINT uq_product_bom_part_no UNIQUE (product_id, product_version, part_no),
    CONSTRAINT uq_product_bom_sort_order
        UNIQUE (product_id, product_version, sort_order) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_product_bom_version CHECK (product_version > 0),
    CONSTRAINT ck_product_bom_pcs CHECK (pcs > 0),
    CONSTRAINT ck_product_bom_sort_order CHECK (sort_order > 0)
);

CREATE TABLE product_process_flow (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    product_version INT NOT NULL,
    flow_json JSONB NOT NULL DEFAULT '{"schema_version": 8, "nodes": [], "edges": []}'::jsonb,
    draft_flow_json JSONB,
    CONSTRAINT ck_process_flow_json_object
        CHECK (jsonb_typeof(flow_json) = 'object'),
    CONSTRAINT ck_process_flow_schema_version_present
        CHECK (flow_json ? 'schema_version'),
    CONSTRAINT ck_process_flow_schema_version_type
        CHECK (jsonb_typeof(flow_json->'schema_version') = 'number'),
    CONSTRAINT ck_process_flow_schema_version
        CHECK (flow_json->>'schema_version' = '8'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_process_flow_nodes_present CHECK (flow_json ? 'nodes'),
    CONSTRAINT ck_process_flow_nodes_type
        CHECK (jsonb_typeof(flow_json->'nodes') = 'array'),
    CONSTRAINT ck_process_flow_edges_present CHECK (flow_json ? 'edges'),
    CONSTRAINT ck_process_flow_edges_type
        CHECK (jsonb_typeof(flow_json->'edges') = 'array'),
    CONSTRAINT ck_process_flow_draft_object
        CHECK (draft_flow_json IS NULL OR jsonb_typeof(draft_flow_json) = 'object'),
    CONSTRAINT ck_process_flow_draft_schema_version
        CHECK (draft_flow_json IS NULL OR draft_flow_json->>'schema_version' = '8'),
    CONSTRAINT ck_process_flow_draft_nodes
        CHECK (draft_flow_json IS NULL OR jsonb_typeof(draft_flow_json->'nodes') = 'array'),
    CONSTRAINT ck_process_flow_draft_edges
        CHECK (draft_flow_json IS NULL OR jsonb_typeof(draft_flow_json->'edges') = 'array'),
    CONSTRAINT fk_product_process_flow_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version) ON DELETE CASCADE,
    CONSTRAINT uq_product_process_flow_version UNIQUE (product_id, product_version),
    CONSTRAINT ck_process_flow_version CHECK (product_version > 0)
);

-- 计划头保存订单和状态，产品明细保存独立的外观版本/BOM/正式流程快照及数量。
CREATE TABLE production_plan (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    order_no TEXT NOT NULL,
    order_date DATE NOT NULL,
    delivery_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    revision INT NOT NULL DEFAULT 1,
    confirmed_at TIMESTAMPTZ,
    confirmed_by TEXT,
    completed_at TIMESTAMPTZ,
    completed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_production_plan_order_no UNIQUE (order_no),
    CONSTRAINT uq_production_plan_customer UNIQUE (id, customer_id),
    CONSTRAINT ck_production_plan_revision CHECK (revision > 0),
    CONSTRAINT ck_production_plan_dates CHECK (delivery_date >= order_date),
    CONSTRAINT ck_production_plan_status
        CHECK (status IN ('draft', 'confirmed', 'cancelled', 'completed')),
    CONSTRAINT ck_production_plan_confirmation CHECK (
        (status IN ('confirmed', 'completed') AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)
        OR status IN ('draft', 'cancelled')
    ),
    CONSTRAINT ck_production_plan_completion CHECK (
        (status = 'completed' AND completed_at IS NOT NULL AND completed_by IS NOT NULL)
        OR (status <> 'completed' AND completed_at IS NULL AND completed_by IS NULL)
    )
);

CREATE TABLE production_plan_item (
    production_plan_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    order_quantity INT NOT NULL,
    production_quantity INT NOT NULL,
    source_version INT NOT NULL,
    source_version_value TEXT NOT NULL,
    product_name TEXT NOT NULL,
    factory_code TEXT NOT NULL,
    customer_code TEXT NOT NULL,
    bom_snapshot JSONB NOT NULL,
    process_flow_snapshot JSONB NOT NULL,
    PRIMARY KEY (production_plan_id, product_id),
    CONSTRAINT fk_production_plan_item_plan FOREIGN KEY (production_plan_id, customer_id)
        REFERENCES production_plan(id, customer_id) ON DELETE CASCADE,
    CONSTRAINT fk_production_plan_item_product FOREIGN KEY (product_id) REFERENCES product(id),
    CONSTRAINT ck_plan_item_source_version CHECK (source_version > 0),
    CONSTRAINT ck_plan_item_version_value CHECK (length(btrim(source_version_value)) BETWEEN 1 AND 100),
    CONSTRAINT ck_production_plan_item_order_quantity CHECK (order_quantity > 0),
    CONSTRAINT ck_production_plan_item_production_quantity CHECK (production_quantity > 0)
);
CREATE INDEX idx_production_plan_item_product ON production_plan_item(product_id);

CREATE TABLE production_department (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    CONSTRAINT uq_production_department_name UNIQUE (name)
);

ALTER TABLE users ADD CONSTRAINT fk_users_department
    FOREIGN KEY (department_code) REFERENCES production_department(code);
CREATE INDEX idx_users_department ON users(department_code);

-- 工程投影供当前工程图使用；生产工单引用计划自己的快照路线。
CREATE TABLE product_department_route (
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    material_node_id TEXT NOT NULL,
    department_node_id TEXT NOT NULL,
    department_code TEXT NOT NULL REFERENCES production_department(code),
    PRIMARY KEY (product_id, material_node_id, department_node_id)
);

CREATE INDEX idx_product_department_route_department ON product_department_route(department_code, product_id);
CREATE TABLE product_route_component (
    product_id BIGINT NOT NULL,
    material_node_id TEXT NOT NULL,
    department_node_id TEXT NOT NULL,
    product_bom_id BIGINT NOT NULL,
    PRIMARY KEY (product_id, material_node_id, department_node_id, product_bom_id),
    CONSTRAINT fk_product_route_component_route
        FOREIGN KEY (product_id, material_node_id, department_node_id)
        REFERENCES product_department_route(product_id, material_node_id, department_node_id) ON DELETE CASCADE,
    CONSTRAINT fk_product_route_component_bom
        FOREIGN KEY (product_bom_id, product_id) REFERENCES product_bom(id, product_id)
);

CREATE INDEX idx_product_route_component_bom ON product_route_component(product_bom_id);

-- 计划独立快照路线，由应用从创建时复制的正式图生成；SQL不解析流程图。
CREATE TABLE plan_product_route (
    production_plan_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    material_node_id TEXT NOT NULL,
    department_node_id TEXT NOT NULL,
    department_code TEXT NOT NULL REFERENCES production_department(code),
    part_no TEXT NOT NULL,
    part_name TEXT NOT NULL,
    unit_requirement INT NOT NULL,
    PRIMARY KEY (production_plan_id, product_id, material_node_id, department_node_id),
    CONSTRAINT fk_plan_product_route_item FOREIGN KEY (production_plan_id, product_id)
        REFERENCES production_plan_item(production_plan_id, product_id) ON DELETE CASCADE,
    CONSTRAINT ck_plan_product_route_quantity CHECK (unit_requirement > 0)
);
CREATE INDEX idx_plan_product_route_department ON plan_product_route(department_code, production_plan_id, product_id);

CREATE TABLE department_work_order (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    material_node_id TEXT NOT NULL,
    department_node_id TEXT NOT NULL,
    task_quantity INT NOT NULL,
    scheduled_date DATE,
    schedule_revision INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_department_work_order_plan
        FOREIGN KEY (production_plan_id, product_id)
        REFERENCES production_plan_item(production_plan_id, product_id) ON DELETE CASCADE,
    CONSTRAINT fk_department_work_order_route
        FOREIGN KEY (production_plan_id, product_id, material_node_id, department_node_id)
        REFERENCES plan_product_route(production_plan_id, product_id, material_node_id, department_node_id),
    CONSTRAINT uq_department_work_order_plan_route UNIQUE (production_plan_id, product_id, material_node_id, department_node_id),
    CONSTRAINT ck_department_work_order_quantity CHECK (task_quantity > 0),
    CONSTRAINT ck_department_work_order_schedule_revision CHECK (schedule_revision > 0)
);

CREATE INDEX idx_department_work_order_route ON department_work_order(product_id, material_node_id, department_node_id);
CREATE INDEX idx_department_work_order_product ON department_work_order(product_id);

CREATE TABLE department_work_order_movement (
    piecework_process TEXT NOT NULL DEFAULT '',
    revoked_at TIMESTAMPTZ,
    revoked_by BIGINT REFERENCES users(id),
    revoke_reason TEXT,
    document_type TEXT NOT NULL DEFAULT 'normal',
    worker_name TEXT NOT NULL DEFAULT '',
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES department_work_order(id),
    direction TEXT NOT NULL,
    quantity BIGINT NOT NULL,
    note TEXT NOT NULL,
    request_id UUID NOT NULL,
    actor_user_id BIGINT NOT NULL REFERENCES users(id),
    receipt_source TEXT,
    ticket_id BIGINT,
    warehouse_pick_id BIGINT,
    input_material_node_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_department_movement_request UNIQUE (work_order_id, request_id),
    CONSTRAINT ck_movement_piecework_process CHECK ((document_type = 'normal' AND piecework_process = '') OR (document_type = 'piecework' AND length(btrim(piecework_process)) <= 100)),
    CONSTRAINT ck_movement_piecework CHECK ((document_type = 'normal' AND worker_name = '') OR (document_type = 'piecework' AND direction = 'issue' AND length(worker_name) BETWEEN 1 AND 100 AND worker_name ~ '[^[:space:]]')),
    CONSTRAINT ck_department_movement_warehouse_pick CHECK ((warehouse_pick_id IS NOT NULL) = (receipt_source IS NOT DISTINCT FROM 'warehouse')),
    CONSTRAINT ck_department_movement_direction CHECK (direction IN ('receipt', 'issue')),
    CONSTRAINT ck_department_movement_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991),
    CONSTRAINT ck_department_movement_source CHECK (
        (direction = 'issue' AND receipt_source IS NULL AND ticket_id IS NULL AND input_material_node_id IS NULL)
        OR (direction = 'receipt' AND receipt_source IS NOT NULL AND input_material_node_id IS NOT NULL
            AND ((receipt_source = 'ticket' AND ticket_id IS NOT NULL) OR (receipt_source = 'warehouse' AND ticket_id IS NULL))))
);

CREATE UNIQUE INDEX uq_department_movement_warehouse_pick ON department_work_order_movement(warehouse_pick_id) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX uq_department_movement_ticket ON department_work_order_movement(ticket_id) WHERE revoked_at IS NULL;
CREATE INDEX idx_department_movement_order ON department_work_order_movement(work_order_id, created_at, id);
CREATE INDEX idx_department_movement_actor ON department_work_order_movement(actor_user_id);
CREATE INDEX idx_movement_piecework_worker ON department_work_order_movement(worker_name, id) WHERE document_type = 'piecework';

CREATE TABLE department_handoff_ticket (
    id BIGSERIAL PRIMARY KEY,
    issue_movement_id BIGINT NOT NULL REFERENCES department_work_order_movement(id),
    target_work_order_id BIGINT NOT NULL REFERENCES department_work_order(id),
    CONSTRAINT uq_handoff_issue UNIQUE (issue_movement_id)
);
CREATE INDEX idx_handoff_target ON department_handoff_ticket(target_work_order_id, id);
ALTER TABLE department_work_order_movement ADD FOREIGN KEY (ticket_id) REFERENCES department_handoff_ticket(id);

CREATE TABLE department_movement_receipt_link (
    issue_movement_id BIGINT NOT NULL REFERENCES department_work_order_movement(id),
    receipt_movement_id BIGINT NOT NULL REFERENCES department_work_order_movement(id),
    PRIMARY KEY (issue_movement_id, receipt_movement_id)
);
CREATE INDEX idx_movement_link_receipt ON department_movement_receipt_link(receipt_movement_id);

CREATE TABLE qc_inspection (
    revoked_at TIMESTAMPTZ,
    revoked_by BIGINT REFERENCES users(id),
    revoke_reason TEXT,
    repair_kind TEXT,
    repair_worker_name TEXT NOT NULL DEFAULT '',
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES department_work_order(id),
    source_ticket_id BIGINT REFERENCES department_handoff_ticket(id),
    source_return_id BIGINT,
    source_pick_id BIGINT,
    good_quantity BIGINT NOT NULL,
    scrap_quantity BIGINT NOT NULL,
    rework_quantity BIGINT NOT NULL,
    repair_department_code TEXT REFERENCES production_department(code),
    request_id UUID NOT NULL,
    actor_user_id BIGINT NOT NULL REFERENCES users(id),
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_qc_repair_kind CHECK ((rework_quantity = 0 AND repair_kind IS NULL AND repair_worker_name = '') OR (rework_quantity > 0 AND repair_kind IS NOT NULL AND repair_kind IN ('original', 'cross') AND (repair_kind = 'original' OR repair_worker_name = ''))),
    CONSTRAINT uq_qc_inspection_request UNIQUE (request_id),
    CONSTRAINT ck_qc_inspection_note CHECK ((scrap_quantity = 0 AND rework_quantity = 0) OR note ~ '[^[:space:]]'),
    CONSTRAINT ck_qc_inspection_source CHECK ((CASE WHEN source_ticket_id IS NULL THEN 0 ELSE 1 END + CASE WHEN source_return_id IS NULL THEN 0 ELSE 1 END + CASE WHEN source_pick_id IS NULL THEN 0 ELSE 1 END) = 1),
    CONSTRAINT ck_qc_inspection_quantities CHECK (good_quantity >= 0 AND scrap_quantity >= 0 AND rework_quantity >= 0 AND good_quantity + scrap_quantity + rework_quantity BETWEEN 1 AND 9007199254740991),
    CONSTRAINT ck_qc_repair_department CHECK (repair_department_code IS NULL OR repair_department_code <> 'qc'),
    CONSTRAINT ck_qc_inspection_repair CHECK ((rework_quantity > 0) = (repair_department_code IS NOT NULL))
);

CREATE UNIQUE INDEX uq_qc_inspection_pick ON qc_inspection(source_pick_id) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX uq_qc_inspection_return ON qc_inspection(source_return_id) WHERE revoked_at IS NULL;
CREATE UNIQUE INDEX uq_qc_inspection_ticket ON qc_inspection(source_ticket_id) WHERE revoked_at IS NULL;
CREATE INDEX idx_qc_inspection_order ON qc_inspection(work_order_id, id);
CREATE INDEX idx_qc_inspection_repair ON qc_inspection(repair_department_code, id);
CREATE TABLE qc_rework_ticket (
    id BIGSERIAL PRIMARY KEY,
    inspection_id BIGINT NOT NULL REFERENCES qc_inspection(id),
    CONSTRAINT uq_qc_rework_inspection UNIQUE (inspection_id)
);
CREATE TABLE qc_rework_event (
    revoked_at TIMESTAMPTZ,
    revoked_by BIGINT REFERENCES users(id),
    revoke_reason TEXT,
    id BIGSERIAL PRIMARY KEY,
    ticket_id BIGINT NOT NULL REFERENCES qc_rework_ticket(id),
    action TEXT NOT NULL,
    quantity BIGINT NOT NULL,
    repaired_quantity BIGINT NOT NULL,
    unrepaired_quantity BIGINT NOT NULL,
    request_id UUID NOT NULL,
    actor_user_id BIGINT NOT NULL REFERENCES users(id),
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_qc_rework_event_request UNIQUE (request_id),
    CONSTRAINT ck_qc_rework_event_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991),
    CONSTRAINT ck_qc_rework_event_result CHECK (repaired_quantity >= 0 AND unrepaired_quantity >= 0 AND ((action = 'receive' AND repaired_quantity = 0 AND unrepaired_quantity = 0) OR (action = 'return' AND repaired_quantity + unrepaired_quantity = quantity))),
    CONSTRAINT ck_qc_rework_event_action CHECK (action IN ('receive', 'return'))
);

CREATE UNIQUE INDEX uq_qc_rework_event_action ON qc_rework_event(ticket_id, action) WHERE revoked_at IS NULL;
ALTER TABLE qc_inspection ADD CONSTRAINT fk_qc_inspection_return FOREIGN KEY (source_return_id) REFERENCES qc_rework_event(id);

CREATE TABLE warehouse_lot (
    id BIGSERIAL PRIMARY KEY,
    warehouse_order_id BIGINT NOT NULL REFERENCES department_work_order(id),
    receipt_movement_id BIGINT NOT NULL REFERENCES department_work_order_movement(id),
    product_id BIGINT NOT NULL REFERENCES product(id),
    material_key TEXT NOT NULL,
    quantity BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_warehouse_lot_receipt UNIQUE (receipt_movement_id),
    CONSTRAINT ck_warehouse_lot_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991)
);
CREATE INDEX idx_warehouse_lot_pool ON warehouse_lot(product_id, material_key, id);
CREATE TABLE warehouse_pick (
    revoked_at TIMESTAMPTZ,
    revoked_by BIGINT REFERENCES users(id),
    revoke_reason TEXT,
    id BIGSERIAL PRIMARY KEY,
    target_order_id BIGINT NOT NULL REFERENCES department_work_order(id),
    route_warehouse_order_id BIGINT NOT NULL REFERENCES department_work_order(id),
    product_id BIGINT NOT NULL REFERENCES product(id),
    material_key TEXT NOT NULL,
    quantity BIGINT NOT NULL,
    request_id UUID NOT NULL,
    actor_user_id BIGINT NOT NULL REFERENCES users(id),
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_warehouse_pick_request UNIQUE (request_id),
    CONSTRAINT ck_warehouse_pick_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991)
);
CREATE INDEX idx_warehouse_pick_target ON warehouse_pick(target_order_id, id);
CREATE TABLE warehouse_allocation (
    pick_id BIGINT NOT NULL REFERENCES warehouse_pick(id),
    lot_id BIGINT NOT NULL REFERENCES warehouse_lot(id),
    quantity BIGINT NOT NULL,
    PRIMARY KEY (pick_id, lot_id),
    CONSTRAINT ck_warehouse_allocation_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991)
);
CREATE INDEX idx_warehouse_allocation_lot ON warehouse_allocation(lot_id);
ALTER TABLE department_work_order_movement ADD CONSTRAINT fk_department_movement_warehouse_pick FOREIGN KEY (warehouse_pick_id) REFERENCES warehouse_pick(id);
ALTER TABLE qc_inspection ADD CONSTRAINT fk_qc_inspection_pick FOREIGN KEY (source_pick_id) REFERENCES warehouse_pick(id);

CREATE TABLE purchase_order (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES department_work_order(id),
    quantity BIGINT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    request_id UUID NOT NULL,
    actor_user_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ,
    revoked_by BIGINT REFERENCES users(id),
    revoke_reason TEXT,
    CONSTRAINT ck_purchase_order_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991),
    CONSTRAINT uq_purchase_order_request UNIQUE (request_id)
);
CREATE INDEX idx_purchase_order_work_order ON purchase_order(work_order_id, id);

CREATE TABLE purchase_receipt (
    id BIGSERIAL PRIMARY KEY,
    purchase_order_id BIGINT NOT NULL REFERENCES purchase_order(id),
    quantity BIGINT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    request_id UUID NOT NULL,
    actor_user_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ,
    revoked_by BIGINT REFERENCES users(id),
    revoke_reason TEXT,
    CONSTRAINT ck_purchase_receipt_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991),
    CONSTRAINT uq_purchase_receipt_request UNIQUE (request_id)
);
CREATE UNIQUE INDEX uq_purchase_receipt_order ON purchase_receipt(purchase_order_id) WHERE revoked_at IS NULL;

CREATE TABLE outsource_dispatch (
    revoked_at TIMESTAMPTZ,
    revoked_by BIGINT REFERENCES users(id),
    revoke_reason TEXT,
    id BIGSERIAL PRIMARY KEY,
    receipt_id BIGINT NOT NULL REFERENCES department_work_order_movement(id),
    process TEXT NOT NULL,
    vendor TEXT NOT NULL,
    quantity BIGINT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    request_id UUID NOT NULL,
    actor_user_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_outsource_process CHECK (process IN ('etching', 'plating')),
    CONSTRAINT ck_outsource_vendor CHECK (length(btrim(vendor)) BETWEEN 1 AND 100 AND vendor ~ '[^[:space:]]'),
    CONSTRAINT ck_outsource_dispatch_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991),
    CONSTRAINT uq_outsource_dispatch_request UNIQUE (request_id)
);
CREATE INDEX idx_outsource_dispatch_receipt ON outsource_dispatch(receipt_id, id);

CREATE TABLE outsource_return (
    revoked_at TIMESTAMPTZ,
    revoked_by BIGINT REFERENCES users(id),
    revoke_reason TEXT,
    id BIGSERIAL PRIMARY KEY,
    dispatch_id BIGINT NOT NULL REFERENCES outsource_dispatch(id),
    quantity BIGINT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    request_id UUID NOT NULL,
    actor_user_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_outsource_return_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991),
    CONSTRAINT uq_outsource_return_request UNIQUE (request_id)
);
CREATE INDEX idx_outsource_return_dispatch ON outsource_return(dispatch_id, id);

CREATE FUNCTION validate_operation_initial_state() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.revoked_at IS NOT NULL OR NEW.revoked_by IS NOT NULL OR NEW.revoke_reason IS NOT NULL THEN
        RAISE EXCEPTION '新登记操作不能预设撤回信息' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_department_work_order_movement_initial_state BEFORE INSERT ON department_work_order_movement
FOR EACH ROW EXECUTE FUNCTION validate_operation_initial_state();
CREATE TRIGGER trg_qc_inspection_initial_state BEFORE INSERT ON qc_inspection
FOR EACH ROW EXECUTE FUNCTION validate_operation_initial_state();
CREATE TRIGGER trg_qc_rework_event_initial_state BEFORE INSERT ON qc_rework_event
FOR EACH ROW EXECUTE FUNCTION validate_operation_initial_state();
CREATE TRIGGER trg_warehouse_pick_initial_state BEFORE INSERT ON warehouse_pick
FOR EACH ROW EXECUTE FUNCTION validate_operation_initial_state();
CREATE TRIGGER trg_outsource_dispatch_initial_state BEFORE INSERT ON outsource_dispatch
FOR EACH ROW EXECUTE FUNCTION validate_operation_initial_state();
CREATE TRIGGER trg_outsource_return_initial_state BEFORE INSERT ON outsource_return
FOR EACH ROW EXECUTE FUNCTION validate_operation_initial_state();
CREATE TRIGGER trg_purchase_order_initial_state BEFORE INSERT ON purchase_order
FOR EACH ROW EXECUTE FUNCTION validate_operation_initial_state();
CREATE TRIGGER trg_purchase_receipt_initial_state BEFORE INSERT ON purchase_receipt
FOR EACH ROW EXECUTE FUNCTION validate_operation_initial_state();

CREATE FUNCTION validate_purchase_order() RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM department_work_order wo JOIN plan_product_route route
        ON (route.production_plan_id, route.product_id, route.material_node_id, route.department_node_id)
            = (wo.production_plan_id, wo.product_id, wo.material_node_id, wo.department_node_id)
        WHERE wo.id = NEW.work_order_id AND route.department_code = 'purchase') THEN
        RAISE EXCEPTION '采购记录必须关联外购节点工单' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_purchase_order BEFORE INSERT ON purchase_order
FOR EACH ROW EXECUTE FUNCTION validate_purchase_order();

CREATE FUNCTION validate_purchase_receipt() RETURNS TRIGGER AS $$
DECLARE purchased BIGINT;
BEGIN
    PERFORM plan.id FROM production_plan plan JOIN department_work_order wo ON wo.production_plan_id = plan.id
        JOIN purchase_order purchase ON purchase.work_order_id = wo.id
        WHERE purchase.id = NEW.purchase_order_id FOR UPDATE OF plan;
    SELECT quantity INTO purchased FROM purchase_order WHERE id = NEW.purchase_order_id AND revoked_at IS NULL FOR UPDATE;
    IF purchased IS NULL OR NEW.quantity > purchased THEN
        RAISE EXCEPTION '采购到料必须关联有效采购且不能超过采购数量' USING ERRCODE = '23514';
    END IF;
    IF NEW.quantity < purchased AND NEW.note !~ '[^[:space:]]' THEN
        RAISE EXCEPTION '采购少到料必须备注' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_purchase_receipt BEFORE INSERT ON purchase_receipt
FOR EACH ROW EXECUTE FUNCTION validate_purchase_receipt();

CREATE FUNCTION validate_purchase_movement() RETURNS TRIGGER AS $$
DECLARE received NUMERIC; issued NUMERIC;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM department_work_order wo JOIN plan_product_route route
        ON (route.production_plan_id, route.product_id, route.material_node_id, route.department_node_id)
            = (wo.production_plan_id, wo.product_id, wo.material_node_id, wo.department_node_id)
        WHERE wo.id = NEW.work_order_id AND route.department_code = 'purchase') THEN
        RETURN NEW;
    END IF;
    PERFORM plan.id FROM production_plan plan JOIN department_work_order wo ON wo.production_plan_id = plan.id
        WHERE wo.id = NEW.work_order_id FOR UPDATE OF plan;
    IF NEW.direction <> 'issue' THEN
        RAISE EXCEPTION '外购到料必须通过采购记录登记' USING ERRCODE = '23514';
    END IF;
    SELECT COALESCE(SUM(receipt.quantity), 0) INTO received FROM purchase_receipt receipt
        JOIN purchase_order purchase ON purchase.id = receipt.purchase_order_id
        WHERE purchase.work_order_id = NEW.work_order_id AND purchase.revoked_at IS NULL AND receipt.revoked_at IS NULL;
    SELECT COALESCE(SUM(quantity), 0) INTO issued FROM department_work_order_movement
        WHERE work_order_id = NEW.work_order_id AND direction = 'issue' AND revoked_at IS NULL;
    IF NEW.quantity > received - issued THEN
        RAISE EXCEPTION '外购出料不能超过实际采购到料余量' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_purchase_movement BEFORE INSERT ON department_work_order_movement
FOR EACH ROW EXECUTE FUNCTION validate_purchase_movement();

CREATE FUNCTION validate_outsource_dispatch() RETURNS TRIGGER AS $$
DECLARE received BIGINT;
BEGIN
    SELECT movement.quantity INTO received FROM department_work_order_movement movement
        JOIN department_work_order wo ON wo.id = movement.work_order_id
        JOIN plan_product_route route ON
            (route.production_plan_id, route.product_id, route.material_node_id, route.department_node_id)
            = (wo.production_plan_id, wo.product_id, wo.material_node_id, wo.department_node_id)
        WHERE movement.id = NEW.receipt_id AND movement.revoked_at IS NULL AND movement.direction = 'receipt' AND route.department_code = 'outsource'
        FOR UPDATE OF movement;
    IF received IS NULL OR NEW.quantity + COALESCE((SELECT sum(quantity) FROM outsource_dispatch
        WHERE receipt_id = NEW.receipt_id AND revoked_at IS NULL), 0) > received THEN
        RAISE EXCEPTION '外发必须关联委外到料且累计不超过到料数量' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_outsource_dispatch BEFORE INSERT ON outsource_dispatch
FOR EACH ROW EXECUTE FUNCTION validate_outsource_dispatch();

CREATE FUNCTION validate_outsource_return() RETURNS TRIGGER AS $$
DECLARE dispatched BIGINT;
BEGIN
    SELECT quantity INTO dispatched FROM outsource_dispatch WHERE id = NEW.dispatch_id AND revoked_at IS NULL FOR UPDATE;
    IF dispatched IS NULL OR NEW.quantity + COALESCE((SELECT sum(quantity) FROM outsource_return
        WHERE dispatch_id = NEW.dispatch_id AND revoked_at IS NULL), 0) > dispatched THEN
        RAISE EXCEPTION '累计回料不能超过外发数量' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_outsource_return BEFORE INSERT ON outsource_return
FOR EACH ROW EXECUTE FUNCTION validate_outsource_return();

CREATE FUNCTION validate_warehouse_lot() RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM department_work_order_movement movement
        JOIN department_work_order wo ON wo.id = movement.work_order_id
        JOIN plan_product_route route ON (route.production_plan_id, route.product_id, route.material_node_id, route.department_node_id)
            = (wo.production_plan_id, wo.product_id, wo.material_node_id, wo.department_node_id)
        WHERE movement.id = NEW.receipt_movement_id AND movement.direction = 'receipt'
          AND movement.quantity = NEW.quantity AND movement.input_material_node_id = wo.material_node_id
          AND wo.id = NEW.warehouse_order_id AND wo.product_id = NEW.product_id AND route.department_code = 'warehouse'
    ) THEN
        RAISE EXCEPTION '仓库批次必须来自对应物料的实际入库流水' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_warehouse_lot BEFORE INSERT ON warehouse_lot FOR EACH ROW EXECUTE FUNCTION validate_warehouse_lot();

CREATE FUNCTION validate_warehouse_pick() RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM department_work_order source JOIN department_work_order target
        ON (source.production_plan_id, source.product_id) = (target.production_plan_id, target.product_id)
        JOIN plan_product_route route ON (route.production_plan_id, route.product_id, route.material_node_id, route.department_node_id)
            = (source.production_plan_id, source.product_id, source.material_node_id, source.department_node_id)
        WHERE source.id = NEW.route_warehouse_order_id AND target.id = NEW.target_order_id
          AND target.product_id = NEW.product_id AND route.department_code = 'warehouse'
          AND NOT EXISTS (SELECT 1 FROM plan_product_route target_route
              WHERE (target_route.production_plan_id, target_route.product_id, target_route.material_node_id, target_route.department_node_id)
                  = (target.production_plan_id, target.product_id, target.material_node_id, target.department_node_id)
                AND target_route.department_code = 'warehouse')
    ) THEN
        RAISE EXCEPTION '领料来源必须为本计划产品的仓库工单' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_warehouse_pick BEFORE INSERT ON warehouse_pick FOR EACH ROW EXECUTE FUNCTION validate_warehouse_pick();

CREATE FUNCTION validate_warehouse_allocation() RETURNS TRIGGER AS $$
DECLARE lot_quantity BIGINT; allocated NUMERIC;
BEGIN
    SELECT quantity INTO lot_quantity FROM warehouse_lot WHERE id = NEW.lot_id FOR UPDATE;
    IF NOT EXISTS (SELECT 1 FROM warehouse_pick pick JOIN warehouse_lot lot
        ON pick.product_id = lot.product_id AND pick.material_key = lot.material_key
        WHERE pick.id = NEW.pick_id AND pick.revoked_at IS NULL AND lot.id = NEW.lot_id
            AND EXISTS (SELECT 1 FROM department_work_order_movement receipt
                WHERE receipt.id = lot.receipt_movement_id AND receipt.revoked_at IS NULL)) THEN
        RAISE EXCEPTION '领料产品和物料规格与库存批次不一致' USING ERRCODE = '23514';
    END IF;
    SELECT COALESCE(SUM(allocation.quantity), 0) INTO allocated FROM warehouse_allocation allocation
        JOIN warehouse_pick pick ON pick.id = allocation.pick_id
        WHERE allocation.lot_id = NEW.lot_id AND pick.revoked_at IS NULL;
    IF allocated + NEW.quantity > lot_quantity THEN
        RAISE EXCEPTION '领料数量超过仓库批次库存' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_warehouse_allocation BEFORE INSERT ON warehouse_allocation FOR EACH ROW EXECUTE FUNCTION validate_warehouse_allocation();

CREATE FUNCTION validate_warehouse_pick_total() RETURNS TRIGGER AS $$
DECLARE pick_id_value BIGINT; expected BIGINT; allocated NUMERIC;
BEGIN
    IF TG_TABLE_NAME = 'warehouse_pick' THEN pick_id_value := NEW.id;
    ELSE pick_id_value := NEW.pick_id;
    END IF;
    SELECT quantity INTO expected FROM warehouse_pick WHERE id = pick_id_value;
    SELECT COALESCE(SUM(quantity), 0) INTO allocated FROM warehouse_allocation WHERE pick_id = pick_id_value;
    IF expected IS DISTINCT FROM allocated THEN
        RAISE EXCEPTION '领料单数量必须等于全部批次扣减数量' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER trg_warehouse_pick_total AFTER INSERT ON warehouse_pick DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION validate_warehouse_pick_total();
CREATE CONSTRAINT TRIGGER trg_warehouse_allocation_total AFTER INSERT ON warehouse_allocation DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION validate_warehouse_pick_total();

CREATE FUNCTION validate_warehouse_movement() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.warehouse_pick_id IS NOT NULL THEN
        PERFORM id FROM warehouse_pick WHERE id = NEW.warehouse_pick_id FOR UPDATE;
        IF EXISTS (SELECT 1 FROM warehouse_pick WHERE id = NEW.warehouse_pick_id
            AND NEW.quantity < quantity) AND NEW.note !~ '[^[:space:]]' THEN
            RAISE EXCEPTION '到料数量小于仓库交接票数量，必须填写备注' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.direction = 'issue' AND EXISTS (
        SELECT 1 FROM department_work_order wo JOIN plan_product_route route
        ON (route.production_plan_id, route.product_id, route.material_node_id, route.department_node_id)
        = (wo.production_plan_id, wo.product_id, wo.material_node_id, wo.department_node_id)
        WHERE wo.id = NEW.work_order_id AND route.department_code = 'warehouse'
    ) THEN RAISE EXCEPTION '仓库出料必须通过库存出料流程' USING ERRCODE = '23514';
    END IF;
    IF NEW.warehouse_pick_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM warehouse_pick pick JOIN department_work_order source ON source.id = pick.route_warehouse_order_id
        WHERE pick.id = NEW.warehouse_pick_id AND pick.revoked_at IS NULL AND pick.target_order_id = NEW.work_order_id
          AND NEW.quantity <= pick.quantity AND NEW.direction = 'receipt'
          AND NEW.input_material_node_id = source.material_node_id
    ) THEN RAISE EXCEPTION '仓库领料到料必须匹配对应领料单' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_warehouse_movement BEFORE INSERT ON department_work_order_movement FOR EACH ROW EXECUTE FUNCTION validate_warehouse_movement();

CREATE FUNCTION validate_qc_inspection() RETURNS TRIGGER AS $$
DECLARE expected_quantity BIGINT;
BEGIN
    PERFORM plan.id FROM production_plan plan JOIN department_work_order wo ON wo.production_plan_id = plan.id
        WHERE wo.id = NEW.work_order_id FOR UPDATE OF plan;
    IF NOT EXISTS (SELECT 1 FROM department_work_order wo JOIN plan_product_route route
        ON (route.production_plan_id, route.product_id, route.material_node_id, route.department_node_id)
        = (wo.production_plan_id, wo.product_id, wo.material_node_id, wo.department_node_id)
        WHERE wo.id = NEW.work_order_id AND route.department_code = 'qc') THEN
        RAISE EXCEPTION '质检记录必须归属QC工单' USING ERRCODE = '23514';
    END IF;
    IF NEW.source_ticket_id IS NOT NULL THEN
        SELECT issue.quantity INTO expected_quantity FROM department_handoff_ticket ticket
            JOIN department_work_order_movement issue ON issue.id = ticket.issue_movement_id
            WHERE ticket.id = NEW.source_ticket_id AND ticket.target_work_order_id = NEW.work_order_id AND issue.revoked_at IS NULL;
        IF EXISTS (SELECT 1 FROM department_work_order_movement WHERE ticket_id = NEW.source_ticket_id AND revoked_at IS NULL) THEN
            RAISE EXCEPTION '此来料已登记到料' USING ERRCODE = '23514';
        END IF;
    ELSIF NEW.source_pick_id IS NOT NULL THEN
        SELECT quantity INTO expected_quantity FROM warehouse_pick WHERE id = NEW.source_pick_id AND revoked_at IS NULL AND target_order_id = NEW.work_order_id;
    ELSE
        SELECT event.quantity INTO expected_quantity FROM qc_rework_event event
            JOIN qc_rework_ticket ticket ON ticket.id = event.ticket_id
            JOIN qc_inspection original ON original.id = ticket.inspection_id
            WHERE event.id = NEW.source_return_id AND event.revoked_at IS NULL AND original.revoked_at IS NULL AND event.action = 'return' AND original.work_order_id = NEW.work_order_id;
    END IF;
    IF expected_quantity IS NULL OR NEW.good_quantity + NEW.scrap_quantity + NEW.rework_quantity <> expected_quantity THEN
        RAISE EXCEPTION '质检分类数量必须等于来料数量' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_qc_inspection BEFORE INSERT ON qc_inspection
FOR EACH ROW EXECUTE FUNCTION validate_qc_inspection();

CREATE FUNCTION validate_qc_rework_event() RETURNS TRIGGER AS $$
DECLARE ticket_quantity BIGINT; received_quantity BIGINT;
BEGIN
    PERFORM plan.id FROM production_plan plan
        JOIN department_work_order wo ON wo.production_plan_id = plan.id
        JOIN qc_inspection inspection ON inspection.work_order_id = wo.id
        JOIN qc_rework_ticket ticket ON ticket.inspection_id = inspection.id
        WHERE ticket.id = NEW.ticket_id FOR UPDATE OF plan;
    SELECT inspection.rework_quantity INTO ticket_quantity FROM qc_rework_ticket ticket
        JOIN qc_inspection inspection ON inspection.id = ticket.inspection_id WHERE ticket.id = NEW.ticket_id AND inspection.revoked_at IS NULL;
    IF ticket_quantity IS NULL THEN
        RAISE EXCEPTION '原质检已撤回' USING ERRCODE = '23514';
    END IF;
    IF NEW.action = 'receive' THEN
        IF NEW.quantity > ticket_quantity THEN
            RAISE EXCEPTION '返修接收不能超过票面数量' USING ERRCODE = '23514';
        END IF;
        IF NEW.quantity < ticket_quantity AND NEW.note !~ '[^[:space:]]' THEN
            RAISE EXCEPTION '返修少收必须备注' USING ERRCODE = '23514';
        END IF;
    ELSE
        SELECT quantity INTO received_quantity FROM qc_rework_event WHERE ticket_id = NEW.ticket_id AND action = 'receive' AND revoked_at IS NULL;
        IF received_quantity IS NULL OR NEW.quantity <> received_quantity THEN
            RAISE EXCEPTION '返修回交总数必须等于实际接收数量' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_qc_rework_event BEFORE INSERT ON qc_rework_event
FOR EACH ROW EXECUTE FUNCTION validate_qc_rework_event();

CREATE FUNCTION validate_qc_movement() RETURNS TRIGGER AS $$
DECLARE good NUMERIC; issued NUMERIC;
BEGIN
    IF EXISTS (SELECT 1 FROM department_work_order wo JOIN plan_product_route route
        ON (route.production_plan_id, route.product_id, route.material_node_id, route.department_node_id)
        = (wo.production_plan_id, wo.product_id, wo.material_node_id, wo.department_node_id)
        WHERE wo.id = NEW.work_order_id AND route.department_code = 'qc') THEN
        PERFORM plan.id FROM production_plan plan JOIN department_work_order wo ON wo.production_plan_id = plan.id
            WHERE wo.id = NEW.work_order_id FOR UPDATE OF plan;
        IF NEW.direction = 'receipt' THEN
            RAISE EXCEPTION 'QC来料必须登记质检' USING ERRCODE = '23514';
        END IF;
        SELECT COALESCE(SUM(good_quantity), 0) INTO good FROM qc_inspection WHERE work_order_id = NEW.work_order_id AND revoked_at IS NULL;
        SELECT COALESCE(SUM(quantity), 0) INTO issued FROM department_work_order_movement
            WHERE work_order_id = NEW.work_order_id AND direction = 'issue' AND revoked_at IS NULL;
        IF NEW.quantity > good - issued THEN
            RAISE EXCEPTION 'QC出料不能超过合格余量' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_qc_movement BEFORE INSERT ON department_work_order_movement
FOR EACH ROW EXECUTE FUNCTION validate_qc_movement();

CREATE FUNCTION validate_handoff_ticket() RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM department_work_order_movement AS issue
        JOIN department_work_order AS source ON source.id = issue.work_order_id
        JOIN department_work_order AS target ON target.id = NEW.target_work_order_id
        WHERE issue.id = NEW.issue_movement_id AND issue.direction = 'issue'
            AND source.production_plan_id = target.production_plan_id AND source.product_id = target.product_id
    ) THEN
        RAISE EXCEPTION '交接票必须引用同计划的出料和目标工单' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_handoff_ticket BEFORE INSERT ON department_handoff_ticket
FOR EACH ROW EXECUTE FUNCTION validate_handoff_ticket();

CREATE FUNCTION validate_piecework_route() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.document_type = 'piecework' AND NOT EXISTS (
        SELECT 1 FROM department_handoff_ticket ticket
        JOIN department_work_order source ON source.id = NEW.work_order_id
        JOIN department_work_order target ON target.id = ticket.target_work_order_id
        JOIN plan_product_route sr ON (sr.production_plan_id, sr.product_id, sr.material_node_id, sr.department_node_id)
            = (source.production_plan_id, source.product_id, source.material_node_id, source.department_node_id)
        JOIN plan_product_route tr ON (tr.production_plan_id, tr.product_id, tr.material_node_id, tr.department_node_id)
            = (target.production_plan_id, target.product_id, target.material_node_id, target.department_node_id)
        WHERE ticket.issue_movement_id = NEW.id AND sr.department_code = 'grinding' AND tr.department_code = 'qc'
    ) THEN RAISE EXCEPTION '计件单仅允许磨房向QC交接' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER trg_piecework_route AFTER INSERT ON department_work_order_movement
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION validate_piecework_route();

CREATE FUNCTION validate_movement_receipt_link() RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM department_work_order_movement AS issue
        JOIN department_work_order_movement AS receipt ON receipt.work_order_id = issue.work_order_id
        WHERE issue.id = NEW.issue_movement_id AND receipt.id = NEW.receipt_movement_id
            AND issue.direction = 'issue' AND receipt.direction = 'receipt'
    ) THEN
        RAISE EXCEPTION '出料只能关联本工单到料' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_movement_receipt_link BEFORE INSERT ON department_movement_receipt_link
FOR EACH ROW EXECUTE FUNCTION validate_movement_receipt_link();

CREATE FUNCTION validate_ticket_receipt() RETURNS TRIGGER AS $$
DECLARE
    issue_quantity BIGINT;
BEGIN
    IF NEW.receipt_source = 'ticket' THEN
        SELECT issue.quantity INTO issue_quantity
        FROM department_handoff_ticket AS ticket
        JOIN department_work_order_movement AS issue ON issue.id = ticket.issue_movement_id
        WHERE ticket.id = NEW.ticket_id FOR UPDATE OF ticket;
        IF NOT FOUND THEN
            RAISE EXCEPTION '交接票不存在' USING ERRCODE = '23514';
        END IF;
        IF NEW.quantity < issue_quantity AND NEW.note !~ '[^[:space:]]' THEN
            RAISE EXCEPTION '登记到料数量小于交接票数量，必须填写备注' USING ERRCODE = '23514';
        END IF;
        IF EXISTS (SELECT 1 FROM department_work_order_movement WHERE ticket_id = NEW.ticket_id AND revoked_at IS NULL) THEN
            RAISE EXCEPTION '此交接票已登记到料，不能再次登记' USING ERRCODE = '23514';
        END IF;
        IF NEW.quantity > issue_quantity THEN
            RAISE EXCEPTION '交接到料不能超过上游出料数量' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.receipt_source = 'ticket' AND NOT EXISTS (
        SELECT 1 FROM department_handoff_ticket AS ticket
        JOIN department_work_order_movement AS issue ON issue.id = ticket.issue_movement_id
        JOIN department_work_order AS source ON source.id = issue.work_order_id
        WHERE ticket.id = NEW.ticket_id AND ticket.target_work_order_id = NEW.work_order_id
            AND issue.revoked_at IS NULL AND source.material_node_id = NEW.input_material_node_id
    ) THEN
        RAISE EXCEPTION '到料必须引用发给本工单的交接票及来源物料' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER trg_validate_ticket_receipt BEFORE INSERT ON department_work_order_movement
FOR EACH ROW EXECUTE FUNCTION validate_ticket_receipt();

CREATE FUNCTION protect_department_movement_history() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND TG_TABLE_NAME IN ('department_work_order_movement', 'qc_inspection',
        'qc_rework_event', 'warehouse_pick', 'outsource_dispatch', 'outsource_return', 'purchase_order', 'purchase_receipt') THEN
        IF (to_jsonb(OLD)->>'revoked_at') IS NULL AND (to_jsonb(NEW)->>'revoked_at') IS NOT NULL
            AND (to_jsonb(NEW)->>'revoked_by') IS NOT NULL
            AND (to_jsonb(NEW)->>'revoke_reason') ~ '[^[:space:]]'
            AND (to_jsonb(NEW) - ARRAY['revoked_at', 'revoked_by', 'revoke_reason'])
                = (to_jsonb(OLD) - ARRAY['revoked_at', 'revoked_by', 'revoke_reason']) THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION '到料和出料流水不能修改或删除' USING ERRCODE = '23514';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_purchase_order_immutable BEFORE UPDATE OR DELETE ON purchase_order
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_purchase_order_no_truncate BEFORE TRUNCATE ON purchase_order
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_purchase_receipt_immutable BEFORE UPDATE OR DELETE ON purchase_receipt
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_purchase_receipt_no_truncate BEFORE TRUNCATE ON purchase_receipt
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();

CREATE TRIGGER trg_outsource_dispatch_immutable BEFORE UPDATE OR DELETE ON outsource_dispatch
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_outsource_dispatch_no_truncate BEFORE TRUNCATE ON outsource_dispatch
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_outsource_return_immutable BEFORE UPDATE OR DELETE ON outsource_return
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_outsource_return_no_truncate BEFORE TRUNCATE ON outsource_return
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();

CREATE TRIGGER trg_qc_inspection_immutable BEFORE UPDATE OR DELETE ON qc_inspection
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_qc_inspection_no_truncate BEFORE TRUNCATE ON qc_inspection
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_qc_rework_ticket_immutable BEFORE UPDATE OR DELETE ON qc_rework_ticket
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_qc_rework_ticket_no_truncate BEFORE TRUNCATE ON qc_rework_ticket
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_qc_rework_event_immutable BEFORE UPDATE OR DELETE ON qc_rework_event
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_qc_rework_event_no_truncate BEFORE TRUNCATE ON qc_rework_event
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();

CREATE TRIGGER trg_warehouse_lot_immutable BEFORE UPDATE OR DELETE ON warehouse_lot
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_warehouse_lot_no_truncate BEFORE TRUNCATE ON warehouse_lot
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_warehouse_pick_immutable BEFORE UPDATE OR DELETE ON warehouse_pick
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_warehouse_pick_no_truncate BEFORE TRUNCATE ON warehouse_pick
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_warehouse_allocation_immutable BEFORE UPDATE OR DELETE ON warehouse_allocation
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_warehouse_allocation_no_truncate BEFORE TRUNCATE ON warehouse_allocation
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();

CREATE TRIGGER trg_department_movement_immutable
BEFORE UPDATE OR DELETE ON department_work_order_movement
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();

CREATE TRIGGER trg_department_movement_no_truncate
BEFORE TRUNCATE ON department_work_order_movement
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();

CREATE TRIGGER trg_handoff_immutable BEFORE UPDATE OR DELETE ON department_handoff_ticket
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_handoff_no_truncate BEFORE TRUNCATE ON department_handoff_ticket
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_receipt_link_immutable BEFORE UPDATE OR DELETE ON department_movement_receipt_link
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();
CREATE TRIGGER trg_receipt_link_no_truncate BEFORE TRUNCATE ON department_movement_receipt_link
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();

CREATE FUNCTION protect_recorded_department_work_order() RETURNS TRIGGER AS $$
BEGIN
    IF ROW(NEW.production_plan_id, NEW.product_id, NEW.material_node_id, NEW.department_node_id, NEW.task_quantity)
        IS DISTINCT FROM ROW(OLD.production_plan_id, OLD.product_id, OLD.material_node_id, OLD.department_node_id, OLD.task_quantity)
        AND (EXISTS (SELECT 1 FROM department_work_order_movement WHERE work_order_id = OLD.id)
             OR EXISTS (SELECT 1 FROM qc_inspection WHERE work_order_id = OLD.id)
             OR EXISTS (SELECT 1 FROM purchase_order WHERE work_order_id = OLD.id)) THEN
        RAISE EXCEPTION '已有流水或质检记录，不能修改工单来源或任务数量' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_recorded_department_work_order
BEFORE UPDATE ON department_work_order
FOR EACH ROW EXECUTE FUNCTION protect_recorded_department_work_order();

-- 表约束补充

ALTER TABLE product
ADD CONSTRAINT fk_product_current_version
FOREIGN KEY (id, version)
REFERENCES product_version(product_id, version)
DEFERRABLE INITIALLY DEFERRED;

-- 通用更新时间函数

CREATE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = clock_timestamp();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 更新时间触发器

CREATE TRIGGER trg_product_updated_at
BEFORE UPDATE ON product
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_customer_updated_at
BEFORE UPDATE ON customer
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_product_bom_updated_at
BEFORE UPDATE ON product_bom
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_product_process_flow_updated_at
BEFORE UPDATE ON product_process_flow
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_production_plan_updated_at
BEFORE UPDATE ON production_plan
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 查询索引

CREATE INDEX idx_customer_name_trgm
    ON customer USING GIN (customer_name gin_trgm_ops);

CREATE INDEX idx_product_customer ON product(customer_id);

CREATE INDEX idx_product_product_name_trgm
    ON product USING GIN (product_name gin_trgm_ops);

CREATE INDEX idx_product_factory_code_trgm
    ON product USING GIN (factory_code gin_trgm_ops);

CREATE INDEX idx_product_customer_code_trgm
    ON product USING GIN (customer_code gin_trgm_ops);

CREATE INDEX idx_product_bom_part_name_trgm
    ON product_bom USING GIN (part_name gin_trgm_ops);

CREATE INDEX idx_product_bom_part_no_trgm
    ON product_bom USING GIN (part_no gin_trgm_ops);

CREATE INDEX idx_product_updated ON product(updated_at DESC, id DESC);

CREATE INDEX idx_product_bom_product ON product_bom(product_id, sort_order);

CREATE INDEX idx_production_plan_status ON production_plan(status, id);

CREATE INDEX idx_production_plan_customer ON production_plan(customer_id);

CREATE INDEX idx_production_plan_updated ON production_plan(updated_at DESC, id DESC);

CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);

CREATE INDEX idx_user_sessions_user ON user_sessions(user_id);

-- 初始化数据：基础资料及可删除的开发示例

INSERT INTO production_department (code, name) VALUES
('stamp', '冲压部'), ('cnc', 'CNC部'), ('grinding', '磨房'),
('outsource', '委外部'), ('vibration', '震机部'), ('laser', '激光部'), ('assembly', '装配部'),
('purchase', '外购部'), ('finished', '成品部'), ('qc', 'QC部'), ('warehouse', '仓库部');

INSERT INTO users (
    username, password, is_system, role, permissions
) VALUES
(
    'engineering', '1', FALSE, 'engineer',
    'engineering:product:view,engineering:product:add,engineering:product:edit'
),
(
    'business', '1', FALSE, 'planner',
    'engineering:product:view,plan:view,plan:add,plan:edit,plan:confirm,plan:cancel'
);

INSERT INTO users (username, password, is_system, role, department_code, permissions)
SELECT code, '1', FALSE, 'production', code, 'department:work-order:view,department:work-order:operate'
FROM production_department;

INSERT INTO customer (customer_name) VALUES ('Celine');

-- 工程示例包含 Z8737、Z8738 和下方独立确认订单使用的 Z8739。
INSERT INTO product (customer_id, product_name, factory_code, customer_code, version)
SELECT customer.id, 'L24.4 椭圆搭扣', 'Z8737', 'FIG6850', 1
FROM customer
WHERE customer.customer_name = 'Celine';

INSERT INTO product_version (product_id, version, value)
SELECT id, 1, 'V1' FROM product WHERE factory_code = 'Z8737';

INSERT INTO product_bom (product_id, product_version, part_name, part_no, pcs, remark, sort_order)
SELECT product.id, 1, component.part_name, component.part_no, 1, NULL, component.sort_order
FROM product
CROSS JOIN (VALUES
    ('主体', 'Z8737-01', 1),
    ('过桥', 'Z8737-02', 2),
    ('冬菇头', 'Z8737-03', 3)
) AS component(part_name, part_no, sort_order)
WHERE product.factory_code = 'Z8737';

-- 三配件先经过独立仓库与QC，再在激光汇合；装配体经过QC、共享仓库及委外后复检。
INSERT INTO product_process_flow (product_id, product_version, flow_json)
SELECT product.id, 1, jsonb_build_object(
    'schema_version', 8,
    'nodes', jsonb_build_array(
        jsonb_build_object('id', 'part-body', 'type', 'part', 'x', 0, 'y', 0,
            'label', body.part_no || ' · ' || body.part_name, 'bom_item_id', body.id),
        jsonb_build_object('id', 'stamp-body', 'type', 'department', 'x', 500, 'y', 0,
            'label', '冲压部', 'department_code', 'stamp'),
        jsonb_build_object('id', 'warehouse-body', 'type', 'department', 'x', 1000, 'y', 0,
            'label', '仓库部', 'department_code', 'warehouse'),
        jsonb_build_object('id', 'cnc-body', 'type', 'department', 'x', 1500, 'y', 0,
            'label', 'CNC部', 'department_code', 'cnc'),
        jsonb_build_object('id', 'grinding-body-before', 'type', 'department', 'x', 2000, 'y', 0,
            'label', '磨房', 'department_code', 'grinding'),
        jsonb_build_object('id', 'qc-body', 'type', 'department', 'x', 2500, 'y', 0,
            'label', 'QC部', 'department_code', 'qc'),
        jsonb_build_object('id', 'part-bridge', 'type', 'part', 'x', 0, 'y', 500,
            'label', bridge.part_no || ' · ' || bridge.part_name, 'bom_item_id', bridge.id),
        jsonb_build_object('id', 'stamp-bridge', 'type', 'department', 'x', 500, 'y', 500,
            'label', '冲压部', 'department_code', 'stamp'),
        jsonb_build_object('id', 'warehouse-bridge', 'type', 'department', 'x', 1000, 'y', 500,
            'label', '仓库部', 'department_code', 'warehouse'),
        jsonb_build_object('id', 'cnc-bridge', 'type', 'department', 'x', 1500, 'y', 500,
            'label', 'CNC部', 'department_code', 'cnc'),
        jsonb_build_object('id', 'grinding-bridge', 'type', 'department', 'x', 2000, 'y', 500,
            'label', '磨房', 'department_code', 'grinding'),
        jsonb_build_object('id', 'qc-bridge', 'type', 'department', 'x', 2500, 'y', 500,
            'label', 'QC部', 'department_code', 'qc'),
        jsonb_build_object('id', 'part-head', 'type', 'part', 'x', 0, 'y', 1000,
            'label', head.part_no || ' · ' || head.part_name, 'bom_item_id', head.id),
        jsonb_build_object('id', 'purchase-head', 'type', 'department', 'x', 500, 'y', 1000,
            'label', '外购部', 'department_code', 'purchase'),
        jsonb_build_object('id', 'warehouse-head', 'type', 'department', 'x', 1000, 'y', 1000,
            'label', '仓库部', 'department_code', 'warehouse'),
        jsonb_build_object('id', 'grinding-head', 'type', 'department', 'x', 1500, 'y', 1000,
            'label', '磨房', 'department_code', 'grinding'),
        jsonb_build_object('id', 'qc-head', 'type', 'department', 'x', 2500, 'y', 1000,
            'label', 'QC部', 'department_code', 'qc'),
        jsonb_build_object('id', 'laser-merge', 'type', 'department', 'x', 3000, 'y', 500,
            'label', '激光部', 'department_code', 'laser'),
        jsonb_build_object('id', 'grinding-assembly', 'type', 'department', 'x', 3500, 'y', 500,
            'label', '磨房', 'department_code', 'grinding'),
        jsonb_build_object('id', 'vibration-next', 'type', 'department', 'x', 4000, 'y', 500,
            'label', '震机部', 'department_code', 'vibration'),
        jsonb_build_object('id', 'qc-assembly-before-warehouse', 'type', 'department', 'x', 4500, 'y', 500,
            'label', 'QC部', 'department_code', 'qc'),
        jsonb_build_object('id', 'warehouse-assembly', 'type', 'department', 'x', 5000, 'y', 500,
            'label', '仓库部', 'department_code', 'warehouse'),
        jsonb_build_object('id', 'outsource-next', 'type', 'department', 'x', 5500, 'y', 500,
            'label', '委外部', 'department_code', 'outsource'),
        jsonb_build_object('id', 'qc-assembly-after-outsource', 'type', 'department', 'x', 6000, 'y', 500,
            'label', 'QC部', 'department_code', 'qc'),
        jsonb_build_object('id', 'finished-end', 'type', 'department', 'x', 6500, 'y', 500,
            'label', '成品部', 'department_code', 'finished')
    ),
    'edges', jsonb_build_array(
        jsonb_build_object('id', 'line-1', 'edge_type', 'polyline',
            'source_node_id', 'part-body', 'target_node_id', 'stamp-body'),
        jsonb_build_object('id', 'line-2', 'edge_type', 'polyline',
            'source_node_id', 'stamp-body', 'target_node_id', 'warehouse-body'),
        jsonb_build_object('id', 'line-3', 'edge_type', 'polyline',
            'source_node_id', 'warehouse-body', 'target_node_id', 'cnc-body'),
        jsonb_build_object('id', 'line-4', 'edge_type', 'polyline',
            'source_node_id', 'cnc-body', 'target_node_id', 'grinding-body-before'),
        jsonb_build_object('id', 'line-5', 'edge_type', 'polyline',
            'source_node_id', 'grinding-body-before', 'target_node_id', 'qc-body'),
        jsonb_build_object('id', 'line-6', 'edge_type', 'polyline',
            'source_node_id', 'qc-body', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'line-7', 'edge_type', 'polyline',
            'source_node_id', 'part-bridge', 'target_node_id', 'stamp-bridge'),
        jsonb_build_object('id', 'line-8', 'edge_type', 'polyline',
            'source_node_id', 'stamp-bridge', 'target_node_id', 'warehouse-bridge'),
        jsonb_build_object('id', 'line-9', 'edge_type', 'polyline',
            'source_node_id', 'warehouse-bridge', 'target_node_id', 'cnc-bridge'),
        jsonb_build_object('id', 'line-10', 'edge_type', 'polyline',
            'source_node_id', 'cnc-bridge', 'target_node_id', 'grinding-bridge'),
        jsonb_build_object('id', 'line-11', 'edge_type', 'polyline',
            'source_node_id', 'grinding-bridge', 'target_node_id', 'qc-bridge'),
        jsonb_build_object('id', 'line-12', 'edge_type', 'polyline',
            'source_node_id', 'qc-bridge', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'line-13', 'edge_type', 'polyline',
            'source_node_id', 'part-head', 'target_node_id', 'purchase-head'),
        jsonb_build_object('id', 'line-14', 'edge_type', 'polyline',
            'source_node_id', 'purchase-head', 'target_node_id', 'warehouse-head'),
        jsonb_build_object('id', 'line-15', 'edge_type', 'polyline',
            'source_node_id', 'warehouse-head', 'target_node_id', 'grinding-head'),
        jsonb_build_object('id', 'line-16', 'edge_type', 'polyline',
            'source_node_id', 'grinding-head', 'target_node_id', 'qc-head'),
        jsonb_build_object('id', 'line-17', 'edge_type', 'polyline',
            'source_node_id', 'qc-head', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'line-18', 'edge_type', 'polyline',
            'source_node_id', 'laser-merge', 'target_node_id', 'grinding-assembly'),
        jsonb_build_object('id', 'line-19', 'edge_type', 'polyline',
            'source_node_id', 'grinding-assembly', 'target_node_id', 'vibration-next'),
        jsonb_build_object('id', 'line-20', 'edge_type', 'polyline',
            'source_node_id', 'vibration-next', 'target_node_id', 'qc-assembly-before-warehouse'),
        jsonb_build_object('id', 'line-21', 'edge_type', 'polyline',
            'source_node_id', 'qc-assembly-before-warehouse', 'target_node_id', 'warehouse-assembly'),
        jsonb_build_object('id', 'line-22', 'edge_type', 'polyline',
            'source_node_id', 'warehouse-assembly', 'target_node_id', 'outsource-next'),
        jsonb_build_object('id', 'line-23', 'edge_type', 'polyline',
            'source_node_id', 'outsource-next', 'target_node_id', 'qc-assembly-after-outsource'),
        jsonb_build_object('id', 'line-24', 'edge_type', 'polyline',
            'source_node_id', 'qc-assembly-after-outsource', 'target_node_id', 'finished-end')
    )
)
FROM product
JOIN product_bom AS body ON body.product_id = product.id
    AND body.product_version = 1 AND body.part_no = 'Z8737-01'
JOIN product_bom AS bridge ON bridge.product_id = product.id
    AND bridge.product_version = 1 AND bridge.part_no = 'Z8737-02'
JOIN product_bom AS head ON head.product_id = product.id
    AND head.product_version = 1 AND head.part_no = 'Z8737-03'
WHERE product.factory_code = 'Z8737';

-- 当前路线投影：汇合前14项配件安排，激光起8项装配体安排。
INSERT INTO product_department_route (product_id, material_node_id, department_node_id, department_code)
SELECT product.id, route.material_node_id, route.department_node_id, route.department_code
FROM product
CROSS JOIN (VALUES
    ('part-body', 'stamp-body', 'stamp'),
    ('part-body', 'warehouse-body', 'warehouse'),
    ('part-body', 'cnc-body', 'cnc'),
    ('part-body', 'grinding-body-before', 'grinding'),
    ('part-body', 'qc-body', 'qc'),
    ('part-bridge', 'stamp-bridge', 'stamp'),
    ('part-bridge', 'warehouse-bridge', 'warehouse'),
    ('part-bridge', 'cnc-bridge', 'cnc'),
    ('part-bridge', 'grinding-bridge', 'grinding'),
    ('part-bridge', 'qc-bridge', 'qc'),
    ('part-head', 'purchase-head', 'purchase'),
    ('part-head', 'warehouse-head', 'warehouse'),
    ('part-head', 'grinding-head', 'grinding'),
    ('part-head', 'qc-head', 'qc'),
    ('laser-merge', 'laser-merge', 'laser'),
    ('laser-merge', 'grinding-assembly', 'grinding'),
    ('laser-merge', 'vibration-next', 'vibration'),
    ('laser-merge', 'qc-assembly-before-warehouse', 'qc'),
    ('laser-merge', 'warehouse-assembly', 'warehouse'),
    ('laser-merge', 'outsource-next', 'outsource'),
    ('laser-merge', 'qc-assembly-after-outsource', 'qc'),
    ('laser-merge', 'finished-end', 'finished')
) AS route(material_node_id, department_node_id, department_code)
WHERE product.factory_code = 'Z8737';

INSERT INTO product_route_component (product_id, material_node_id, department_node_id, product_bom_id)
SELECT route.product_id, route.material_node_id, route.department_node_id, part.id
FROM product_department_route AS route
JOIN product_bom AS part ON part.product_id = route.product_id AND part.product_version = 1
WHERE (route.material_node_id = 'part-body' AND part.part_no = 'Z8737-01')
    OR (route.material_node_id = 'part-bridge' AND part.part_no = 'Z8737-02')
    OR (route.material_node_id = 'part-head' AND part.part_no = 'Z8737-03')
    OR route.material_node_id = 'laser-merge';

-- Z8738：面盖、底座先激光汇合，再与连接环在装配部二次汇合。
INSERT INTO product (customer_id, product_name, factory_code, customer_code, version)
SELECT id, '双段装配搭扣', 'Z8738', 'DEMO-Z8738', 1
FROM customer WHERE customer_name = 'Celine';

INSERT INTO product_version (product_id, version, value)
SELECT id, 1, 'V1' FROM product WHERE factory_code = 'Z8738';

INSERT INTO product_bom (product_id, product_version, part_name, part_no, pcs, remark, sort_order)
SELECT product.id, 1, component.part_name, component.part_no, 1, NULL, component.sort_order
FROM product
CROSS JOIN (VALUES
    ('面盖', 'Z8738-01', 1),
    ('底座', 'Z8738-02', 2),
    ('连接环', 'Z8738-03', 3)
) AS component(part_name, part_no, sort_order)
WHERE product.factory_code = 'Z8738';

INSERT INTO product_process_flow (product_id, product_version, flow_json)
SELECT product.id, 1, jsonb_build_object(
    'schema_version', 8,
    'nodes', jsonb_build_array(
        jsonb_build_object('id', 'part-cover', 'type', 'part', 'x', 0, 'y', 0,
            'label', cover.part_no || ' · ' || cover.part_name, 'bom_item_id', cover.id),
        jsonb_build_object('id', 'part-base', 'type', 'part', 'x', 0, 'y', 500,
            'label', base.part_no || ' · ' || base.part_name, 'bom_item_id', base.id),
        jsonb_build_object('id', 'part-ring', 'type', 'part', 'x', 0, 'y', 1000,
            'label', ring.part_no || ' · ' || ring.part_name, 'bom_item_id', ring.id),
        jsonb_build_object('id', 'stamp-cover', 'type', 'department', 'x', 500, 'y', 0,
            'label', '冲压部', 'department_code', 'stamp'),
        jsonb_build_object('id', 'stamp-base', 'type', 'department', 'x', 500, 'y', 500,
            'label', '冲压部', 'department_code', 'stamp'),
        jsonb_build_object('id', 'purchase-ring', 'type', 'department', 'x', 500, 'y', 1000,
            'label', '外购部', 'department_code', 'purchase'),
        jsonb_build_object('id', 'laser-primary', 'type', 'department', 'x', 1000, 'y', 250,
            'label', '激光部', 'department_code', 'laser'),
        jsonb_build_object('id', 'assembly-final', 'type', 'department', 'x', 1500, 'y', 500,
            'label', '装配部', 'department_code', 'assembly'),
        jsonb_build_object('id', 'finished-final', 'type', 'department', 'x', 2000, 'y', 500,
            'label', '成品部', 'department_code', 'finished')
    ),
    'edges', jsonb_build_array(
        jsonb_build_object('id', 'line-1', 'edge_type', 'polyline',
            'source_node_id', 'part-cover', 'target_node_id', 'stamp-cover'),
        jsonb_build_object('id', 'line-2', 'edge_type', 'polyline',
            'source_node_id', 'stamp-cover', 'target_node_id', 'laser-primary'),
        jsonb_build_object('id', 'line-3', 'edge_type', 'polyline',
            'source_node_id', 'part-base', 'target_node_id', 'stamp-base'),
        jsonb_build_object('id', 'line-4', 'edge_type', 'polyline',
            'source_node_id', 'stamp-base', 'target_node_id', 'laser-primary'),
        jsonb_build_object('id', 'line-5', 'edge_type', 'polyline',
            'source_node_id', 'part-ring', 'target_node_id', 'purchase-ring'),
        jsonb_build_object('id', 'line-6', 'edge_type', 'polyline',
            'source_node_id', 'purchase-ring', 'target_node_id', 'assembly-final'),
        jsonb_build_object('id', 'line-7', 'edge_type', 'polyline',
            'source_node_id', 'laser-primary', 'target_node_id', 'assembly-final'),
        jsonb_build_object('id', 'line-8', 'edge_type', 'polyline',
            'source_node_id', 'assembly-final', 'target_node_id', 'finished-final')
    )
)
FROM product
JOIN product_bom AS cover ON cover.product_id = product.id
    AND cover.product_version = 1 AND cover.part_no = 'Z8738-01'
JOIN product_bom AS base ON base.product_id = product.id
    AND base.product_version = 1 AND base.part_no = 'Z8738-02'
JOIN product_bom AS ring ON ring.product_id = product.id
    AND ring.product_version = 1 AND ring.part_no = 'Z8738-03'
WHERE product.factory_code = 'Z8738';

INSERT INTO product_department_route (product_id, material_node_id, department_node_id, department_code)
SELECT product.id, route.material_node_id, route.department_node_id, route.department_code
FROM product
CROSS JOIN (VALUES
    ('part-cover', 'stamp-cover', 'stamp'),
    ('part-base', 'stamp-base', 'stamp'),
    ('part-ring', 'purchase-ring', 'purchase'),
    ('laser-primary', 'laser-primary', 'laser'),
    ('assembly-final', 'assembly-final', 'assembly'),
    ('assembly-final', 'finished-final', 'finished')
) AS route(material_node_id, department_node_id, department_code)
WHERE product.factory_code = 'Z8738';

INSERT INTO product_route_component (product_id, material_node_id, department_node_id, product_bom_id)
SELECT route.product_id, route.material_node_id, route.department_node_id, part.id
FROM product_department_route AS route
JOIN product AS product ON product.id = route.product_id
JOIN product_bom AS part ON part.product_id = route.product_id AND part.product_version = 1
WHERE product.factory_code = 'Z8738' AND (
    (route.material_node_id = 'part-cover' AND part.part_no = 'Z8738-01')
    OR (route.material_node_id = 'part-base' AND part.part_no = 'Z8738-02')
    OR (route.material_node_id = 'part-ring' AND part.part_no = 'Z8738-03')
    OR (route.material_node_id = 'laser-primary' AND part.part_no IN ('Z8738-01', 'Z8738-02'))
    OR route.material_node_id = 'assembly-final'
);

-- 两个相同草稿计划，各包含两个产品，数量独立。
INSERT INTO production_plan (customer_id, order_no, order_date, delivery_date, status, revision)
SELECT customer.id, seed.order_no, DATE '2026-11-18', DATE '2026-12-18', 'draft', 1 FROM customer
CROSS JOIN (VALUES ('ORDER-Z8737-0001'), ('ORDER-Z8737-0002')) AS seed(order_no)
WHERE customer.customer_name = 'Celine';

INSERT INTO production_plan_item (
    production_plan_id, product_id, customer_id, order_quantity, production_quantity,
    source_version, source_version_value, product_name, factory_code, customer_code, bom_snapshot, process_flow_snapshot
)
SELECT plan.id, product.id, plan.customer_id, item.order_quantity, item.production_quantity,
       product.version, version.value, product.product_name, product.factory_code, product.customer_code,
       (SELECT jsonb_agg(jsonb_build_object('id', bom.id, 'part_name', bom.part_name,
            'part_no', bom.part_no, 'pcs', bom.pcs, 'remark', COALESCE(bom.remark, ''),
            'sort_order', bom.sort_order) ORDER BY bom.sort_order)
        FROM product_bom AS bom WHERE bom.product_id = product.id AND bom.product_version = product.version),
       flow.flow_json
FROM production_plan AS plan
JOIN product ON product.customer_id = plan.customer_id
JOIN product_process_flow AS flow ON flow.product_id = product.id AND flow.product_version = product.version
JOIN product_version AS version ON version.product_id = product.id AND version.version = product.version
JOIN (VALUES ('Z8737', 3000, 4000), ('Z8738', 1000, 1200))
    AS item(factory_code, order_quantity, production_quantity) ON item.factory_code = product.factory_code
WHERE plan.order_no IN ('ORDER-Z8737-0001', 'ORDER-Z8737-0002');

-- Z8739：独立的已确认订单示例，三路物料在装配部汇合。
INSERT INTO product (customer_id, product_name, factory_code, customer_code, version)
SELECT id, '三配件装配搭扣', 'Z8739', 'DEMO-Z8739', 1 FROM customer WHERE customer_name = 'Celine';

INSERT INTO product_version (product_id, version, value)
SELECT id, 1, 'V1' FROM product WHERE factory_code = 'Z8739';

INSERT INTO product_bom (product_id, product_version, part_name, part_no, pcs, sort_order)
SELECT product.id, 1, component.name, component.number, 1, component.position
FROM product CROSS JOIN (VALUES
    ('主体', 'Z8739-01', 1), ('过桥', 'Z8739-02', 2), ('冬菇头', 'Z8739-03', 3)
) AS component(name, number, position) WHERE product.factory_code = 'Z8739';

WITH nodes AS (
    SELECT product.id AS product_id, jsonb_build_object('id', part.node_id, 'type', 'part',
        'x', 0, 'y', part.y, 'label', bom.part_no || ' · ' || bom.part_name, 'bom_item_id', bom.id) AS node
    FROM product JOIN product_bom bom ON bom.product_id = product.id AND bom.product_version = 1
    JOIN (VALUES ('part-body', 'Z8739-01', 0), ('part-bridge', 'Z8739-02', 400),
        ('part-head', 'Z8739-03', 800)) AS part(node_id, part_no, y) ON part.part_no = bom.part_no
    WHERE product.factory_code = 'Z8739'
    UNION ALL
    SELECT product.id, jsonb_build_object('id', department.node_id, 'type', 'department',
        'x', department.x, 'y', department.y, 'label', department.label, 'department_code', department.code)
    FROM product CROSS JOIN (VALUES
        ('purchase-body', 'purchase', '外购部', 400, 0),
        ('qc-body', 'qc', 'QC部', 800, 0),
        ('warehouse-body', 'warehouse', '仓库部', 1200, 0),
        ('stamp-bridge', 'stamp', '冲压部', 400, 400),
        ('grinding-bridge', 'grinding', '磨房', 800, 400),
        ('qc-bridge', 'qc', 'QC部', 1200, 400),
        ('stamp-head', 'stamp', '冲压部', 400, 800),
        ('plating-head', 'outsource', '外发电镀', 800, 800),
        ('qc-head', 'qc', 'QC部', 1200, 800),
        ('assembly-final', 'assembly', '装配部', 1600, 400),
        ('finished-final', 'finished', '成品部', 2000, 400)
    ) AS department(node_id, code, label, x, y) WHERE product.factory_code = 'Z8739'
), edges AS (
    SELECT jsonb_agg(jsonb_build_object('id', 'edge-' || source || '-' || target,
        'edge_type', 'polyline', 'source_node_id', source, 'target_node_id', target)
        ORDER BY source, target) AS data
    FROM (VALUES
        ('part-body', 'purchase-body'), ('purchase-body', 'qc-body'), ('qc-body', 'warehouse-body'),
        ('warehouse-body', 'assembly-final'), ('part-bridge', 'stamp-bridge'),
        ('stamp-bridge', 'grinding-bridge'), ('grinding-bridge', 'qc-bridge'),
        ('qc-bridge', 'assembly-final'), ('part-head', 'stamp-head'),
        ('stamp-head', 'plating-head'), ('plating-head', 'qc-head'),
        ('qc-head', 'assembly-final'), ('assembly-final', 'finished-final')
    ) AS edge(source, target)
)
INSERT INTO product_process_flow (product_id, product_version, flow_json)
SELECT nodes.product_id, 1, jsonb_build_object('schema_version', 8,
    'nodes', jsonb_agg(nodes.node ORDER BY nodes.node->>'id'), 'edges', edges.data)
FROM nodes CROSS JOIN edges GROUP BY nodes.product_id, edges.data;

INSERT INTO product_department_route (product_id, material_node_id, department_node_id, department_code)
SELECT product.id, route.material, route.node, route.code FROM product CROSS JOIN (VALUES
    ('part-body', 'purchase-body', 'purchase'), ('part-body', 'qc-body', 'qc'),
    ('part-body', 'warehouse-body', 'warehouse'), ('part-bridge', 'stamp-bridge', 'stamp'),
    ('part-bridge', 'grinding-bridge', 'grinding'), ('part-bridge', 'qc-bridge', 'qc'),
    ('part-head', 'stamp-head', 'stamp'), ('part-head', 'plating-head', 'outsource'),
    ('part-head', 'qc-head', 'qc'), ('assembly-final', 'assembly-final', 'assembly'),
    ('assembly-final', 'finished-final', 'finished')
) AS route(material, node, code) WHERE product.factory_code = 'Z8739';

INSERT INTO product_route_component (product_id, material_node_id, department_node_id, product_bom_id)
SELECT route.product_id, route.material_node_id, route.department_node_id, bom.id
FROM product_department_route route JOIN product ON product.id = route.product_id
JOIN product_bom bom ON bom.product_id = product.id AND bom.product_version = 1
WHERE product.factory_code = 'Z8739' AND (
    (route.material_node_id = 'part-body' AND bom.part_no = 'Z8739-01')
    OR (route.material_node_id = 'part-bridge' AND bom.part_no = 'Z8739-02')
    OR (route.material_node_id = 'part-head' AND bom.part_no = 'Z8739-03')
    OR route.material_node_id = 'assembly-final'
);

INSERT INTO production_plan (customer_id, order_no, order_date, delivery_date, status, revision, confirmed_at, confirmed_by)
SELECT id, 'ORDER-Z8739-0001', DATE '2026-11-20', DATE '2026-12-20', 'confirmed', 1,
    CURRENT_TIMESTAMP, 'business' FROM customer WHERE customer_name = 'Celine';

INSERT INTO production_plan_item (
    production_plan_id, product_id, customer_id, order_quantity, production_quantity,
    source_version, source_version_value, product_name, factory_code, customer_code, bom_snapshot, process_flow_snapshot
)
SELECT plan.id, product.id, plan.customer_id, 1000, 1200, product.version, version.value,
    product.product_name, product.factory_code, product.customer_code,
    (SELECT jsonb_agg(jsonb_build_object('id', bom.id, 'part_name', bom.part_name, 'part_no', bom.part_no,
        'pcs', bom.pcs, 'remark', COALESCE(bom.remark, ''), 'sort_order', bom.sort_order) ORDER BY bom.sort_order)
     FROM product_bom bom WHERE bom.product_id = product.id AND bom.product_version = product.version), flow.flow_json
FROM production_plan plan JOIN product ON product.customer_id = plan.customer_id
JOIN product_version version ON version.product_id = product.id AND version.version = product.version
JOIN product_process_flow flow ON flow.product_id = product.id AND flow.product_version = product.version
WHERE plan.order_no = 'ORDER-Z8739-0001' AND product.factory_code = 'Z8739';

-- 示例快照投影复制各产品的种子组成数据。
INSERT INTO plan_product_route (
    production_plan_id, product_id, material_node_id, department_node_id,
    department_code, part_no, part_name, unit_requirement
)
SELECT item.production_plan_id, item.product_id, route.material_node_id, route.department_node_id,
       route.department_code, string_agg(part.part_no, ' + ' ORDER BY part.part_no),
       CASE WHEN COUNT(part.id) > 1 THEN '（' || string_agg(part.part_name, '+' ORDER BY part.part_no) || '）装配体'
            ELSE MAX(part.part_name) END,
       CASE WHEN COUNT(part.id) > 1 THEN 1 ELSE MAX(part.pcs) END
FROM production_plan_item AS item
JOIN product_department_route AS route ON route.product_id = item.product_id
JOIN product_route_component AS component ON component.product_id = route.product_id
    AND component.material_node_id = route.material_node_id AND component.department_node_id = route.department_node_id
JOIN product_bom AS part ON part.id = component.product_bom_id
GROUP BY item.production_plan_id, item.product_id, route.material_node_id, route.department_node_id, route.department_code;

-- 仅已确认的新订单预置工单；两个原草稿仍由业务确认时生成。
INSERT INTO department_work_order (production_plan_id, product_id, material_node_id, department_node_id, task_quantity)
SELECT route.production_plan_id, route.product_id, route.material_node_id, route.department_node_id,
    item.production_quantity * route.unit_requirement
FROM plan_product_route route
JOIN production_plan plan ON plan.id = route.production_plan_id
JOIN production_plan_item item ON item.production_plan_id = route.production_plan_id AND item.product_id = route.product_id
WHERE plan.order_no = 'ORDER-Z8739-0001' AND plan.status = 'confirmed';

COMMIT;

