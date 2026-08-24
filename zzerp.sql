BEGIN;

-- ============================================================
-- 环境准备（整个破坏性重建受同一事务保护）
-- ============================================================

DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

GRANT ALL ON SCHEMA public TO CURRENT_USER;
GRANT ALL ON SCHEMA public TO public;

-- ============================================================
-- ZZ ERP 数据库初始化
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- 表结构
-- ============================================================

-- ------------------------------------------------------------
-- 认证与会话
-- ------------------------------------------------------------

-- department：部门代码是账号授权和业务归属使用的稳定身份。
CREATE TABLE department (
    id BIGSERIAL PRIMARY KEY,
    department_name TEXT NOT NULL,
    department_code TEXT NOT NULL,
    CONSTRAINT uq_department_name UNIQUE (department_name),
    CONSTRAINT uq_department_code UNIQUE (department_code)
);

-- users：保存系统登录账号、所属部门、角色和权限集合。
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    department TEXT,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    role TEXT NOT NULL,
    permissions TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT fk_users_department
        FOREIGN KEY (department) REFERENCES department(department_code),
    CONSTRAINT ck_users_department_scope CHECK (
        (is_system AND department IS NULL)
        OR (NOT is_system AND department IS NOT NULL)
    )
);

-- user_sessions：保存用户登录会话、CSRF 令牌和会话有效期。
CREATE TABLE user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    csrf_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_sessions_token_hash UNIQUE (token_hash)
);

-- ------------------------------------------------------------
-- 客户、工程产品、版本、BOM 与工艺路线
-- ------------------------------------------------------------

-- customer：保存工程产品和业务订单共用的客户主数据。
CREATE TABLE customer (
    id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_customer_name UNIQUE (customer_name)
);

-- product：保存工程确认后的可复用产品主数据和当前版本，不代表具体订单或生产批次。
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
    CONSTRAINT ck_product_version CHECK (version > 0),
    CONSTRAINT ck_product_revision CHECK (revision > 0)
);

-- product_version：保存产品的版本清单，供 BOM、流程图和订单锁定具体版本。
CREATE TABLE product_version (
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    version INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, version),
    CONSTRAINT ck_product_version_number CHECK (version > 0)
);

-- product_bom：保存产品各版本的物料明细；同一物料不配置多个来源。
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
    CONSTRAINT uq_product_bom_id_version
        UNIQUE (id, product_id, product_version),
    CONSTRAINT uq_product_bom_part_no UNIQUE (product_id, product_version, part_no),
    CONSTRAINT uq_product_bom_sort_order
        UNIQUE (product_id, product_version, sort_order) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_product_bom_version CHECK (product_version > 0),
    CONSTRAINT ck_product_bom_pcs CHECK (pcs > 0),
    CONSTRAINT ck_product_bom_sort_order CHECK (sort_order > 0)
);

-- product_process_flow：保存产品各版本的流程图 JSON 配置。
CREATE TABLE product_process_flow (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    product_version INT NOT NULL,
    flow_json JSONB NOT NULL DEFAULT '{"schema_version": 4, "nodes": [], "edges": []}'::jsonb,
    draft_flow_json JSONB,
    CONSTRAINT ck_process_flow_json_object
        CHECK (jsonb_typeof(flow_json) = 'object'),
    CONSTRAINT ck_process_flow_schema_version_present
        CHECK (flow_json ? 'schema_version'),
    CONSTRAINT ck_process_flow_schema_version_type
        CHECK (jsonb_typeof(flow_json->'schema_version') = 'number'),
    CONSTRAINT ck_process_flow_schema_version
        CHECK (flow_json->>'schema_version' = '4'),
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
        CHECK (draft_flow_json IS NULL OR draft_flow_json->>'schema_version' = '4'),
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

-- ------------------------------------------------------------
-- 车间、工艺与人员
-- ------------------------------------------------------------

-- workshop：保存部门下属车间，作为工艺和工人的组织范围。
CREATE TABLE workshop (
    id BIGSERIAL PRIMARY KEY,
    department_id BIGINT NOT NULL REFERENCES department(id),
    workshop_name TEXT NOT NULL,
    CONSTRAINT uq_workshop_department_context UNIQUE (id, department_id),
    CONSTRAINT uq_workshop_name UNIQUE (department_id, workshop_name)
);

-- product_route_task：正式流程按物料起点展开后的车间路线投影。
CREATE TABLE product_route_task (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    product_bom_id BIGINT,
    origin_flow_node_id TEXT NOT NULL,
    origin_node_type TEXT NOT NULL,
    origin_item_code TEXT NOT NULL,
    origin_item_name TEXT NOT NULL,
    route_flow_node_id TEXT NOT NULL,
    route_node_type TEXT NOT NULL,
    workshop_id BIGINT NOT NULL REFERENCES workshop(id),
    route_order INT NOT NULL,
    CONSTRAINT fk_product_route_task_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version) ON DELETE CASCADE,
    CONSTRAINT fk_product_route_task_bom_version
        FOREIGN KEY (product_bom_id, product_id, product_version)
        REFERENCES product_bom(id, product_id, product_version) ON DELETE CASCADE,
    CONSTRAINT ck_product_route_task_origin_type
        CHECK (origin_node_type IN ('part', 'assembly')),
    CONSTRAINT ck_product_route_task_origin_scope CHECK (
        (origin_node_type = 'part' AND product_bom_id IS NOT NULL)
        OR (origin_node_type = 'assembly' AND product_bom_id IS NULL)
    ),
    CONSTRAINT ck_product_route_task_node_type
        CHECK (route_node_type IN ('process', 'assembly')),
    CONSTRAINT ck_product_route_task_order CHECK (route_order >= 0),
    CONSTRAINT uq_product_route_task_origin_node UNIQUE (
        product_id, product_version, origin_flow_node_id, route_flow_node_id
    )
);

-- procedure：保存车间可执行的工艺；多路输入工艺按工单记录各个来源的投入数量。
CREATE TABLE procedure (
    id BIGSERIAL PRIMARY KEY,
    workshop_id BIGINT NOT NULL REFERENCES workshop(id),
    procedure_name TEXT NOT NULL,
    procedure_type TEXT NOT NULL DEFAULT 'standard',
    input_mode TEXT NOT NULL DEFAULT 'single',
    CONSTRAINT ck_procedure_type
        CHECK (procedure_type IN ('standard', 'purchase_receipt')),
    CONSTRAINT ck_procedure_input_mode CHECK (input_mode IN ('single', 'multiple')),
    CONSTRAINT uq_procedure_name UNIQUE (workshop_id, procedure_name)
);

-- procedure_price：按产品版本、物料和流程节点配置可选工艺及单价。
CREATE TABLE procedure_price (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    material_key TEXT NOT NULL,
    flow_node_id TEXT NOT NULL,
    procedure_id BIGINT NOT NULL REFERENCES procedure(id),
    unit_price NUMERIC(12, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_procedure_price_product_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version) ON DELETE CASCADE,
    CONSTRAINT ck_procedure_price_nonnegative CHECK (unit_price >= 0),
    CONSTRAINT uq_procedure_price_scope
        UNIQUE (product_id, product_version, material_key, flow_node_id, procedure_id)
);

-- worker：保存部门或车间下可分配到工单、QC 批次的工作人员。
CREATE TABLE worker (
    id BIGSERIAL PRIMARY KEY,
    worker_name TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    workshop_id BIGINT,
    CONSTRAINT fk_worker_workshop_department
        FOREIGN KEY (workshop_id, department_id) REFERENCES workshop(id, department_id)
);

-- ------------------------------------------------------------
-- 客户订单
-- ------------------------------------------------------------

-- customer_order：保存客户订单主信息、业务状态和并发修订版本。
CREATE TABLE customer_order (
    id BIGSERIAL PRIMARY KEY,
    customer_order_no TEXT NOT NULL,
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    status TEXT NOT NULL DEFAULT 'draft',
    revision INT NOT NULL DEFAULT 1,
    remark TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_customer_order_no UNIQUE (customer_order_no),
    CONSTRAINT ck_customer_order_status
        CHECK (status IN ('draft', 'confirmed', 'planned', 'cancelled', 'closed')),
    CONSTRAINT ck_customer_order_revision CHECK (revision > 0)
);

-- customer_order_item：保存客户订单中的产品、锁定版本、订购数量和交期。
CREATE TABLE customer_order_item (
    id BIGSERIAL PRIMARY KEY,
    customer_order_id BIGINT NOT NULL REFERENCES customer_order(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES product(id),
    product_version INT NOT NULL,
    quantity INT NOT NULL,
    delivery_date DATE NOT NULL,
    remark TEXT,
    CONSTRAINT fk_customer_order_item_product_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version),
    CONSTRAINT uq_customer_order_item_id_version
        UNIQUE (id, product_id, product_version),
    CONSTRAINT uq_customer_order_item_context
        UNIQUE (id, customer_order_id, product_id, product_version),
    CONSTRAINT uq_customer_order_item_product_version
        UNIQUE (customer_order_id, product_id, product_version),
    CONSTRAINT ck_order_item_version CHECK (product_version > 0),
    CONSTRAINT ck_order_item_quantity CHECK (quantity > 0)
);

-- production_plan：客户订单确认后自动生成、由业务部另行填写和确认的生产计划。
CREATE TABLE production_plan (
    id BIGSERIAL PRIMARY KEY,
    customer_order_id BIGINT NOT NULL
        REFERENCES customer_order(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'draft',
    revision INT NOT NULL DEFAULT 1,
    confirmed_at TIMESTAMPTZ,
    confirmed_by TEXT,
    completed_at TIMESTAMPTZ,
    completed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_production_plan_order UNIQUE (customer_order_id),
    CONSTRAINT uq_production_plan_context UNIQUE (id, customer_order_id),
    CONSTRAINT ck_production_plan_status
        CHECK (status IN ('draft', 'confirmed', 'cancelled', 'completed')),
    CONSTRAINT ck_production_plan_revision CHECK (revision > 0),
    CONSTRAINT ck_production_plan_confirmation CHECK (
        (status IN ('confirmed', 'completed') AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)
        OR status IN ('draft', 'cancelled')
    ),
    CONSTRAINT ck_production_plan_completion CHECK (
        (status = 'completed' AND completed_at IS NOT NULL AND completed_by IS NOT NULL)
        OR (status <> 'completed' AND completed_at IS NULL AND completed_by IS NULL)
    )
);

-- production_plan_item：内部保留成品、装配体和普通配件节点；业务部只填写普通配件数量。
CREATE TABLE production_plan_item (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL,
    customer_order_id BIGINT NOT NULL,
    customer_order_item_id BIGINT NOT NULL,
    identity_key TEXT NOT NULL,
    item_type TEXT NOT NULL,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    product_bom_id BIGINT,
    flow_node_id TEXT NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    unit_requirement INT NOT NULL,
    gross_required_quantity INT NOT NULL,
    estimated_inventory_quantity INT NOT NULL DEFAULT 0,
    net_required_quantity INT NOT NULL,
    planned_production_quantity INT NOT NULL,
    reserved_inventory_quantity INT NOT NULL DEFAULT 0,
    issued_inventory_quantity INT NOT NULL DEFAULT 0,
    sort_order INT NOT NULL,
    CONSTRAINT fk_production_plan_item_plan_context
        FOREIGN KEY (production_plan_id, customer_order_id)
        REFERENCES production_plan(id, customer_order_id) ON DELETE CASCADE,
    CONSTRAINT fk_production_plan_item_order_context
        FOREIGN KEY (
            customer_order_item_id, customer_order_id, product_id, product_version
        )
        REFERENCES customer_order_item(
            id, customer_order_id, product_id, product_version
        ) ON DELETE CASCADE,
    CONSTRAINT fk_production_plan_item_bom_version
        FOREIGN KEY (product_bom_id, product_id, product_version)
        REFERENCES product_bom(id, product_id, product_version),
    CONSTRAINT ck_production_plan_item_type
        CHECK (item_type IN ('part', 'assembly', 'finished_product')),
    CONSTRAINT ck_production_plan_item_bom_scope CHECK (
        (item_type = 'part' AND product_bom_id IS NOT NULL)
        OR (item_type IN ('assembly', 'finished_product') AND product_bom_id IS NULL)
    ),
    CONSTRAINT ck_plan_item_version CHECK (product_version > 0),
    CONSTRAINT ck_plan_item_unit_requirement CHECK (unit_requirement > 0),
    CONSTRAINT ck_plan_item_gross_required CHECK (gross_required_quantity >= 0),
    CONSTRAINT ck_plan_item_estimated_stock CHECK (estimated_inventory_quantity >= 0),
    CONSTRAINT ck_plan_item_net_required CHECK (net_required_quantity >= 0),
    CONSTRAINT ck_plan_item_planned CHECK (planned_production_quantity >= 0),
    CONSTRAINT ck_plan_item_reserved CHECK (reserved_inventory_quantity >= 0),
    CONSTRAINT ck_plan_item_issued CHECK (issued_inventory_quantity >= 0),
    CONSTRAINT uq_production_plan_item_identity
        UNIQUE (production_plan_id, customer_order_item_id, identity_key),
    CONSTRAINT uq_production_plan_item_plan_context
        UNIQUE (id, production_plan_id)
);

-- production_route_task：确定保存计划物料在绑定版本正式流程中的车间路线；数量和执行状态仍以计划、生产、工单及 QC 表为准。
CREATE TABLE production_route_task (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL,
    production_plan_item_id BIGINT NOT NULL,
    route_flow_node_id TEXT NOT NULL,
    route_node_type TEXT NOT NULL,
    workshop_id BIGINT NOT NULL REFERENCES workshop(id),
    route_order INT NOT NULL,
    CONSTRAINT fk_production_route_task_plan_item
        FOREIGN KEY (production_plan_item_id, production_plan_id)
        REFERENCES production_plan_item(id, production_plan_id) ON DELETE CASCADE,
    CONSTRAINT ck_production_route_task_node_type
        CHECK (route_node_type IN ('process', 'assembly')),
    CONSTRAINT ck_production_route_task_order CHECK (route_order >= 0),
    CONSTRAINT uq_production_route_task_item_node
        UNIQUE (production_plan_item_id, route_flow_node_id)
);

-- inventory_stock：按产品、版本、物料节点和系统推导的完成节点保存跨订单库存。
CREATE TABLE inventory_stock (
    id BIGSERIAL PRIMARY KEY,
    department_code TEXT NOT NULL,
    item_type TEXT NOT NULL,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    product_bom_id BIGINT,
    flow_node_id TEXT NOT NULL,
    completed_flow_node_id TEXT NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    reserved_quantity INT NOT NULL DEFAULT 0,
    revision INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inventory_stock_product_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version),
    CONSTRAINT fk_inventory_stock_bom_version
        FOREIGN KEY (product_bom_id, product_id, product_version)
        REFERENCES product_bom(id, product_id, product_version),
    CONSTRAINT ck_inventory_stock_department
        CHECK (department_code IN ('warehouse', 'finished')),
    CONSTRAINT ck_inventory_stock_item_type
        CHECK (item_type IN ('part', 'assembly', 'finished_product')),
    CONSTRAINT ck_inventory_stock_version CHECK (product_version > 0),
    CONSTRAINT ck_inventory_stock_bom_scope CHECK (
        (item_type = 'part' AND product_bom_id IS NOT NULL)
        OR (item_type IN ('assembly', 'finished_product') AND product_bom_id IS NULL)
    ),
    CONSTRAINT ck_inventory_stock_quantity CHECK (quantity >= 0),
    CONSTRAINT ck_inventory_stock_reserved_quantity
        CHECK (reserved_quantity >= 0 AND reserved_quantity <= quantity),
    CONSTRAINT ck_inventory_stock_revision CHECK (revision > 0),
    CONSTRAINT ck_inventory_stock_location_type CHECK (
        (department_code = 'finished' AND item_type = 'finished_product')
        OR (department_code = 'warehouse' AND item_type IN ('part', 'assembly'))
    )
);

-- inventory_reservation：生产计划确认时对实物库存的占用和出库状态。
CREATE TABLE inventory_reservation (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL,
    production_plan_item_id BIGINT NOT NULL,
    inventory_stock_id BIGINT NOT NULL REFERENCES inventory_stock(id),
    reserved_quantity INT NOT NULL,
    issued_quantity INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'reserved',
    reserved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    issued_at TIMESTAMPTZ,
    issued_by TEXT,
    released_at TIMESTAMPTZ,
    CONSTRAINT fk_inventory_reservation_plan_item
        FOREIGN KEY (production_plan_item_id, production_plan_id)
        REFERENCES production_plan_item(id, production_plan_id) ON DELETE CASCADE,
    CONSTRAINT uq_inventory_reservation_context UNIQUE (
        id, production_plan_id, production_plan_item_id, inventory_stock_id
    ),
    CONSTRAINT ck_inventory_reservation_quantity CHECK (reserved_quantity > 0),
    CONSTRAINT ck_inventory_reservation_issued
        CHECK (issued_quantity >= 0 AND issued_quantity <= reserved_quantity),
    CONSTRAINT ck_inventory_reservation_status
        CHECK (status IN ('reserved', 'issued', 'released')),
    CONSTRAINT ck_inventory_reservation_state CHECK (
        (status = 'reserved' AND issued_quantity = 0 AND issued_at IS NULL AND released_at IS NULL)
        OR (status = 'issued' AND issued_quantity > 0 AND issued_at IS NOT NULL AND released_at IS NULL)
        OR (status = 'released' AND issued_quantity = 0 AND released_at IS NOT NULL)
    )
);

-- inventory_receipt：保存生产节点入库及订单成品结余入库的来源快照。
CREATE TABLE inventory_receipt (
    id BIGSERIAL PRIMARY KEY,
    source_customer_order_id BIGINT,
    source_customer_order_item_id BIGINT,
    source_production_item_id BIGINT,
    department_code TEXT NOT NULL,
    item_type TEXT NOT NULL,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    product_bom_id BIGINT,
    flow_node_id TEXT NOT NULL,
    completed_flow_node_id TEXT NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    quantity INT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMPTZ,
    confirmed_by TEXT,
    CONSTRAINT fk_inventory_receipt_order_context
        FOREIGN KEY (
            source_customer_order_item_id, source_customer_order_id,
            product_id, product_version
        ) REFERENCES customer_order_item(
            id, customer_order_id, product_id, product_version
        ),
    CONSTRAINT fk_inventory_receipt_product_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version),
    CONSTRAINT fk_inventory_receipt_bom_version
        FOREIGN KEY (product_bom_id, product_id, product_version)
        REFERENCES product_bom(id, product_id, product_version),
    CONSTRAINT ck_inventory_receipt_version CHECK (product_version > 0),
    CONSTRAINT ck_inventory_receipt_bom_scope CHECK (
        (item_type = 'part' AND product_bom_id IS NOT NULL)
        OR (item_type IN ('assembly', 'finished_product') AND product_bom_id IS NULL)
    ),
    CONSTRAINT ck_inventory_receipt_source_context CHECK (
        (source_customer_order_id IS NULL AND source_customer_order_item_id IS NULL
            AND source_production_item_id IS NULL)
        OR (source_customer_order_id IS NOT NULL AND source_customer_order_item_id IS NOT NULL
            AND source_production_item_id IS NOT NULL)
    ),
    CONSTRAINT ck_inventory_receipt_quantity CHECK (quantity > 0),
    CONSTRAINT ck_inventory_receipt_department
        CHECK (department_code IN ('warehouse', 'finished')),
    CONSTRAINT ck_inventory_receipt_item_type
        CHECK (item_type IN ('part', 'assembly', 'finished_product')),
    CONSTRAINT ck_inventory_receipt_status
        CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    CONSTRAINT ck_inventory_receipt_confirmation CHECK (
        (status = 'confirmed' AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)
        OR (status <> 'confirmed' AND confirmed_at IS NULL AND confirmed_by IS NULL)
    ),
    CONSTRAINT ck_inventory_receipt_location_type CHECK (
        (department_code = 'finished' AND item_type = 'finished_product')
        OR (department_code = 'warehouse' AND item_type IN ('part', 'assembly'))
    )
);

-- inventory_transaction：记录入库、占用、释放、出库和调整的不可变流水。
CREATE TABLE inventory_transaction (
    id BIGSERIAL PRIMARY KEY,
    inventory_stock_id BIGINT NOT NULL REFERENCES inventory_stock(id),
    production_plan_id BIGINT REFERENCES production_plan(id),
    production_plan_item_id BIGINT,
    inventory_reservation_id BIGINT,
    inventory_receipt_id BIGINT REFERENCES inventory_receipt(id),
    transaction_type TEXT NOT NULL,
    quantity INT NOT NULL,
    quantity_before INT NOT NULL,
    quantity_after INT NOT NULL,
    reserved_before INT NOT NULL,
    reserved_after INT NOT NULL,
    actor_username TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inventory_transaction_plan_item
        FOREIGN KEY (production_plan_item_id, production_plan_id)
        REFERENCES production_plan_item(id, production_plan_id),
    CONSTRAINT fk_inventory_transaction_reservation_context
        FOREIGN KEY (
            inventory_reservation_id, production_plan_id,
            production_plan_item_id, inventory_stock_id
        ) REFERENCES inventory_reservation(
            id, production_plan_id, production_plan_item_id, inventory_stock_id
        ),
    CONSTRAINT ck_inventory_transaction_type CHECK (
        transaction_type IN ('receipt', 'reserve', 'release', 'issue', 'adjust_in', 'adjust_out')
    ),
    CONSTRAINT ck_inventory_transaction_quantity CHECK (quantity > 0),
    CONSTRAINT ck_inventory_transaction_quantity_before CHECK (quantity_before >= 0),
    CONSTRAINT ck_inventory_transaction_quantity_after CHECK (quantity_after >= 0),
    CONSTRAINT ck_inventory_transaction_reserved_before CHECK (reserved_before >= 0),
    CONSTRAINT ck_inventory_transaction_reserved_after CHECK (reserved_after >= 0),
    CONSTRAINT ck_inventory_transaction_source CHECK (
        (transaction_type = 'receipt' AND inventory_receipt_id IS NOT NULL
            AND inventory_reservation_id IS NULL AND production_plan_id IS NULL
            AND production_plan_item_id IS NULL)
        OR (transaction_type IN ('reserve', 'release', 'issue')
            AND inventory_receipt_id IS NULL AND inventory_reservation_id IS NOT NULL
            AND production_plan_id IS NOT NULL AND production_plan_item_id IS NOT NULL)
        OR (transaction_type IN ('adjust_in', 'adjust_out')
            AND inventory_receipt_id IS NULL AND inventory_reservation_id IS NULL
            AND production_plan_id IS NULL AND production_plan_item_id IS NULL)
    )
);

-- finished_order_stock：订单专属成品暂存，区分待入库、可发货、已发货和结余结转。
CREATE TABLE finished_order_stock (
    id BIGSERIAL PRIMARY KEY,
    customer_order_id BIGINT NOT NULL
        REFERENCES customer_order(id) ON DELETE CASCADE,
    customer_order_item_id BIGINT NOT NULL
        REFERENCES customer_order_item(id) ON DELETE CASCADE,
    production_item_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    flow_node_id TEXT NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    unit_quantity INT NOT NULL,
    pending_quantity INT NOT NULL DEFAULT 0,
    available_quantity INT NOT NULL DEFAULT 0,
    shipped_quantity INT NOT NULL DEFAULT 0,
    transferred_quantity INT NOT NULL DEFAULT 0,
    revision INT NOT NULL DEFAULT 1,
    received_at TIMESTAMPTZ,
    received_by TEXT,
    last_shipped_at TIMESTAMPTZ,
    last_shipped_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_finished_order_stock_item_node UNIQUE (production_item_id, flow_node_id),
    CONSTRAINT ck_finished_order_stock_version CHECK (product_version > 0),
    CONSTRAINT ck_finished_order_stock_unit CHECK (unit_quantity > 0),
    CONSTRAINT ck_finished_order_stock_pending CHECK (pending_quantity >= 0),
    CONSTRAINT ck_finished_order_stock_available CHECK (available_quantity >= 0),
    CONSTRAINT ck_finished_order_stock_shipped CHECK (shipped_quantity >= 0),
    CONSTRAINT ck_finished_order_stock_transferred CHECK (transferred_quantity >= 0),
    CONSTRAINT ck_finished_order_stock_revision CHECK (revision > 0)
);

-- finished_goods_transaction：订单专属成品的真实入库、发货与库存领用流水。
CREATE TABLE finished_goods_transaction (
    id BIGSERIAL PRIMARY KEY,
    finished_order_stock_id BIGINT NOT NULL
        REFERENCES finished_order_stock(id) ON DELETE CASCADE,
    transaction_type TEXT NOT NULL,
    quantity INT NOT NULL,
    quantity_before INT NOT NULL,
    quantity_after INT NOT NULL,
    actor_username TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_finished_goods_transaction_type CHECK (
        transaction_type IN (
            'finished_receipt', 'customer_shipment', 'finished_stock_issue',
            'finished_surplus_transfer'
        )
    ),
    CONSTRAINT ck_finished_goods_transaction_quantity CHECK (quantity > 0),
    CONSTRAINT ck_finished_goods_transaction_before CHECK (quantity_before >= 0),
    CONSTRAINT ck_finished_goods_transaction_after CHECK (quantity_after >= 0)
);

-- ------------------------------------------------------------
-- 生产库存、工单、QC 批次与流动记录
-- ------------------------------------------------------------

-- production_item：保存订单确认后生成的具体生产对象，包括 BOM 配件或装配产出。
CREATE TABLE production_item (
    id BIGSERIAL PRIMARY KEY,
    customer_order_item_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    product_bom_id BIGINT,
    origin_flow_node_id TEXT NOT NULL,
    CONSTRAINT fk_production_item_order_version
        FOREIGN KEY (customer_order_item_id, product_id, product_version)
        REFERENCES customer_order_item(id, product_id, product_version) ON DELETE CASCADE,
    CONSTRAINT fk_production_item_bom_version
        FOREIGN KEY (product_bom_id, product_id, product_version)
        REFERENCES product_bom(id, product_id, product_version),
    CONSTRAINT ck_production_item_version CHECK (product_version > 0),
    CONSTRAINT uq_production_item_context UNIQUE (
        id, customer_order_item_id, product_id, product_version
    )
);

ALTER TABLE finished_order_stock
    ADD CONSTRAINT fk_finished_order_stock_production_item
    FOREIGN KEY (production_item_id) REFERENCES production_item(id) ON DELETE CASCADE;

ALTER TABLE inventory_receipt
    ADD CONSTRAINT fk_inventory_receipt_production_context
    FOREIGN KEY (
        source_production_item_id, source_customer_order_item_id,
        product_id, product_version
    ) REFERENCES production_item(
        id, customer_order_item_id, product_id, product_version
    );

-- repository：保存生产对象在流程节点中的可用数量；工单产出按来源工单独立存放。
CREATE TABLE repository (
    id BIGSERIAL PRIMARY KEY,
    production_item_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    flow_node_id TEXT NOT NULL,
    source_flow_node_id TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    source_work_order_id BIGINT,
    quantity INT NOT NULL,
    CONSTRAINT uq_repository_id_production_item UNIQUE (id, production_item_id),
    CONSTRAINT ck_repository_quantity_positive CHECK (quantity > 0)
);

-- work_order：保存普通加工、外购入库和装配工单及其执行快照和进度。
CREATE TABLE work_order (
    id BIGSERIAL PRIMARY KEY,
    work_order_no TEXT,
    repository_id BIGINT,
    production_item_id BIGINT NOT NULL REFERENCES production_item(id),
    procedure_id BIGINT NOT NULL REFERENCES procedure(id),
    work_order_type TEXT NOT NULL,
    flow_node_id TEXT NOT NULL,
    -- 工单创建时记录执行来源快照；装配工单记录自身装配节点，物料来源另见 work_order_material。
    source_flow_node_id TEXT,
    work_order_name TEXT NOT NULL,
    created_by VARCHAR(50) NOT NULL,
    remark TEXT,
    worker_id BIGINT REFERENCES worker(id),
    worker_name VARCHAR(100),
    quantity INT NOT NULL,
    processed_quantity INT NOT NULL DEFAULT 0,
    completed_quantity INT NOT NULL DEFAULT 0,
    CONSTRAINT ck_work_order_completed_quantity
        CHECK (completed_quantity >= 0 AND completed_quantity <= quantity),
    CONSTRAINT ck_work_order_processed_quantity CHECK (
        processed_quantity >= completed_quantity
        AND processed_quantity <= quantity
    ),
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMPTZ,
    CONSTRAINT uq_work_order_no UNIQUE (work_order_no),
    CONSTRAINT ck_work_order_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_work_order_type
        CHECK (work_order_type IN ('standard', 'purchase_receipt', 'assembly')),
    CONSTRAINT ck_work_order_status CHECK (status IN ('open', 'closed', 'cancelled')),
    CONSTRAINT ck_work_order_closed_at CHECK (
        (status = 'open' AND closed_at IS NULL)
        OR (status IN ('closed', 'cancelled') AND closed_at IS NOT NULL)
    ),
    CONSTRAINT ck_work_order_closed_quantity
        CHECK (status <> 'closed' OR completed_quantity = quantity),
    CONSTRAINT ck_work_order_cancelled_quantity CHECK (
        status <> 'cancelled'
        OR (completed_quantity = 0 AND processed_quantity = 0)
    ),
    CONSTRAINT ck_work_order_repository_lifecycle CHECK (
        (status = 'open' AND completed_quantity < quantity)
        OR repository_id IS NULL
    ),
    CONSTRAINT ck_work_order_type_source CHECK (
        (work_order_type = 'assembly'
            AND source_flow_node_id IS NOT NULL)
        OR (work_order_type = 'standard'
            AND source_flow_node_id IS NOT NULL
            AND (status <> 'open'
                OR completed_quantity = quantity
                OR repository_id IS NOT NULL))
        OR (work_order_type = 'purchase_receipt'
            AND source_flow_node_id IS NOT NULL
            AND (status <> 'open' OR repository_id IS NOT NULL))
    ),
    CONSTRAINT fk_work_order_repository_item
        FOREIGN KEY (repository_id, production_item_id)
        REFERENCES repository(id, production_item_id)
);

ALTER TABLE repository
    ADD CONSTRAINT fk_repository_source_work_order
    FOREIGN KEY (source_work_order_id) REFERENCES work_order(id);

-- work_order_pay_detail：保存工单选择的工艺和当前单价；调价时同步更新历史工单。
CREATE TABLE work_order_pay_detail (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    procedure_id BIGINT NOT NULL REFERENCES procedure(id),
    procedure_name TEXT NOT NULL,
    unit_price NUMERIC(12, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_work_order_pay_detail_order UNIQUE (work_order_id),
    CONSTRAINT ck_work_order_pay_detail_procedure_name
        CHECK (procedure_name = btrim(procedure_name) AND procedure_name <> ''),
    CONSTRAINT ck_work_order_pay_detail_nonnegative
        CHECK (unit_price IS NULL OR unit_price >= 0)
);

-- work_order_material：保存装配工单占用的来源库存、生产对象和物料数量。
CREATE TABLE work_order_material (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    repository_id BIGINT,
    production_item_id BIGINT NOT NULL REFERENCES production_item(id),
    quantity INT NOT NULL,
    source_flow_node_id TEXT NOT NULL,
    source_previous_flow_node_id TEXT NOT NULL,
    source_department_id BIGINT NOT NULL REFERENCES department(id),
    source_work_order_id BIGINT,
    CONSTRAINT fk_work_order_material_repository_item
        FOREIGN KEY (repository_id, production_item_id)
        REFERENCES repository(id, production_item_id),
    CONSTRAINT uq_work_order_material_repository UNIQUE (work_order_id, repository_id),
    CONSTRAINT uq_work_order_material_movement_context
        UNIQUE (id, work_order_id, production_item_id),
    CONSTRAINT ck_work_order_material_quantity CHECK (quantity > 0)
);

-- work_order_batch：保存工单送检批次、QC 结果及返工复检的父子关系。
CREATE TABLE work_order_batch (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    submitted_quantity INT NOT NULL,
    -- 记录本次工单完成并送往 QC 的加工节点，即 work_order.flow_node_id。
    source_flow_node_id TEXT NOT NULL,
    -- 返工复检批次指向产生返工数量的上一批 QC；首次送检保持 NULL。
    rework_source_batch_id BIGINT,
    qualified_quantity INT,
    rework_quantity INT,
    scrap_quantity INT,
    lost_quantity INT,
    qc_worker_id BIGINT REFERENCES worker(id),
    qc_worker_name TEXT,
    defect_reason TEXT,
    qualified_disposition TEXT,
    recorded_at TIMESTAMPTZ,
    CONSTRAINT uq_work_order_batch_id_order UNIQUE (id, work_order_id),
    CONSTRAINT fk_work_order_batch_rework_source
        FOREIGN KEY (rework_source_batch_id, work_order_id)
        REFERENCES work_order_batch(id, work_order_id),
    CONSTRAINT ck_batch_submitted_positive CHECK (submitted_quantity > 0),
    CONSTRAINT ck_batch_qualified
        CHECK (qualified_quantity IS NULL OR qualified_quantity >= 0),
    CONSTRAINT ck_batch_rework CHECK (rework_quantity IS NULL OR rework_quantity >= 0),
    CONSTRAINT ck_batch_scrap CHECK (scrap_quantity IS NULL OR scrap_quantity >= 0),
    CONSTRAINT ck_batch_lost CHECK (lost_quantity IS NULL OR lost_quantity >= 0),
    CONSTRAINT ck_batch_inspection_complete CHECK (
        (recorded_at IS NULL AND qualified_quantity IS NULL
            AND rework_quantity IS NULL AND scrap_quantity IS NULL
            AND lost_quantity IS NULL AND qc_worker_id IS NULL AND qc_worker_name IS NULL
            AND qualified_disposition IS NULL)
        OR
        (recorded_at IS NOT NULL AND qualified_quantity IS NOT NULL
            AND rework_quantity IS NOT NULL AND scrap_quantity IS NOT NULL
            AND lost_quantity IS NOT NULL AND qc_worker_id IS NOT NULL
            AND qc_worker_name IS NOT NULL
            AND ((qualified_quantity = 0 AND qualified_disposition IS NULL)
                OR (qualified_quantity > 0
                    AND qualified_disposition IN ('return', 'release')))
            AND qualified_quantity + rework_quantity + scrap_quantity + lost_quantity
                = submitted_quantity)
    )
);

-- production_movement：保存数量在流程节点、部门和 QC 结果之间的不可变流动历史。
CREATE TABLE production_movement (
    id BIGSERIAL PRIMARY KEY,
    production_item_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    source_flow_node_id TEXT,
    target_flow_node_id TEXT,
    source_department_id BIGINT REFERENCES department(id),
    target_department_id BIGINT REFERENCES department(id),
    quantity INT NOT NULL,
    movement_type TEXT NOT NULL,
    CONSTRAINT ck_production_movement_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_production_movement_type CHECK (
        movement_type IN (
            'initial', 'process', 'purchase_receipt', 'assembly_input', 'assembly_output',
            'qc_qualified', 'qc_rework', 'inventory_issue',
            'finished_receipt', 'customer_shipment', 'assembly_input_restore',
            'scrap', 'lost'
        )
    ),
    work_order_id BIGINT REFERENCES work_order(id),
    work_order_batch_id BIGINT,
    work_order_material_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_production_movement_batch_order
        FOREIGN KEY (work_order_batch_id, work_order_id)
        REFERENCES work_order_batch(id, work_order_id),
    CONSTRAINT fk_production_movement_assembly_material_context
        FOREIGN KEY (work_order_material_id, work_order_id, production_item_id)
        REFERENCES work_order_material(id, work_order_id, production_item_id),
    CONSTRAINT ck_production_movement_context CHECK (
        (movement_type = 'initial'
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NOT NULL
            AND source_department_id IS NULL
            AND target_department_id IS NOT NULL
            AND work_order_id IS NULL
            AND work_order_batch_id IS NULL)
        OR (movement_type = 'inventory_issue'
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NOT NULL
            AND source_department_id IS NOT NULL
            AND target_department_id IS NOT NULL
            AND work_order_id IS NULL
            AND work_order_batch_id IS NULL)
        OR (movement_type IN ('finished_receipt', 'customer_shipment')
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NOT NULL
            AND source_department_id IS NOT NULL
            AND target_department_id IS NOT NULL
            AND work_order_id IS NULL
            AND work_order_batch_id IS NULL)
        OR (movement_type IN ('process', 'purchase_receipt', 'assembly_output')
            AND source_flow_node_id IS NOT NULL
            AND source_department_id IS NOT NULL
            AND (target_flow_node_id IS NULL) = (target_department_id IS NULL)
            AND work_order_id IS NOT NULL)
        OR (movement_type = 'assembly_input'
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NULL
            AND source_department_id IS NOT NULL
            AND target_department_id IS NULL
            AND work_order_id IS NOT NULL
            AND work_order_batch_id IS NULL)
        OR (movement_type = 'assembly_input_restore'
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NOT NULL
            AND source_department_id IS NOT NULL
            AND target_department_id IS NOT NULL
            AND work_order_id IS NOT NULL
            AND work_order_batch_id IS NULL)
        OR (movement_type = 'qc_qualified'
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NOT NULL
            AND source_department_id IS NOT NULL
            AND target_department_id IS NOT NULL
            AND work_order_id IS NOT NULL
            AND work_order_batch_id IS NOT NULL)
        OR (movement_type = 'qc_rework'
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NOT NULL
            AND source_department_id IS NOT NULL
            AND target_department_id IS NOT NULL
            AND work_order_id IS NOT NULL
            AND work_order_batch_id IS NOT NULL)
        OR (movement_type IN ('scrap', 'lost')
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NULL
            AND source_department_id IS NOT NULL
            AND target_department_id IS NULL
            AND work_order_id IS NOT NULL
            AND work_order_batch_id IS NOT NULL)
    ),
    CONSTRAINT ck_production_movement_assembly_material CHECK (
        (movement_type IN ('assembly_input', 'assembly_input_restore')
            AND work_order_material_id IS NOT NULL)
        OR (movement_type NOT IN ('assembly_input', 'assembly_input_restore')
            AND work_order_material_id IS NULL)
    )
);

-- production_operation_undo：保存生产提交前后的库存与工单快照，用于在没有后续流转时安全撤回。
CREATE TABLE production_operation_undo (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    -- 批次删除后仍保留原编号作为撤回审计信息，因此不设置外键。
    work_order_batch_id BIGINT,
    operation_type TEXT NOT NULL,
    operation_label TEXT NOT NULL,
    department_code TEXT NOT NULL,
    actor_username TEXT NOT NULL,
    snapshot_json JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'applied',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reversed_at TIMESTAMPTZ,
    reversed_by TEXT,
    CONSTRAINT ck_production_operation_undo_type
        CHECK (operation_type IN ('purchase_arrival', 'submission', 'rework_submission')),
    CONSTRAINT ck_production_operation_undo_status
        CHECK (status IN ('applied', 'reversed')),
    CONSTRAINT ck_production_operation_undo_reversed CHECK (
        (status = 'applied' AND reversed_at IS NULL AND reversed_by IS NULL)
        OR (status = 'reversed' AND reversed_at IS NOT NULL AND reversed_by IS NOT NULL)
    )
);

-- ============================================================
-- 表约束补充
-- ============================================================

ALTER TABLE product
ADD CONSTRAINT fk_product_current_version
FOREIGN KEY (id, version)
REFERENCES product_version(product_id, version)
DEFERRABLE INITIALLY DEFERRED;

-- ============================================================
-- 数据完整性函数
-- ============================================================

CREATE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = clock_timestamp();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_work_order_closure() RETURNS TRIGGER AS $$
BEGIN
    -- 外购工单在整单到货提交时关闭；其 QC 批次不依赖工单开放状态继续处理。
    IF NEW.status = 'closed'
        AND NEW.work_order_type <> 'purchase_receipt'
        AND EXISTS (
            SELECT 1 FROM work_order_batch
            WHERE work_order_id = NEW.id AND recorded_at IS NULL
        ) THEN
        RAISE EXCEPTION 'work order with pending QC batches cannot be closed'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'closed'
        AND NEW.work_order_type <> 'purchase_receipt'
        AND EXISTS (
        SELECT 1
        FROM work_order_batch AS source_batch
        WHERE source_batch.work_order_id = NEW.id
          AND source_batch.recorded_at IS NOT NULL
          AND source_batch.rework_quantity > COALESCE((
              SELECT SUM(child_batch.submitted_quantity)
              FROM work_order_batch AS child_batch
              WHERE child_batch.work_order_id = NEW.id
                AND child_batch.rework_source_batch_id = source_batch.id
          ), 0)
    ) THEN
        RAISE EXCEPTION 'work order with pending rework cannot be closed'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_qc_submission_movement_quantity() RETURNS TRIGGER AS $$
DECLARE
    batch_submitted_quantity INT;
BEGIN
    SELECT submitted_quantity INTO batch_submitted_quantity
    FROM work_order_batch
    WHERE id = NEW.work_order_batch_id
      AND work_order_id = NEW.work_order_id
    FOR UPDATE;

    IF NOT FOUND OR NEW.quantity <> batch_submitted_quantity THEN
        RAISE EXCEPTION 'submission movement must match its QC batch quantity'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_assembly_material_movement_quantity() RETURNS TRIGGER AS $$
DECLARE
    material_quantity INT;
BEGIN
    SELECT quantity INTO material_quantity
    FROM work_order_material
    WHERE id = NEW.work_order_material_id
      AND work_order_id = NEW.work_order_id
      AND production_item_id = NEW.production_item_id
    FOR UPDATE;

    IF NOT FOUND OR NEW.quantity <> material_quantity THEN
        RAISE EXCEPTION 'assembly movement quantity must match its material allocation'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_assembly_material_movement_context() RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM production_movement
        WHERE work_order_material_id = OLD.id
          AND movement_type = 'assembly_input'
    ) THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'assembly material identity is retained by movement history'
                USING ERRCODE = '23514';
        END IF;
        IF (
            NEW.work_order_id, NEW.production_item_id, NEW.quantity,
            NEW.source_flow_node_id, NEW.source_previous_flow_node_id,
            NEW.source_department_id, NEW.source_work_order_id
        ) IS DISTINCT FROM (
            OLD.work_order_id, OLD.production_item_id, OLD.quantity,
            OLD.source_flow_node_id, OLD.source_previous_flow_node_id,
            OLD.source_department_id, OLD.source_work_order_id
        ) THEN
            RAISE EXCEPTION 'assembly material identity and quantity are retained by movement history'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_work_order_movement_items() RETURNS TRIGGER AS $$
BEGIN
    IF (
        NEW.procedure_id,
        NEW.work_order_type,
        NEW.work_order_name,
        NEW.remark,
        NEW.flow_node_id,
        NEW.source_flow_node_id
    ) IS DISTINCT FROM (
        OLD.procedure_id,
        OLD.work_order_type,
        OLD.work_order_name,
        OLD.remark,
        OLD.flow_node_id,
        OLD.source_flow_node_id
    ) AND EXISTS (
        SELECT 1
        FROM production_movement
        WHERE work_order_id = NEW.id
    ) THEN
        RAISE EXCEPTION 'work order execution snapshot is retained by movement history'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.production_item_id IS DISTINCT FROM OLD.production_item_id
        AND EXISTS (
            SELECT 1
            FROM production_movement
            WHERE work_order_id = NEW.id
              AND movement_type <> 'assembly_input'
              AND production_item_id <> NEW.production_item_id
        ) THEN
        RAISE EXCEPTION 'work order production item conflicts with existing movements'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_rework_submission_quantity() RETURNS TRIGGER AS $$
DECLARE
    source_batch_rework_quantity INT;
    source_batch_recorded_at TIMESTAMPTZ;
    source_batch_resubmitted BIGINT;
BEGIN
    SELECT rework_quantity, recorded_at
    INTO source_batch_rework_quantity, source_batch_recorded_at
    FROM work_order_batch
    WHERE id = NEW.rework_source_batch_id
      AND work_order_id = NEW.work_order_id
    FOR UPDATE;
    IF NOT FOUND OR source_batch_recorded_at IS NULL THEN
        RAISE EXCEPTION 'rework source batch must have a completed QC result'
            USING ERRCODE = '23514';
    END IF;
    SELECT COALESCE(SUM(submitted_quantity), 0)
    INTO source_batch_resubmitted
    FROM work_order_batch
    WHERE rework_source_batch_id = NEW.rework_source_batch_id
      AND work_order_id = NEW.work_order_id;
    IF NEW.submitted_quantity
        > source_batch_rework_quantity - source_batch_resubmitted THEN
        RAISE EXCEPTION 'rework submission exceeds the source batch remainder'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_qc_batch_history() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.recorded_at IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'completed QC batch history is immutable'
            USING ERRCODE = '23514';
    END IF;
    IF (
        NEW.work_order_id,
        NEW.rework_source_batch_id,
        NEW.source_flow_node_id,
        NEW.submitted_quantity
    )
        IS DISTINCT FROM (
            OLD.work_order_id,
            OLD.rework_source_batch_id,
            OLD.source_flow_node_id,
            OLD.submitted_quantity
        )
        AND EXISTS (
            SELECT 1
            FROM production_movement
            WHERE work_order_batch_id = NEW.id
        ) THEN
        RAISE EXCEPTION 'batch work order, source and submitted quantity are retained by movement history'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_qc_batch_result_balance() RETURNS TRIGGER AS $$
DECLARE
    submission_count INT;
    submission_quantity BIGINT;
    moved_qualified BIGINT;
    moved_rework BIGINT;
    moved_scrap BIGINT;
    moved_lost BIGINT;
BEGIN
    SELECT
        COUNT(*) FILTER (
            WHERE movement_type IN ('process', 'purchase_receipt', 'assembly_output')
        ),
        COALESCE(SUM(quantity) FILTER (
            WHERE movement_type IN ('process', 'purchase_receipt', 'assembly_output')
        ), 0),
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'qc_qualified'), 0),
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'qc_rework'), 0),
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'scrap'), 0),
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'lost'), 0)
    INTO
        submission_count,
        submission_quantity,
        moved_qualified,
        moved_rework,
        moved_scrap,
        moved_lost
    FROM production_movement
    WHERE work_order_batch_id = NEW.id;

    IF submission_count <> 1 OR submission_quantity <> NEW.submitted_quantity THEN
        RAISE EXCEPTION 'QC batch must retain one matching submission movement'
            USING ERRCODE = '23514';
    END IF;
    IF (
        moved_qualified,
        moved_rework,
        moved_scrap,
        moved_lost
    ) IS DISTINCT FROM (
        NEW.qualified_quantity,
        NEW.rework_quantity,
        NEW.scrap_quantity,
        NEW.lost_quantity
    ) THEN
        RAISE EXCEPTION 'QC batch quantities must match its movement history'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_production_movement_history() RETURNS TRIGGER AS $$
DECLARE
    undo_operation_id_text TEXT;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'production movement history is immutable'
            USING ERRCODE = '23514';
    END IF;
    undo_operation_id_text := current_setting('zzerp.undo_operation_id', TRUE);
    IF undo_operation_id_text IS NOT NULL
        AND undo_operation_id_text ~ '^[0-9]+$'
        AND EXISTS (
            SELECT 1
            FROM production_operation_undo AS undo_operation
            WHERE undo_operation.id = undo_operation_id_text::BIGINT
              AND undo_operation.status = 'applied'
              AND undo_operation.work_order_id = OLD.work_order_id
              AND undo_operation.snapshot_json->'after'->'movement_ids'
                    @> to_jsonb(ARRAY[OLD.id])
              AND NOT (
                  undo_operation.snapshot_json->'before'->'movement_ids'
                    @> to_jsonb(ARRAY[OLD.id])
              )
        ) THEN
        RETURN OLD;
    END IF;
    IF OLD.movement_type <> 'initial'
        OR OLD.work_order_id IS NOT NULL
        OR OLD.work_order_batch_id IS NOT NULL THEN
        RAISE EXCEPTION 'production execution movement history cannot be deleted'
            USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1 FROM production_item WHERE id = OLD.production_item_id
    ) THEN
        RAISE EXCEPTION 'initial movement can only be deleted with its production item'
            USING ERRCODE = '23514';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 触发器
-- ============================================================

CREATE FUNCTION protect_inventory_transaction_history() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'inventory transaction history is immutable'
        USING ERRCODE = '23514';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_qc_submission_movement_quantity
BEFORE INSERT ON production_movement
FOR EACH ROW
WHEN (
    NEW.work_order_batch_id IS NOT NULL
    AND NEW.movement_type IN ('process', 'purchase_receipt', 'assembly_output')
)
EXECUTE FUNCTION validate_qc_submission_movement_quantity();

CREATE TRIGGER trg_assembly_material_movement_quantity
BEFORE INSERT ON production_movement
FOR EACH ROW
WHEN (NEW.movement_type IN ('assembly_input', 'assembly_input_restore'))
EXECUTE FUNCTION validate_assembly_material_movement_quantity();

CREATE TRIGGER trg_work_order_closure
BEFORE UPDATE OF status
ON work_order
FOR EACH ROW
WHEN (NEW.status = 'closed' AND OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION protect_work_order_closure();

CREATE TRIGGER trg_work_order_movement_items
BEFORE UPDATE OF production_item_id, procedure_id, work_order_type, work_order_name,
    remark, flow_node_id, source_flow_node_id
ON work_order
FOR EACH ROW EXECUTE FUNCTION validate_work_order_movement_items();

CREATE TRIGGER trg_rework_submission_quantity
BEFORE INSERT ON work_order_batch
FOR EACH ROW
WHEN (NEW.rework_source_batch_id IS NOT NULL)
EXECUTE FUNCTION protect_rework_submission_quantity();

CREATE TRIGGER trg_qc_batch_history
BEFORE UPDATE ON work_order_batch
FOR EACH ROW EXECUTE FUNCTION protect_qc_batch_history();

CREATE TRIGGER trg_qc_batch_result_balance
BEFORE UPDATE OF recorded_at, qualified_quantity, rework_quantity,
    scrap_quantity, lost_quantity
ON work_order_batch
FOR EACH ROW
WHEN (NEW.recorded_at IS NOT NULL AND OLD.recorded_at IS NULL)
EXECUTE FUNCTION validate_qc_batch_result_balance();

CREATE TRIGGER trg_assembly_material_movement_update
BEFORE UPDATE OF work_order_id, production_item_id, quantity ON work_order_material
FOR EACH ROW EXECUTE FUNCTION protect_assembly_material_movement_context();

CREATE TRIGGER trg_assembly_material_movement_delete
BEFORE DELETE ON work_order_material
FOR EACH ROW EXECUTE FUNCTION protect_assembly_material_movement_context();

CREATE TRIGGER trg_production_movement_history
BEFORE UPDATE OR DELETE ON production_movement
FOR EACH ROW EXECUTE FUNCTION protect_production_movement_history();

CREATE TRIGGER trg_inventory_transaction_history
BEFORE UPDATE OR DELETE ON inventory_transaction
FOR EACH ROW EXECUTE FUNCTION protect_inventory_transaction_history();

CREATE TRIGGER trg_finished_goods_transaction_history
BEFORE UPDATE OR DELETE ON finished_goods_transaction
FOR EACH ROW EXECUTE FUNCTION protect_inventory_transaction_history();

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

CREATE TRIGGER trg_procedure_price_updated_at
BEFORE UPDATE ON procedure_price
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_customer_order_updated_at
BEFORE UPDATE ON customer_order
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_production_plan_updated_at
BEFORE UPDATE ON production_plan
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_inventory_stock_updated_at
BEFORE UPDATE ON inventory_stock
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_finished_order_stock_updated_at
BEFORE UPDATE ON finished_order_stock
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- 索引
-- ============================================================

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
CREATE INDEX idx_product_route_task_department_page
    ON product_route_task(
        workshop_id, product_id, product_version, origin_flow_node_id, route_order
    );
CREATE INDEX idx_product_route_task_item_code_trgm
    ON product_route_task USING GIN (origin_item_code gin_trgm_ops);
CREATE INDEX idx_product_route_task_item_name_trgm
    ON product_route_task USING GIN (origin_item_name gin_trgm_ops);
CREATE INDEX idx_customer_order_item_order ON customer_order_item(customer_order_id);
CREATE INDEX idx_customer_order_customer ON customer_order(customer_id);
CREATE INDEX idx_customer_order_status ON customer_order(status, id);
CREATE INDEX idx_customer_order_updated ON customer_order(updated_at DESC, id DESC);
CREATE INDEX idx_customer_order_no_trgm
    ON customer_order USING GIN (customer_order_no gin_trgm_ops);
CREATE INDEX idx_customer_order_item_product_version
    ON customer_order_item(product_id, product_version);
CREATE INDEX idx_production_plan_status ON production_plan(status, id);
CREATE INDEX idx_production_plan_item_plan
    ON production_plan_item(production_plan_id, sort_order);
CREATE INDEX idx_production_plan_item_order_item
    ON production_plan_item(customer_order_item_id);
CREATE INDEX idx_production_route_task_plan_page
    ON production_route_task(
        production_plan_id, production_plan_item_id, route_order
    );
CREATE INDEX idx_production_route_task_workshop
    ON production_route_task(workshop_id, production_plan_item_id);
CREATE INDEX idx_inventory_stock_component
    ON inventory_stock(
        product_id, product_version, item_type, product_bom_id, flow_node_id
    );
CREATE INDEX idx_inventory_stock_department
    ON inventory_stock(department_code, item_type);
CREATE UNIQUE INDEX uq_inventory_stock_part_identity
    ON inventory_stock(
        department_code, item_type, product_id, product_version, product_bom_id,
        flow_node_id, completed_flow_node_id
    ) WHERE item_type = 'part';
CREATE UNIQUE INDEX uq_inventory_stock_node_identity
    ON inventory_stock(
        department_code, item_type, product_id, product_version,
        flow_node_id, completed_flow_node_id
    ) WHERE item_type IN ('assembly', 'finished_product');
CREATE INDEX idx_inventory_reservation_plan
    ON inventory_reservation(production_plan_id, status);
CREATE INDEX idx_inventory_reservation_item
    ON inventory_reservation(production_plan_item_id);
CREATE INDEX idx_inventory_reservation_stock
    ON inventory_reservation(inventory_stock_id, status);
CREATE INDEX idx_inventory_receipt_status
    ON inventory_receipt(department_code, status, id);
CREATE INDEX idx_inventory_receipt_order_item
    ON inventory_receipt(source_customer_order_item_id, id);
CREATE INDEX idx_inventory_receipt_production_item
    ON inventory_receipt(source_production_item_id, id);
CREATE INDEX idx_finished_goods_transaction_lot
    ON finished_goods_transaction(finished_order_stock_id, id);
CREATE INDEX idx_finished_goods_transaction_created
    ON finished_goods_transaction(created_at DESC, id DESC);
CREATE INDEX idx_inventory_transaction_stock
    ON inventory_transaction(inventory_stock_id, id);
CREATE INDEX idx_inventory_transaction_plan
    ON inventory_transaction(production_plan_id, id);
CREATE INDEX idx_inventory_transaction_reservation
    ON inventory_transaction(inventory_reservation_id, id);
CREATE INDEX idx_inventory_transaction_receipt
    ON inventory_transaction(inventory_receipt_id, id);
CREATE INDEX idx_finished_order_stock_order
    ON finished_order_stock(customer_order_id, id);
CREATE INDEX idx_finished_order_stock_order_item
    ON finished_order_stock(customer_order_item_id, id);
CREATE INDEX idx_production_movement_item_created
    ON production_movement(production_item_id, created_at);
CREATE INDEX idx_production_movement_target_department_created
    ON production_movement(target_department_id, created_at);
CREATE INDEX idx_production_movement_work_order
    ON production_movement(work_order_id, id)
    WHERE work_order_id IS NOT NULL;
CREATE INDEX idx_production_movement_batch
    ON production_movement(work_order_batch_id, id)
    WHERE work_order_batch_id IS NOT NULL;
CREATE UNIQUE INDEX uq_production_movement_batch_submission
    ON production_movement(work_order_batch_id)
    WHERE work_order_batch_id IS NOT NULL
      AND movement_type IN ('process', 'purchase_receipt', 'assembly_output');
CREATE UNIQUE INDEX uq_production_movement_assembly_input
    ON production_movement(work_order_material_id)
    WHERE movement_type = 'assembly_input';
CREATE INDEX idx_production_movement_assembly_material
    ON production_movement(work_order_material_id)
    WHERE work_order_material_id IS NOT NULL;
CREATE INDEX idx_repository_department ON repository(department_id);
CREATE UNIQUE INDEX uq_repository_initial_position
    ON repository(production_item_id, flow_node_id, source_flow_node_id, department_id)
    WHERE source_work_order_id IS NULL;
CREATE UNIQUE INDEX uq_repository_work_order_output
    ON repository(source_work_order_id, production_item_id, flow_node_id)
    WHERE source_work_order_id IS NOT NULL;
CREATE INDEX idx_procedure_price_scope
    ON procedure_price(
        procedure_id, product_id, product_version, flow_node_id
    );
CREATE INDEX idx_production_item_order_item ON production_item(customer_order_item_id);
CREATE INDEX idx_production_item_bom ON production_item(product_bom_id);
CREATE INDEX idx_work_order_repository ON work_order(repository_id);
CREATE INDEX idx_work_order_production_item ON work_order(production_item_id);
CREATE INDEX idx_work_order_no_trgm
    ON work_order USING GIN (work_order_no gin_trgm_ops);
CREATE INDEX idx_work_order_name_trgm
    ON work_order USING GIN (work_order_name gin_trgm_ops);
CREATE INDEX idx_work_order_worker_activity
    ON work_order(worker_id, COALESCE(closed_at, created_at) DESC, id DESC);
CREATE INDEX idx_work_order_repository_open ON work_order(repository_id)
    WHERE status = 'open';
CREATE INDEX idx_work_order_item_node_status
    ON work_order(production_item_id, flow_node_id, status);
CREATE INDEX idx_work_order_process_position
    ON work_order(production_item_id, flow_node_id, procedure_id, id DESC);
CREATE INDEX idx_work_order_pay_detail_procedure
    ON work_order_pay_detail(procedure_id, work_order_id);
CREATE INDEX idx_work_order_batch_order ON work_order_batch(work_order_id);
CREATE INDEX idx_work_order_batch_rework_source
    ON work_order_batch(rework_source_batch_id);
CREATE INDEX idx_work_order_material_repository ON work_order_material(repository_id);
CREATE INDEX idx_work_order_material_production_item ON work_order_material(production_item_id);
CREATE INDEX idx_work_order_batch_pending ON work_order_batch(id DESC, work_order_id)
    WHERE recorded_at IS NULL;
CREATE INDEX idx_work_order_batch_history ON work_order_batch(id DESC)
    WHERE recorded_at IS NOT NULL;
CREATE INDEX idx_work_order_batch_qc_worker_recorded
    ON work_order_batch(qc_worker_id, recorded_at DESC);
CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX idx_user_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_worker_department_name ON worker(department_id, worker_name, id);
CREATE UNIQUE INDEX uq_worker_workshop_name
    ON worker(department_id, workshop_id, worker_name)
    WHERE workshop_id IS NOT NULL;
CREATE UNIQUE INDEX uq_worker_department_direct_name
    ON worker(department_id, worker_name)
    WHERE workshop_id IS NULL;
CREATE INDEX idx_worker_workshop_department
    ON worker(workshop_id, department_id) WHERE workshop_id IS NOT NULL;
CREATE INDEX idx_production_movement_source_department
    ON production_movement(source_department_id)
    WHERE source_department_id IS NOT NULL;
CREATE INDEX idx_production_movement_position_latest
    ON production_movement(
        target_department_id,
        production_item_id,
        target_flow_node_id,
        source_flow_node_id,
        created_at DESC,
        id DESC
    ) WHERE target_department_id IS NOT NULL;
CREATE INDEX idx_production_operation_undo_order
    ON production_operation_undo(work_order_id, id DESC);
CREATE INDEX idx_production_operation_undo_active
    ON production_operation_undo(work_order_id, id DESC)
    WHERE status = 'applied';

-- ============================================================
-- 初始化数据
-- 所有 INSERT 统一放在文件末尾。
-- ============================================================

-- ------------------------------------------------------------
-- 系统必需基础数据：部门、账号、车间、工艺和默认人员
-- ------------------------------------------------------------

INSERT INTO department (department_name, department_code) VALUES
('工程部', 'engineering'),
('业务部', 'business'),
('PMC部门', 'pmc'),
('冲压部', 'stamp'),
('机加部', 'cnc'),
('表面处理部', 'polish'),
('外协部', 'outsource'),
('采购部', 'purchasing'),
('QC部门', 'qc'),
('装配部', 'assembly'),
('成品部', 'finished'),
('仓库', 'warehouse');

INSERT INTO users (
    username, password, department, is_system, role, permissions
) VALUES
(
    'admin',
    '1',
    NULL,
    TRUE,
    'supervisor',
    'engineering:product:view,engineering:product:add,engineering:product:edit,engineering:product:delete,order:view,order:add,order:edit,order:confirm,order:cancel,production:view,production:manage,qc:inspect,sys:user:add'
),
(
    'engineering',
    '1',
    'engineering',
    FALSE,
    'engineer',
    'engineering:product:view,engineering:product:add,engineering:product:edit,engineering:product:delete'
),
(
    'business',
    '1',
    'business',
    FALSE,
    'sales',
    'engineering:product:view,order:view,order:add,order:edit,order:confirm,order:cancel'
),
(
    'pmc',
    '1',
    'pmc',
    FALSE,
    'pmc',
    'engineering:product:view,order:view,production:view'
),
(
    'stamp', '1', 'stamp', FALSE, 'operator', 'production:view,production:manage'
),
(
    'cnc', '1', 'cnc', FALSE, 'operator', 'production:view,production:manage'
),
(
    'polish', '1', 'polish', FALSE, 'operator', 'production:view,production:manage'
),
(
    'outsource', '1', 'outsource', FALSE, 'operator', 'production:view,production:manage'
),
(
    'purchasing', '1', 'purchasing', FALSE, 'operator', 'production:view,production:manage'
),
(
    'qc', '1', 'qc', FALSE, 'operator', 'production:view,qc:inspect'
),
(
    'assembly', '1', 'assembly', FALSE, 'operator', 'production:view,production:manage'
),
(
    'finished', '1', 'finished', FALSE, 'operator', 'production:view,production:manage'
),
(
    'warehouse', '1', 'warehouse', FALSE, 'operator', 'production:view,production:manage'
);

INSERT INTO workshop (department_id, workshop_name)
SELECT department.id, source.workshop_name
FROM (
    VALUES
        ('stamp', '激光开料车间'),
        ('stamp', '热锻车间'),
        ('stamp', '冷锻车间'),
        ('stamp', '冲床车间'),
        ('stamp', '回火车间'),
        ('stamp', '除油车间'),
        ('stamp', '水磨车间'),
        ('stamp', '溜磨车间'),
        ('cnc', 'CNC车间'),
        ('cnc', 'NC车间'),
        ('cnc', '钻床车间'),
        ('cnc', '激光焊接车间'),
        ('polish', '手磨车间'),
        ('polish', '砂机车间'),
        ('polish', '自动平磨车间'),
        ('polish', '双面水磨车间'),
        ('polish', '酸洗车间'),
        ('polish', '电抛车间'),
        ('polish', '振机车间'),
        ('polish', '干滚车间'),
        ('polish', '清光车间'),
        ('outsource', '蚀字外协'),
        ('outsource', '电镀外协'),
        ('purchasing', '采购组'),
        ('assembly', '装包车间'),
        ('assembly', '焊接车间')
) AS source(department_code, workshop_name)
JOIN department
    ON department.department_code = source.department_code;

INSERT INTO procedure (workshop_id, procedure_name, procedure_type)
SELECT workshop.id, source.procedure_name, source.procedure_type
FROM (
    VALUES
        ('stamp', '激光开料车间', '激光开料', 'standard'),
        ('stamp', '热锻车间', '热压1', 'standard'),
        ('stamp', '热锻车间', '热压2', 'standard'),
        ('stamp', '热锻车间', '热压3', 'standard'),
        ('stamp', '冷锻车间', '冷锻', 'standard'),
        ('stamp', '冲床车间', '冲压', 'standard'),
        ('stamp', '回火车间', '回火', 'standard'),
        ('stamp', '除油车间', '除油', 'standard'),
        ('stamp', '水磨车间', '水磨', 'standard'),
        ('stamp', '溜磨车间', '溜磨', 'standard'),
        ('cnc', 'CNC车间', 'CNC加工', 'standard'),
        ('cnc', 'NC车间', 'NC加工', 'standard'),
        ('cnc', '钻床车间', '钻孔', 'standard'),
        ('cnc', '激光焊接车间', '激光焊接', 'standard'),
        ('polish', '手磨车间', '粗1', 'standard'),
        ('polish', '手磨车间', '粗2', 'standard'),
        ('polish', '手磨车间', '粗3', 'standard'),
        ('polish', '砂机车间', '砂机', 'standard'),
        ('polish', '自动平磨车间', '自动平磨', 'standard'),
        ('polish', '双面水磨车间', '双面水磨', 'standard'),
        ('polish', '酸洗车间', '酸洗', 'standard'),
        ('polish', '电抛车间', '电抛', 'standard'),
        ('polish', '振机车间', '振机', 'standard'),
        ('polish', '干滚车间', '干滚', 'standard'),
        ('polish', '清光车间', '清光', 'standard'),
        ('outsource', '蚀字外协', '蚀字', 'standard'),
        ('outsource', '电镀外协', '电镀', 'standard'),
        ('purchasing', '采购组', '外购', 'purchase_receipt'),
        ('assembly', '装包车间', '装包', 'standard'),
        ('assembly', '焊接车间', '焊接', 'standard')
) AS source(department_code, workshop_name, procedure_name, procedure_type)
JOIN department
    ON department.department_code = source.department_code
JOIN workshop
    ON workshop.department_id = department.id
    AND workshop.workshop_name = source.workshop_name;

UPDATE procedure
SET input_mode = 'multiple'
FROM workshop, department
WHERE procedure.workshop_id = workshop.id
  AND workshop.department_id = department.id
  AND department.department_code = 'assembly';

-- 默认业务人员：外协单位和采购经办人属于系统必需基础数据。
INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '新南伟', department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
WHERE department.department_code = 'outsource' AND workshop.workshop_name = '蚀字外协';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT company.company_name, department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
CROSS JOIN (
    VALUES ('智诚'), ('未来')
) AS company(company_name)
WHERE department.department_code = 'outsource' AND workshop.workshop_name = '电镀外协';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '赵哥', department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
WHERE department.department_code = 'purchasing' AND workshop.workshop_name = '采购组';

-- ------------------------------------------------------------
-- 可删除的开发业务数据：客户、产品、版本、BOM、流程图与订单
-- ------------------------------------------------------------

INSERT INTO customer (customer_name) VALUES ('Celine'), ('示例客户');

INSERT INTO product (
    customer_id, product_name, factory_code, customer_code, version
)
SELECT customer.id, 'CH-L43 双C锁扣', 'Z8735', 'Z8735', 1
FROM customer
WHERE customer.customer_name = 'Celine';

INSERT INTO product (
    customer_id, product_name, factory_code, customer_code, version
)
SELECT customer.id, '示例产品', 'DEMO-001', 'DEMO-001', 1
FROM customer
WHERE customer.customer_name = '示例客户';

INSERT INTO product_version (product_id, version)
SELECT id, 1 FROM product WHERE factory_code = 'DEMO-001';

INSERT INTO product_bom (
    product_id, product_version, part_name, part_no, pcs, remark, sort_order
)
SELECT product.id, 1, '示例配件', 'DEMO-001-01', 1, NULL, 1
FROM product
WHERE product.factory_code = 'DEMO-001';

INSERT INTO product_process_flow (product_id, product_version, flow_json)
SELECT product.id, 1, '{"schema_version": 4, "nodes": [], "edges": []}'::jsonb
FROM product
WHERE product.factory_code = 'DEMO-001';

INSERT INTO product_version (product_id, version)
SELECT id, 1
FROM product
WHERE factory_code = 'Z8735';

INSERT INTO product_bom (
    product_id,
    product_version,
    part_name,
    part_no,
    pcs,
    remark,
    sort_order
)
SELECT
    product.id,
    1,
    component.part_name,
    component.part_no,
    1,
    NULL,
    component.sort_order
FROM product
CROSS JOIN (
    VALUES
        ('配件',     'Z8735-01', 1),
        ('母件',     'Z8735-02', 2),
        ('右按件',   'Z8735-03', 3),
        ('固定按的', 'Z8735-04', 4),
        ('中心控件', 'Z8735-05', 5),
        ('钩扣',     'Z8735-06', 6),
        ('母件盖板', 'Z8735-07', 7),
        ('铝底板',   'Z8735-08', 8),
        ('公件盖板', 'Z8735-09', 9)
) AS component(part_name, part_no, sort_order)
WHERE product.factory_code = 'Z8735';

INSERT INTO product_process_flow (
    product_id,
    product_version,
    flow_json
)
SELECT
    product.id,
    1,
    '{"schema_version": 4, "nodes": [], "edges": []}'::jsonb
FROM product
WHERE product.factory_code = 'Z8735';

-- Celine 新产品；生产流程图由工程部后续配置。
INSERT INTO product (
    customer_id,
    product_name,
    factory_code,
    customer_code,
    version
)
SELECT
    customer.id,
    product_data.product_name,
    product_data.factory_code,
    product_data.customer_code,
    1
FROM customer
CROSS JOIN (
    VALUES
        ('L24.4 椭圆搭扣',    'Z8737', 'FIG6850'),
        ('W10.5 D圈',         'Z8739', 'AN00433'),
        ('W46.1 马蹄扣',      'Z8740', 'FI01248'),
        ('D10 磁力包扣',      'Z8711', 'CMG3H88'),
        ('L15.1双C镂空件',    'Z8609', 'PAG4N04')
) AS product_data(product_name, factory_code, customer_code)
WHERE customer.customer_name = 'Celine';

INSERT INTO product_version (product_id, version)
SELECT product.id, 1
FROM product
WHERE product.factory_code IN ('Z8737', 'Z8739', 'Z8740', 'Z8711', 'Z8609');

INSERT INTO product_bom (
    product_id,
    product_version,
    part_name,
    part_no,
    pcs,
    remark,
    sort_order
)
SELECT
    product.id,
    1,
    component.part_name,
    component.part_no,
    1,
    component.remark,
    component.sort_order
FROM product
JOIN (
    VALUES
        ('Z8737', '主体',            'Z8737-01', NULL,   1),
        ('Z8737', '过桥',            'Z8737-02', NULL,   2),
        ('Z8737', '利仔',            'Z8737-03', NULL,   3),
        ('Z8739', '主体',            'Z8739-01', NULL,   1),
        ('Z8740', '主体',            'Z8740-01', NULL,   1),
        ('Z8740', '中针',            'Z8740-02', NULL,   2),
        ('Z8711', 'logo件',          'Z8711-01', NULL,   1),
        ('Z8711', '脚钉（外购）',    'Z8711-02', NULL,   2),
        ('Z8609', 'L15.1双C镂空件',  'Z8609-01', NULL,   1)
) AS component(factory_code, part_name, part_no, remark, sort_order)
    ON component.factory_code = product.factory_code;

INSERT INTO product_process_flow (
    product_id,
    product_version,
    flow_json
)
SELECT
    product.id,
    1,
    '{"schema_version": 4, "nodes": [], "edges": []}'::jsonb
FROM product
WHERE product.factory_code IN ('Z8737', 'Z8739', 'Z8740', 'Z8711', 'Z8609');

-- 示例客户订单：订购 500 个示例产品；由业务部确认后生成草稿生产计划。
INSERT INTO customer_order (
    customer_order_no,
    customer_id,
    status,
    remark
)
SELECT
    'DEMO-ORDER-001',
    customer.id,
    'draft',
    '500个示例产品的客户订单'
FROM customer
WHERE customer.customer_name = '示例客户';

INSERT INTO customer_order_item (
    customer_order_id,
    product_id,
    product_version,
    quantity,
    delivery_date,
    remark
)
SELECT
    customer_order.id,
    product.id,
    1,
    500,
    CURRENT_DATE + 30,
    '示例订单明细'
FROM customer_order
JOIN customer
    ON customer.id = customer_order.customer_id
    AND customer.customer_name = '示例客户'
JOIN product
    ON product.customer_id = customer.id
    AND product.factory_code = 'DEMO-001'
WHERE customer_order.customer_order_no = 'DEMO-ORDER-001';

-- ------------------------------------------------------------
-- 可删除的开发示例人员
-- ------------------------------------------------------------

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '工程示例员工', id, NULL FROM department WHERE department_code = 'engineering';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '业务示例员工', id, NULL FROM department WHERE department_code = 'business';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '冲压示例工人', department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
WHERE department.department_code = 'stamp' AND workshop.workshop_name = '激光开料车间';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '表面处理示例工人', department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
WHERE department.department_code = 'polish' AND workshop.workshop_name = '手磨车间';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '机加示例工人', department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
WHERE department.department_code = 'cnc' AND workshop.workshop_name = 'CNC车间';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT 'QC示例工人', id, NULL FROM department WHERE department_code = 'qc';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '装配示例工人', department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
WHERE department.department_code = 'assembly' AND workshop.workshop_name = '装包车间';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '焊接示例工人', department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
WHERE department.department_code = 'assembly' AND workshop.workshop_name = '焊接车间';

COMMIT;
