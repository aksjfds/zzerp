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
CREATE EXTENSION IF NOT EXISTS pgcrypto;

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
    flow_json JSONB NOT NULL DEFAULT '{"schema_version": 5, "nodes": [], "edges": []}'::jsonb,
    draft_flow_json JSONB,
    CONSTRAINT ck_process_flow_json_object
        CHECK (jsonb_typeof(flow_json) = 'object'),
    CONSTRAINT ck_process_flow_schema_version_present
        CHECK (flow_json ? 'schema_version'),
    CONSTRAINT ck_process_flow_schema_version_type
        CHECK (jsonb_typeof(flow_json->'schema_version') = 'number'),
    CONSTRAINT ck_process_flow_schema_version
        CHECK (flow_json->>'schema_version' = '5'),
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
        CHECK (draft_flow_json IS NULL OR draft_flow_json->>'schema_version' = '5'),
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

-- workshop：保存部门下属车间及其单路/多路输入模式，作为流程节点、工艺和工人的组织范围。
CREATE TABLE workshop (
    id BIGSERIAL PRIMARY KEY,
    department_id BIGINT NOT NULL REFERENCES department(id),
    workshop_name TEXT NOT NULL,
    input_mode TEXT NOT NULL DEFAULT 'single',
    CONSTRAINT ck_workshop_input_mode CHECK (input_mode IN ('single', 'multiple')),
    CONSTRAINT uq_workshop_department_context UNIQUE (id, department_id),
    CONSTRAINT uq_workshop_name UNIQUE (department_id, workshop_name)
);

-- product_route_task：正式流程按物料起点展开后的执行路线投影。
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
    workshop_id BIGINT,
    department_id BIGINT NOT NULL REFERENCES department(id),
    route_order INT NOT NULL,
    CONSTRAINT fk_product_route_task_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version) ON DELETE CASCADE,
    CONSTRAINT fk_product_route_task_bom_version
        FOREIGN KEY (product_bom_id, product_id, product_version)
        REFERENCES product_bom(id, product_id, product_version) ON DELETE CASCADE,
    CONSTRAINT fk_product_route_task_workshop_department
        FOREIGN KEY (workshop_id, department_id)
        REFERENCES workshop(id, department_id),
    CONSTRAINT ck_product_route_task_origin_type
        CHECK (origin_node_type IN ('part', 'assembly')),
    CONSTRAINT ck_product_route_task_origin_scope CHECK (
        (origin_node_type = 'part' AND product_bom_id IS NOT NULL)
        OR (origin_node_type = 'assembly' AND product_bom_id IS NULL)
    ),
    CONSTRAINT ck_product_route_task_node_type
        CHECK (route_node_type IN ('process', 'assembly', 'supplier_processing')),
    CONSTRAINT ck_product_route_task_execution_scope CHECK (
        (route_node_type IN ('process', 'assembly') AND workshop_id IS NOT NULL)
        OR (route_node_type = 'supplier_processing'
            AND workshop_id IS NULL AND origin_node_type = 'part')
    ),
    CONSTRAINT ck_product_route_task_order CHECK (route_order >= 0),
    CONSTRAINT uq_product_route_task_origin_node UNIQUE (
        product_id, product_version, origin_flow_node_id, route_flow_node_id
    )
);

-- procedure：保存车间可执行的具体工艺；单路/多路由所属车间统一决定。
CREATE TABLE procedure (
    id BIGSERIAL PRIMARY KEY,
    workshop_id BIGINT NOT NULL REFERENCES workshop(id),
    procedure_name TEXT NOT NULL,
    CONSTRAINT uq_procedure_name UNIQUE (workshop_id, procedure_name)
);

-- procedure_configuration：保存产品版本、物料和车间节点的工艺配置及确认状态。
CREATE TABLE procedure_configuration (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    material_key TEXT NOT NULL,
    flow_node_id TEXT NOT NULL,
    confirmed_at TIMESTAMPTZ,
    confirmed_by VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_procedure_configuration_product_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version) ON DELETE CASCADE,
    CONSTRAINT ck_procedure_configuration_confirmation CHECK (
        (confirmed_at IS NULL AND confirmed_by IS NULL)
        OR (confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)
    ),
    CONSTRAINT uq_procedure_configuration_scope
        UNIQUE (product_id, product_version, material_key, flow_node_id)
);

-- procedure_price：保存已归属明确配置的工艺成员及可空单价。
CREATE TABLE procedure_price (
    id BIGSERIAL PRIMARY KEY,
    configuration_id BIGINT NOT NULL
        REFERENCES procedure_configuration(id) ON DELETE CASCADE,
    procedure_id BIGINT NOT NULL REFERENCES procedure(id),
    unit_price NUMERIC(12, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_procedure_price_nonnegative CHECK (unit_price >= 0),
    CONSTRAINT uq_procedure_price_scope
        UNIQUE (configuration_id, procedure_id)
);

-- procedure_price_revision：追加保存正式与临时工艺单价的每次实际变更。
CREATE TABLE procedure_price_revision (
    id BIGSERIAL PRIMARY KEY,
    department_id BIGINT NOT NULL REFERENCES department(id),
    target_type TEXT NOT NULL,
    target_id BIGINT NOT NULL,
    target_label TEXT NOT NULL,
    previous_unit_price NUMERIC(12, 2),
    new_unit_price NUMERIC(12, 2),
    actor_username VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_procedure_price_revision_target_type
        CHECK (target_type IN ('formal', 'temporary')),
    CONSTRAINT ck_procedure_price_revision_previous_nonnegative
        CHECK (previous_unit_price IS NULL OR previous_unit_price >= 0),
    CONSTRAINT ck_procedure_price_revision_new_nonnegative
        CHECK (new_unit_price IS NULL OR new_unit_price >= 0)
);
CREATE INDEX idx_procedure_price_revision_department
    ON procedure_price_revision(department_id, created_at DESC, id DESC);

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
    CONSTRAINT uq_customer_order_item_order
        UNIQUE (id, customer_order_id),
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
    allocated_inventory_quantity INT NOT NULL DEFAULT 0,
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
    CONSTRAINT ck_plan_item_allocated_inventory CHECK (allocated_inventory_quantity >= 0),
    CONSTRAINT uq_production_plan_item_identity
        UNIQUE (production_plan_id, customer_order_item_id, identity_key),
    CONSTRAINT uq_production_plan_item_plan_context
        UNIQUE (id, production_plan_id),
    CONSTRAINT uq_production_plan_item_reservation_context
        UNIQUE (id, production_plan_id, customer_order_item_id)
);

-- production_route_task：确定保存计划物料在绑定版本正式流程中的执行路线；数量和执行状态仍以计划、生产、工单及 QC 表为准。
CREATE TABLE production_route_task (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL,
    production_plan_item_id BIGINT NOT NULL,
    route_flow_node_id TEXT NOT NULL,
    route_node_type TEXT NOT NULL,
    workshop_id BIGINT,
    department_id BIGINT NOT NULL REFERENCES department(id),
    route_order INT NOT NULL,
    CONSTRAINT fk_production_route_task_plan_item
        FOREIGN KEY (production_plan_item_id, production_plan_id)
        REFERENCES production_plan_item(id, production_plan_id) ON DELETE CASCADE,
    CONSTRAINT fk_production_route_task_workshop_department
        FOREIGN KEY (workshop_id, department_id)
        REFERENCES workshop(id, department_id),
    CONSTRAINT ck_production_route_task_node_type
        CHECK (route_node_type IN ('process', 'assembly', 'supplier_processing')),
    CONSTRAINT ck_production_route_task_execution_scope CHECK (
        (route_node_type IN ('process', 'assembly') AND workshop_id IS NOT NULL)
        OR (route_node_type = 'supplier_processing' AND workshop_id IS NULL)
    ),
    CONSTRAINT ck_production_route_task_order CHECK (route_order >= 0),
    CONSTRAINT uq_production_route_task_item_node
        UNIQUE (production_plan_item_id, route_flow_node_id)
);

-- warehouse_stock：临时模拟实际 SQL Server 仓库，只保存配件和装配体业务库存。
CREATE TABLE warehouse_stock (
    id BIGSERIAL PRIMARY KEY,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    product_version INT NOT NULL,
    item_type TEXT NOT NULL,
    specification TEXT NOT NULL DEFAULT '',
    inventory_unit TEXT NOT NULL DEFAULT 'PCS',
    warehouse_code TEXT NOT NULL,
    warehouse_name TEXT NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    completion_status TEXT NOT NULL,
    last_inbound_date DATE,
    last_outbound_date DATE,
    CONSTRAINT ck_warehouse_stock_version CHECK (product_version > 0),
    CONSTRAINT ck_warehouse_stock_item_type
        CHECK (item_type IN ('part', 'assembly')),
    CONSTRAINT ck_warehouse_stock_item_code
        CHECK (item_code = btrim(item_code) AND item_code <> ''),
    CONSTRAINT ck_warehouse_stock_item_name
        CHECK (item_name = btrim(item_name) AND item_name <> ''),
    CONSTRAINT ck_warehouse_stock_completion_status
        CHECK (completion_status = btrim(completion_status) AND completion_status <> ''),
    CONSTRAINT ck_warehouse_stock_unit CHECK (inventory_unit = 'PCS'),
    CONSTRAINT ck_warehouse_stock_location CHECK (
        (warehouse_code = 'C01' AND warehouse_name = '主料仓')
        OR (warehouse_code = 'C02' AND warehouse_name = '辅料仓')
    ),
    CONSTRAINT ck_warehouse_stock_quantity CHECK (quantity >= 0),
    CONSTRAINT uq_warehouse_stock_identity UNIQUE (
        item_code, product_version, item_type, completion_status, warehouse_code
    ),
    CONSTRAINT uq_warehouse_stock_context UNIQUE (
        id, item_code, product_version, item_type, completion_status, warehouse_code
    )
);

-- finished_receipt：QC 放行或装包完成后等待成品部整批确认的成品入库记录。
CREATE TABLE finished_receipt (
    id BIGSERIAL PRIMARY KEY,
    work_order_batch_id BIGINT,
    work_order_id BIGINT,
    replacement_for_receipt_id BIGINT,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    quantity INT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    received_at TIMESTAMPTZ,
    received_by TEXT,
    corrected_at TIMESTAMPTZ,
    corrected_by TEXT,
    correction_reason TEXT,
    revision INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_finished_receipt_product_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version),
    CONSTRAINT fk_finished_receipt_replacement
        FOREIGN KEY (replacement_for_receipt_id) REFERENCES finished_receipt(id),
    CONSTRAINT uq_finished_receipt_replacement UNIQUE (replacement_for_receipt_id),
    CONSTRAINT ck_finished_receipt_source CHECK (
        (work_order_batch_id IS NOT NULL AND work_order_id IS NULL)
        OR (work_order_batch_id IS NULL AND work_order_id IS NOT NULL)
    ),
    CONSTRAINT ck_finished_receipt_version CHECK (product_version > 0),
    CONSTRAINT ck_finished_receipt_quantity CHECK (quantity > 0),
    CONSTRAINT ck_finished_receipt_status
        CHECK (status IN ('pending', 'received', 'cancelled', 'reversed')),
    CONSTRAINT ck_finished_receipt_revision CHECK (revision > 0),
    CONSTRAINT ck_finished_receipt_lifecycle CHECK (
        (status = 'pending' AND received_at IS NULL AND received_by IS NULL
            AND corrected_at IS NULL AND corrected_by IS NULL)
        OR (status = 'received' AND received_at IS NOT NULL
            AND received_by IS NOT NULL
            AND received_by = btrim(received_by) AND received_by <> ''
            AND corrected_at IS NULL AND corrected_by IS NULL)
        OR (status = 'cancelled' AND received_at IS NULL AND received_by IS NULL
            AND corrected_at IS NOT NULL AND corrected_by IS NOT NULL
            AND corrected_by = btrim(corrected_by) AND corrected_by <> '')
        OR (status = 'reversed' AND received_at IS NOT NULL AND received_by IS NOT NULL
            AND corrected_at IS NOT NULL AND corrected_by IS NOT NULL
            AND corrected_by = btrim(corrected_by) AND corrected_by <> '')
    )
);

-- finished_stock：成品部统一成品仓；库存唯一身份只有产品和产品版本。
CREATE TABLE finished_stock (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    reserved_quantity INT NOT NULL DEFAULT 0,
    revision INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_finished_stock_product_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version),
    CONSTRAINT uq_finished_stock_identity UNIQUE (product_id, product_version),
    CONSTRAINT ck_finished_stock_version CHECK (product_version > 0),
    CONSTRAINT ck_finished_stock_quantity CHECK (quantity >= 0),
    CONSTRAINT ck_finished_stock_reserved CHECK (reserved_quantity >= 0),
    CONSTRAINT ck_finished_stock_availability CHECK (reserved_quantity <= quantity),
    CONSTRAINT ck_finished_stock_revision CHECK (revision > 0)
);

-- finished_stock_reservation：生产计划对统一成品库存的占用，不形成第二套库存。
CREATE TABLE finished_stock_reservation (
    id BIGSERIAL PRIMARY KEY,
    finished_stock_id BIGINT NOT NULL REFERENCES finished_stock(id),
    production_plan_id BIGINT NOT NULL,
    production_plan_item_id BIGINT NOT NULL,
    customer_order_item_id BIGINT NOT NULL REFERENCES customer_order_item(id),
    reserved_quantity INT NOT NULL,
    shipped_quantity INT NOT NULL DEFAULT 0,
    released_quantity INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_finished_stock_reservation_plan_item
        FOREIGN KEY (
            production_plan_item_id, production_plan_id, customer_order_item_id
        ) REFERENCES production_plan_item(
            id, production_plan_id, customer_order_item_id
        ),
    CONSTRAINT uq_finished_stock_reservation_context
        UNIQUE (id, finished_stock_id, customer_order_item_id),
    CONSTRAINT ck_finished_stock_reservation_reserved CHECK (reserved_quantity > 0),
    CONSTRAINT ck_finished_stock_reservation_shipped CHECK (shipped_quantity >= 0),
    CONSTRAINT ck_finished_stock_reservation_released CHECK (released_quantity >= 0),
    CONSTRAINT ck_finished_stock_reservation_balance CHECK (
        shipped_quantity + released_quantity <= reserved_quantity
    )
);

-- finished_stock_transaction：统一成品仓的真实入库和客户发货不可变流水。
CREATE TABLE finished_stock_transaction (
    id BIGSERIAL PRIMARY KEY,
    finished_stock_id BIGINT NOT NULL REFERENCES finished_stock(id),
    finished_receipt_id BIGINT REFERENCES finished_receipt(id),
    customer_order_id BIGINT REFERENCES customer_order(id),
    customer_order_item_id BIGINT REFERENCES customer_order_item(id),
    finished_stock_reservation_id BIGINT,
    operation_group_no TEXT NOT NULL,
    reversal_of_transaction_id BIGINT,
    transaction_type TEXT NOT NULL,
    quantity INT NOT NULL,
    quantity_before INT NOT NULL,
    quantity_after INT NOT NULL,
    actor_username TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_finished_stock_transaction_reversal
        UNIQUE (reversal_of_transaction_id),
    CONSTRAINT fk_finished_stock_transaction_reversal
        FOREIGN KEY (reversal_of_transaction_id)
        REFERENCES finished_stock_transaction(id),
    CONSTRAINT fk_finished_stock_transaction_order_item
        FOREIGN KEY (customer_order_item_id, customer_order_id)
        REFERENCES customer_order_item(id, customer_order_id),
    CONSTRAINT fk_finished_stock_transaction_reservation
        FOREIGN KEY (
            finished_stock_reservation_id, finished_stock_id, customer_order_item_id
        ) REFERENCES finished_stock_reservation(
            id, finished_stock_id, customer_order_item_id
        ),
    CONSTRAINT ck_finished_stock_transaction_type CHECK (
        transaction_type IN (
            'receipt', 'receipt_reversal',
            'customer_shipment', 'customer_shipment_reversal'
        )
    ),
    CONSTRAINT ck_finished_stock_transaction_quantity CHECK (quantity > 0),
    CONSTRAINT ck_finished_stock_transaction_group CHECK (
        operation_group_no = btrim(operation_group_no) AND operation_group_no <> ''
    ),
    CONSTRAINT ck_finished_stock_transaction_before CHECK (quantity_before >= 0),
    CONSTRAINT ck_finished_stock_transaction_after CHECK (quantity_after >= 0),
    CONSTRAINT ck_finished_stock_transaction_actor CHECK (
        actor_username = btrim(actor_username) AND actor_username <> ''
    ),
    CONSTRAINT ck_finished_stock_transaction_source CHECK (
        (transaction_type IN ('receipt', 'receipt_reversal')
            AND finished_receipt_id IS NOT NULL
            AND customer_order_id IS NULL
            AND customer_order_item_id IS NULL
            AND finished_stock_reservation_id IS NULL)
        OR (transaction_type IN ('customer_shipment', 'customer_shipment_reversal')
            AND finished_receipt_id IS NULL
            AND customer_order_id IS NOT NULL
            AND customer_order_item_id IS NOT NULL)
    ),
    CONSTRAINT ck_finished_stock_transaction_balance CHECK (
        (transaction_type = 'receipt'
            AND quantity_after = quantity_before + quantity)
        OR (transaction_type = 'customer_shipment'
            AND quantity_after = quantity_before - quantity)
        OR (transaction_type = 'receipt_reversal'
            AND quantity_after = quantity_before - quantity)
        OR (transaction_type = 'customer_shipment_reversal'
            AND quantity_after = quantity_before + quantity)
    ),
    CONSTRAINT ck_finished_stock_transaction_reversal CHECK (
        (transaction_type IN ('receipt', 'customer_shipment')
            AND reversal_of_transaction_id IS NULL)
        OR (transaction_type IN ('receipt_reversal', 'customer_shipment_reversal')
            AND reversal_of_transaction_id IS NOT NULL)
    )
);

-- ------------------------------------------------------------
-- 生产库存、工单、QC 批次与流动记录
-- ------------------------------------------------------------

-- material_processing_state：不保存数量，只定义可合并物料的加工履历、QC 去向和继续节点。
CREATE TABLE material_processing_state (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    item_type TEXT NOT NULL,
    product_bom_id BIGINT,
    origin_flow_node_id TEXT NOT NULL,
    completed_flow_node_id TEXT NOT NULL,
    resume_flow_node_id TEXT NOT NULL,
    procedure_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    qc_status TEXT NOT NULL,
    display_text TEXT NOT NULL,
    state_signature VARCHAR(64) NOT NULL,
    CONSTRAINT fk_material_processing_state_product_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version),
    CONSTRAINT fk_material_processing_state_bom_version
        FOREIGN KEY (product_bom_id, product_id, product_version)
        REFERENCES product_bom(id, product_id, product_version),
    CONSTRAINT ck_material_processing_state_version CHECK (product_version > 0),
    CONSTRAINT ck_material_processing_state_item_type
        CHECK (item_type IN ('part', 'assembly')),
    CONSTRAINT ck_material_processing_state_material CHECK (
        (item_type = 'part' AND product_bom_id IS NOT NULL)
        OR (item_type = 'assembly' AND product_bom_id IS NULL)
    ),
    CONSTRAINT ck_material_processing_state_qc_status
        CHECK (qc_status IN ('none', 'returned', 'released', 'stored')),
    CONSTRAINT ck_material_processing_state_display
        CHECK (display_text = btrim(display_text) AND display_text <> ''),
    CONSTRAINT ck_material_processing_state_nodes CHECK (
        origin_flow_node_id = btrim(origin_flow_node_id) AND origin_flow_node_id <> ''
        AND completed_flow_node_id = btrim(completed_flow_node_id)
            AND completed_flow_node_id <> ''
        AND resume_flow_node_id = btrim(resume_flow_node_id)
            AND resume_flow_node_id <> ''
    ),
    CONSTRAINT ck_material_processing_state_history
        CHECK (jsonb_typeof(procedure_history) = 'array'),
    CONSTRAINT ck_material_processing_state_signature
        CHECK (length(state_signature) = 64),
    CONSTRAINT uq_material_processing_state_signature UNIQUE (state_signature),
    CONSTRAINT uq_material_processing_state_context
        UNIQUE (id, product_id, product_version)
);

CREATE INDEX idx_material_processing_state_lookup
ON material_processing_state(
    product_id, product_version, item_type, product_bom_id,
    origin_flow_node_id, display_text
);

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

-- repository：保存生产对象在流程节点中的可用数量；工单产出按来源工单独立存放。
CREATE TABLE repository (
    id BIGSERIAL PRIMARY KEY,
    production_item_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    processing_state_id BIGINT NOT NULL REFERENCES material_processing_state(id),
    flow_node_id TEXT NOT NULL,
    source_flow_node_id TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    source_work_order_id BIGINT,
    quantity INT NOT NULL,
    CONSTRAINT uq_repository_id_production_item UNIQUE (id, production_item_id),
    CONSTRAINT uq_repository_source_context
        UNIQUE (id, production_item_id, processing_state_id),
    CONSTRAINT ck_repository_quantity_positive CHECK (quantity > 0)
);

-- work_order：保存普通加工、装配和委外加工工单及其执行快照和进度。
CREATE TABLE work_order (
    id BIGSERIAL PRIMARY KEY,
    work_order_no TEXT,
    repository_id BIGINT,
    production_item_id BIGINT NOT NULL REFERENCES production_item(id),
    source_processing_state_id BIGINT REFERENCES material_processing_state(id),
    procedure_id BIGINT REFERENCES procedure(id),
    work_order_type TEXT NOT NULL,
    is_temporary BOOLEAN NOT NULL,
    flow_node_id TEXT NOT NULL,
    -- 工单创建时记录执行来源快照；装配工单记录自身装配节点，物料来源另见 work_order_material。
    source_flow_node_id TEXT,
    supplier_name TEXT,
    supplier_process_name TEXT,
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
    CONSTRAINT ck_work_order_supplier_progress CHECK (
        work_order_type <> 'supplier_processing'
        OR processed_quantity = completed_quantity
    ),
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMPTZ,
    CONSTRAINT uq_work_order_no UNIQUE (work_order_no),
    CONSTRAINT ck_work_order_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_work_order_type
        CHECK (work_order_type IN ('standard', 'assembly', 'supplier_processing')),
    CONSTRAINT ck_work_order_supplier_name CHECK (
        supplier_name IS NULL
        OR (supplier_name = btrim(supplier_name) AND supplier_name <> '')
    ),
    CONSTRAINT ck_work_order_supplier_process_name CHECK (
        supplier_process_name IS NULL
        OR (supplier_process_name = btrim(supplier_process_name)
            AND supplier_process_name <> '')
    ),
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
            AND procedure_id IS NOT NULL
            AND source_flow_node_id IS NOT NULL
            AND supplier_name IS NULL
            AND supplier_process_name IS NULL)
        OR (work_order_type = 'standard'
            AND procedure_id IS NOT NULL
            AND source_processing_state_id IS NOT NULL
            AND source_flow_node_id IS NOT NULL
            AND supplier_name IS NULL
            AND supplier_process_name IS NULL
            AND (status <> 'open'
                OR completed_quantity = quantity
                OR repository_id IS NOT NULL))
        OR (work_order_type = 'supplier_processing'
            AND procedure_id IS NULL
            AND source_processing_state_id IS NULL
            AND is_temporary = FALSE
            AND repository_id IS NULL
            AND worker_id IS NULL
            AND worker_name IS NULL
            AND source_flow_node_id IS NOT NULL
            AND supplier_name IS NOT NULL
            AND supplier_process_name IS NOT NULL)
    ),
    CONSTRAINT fk_work_order_repository_item
        FOREIGN KEY (repository_id, production_item_id, source_processing_state_id)
        REFERENCES repository(id, production_item_id, processing_state_id)
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

-- work_order_material：保存装配工单选定的投入来源快照；repository_id 只在来源仍被直接占用时保留。
CREATE TABLE work_order_material (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    repository_id BIGINT,
    production_item_id BIGINT NOT NULL REFERENCES production_item(id),
    source_processing_state_id BIGINT NOT NULL REFERENCES material_processing_state(id),
    quantity INT NOT NULL,
    source_flow_node_id TEXT NOT NULL,
    source_previous_flow_node_id TEXT NOT NULL,
    source_department_id BIGINT NOT NULL REFERENCES department(id),
    source_work_order_id BIGINT,
    CONSTRAINT fk_work_order_material_repository_item
        FOREIGN KEY (repository_id, production_item_id, source_processing_state_id)
        REFERENCES repository(id, production_item_id, processing_state_id),
    CONSTRAINT uq_work_order_material_repository UNIQUE (work_order_id, repository_id),
    CONSTRAINT uq_work_order_material_movement_context
        UNIQUE (id, work_order_id, production_item_id),
    CONSTRAINT ck_work_order_material_quantity CHECK (quantity > 0)
);

-- work_order_batch：保存普通工单送检批次、委外分次 QC 结果及普通返工复检关系。
CREATE TABLE work_order_batch (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    submitted_quantity INT NOT NULL,
    -- 普通批次记录送检执行节点；委外批次记录对应委外节点，均等于 work_order.flow_node_id。
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
    qualified_destination TEXT,
    destination_decided_at TIMESTAMPTZ,
    destination_decided_by TEXT,
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
    CONSTRAINT ck_batch_destination_actor CHECK (
        destination_decided_by IS NULL
        OR (destination_decided_by = btrim(destination_decided_by)
            AND destination_decided_by <> '')
    ),
    CONSTRAINT ck_batch_inspection_complete CHECK (
        (recorded_at IS NULL AND qualified_quantity IS NULL
            AND rework_quantity IS NULL AND scrap_quantity IS NULL
            AND lost_quantity IS NULL AND qc_worker_id IS NULL AND qc_worker_name IS NULL
            AND qualified_destination IS NULL
            AND destination_decided_at IS NULL AND destination_decided_by IS NULL)
        OR
        (recorded_at IS NOT NULL AND qualified_quantity IS NOT NULL
            AND rework_quantity IS NOT NULL AND scrap_quantity IS NOT NULL
            AND lost_quantity IS NOT NULL AND qc_worker_id IS NOT NULL
            AND qc_worker_name IS NOT NULL
            AND ((qualified_quantity = 0 AND qualified_destination IS NULL
                    AND destination_decided_at IS NULL AND destination_decided_by IS NULL)
                OR (qualified_quantity > 0
                    AND ((qualified_destination IS NULL
                            AND destination_decided_at IS NULL
                            AND destination_decided_by IS NULL)
                        OR (qualified_destination IN ('return', 'release', 'inventory')
                            AND destination_decided_at IS NOT NULL
                            AND destination_decided_by IS NOT NULL))))
            AND qualified_quantity + rework_quantity + scrap_quantity + lost_quantity
                = submitted_quantity)
    )
);

ALTER TABLE finished_receipt
    ADD CONSTRAINT fk_finished_receipt_qc_batch
        FOREIGN KEY (work_order_batch_id) REFERENCES work_order_batch(id),
    ADD CONSTRAINT fk_finished_receipt_packaging_order
        FOREIGN KEY (work_order_id) REFERENCES work_order(id);

-- warehouse_operation：只记录本项目发起的仓库操作及跨数据库处理结果。
CREATE TABLE warehouse_operation (
    id BIGSERIAL PRIMARY KEY,
    operation_group_no TEXT NOT NULL,
    operation_no TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    production_plan_id BIGINT,
    production_plan_item_id BIGINT,
    work_order_id BIGINT,
    work_order_batch_id BIGINT,
    production_item_id BIGINT,
    processing_state_id BIGINT NOT NULL,
    reversal_of_operation_id BIGINT,
    warehouse_stock_id BIGINT,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    product_version INT NOT NULL,
    item_type TEXT NOT NULL,
    specification TEXT NOT NULL DEFAULT '',
    inventory_unit TEXT NOT NULL DEFAULT 'PCS',
    warehouse_code TEXT NOT NULL,
    warehouse_name TEXT NOT NULL,
    completion_status TEXT NOT NULL,
    quantity INT NOT NULL,
    quantity_before INT,
    quantity_after INT,
    status TEXT NOT NULL DEFAULT 'pending',
    actor_username TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMPTZ,
    manual_reviewed_at TIMESTAMPTZ,
    manual_reviewed_by TEXT,
    manual_review_note TEXT,
    CONSTRAINT uq_warehouse_operation_no UNIQUE (operation_no),
    CONSTRAINT uq_warehouse_operation_reversal UNIQUE (reversal_of_operation_id),
    CONSTRAINT fk_warehouse_operation_reversal
        FOREIGN KEY (reversal_of_operation_id) REFERENCES warehouse_operation(id),
    CONSTRAINT fk_warehouse_operation_plan
        FOREIGN KEY (production_plan_id) REFERENCES production_plan(id),
    CONSTRAINT fk_warehouse_operation_plan_item
        FOREIGN KEY (production_plan_item_id, production_plan_id)
        REFERENCES production_plan_item(id, production_plan_id),
    CONSTRAINT fk_warehouse_operation_work_order
        FOREIGN KEY (work_order_id) REFERENCES work_order(id),
    CONSTRAINT fk_warehouse_operation_batch_order
        FOREIGN KEY (work_order_batch_id, work_order_id)
        REFERENCES work_order_batch(id, work_order_id),
    CONSTRAINT fk_warehouse_operation_production_item
        FOREIGN KEY (production_item_id) REFERENCES production_item(id),
    CONSTRAINT fk_warehouse_operation_processing_state
        FOREIGN KEY (processing_state_id) REFERENCES material_processing_state(id),
    CONSTRAINT fk_warehouse_operation_stock_context
        FOREIGN KEY (
            warehouse_stock_id, item_code, product_version,
            item_type, completion_status, warehouse_code
        ) REFERENCES warehouse_stock(
            id, item_code, product_version, item_type, completion_status, warehouse_code
        ),
    CONSTRAINT ck_warehouse_operation_type
        CHECK (operation_type IN ('inbound', 'outbound')),
    CONSTRAINT ck_warehouse_operation_source_type CHECK (
        source_type IN (
            'plan_confirmation', 'qc_inventory', 'production_position', 'reversal'
        )
    ),
    CONSTRAINT ck_warehouse_operation_direction CHECK (
        (source_type = 'plan_confirmation' AND operation_type = 'outbound')
        OR (source_type IN ('qc_inventory', 'production_position')
            AND operation_type = 'inbound')
        OR source_type = 'reversal'
    ),
    CONSTRAINT ck_warehouse_operation_source_context CHECK (
        (source_type = 'plan_confirmation'
            AND production_plan_id IS NOT NULL
            AND production_plan_item_id IS NOT NULL
            AND work_order_id IS NULL
            AND work_order_batch_id IS NULL
            AND production_item_id IS NULL)
        OR (source_type = 'qc_inventory'
            AND work_order_id IS NOT NULL
            AND work_order_batch_id IS NOT NULL
            AND production_item_id IS NOT NULL
            AND production_plan_id IS NULL
            AND production_plan_item_id IS NULL)
        OR (source_type = 'production_position'
            AND production_item_id IS NOT NULL
            AND production_plan_id IS NULL
            AND production_plan_item_id IS NULL
            AND work_order_id IS NULL
            AND work_order_batch_id IS NULL)
        OR (source_type = 'reversal'
            AND reversal_of_operation_id IS NOT NULL
            AND production_plan_id IS NULL
            AND production_plan_item_id IS NULL
            AND work_order_id IS NULL
            AND work_order_batch_id IS NULL
            AND production_item_id IS NULL)
    ),
    CONSTRAINT ck_warehouse_operation_group_no
        CHECK (operation_group_no = btrim(operation_group_no)
            AND operation_group_no <> ''),
    CONSTRAINT ck_warehouse_operation_no
        CHECK (operation_no = btrim(operation_no) AND operation_no <> ''),
    CONSTRAINT ck_warehouse_operation_number_scope CHECK (
        left(operation_no, length(operation_group_no) + 1)
            = operation_group_no || ':'
    ),
    CONSTRAINT ck_warehouse_operation_item_code
        CHECK (item_code = btrim(item_code) AND item_code <> ''),
    CONSTRAINT ck_warehouse_operation_item_name
        CHECK (item_name = btrim(item_name) AND item_name <> ''),
    CONSTRAINT ck_warehouse_operation_completion_status
        CHECK (completion_status = btrim(completion_status) AND completion_status <> ''),
    CONSTRAINT ck_warehouse_operation_actor
        CHECK (actor_username = btrim(actor_username) AND actor_username <> ''),
    CONSTRAINT ck_warehouse_operation_item_type
        CHECK (item_type IN ('part', 'assembly')),
    CONSTRAINT ck_warehouse_operation_unit CHECK (inventory_unit = 'PCS'),
    CONSTRAINT ck_warehouse_operation_location CHECK (
        (warehouse_code = 'C01' AND warehouse_name = '主料仓')
        OR (warehouse_code = 'C02' AND warehouse_name = '辅料仓')
    ),
    CONSTRAINT ck_warehouse_operation_version CHECK (product_version > 0),
    CONSTRAINT ck_warehouse_operation_quantity CHECK (quantity > 0),
    CONSTRAINT ck_warehouse_operation_before
        CHECK (quantity_before IS NULL OR quantity_before >= 0),
    CONSTRAINT ck_warehouse_operation_after
        CHECK (quantity_after IS NULL OR quantity_after >= 0),
    CONSTRAINT ck_warehouse_operation_quantity_pair
        CHECK ((quantity_before IS NULL) = (quantity_after IS NULL)),
    CONSTRAINT ck_warehouse_operation_status
        CHECK (status IN ('pending', 'succeeded', 'failed', 'uncertain')),
    CONSTRAINT ck_warehouse_operation_lifecycle CHECK (
        (status = 'pending' AND executed_at IS NULL
            AND quantity_before IS NULL AND quantity_after IS NULL
            AND error_message IS NULL)
        OR (status = 'succeeded' AND executed_at IS NOT NULL
            AND quantity_before IS NOT NULL AND quantity_after IS NOT NULL
            AND error_message IS NULL)
        OR (status IN ('failed', 'uncertain') AND executed_at IS NOT NULL
            AND error_message IS NOT NULL AND btrim(error_message) <> '')
    ),
    CONSTRAINT ck_warehouse_operation_balance CHECK (
        status <> 'succeeded'
        OR (operation_type = 'inbound' AND quantity_after = quantity_before + quantity)
        OR (operation_type = 'outbound' AND quantity_after = quantity_before - quantity)
    ),
    CONSTRAINT ck_warehouse_operation_manual_review CHECK (
        (manual_reviewed_at IS NULL AND manual_reviewed_by IS NULL
            AND manual_review_note IS NULL)
        OR (status = 'uncertain' AND manual_reviewed_at IS NOT NULL
            AND manual_reviewed_by IS NOT NULL
            AND manual_review_note IS NOT NULL
            AND btrim(manual_review_note) <> '')
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
            'initial', 'process', 'assembly_input', 'assembly_output',
            'qc_qualified', 'qc_inventory', 'production_inventory', 'qc_rework',
            'production_inventory_restore',
            'inventory_issue', 'assembly_input_restore',
            'scrap', 'lost'
        )
    ),
    work_order_id BIGINT REFERENCES work_order(id),
    work_order_batch_id BIGINT,
    work_order_material_id BIGINT,
    warehouse_operation_id BIGINT REFERENCES warehouse_operation(id),
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
        OR (movement_type IN ('process', 'assembly_output')
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
        OR (movement_type = 'qc_inventory'
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NULL
            AND source_department_id IS NOT NULL
            AND target_department_id IS NOT NULL
            AND work_order_id IS NOT NULL
            AND work_order_batch_id IS NOT NULL)
        OR (movement_type = 'production_inventory'
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NULL
            AND source_department_id IS NOT NULL
            AND target_department_id IS NOT NULL
            AND work_order_id IS NULL
            AND work_order_batch_id IS NULL)
        OR (movement_type = 'production_inventory_restore'
            AND source_flow_node_id IS NOT NULL
            AND target_flow_node_id IS NOT NULL
            AND source_department_id IS NOT NULL
            AND target_department_id IS NOT NULL
            AND work_order_id IS NULL
            AND work_order_batch_id IS NULL)
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
    ),
    CONSTRAINT ck_production_movement_warehouse_operation CHECK (
        (movement_type IN ('production_inventory', 'production_inventory_restore')
            AND warehouse_operation_id IS NOT NULL)
        OR (movement_type NOT IN ('production_inventory', 'production_inventory_restore')
            AND warehouse_operation_id IS NULL)
    )
);

-- production_warehouse_storage_line：生产节点物料入库实际消耗的生产仓位快照，用于受限冲销。
CREATE TABLE production_warehouse_storage_line (
    id BIGSERIAL PRIMARY KEY,
    warehouse_operation_id BIGINT NOT NULL REFERENCES warehouse_operation(id),
    original_repository_id BIGINT NOT NULL,
    production_item_id BIGINT NOT NULL REFERENCES production_item(id) ON DELETE CASCADE,
    processing_state_id BIGINT NOT NULL REFERENCES material_processing_state(id),
    flow_node_id TEXT NOT NULL,
    source_flow_node_id TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    source_work_order_id BIGINT REFERENCES work_order(id),
    quantity INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_production_warehouse_storage_line
        UNIQUE (warehouse_operation_id, original_repository_id),
    CONSTRAINT ck_production_warehouse_storage_line_quantity CHECK (quantity > 0)
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
        CHECK (operation_type IN ('submission', 'rework_submission', 'qc_destination')),
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

CREATE FUNCTION protect_procedure_configuration() RETURNS TRIGGER AS $$
BEGIN
    IF (
        NEW.product_id,
        NEW.product_version,
        NEW.material_key,
        NEW.flow_node_id
    ) IS DISTINCT FROM (
        OLD.product_id,
        OLD.product_version,
        OLD.material_key,
        OLD.flow_node_id
    ) THEN
        RAISE EXCEPTION 'procedure configuration scope is immutable'
            USING ERRCODE = '23514';
    END IF;
    IF OLD.confirmed_at IS NOT NULL AND (
        NEW.confirmed_at,
        NEW.confirmed_by
    ) IS DISTINCT FROM (
        OLD.confirmed_at,
        OLD.confirmed_by
    ) THEN
        IF NOT (
            NEW.confirmed_at IS NULL
            AND NEW.confirmed_by IS NULL
            AND NOT EXISTS (
                SELECT 1
                FROM work_order wo
                JOIN production_item pi ON pi.id = wo.production_item_id
                WHERE pi.product_id = OLD.product_id
                  AND pi.product_version = OLD.product_version
                  AND wo.flow_node_id = OLD.flow_node_id
                  AND CASE
                      WHEN pi.product_bom_id IS NOT NULL
                          THEN 'part:' || pi.product_bom_id::TEXT
                      ELSE 'assembly:' || pi.origin_flow_node_id
                  END = OLD.material_key
            )
        ) THEN
            RAISE EXCEPTION 'confirmed procedure configuration is immutable'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    IF OLD.confirmed_at IS NULL AND NEW.confirmed_at IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM procedure_price
            WHERE configuration_id = NEW.id
        ) THEN
        RAISE EXCEPTION 'procedure configuration cannot be confirmed without a procedure'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_confirmed_procedure_membership() RETURNS TRIGGER AS $$
DECLARE
    old_confirmed BOOLEAN := FALSE;
    new_confirmed BOOLEAN := FALSE;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        SELECT confirmed_at IS NOT NULL INTO old_confirmed
        FROM procedure_configuration WHERE id = OLD.configuration_id;
    END IF;
    IF TG_OP <> 'DELETE' THEN
        SELECT confirmed_at IS NOT NULL INTO new_confirmed
        FROM procedure_configuration WHERE id = NEW.configuration_id;
    END IF;
    IF TG_OP = 'INSERT' AND new_confirmed THEN
        RAISE EXCEPTION 'confirmed procedure configuration membership is immutable'
            USING ERRCODE = '23514';
    ELSIF TG_OP = 'DELETE' AND old_confirmed THEN
        RAISE EXCEPTION 'confirmed procedure configuration membership is immutable'
            USING ERRCODE = '23514';
    ELSIF TG_OP = 'UPDATE'
        AND (NEW.configuration_id, NEW.procedure_id)
            IS DISTINCT FROM (OLD.configuration_id, OLD.procedure_id)
        AND (old_confirmed OR new_confirmed) THEN
        RAISE EXCEPTION 'confirmed procedure configuration membership is immutable'
            USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_work_order_closure() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'closed'
        AND EXISTS (
            SELECT 1 FROM work_order_batch
            WHERE work_order_id = NEW.id
              AND (
                  recorded_at IS NULL
                  OR (qualified_quantity > 0 AND destination_decided_at IS NULL)
              )
        ) THEN
        RAISE EXCEPTION 'work order with pending QC batches cannot be closed'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'closed'
        AND NEW.work_order_type IN ('standard', 'assembly')
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
        NEW.is_temporary,
        NEW.work_order_name,
        NEW.supplier_name,
        NEW.supplier_process_name,
        NEW.remark,
        NEW.flow_node_id,
        NEW.source_flow_node_id
    ) IS DISTINCT FROM (
        OLD.procedure_id,
        OLD.work_order_type,
        OLD.is_temporary,
        OLD.work_order_name,
        OLD.supplier_name,
        OLD.supplier_process_name,
        OLD.remark,
        OLD.flow_node_id,
        OLD.source_flow_node_id
    ) AND (
        EXISTS (
            SELECT 1
            FROM production_movement
            WHERE work_order_id = NEW.id
        )
        OR EXISTS (
            SELECT 1
            FROM work_order_batch
            WHERE work_order_id = NEW.id
        )
    ) THEN
        RAISE EXCEPTION 'work order execution snapshot is retained by production history'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.production_item_id IS DISTINCT FROM OLD.production_item_id
        AND (
            EXISTS (
                SELECT 1
                FROM work_order_batch
                WHERE work_order_id = NEW.id
            )
            OR EXISTS (
                SELECT 1
                FROM production_movement
                WHERE work_order_id = NEW.id
                  AND movement_type <> 'assembly_input'
                  AND production_item_id <> NEW.production_item_id
            )
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
DECLARE
    qc_undo_batch_id_text TEXT;
    operation_undo_id_text TEXT;
BEGIN
    IF OLD.recorded_at IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN
        qc_undo_batch_id_text := current_setting(
            'zzerp.qc_inspection_undo_batch_id',
            TRUE
        );
        IF qc_undo_batch_id_text = OLD.id::TEXT
            AND OLD.qualified_destination IS NULL
            AND OLD.destination_decided_at IS NULL
            AND OLD.destination_decided_by IS NULL
            AND ROW(
                NEW.work_order_id,
                NEW.submitted_quantity,
                NEW.source_flow_node_id,
                NEW.rework_source_batch_id
            ) IS NOT DISTINCT FROM ROW(
                OLD.work_order_id,
                OLD.submitted_quantity,
                OLD.source_flow_node_id,
                OLD.rework_source_batch_id
            )
            AND NEW.recorded_at IS NULL
            AND NEW.qualified_quantity IS NULL
            AND NEW.rework_quantity IS NULL
            AND NEW.scrap_quantity IS NULL
            AND NEW.lost_quantity IS NULL
            AND NEW.qc_worker_id IS NULL
            AND NEW.qc_worker_name IS NULL
            AND NEW.defect_reason IS NULL
            AND NEW.qualified_destination IS NULL
            AND NEW.destination_decided_at IS NULL
            AND NEW.destination_decided_by IS NULL
            AND NOT EXISTS (
                SELECT 1
                FROM work_order_batch AS child_batch
                WHERE child_batch.work_order_id = OLD.work_order_id
                  AND child_batch.rework_source_batch_id = OLD.id
            ) THEN
            RETURN NEW;
        END IF;
        operation_undo_id_text := current_setting(
            'zzerp.undo_operation_id',
            TRUE
        );
        IF operation_undo_id_text IS NOT NULL
            AND operation_undo_id_text ~ '^[0-9]+$'
            AND OLD.qualified_destination IS NOT NULL
            AND NEW.qualified_destination IS NULL
            AND NEW.destination_decided_at IS NULL
            AND NEW.destination_decided_by IS NULL
            AND (to_jsonb(NEW) - ARRAY[
                'qualified_destination', 'destination_decided_at',
                'destination_decided_by'
            ]) = (to_jsonb(OLD) - ARRAY[
                'qualified_destination', 'destination_decided_at',
                'destination_decided_by'
            ])
            AND EXISTS (
                SELECT 1
                FROM production_operation_undo AS undo_operation
                WHERE undo_operation.id = operation_undo_id_text::BIGINT
                  AND undo_operation.status = 'applied'
                  AND undo_operation.operation_type = 'qc_destination'
                  AND undo_operation.work_order_id = OLD.work_order_id
                  AND undo_operation.work_order_batch_id = OLD.id
            ) THEN
            RETURN NEW;
        END IF;
        IF OLD.qualified_quantity > 0
            AND OLD.qualified_destination IS NULL
            AND OLD.destination_decided_at IS NULL
            AND OLD.destination_decided_by IS NULL
            AND NEW.qualified_destination IN ('return', 'release', 'inventory')
            AND NEW.destination_decided_at IS NOT NULL
            AND NEW.destination_decided_by IS NOT NULL
            AND (to_jsonb(NEW) - ARRAY[
                'qualified_destination', 'destination_decided_at', 'destination_decided_by'
            ]) = (to_jsonb(OLD) - ARRAY[
                'qualified_destination', 'destination_decided_at', 'destination_decided_by'
            ]) THEN
            RETURN NEW;
        END IF;
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
    batch_work_order_type TEXT;
    batch_work_order_quantity INT;
    batch_work_order_flow_node_id TEXT;
    batch_work_order_status TEXT;
    recorded_qualified_quantity BIGINT;
    submission_count INT;
    submission_quantity BIGINT;
    moved_qualified BIGINT;
    moved_inventory BIGINT;
    moved_rework BIGINT;
    moved_scrap BIGINT;
    moved_lost BIGINT;
BEGIN
    SELECT work_order_type
    INTO batch_work_order_type
    FROM work_order
    WHERE id = NEW.work_order_id;

    SELECT
        COUNT(*) FILTER (
            WHERE movement_type IN ('process', 'assembly_output')
        ),
        COALESCE(SUM(quantity) FILTER (
            WHERE movement_type IN ('process', 'assembly_output')
        ), 0),
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'qc_qualified'), 0),
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'qc_inventory'), 0),
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'qc_rework'), 0),
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'scrap'), 0),
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'lost'), 0)
    INTO
        submission_count,
        submission_quantity,
        moved_qualified,
        moved_inventory,
        moved_rework,
        moved_scrap,
        moved_lost
    FROM production_movement
    WHERE work_order_batch_id = NEW.id;

    IF batch_work_order_type = 'supplier_processing' THEN
        SELECT quantity, flow_node_id, status
        INTO
            batch_work_order_quantity,
            batch_work_order_flow_node_id,
            batch_work_order_status
        FROM work_order
        WHERE id = NEW.work_order_id
        FOR UPDATE;

        SELECT COALESCE(SUM(qualified_quantity), 0)
        INTO recorded_qualified_quantity
        FROM work_order_batch
        WHERE work_order_id = NEW.work_order_id
          AND id <> NEW.id
          AND recorded_at IS NOT NULL;

        IF batch_work_order_status <> 'open' THEN
            RAISE EXCEPTION 'closed supplier-processing work order cannot accept QC results'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.source_flow_node_id <> batch_work_order_flow_node_id
            OR NEW.rework_source_batch_id IS NOT NULL
            OR submission_count <> 0
            OR moved_qualified <> 0
            OR moved_inventory <> 0
            OR moved_rework <> 0
            OR moved_scrap <> 0
            OR moved_lost <> 0 THEN
            RAISE EXCEPTION 'supplier-processing QC result cannot retain production movements or a rework source'
                USING ERRCODE = '23514';
        END IF;
        IF recorded_qualified_quantity + NEW.qualified_quantity
            > batch_work_order_quantity THEN
            RAISE EXCEPTION 'supplier-processing qualified quantity exceeds work order quantity'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;

    IF submission_count <> 1 OR submission_quantity <> NEW.submitted_quantity THEN
        RAISE EXCEPTION 'QC batch must retain one matching submission movement'
            USING ERRCODE = '23514';
    END IF;
    IF (
        moved_qualified,
        moved_inventory,
        moved_rework,
        moved_scrap,
        moved_lost
    ) IS DISTINCT FROM (
        0,
        0,
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

CREATE FUNCTION validate_qc_batch_destination_balance() RETURNS TRIGGER AS $$
DECLARE
    batch_work_order_type TEXT;
    batch_work_order_status TEXT;
    moved_qualified BIGINT;
    moved_inventory BIGINT;
    stored_inventory BIGINT;
BEGIN
    SELECT work_order_type, status
    INTO batch_work_order_type, batch_work_order_status
    FROM work_order
    WHERE id = NEW.work_order_id
    FOR UPDATE;

    IF batch_work_order_type = 'supplier_processing'
        AND (
            batch_work_order_status <> 'open'
            OR NEW.qualified_destination <> 'release'
        ) THEN
        RAISE EXCEPTION 'supplier-processing qualified material can only be released from an open work order'
            USING ERRCODE = '23514';
    END IF;

    SELECT
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'qc_qualified'), 0),
        COALESCE(SUM(quantity) FILTER (WHERE movement_type = 'qc_inventory'), 0)
    INTO moved_qualified, moved_inventory
    FROM production_movement
    WHERE work_order_batch_id = NEW.id;

    SELECT COALESCE(SUM(quantity), 0)
    INTO stored_inventory
    FROM warehouse_operation
    WHERE work_order_batch_id = NEW.id
      AND source_type = 'qc_inventory'
      AND status = 'succeeded';

    IF NEW.qualified_destination IN ('return', 'release') THEN
        IF moved_qualified <> NEW.qualified_quantity
            OR moved_inventory <> 0
            OR stored_inventory <> 0 THEN
            RAISE EXCEPTION 'QC production destination does not match its movement history'
                USING ERRCODE = '23514';
        END IF;
    ELSIF NEW.qualified_destination = 'inventory' THEN
        IF moved_qualified <> 0
            OR moved_inventory <> NEW.qualified_quantity
            OR stored_inventory <> NEW.qualified_quantity THEN
            RAISE EXCEPTION 'QC inventory destination does not match movement and warehouse history'
                USING ERRCODE = '23514';
        END IF;
    ELSE
        RAISE EXCEPTION 'QC qualified destination is invalid'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 委外工单进度只校验已放行合格数；实际流转和状态转换仍由后端负责。
CREATE FUNCTION assert_supplier_processing_release_progress(
    checked_work_order_id BIGINT,
    checked_quantity INT,
    checked_processed_quantity INT,
    checked_completed_quantity INT,
    checked_status TEXT
) RETURNS VOID AS $$
DECLARE
    released_quantity BIGINT;
BEGIN
    SELECT COALESCE(SUM(qualified_quantity), 0)
    INTO released_quantity
    FROM work_order_batch
    WHERE work_order_id = checked_work_order_id
      AND qualified_destination = 'release'
      AND destination_decided_at IS NOT NULL;

    IF checked_processed_quantity <> released_quantity
        OR checked_completed_quantity <> released_quantity
        OR released_quantity > checked_quantity
        OR (checked_status = 'open' AND released_quantity >= checked_quantity)
        OR (checked_status = 'closed' AND released_quantity <> checked_quantity)
        OR (checked_status = 'cancelled' AND released_quantity <> 0) THEN
        RAISE EXCEPTION 'supplier-processing work order progress must match released QC quantity'
            USING ERRCODE = '23514';
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_supplier_processing_work_order_progress() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.work_order_type = 'supplier_processing' THEN
        PERFORM assert_supplier_processing_release_progress(
            NEW.id,
            NEW.quantity,
            NEW.processed_quantity,
            NEW.completed_quantity,
            NEW.status
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_supplier_processing_batch_progress() RETURNS TRIGGER AS $$
DECLARE
    batch_work_order_type TEXT;
    batch_work_order_quantity INT;
    batch_work_order_processed_quantity INT;
    batch_work_order_completed_quantity INT;
    batch_work_order_status TEXT;
BEGIN
    SELECT
        work_order_type,
        quantity,
        processed_quantity,
        completed_quantity,
        status
    INTO
        batch_work_order_type,
        batch_work_order_quantity,
        batch_work_order_processed_quantity,
        batch_work_order_completed_quantity,
        batch_work_order_status
    FROM work_order
    WHERE id = NEW.work_order_id;

    IF batch_work_order_type = 'supplier_processing' THEN
        PERFORM assert_supplier_processing_release_progress(
            NEW.work_order_id,
            batch_work_order_quantity,
            batch_work_order_processed_quantity,
            batch_work_order_completed_quantity,
            batch_work_order_status
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_production_position_warehouse_operation() RETURNS TRIGGER AS $$
DECLARE
    moved_count INT;
    moved_quantity BIGINT;
BEGIN
    SELECT COUNT(*), COALESCE(SUM(quantity), 0)
    INTO moved_count, moved_quantity
    FROM production_movement
    WHERE warehouse_operation_id = NEW.id
      AND production_item_id = NEW.production_item_id
      AND movement_type = 'production_inventory';

    IF moved_count <> 1 OR moved_quantity <> NEW.quantity THEN
        RAISE EXCEPTION 'production-position warehouse operation must match one movement'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_production_inventory_movement() RETURNS TRIGGER AS $$
DECLARE
    matching_operation_count INT;
BEGIN
    SELECT COUNT(*)
    INTO matching_operation_count
    FROM warehouse_operation
    WHERE id = NEW.warehouse_operation_id
      AND source_type = 'production_position'
      AND status = 'succeeded'
      AND production_item_id = NEW.production_item_id
      AND quantity = NEW.quantity;

    IF matching_operation_count <> 1 THEN
        RAISE EXCEPTION 'production inventory movement must match its warehouse operation'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_production_movement_history() RETURNS TRIGGER AS $$
DECLARE
    undo_operation_id_text TEXT;
    qc_undo_batch_id_text TEXT;
    plan_unconfirm_order_id_text TEXT;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'production movement history is immutable'
            USING ERRCODE = '23514';
    END IF;
    qc_undo_batch_id_text := current_setting(
        'zzerp.qc_inspection_undo_batch_id',
        TRUE
    );
    IF qc_undo_batch_id_text IS NOT NULL
        AND qc_undo_batch_id_text ~ '^[0-9]+$'
        AND OLD.work_order_batch_id = qc_undo_batch_id_text::BIGINT
        AND OLD.movement_type IN ('qc_rework', 'scrap', 'lost')
        AND EXISTS (
            SELECT 1
            FROM work_order_batch AS qc_batch
            WHERE qc_batch.id = OLD.work_order_batch_id
              AND qc_batch.work_order_id = OLD.work_order_id
              AND qc_batch.recorded_at IS NOT NULL
              AND qc_batch.qualified_destination IS NULL
              AND qc_batch.destination_decided_at IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM work_order_batch AS child_batch
                  WHERE child_batch.work_order_id = qc_batch.work_order_id
                    AND child_batch.rework_source_batch_id = qc_batch.id
              )
        ) THEN
        RETURN OLD;
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
    plan_unconfirm_order_id_text := current_setting(
        'zzerp.plan_unconfirm_order_id',
        TRUE
    );
    IF plan_unconfirm_order_id_text IS NOT NULL
        AND plan_unconfirm_order_id_text ~ '^[0-9]+$'
        AND OLD.movement_type IN ('initial', 'inventory_issue')
        AND OLD.work_order_id IS NULL
        AND OLD.work_order_batch_id IS NULL
        AND EXISTS (
            SELECT 1
            FROM production_item AS plan_item
            JOIN customer_order_item AS order_item
              ON order_item.id = plan_item.customer_order_item_id
            WHERE plan_item.id = OLD.production_item_id
              AND order_item.customer_order_id
                    = plan_unconfirm_order_id_text::BIGINT
              AND NOT EXISTS (
                  SELECT 1 FROM work_order
                  WHERE work_order.production_item_id = plan_item.id
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

CREATE FUNCTION protect_append_only_history() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'append-only history cannot be modified'
        USING ERRCODE = '23514';
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_finished_receipt_history() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'finished receipt history cannot be deleted'
            USING ERRCODE = '23514';
    END IF;
    IF OLD.status = 'pending'
        AND NEW.status = 'received'
        AND NEW.received_at IS NOT NULL
        AND NEW.received_by IS NOT NULL
        AND NEW.revision = OLD.revision + 1
        AND (to_jsonb(NEW) - ARRAY[
            'status', 'received_at', 'received_by', 'revision'
        ]) = (to_jsonb(OLD) - ARRAY[
            'status', 'received_at', 'received_by', 'revision'
        ]) THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'pending'
        AND NEW.status = 'cancelled'
        AND NEW.corrected_at IS NOT NULL
        AND NEW.corrected_by IS NOT NULL
        AND NEW.revision = OLD.revision + 1
        AND (to_jsonb(NEW) - ARRAY[
            'status', 'corrected_at', 'corrected_by', 'correction_reason', 'revision'
        ]) = (to_jsonb(OLD) - ARRAY[
            'status', 'corrected_at', 'corrected_by', 'correction_reason', 'revision'
        ]) THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'received'
        AND NEW.status = 'reversed'
        AND NEW.corrected_at IS NOT NULL
        AND NEW.corrected_by IS NOT NULL
        AND NEW.revision = OLD.revision + 1
        AND (to_jsonb(NEW) - ARRAY[
            'status', 'corrected_at', 'corrected_by', 'correction_reason', 'revision'
        ]) = (to_jsonb(OLD) - ARRAY[
            'status', 'corrected_at', 'corrected_by', 'correction_reason', 'revision'
        ]) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'finished receipt only supports one complete receipt transition'
        USING ERRCODE = '23514';
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_finished_stock_reservation_history() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'finished stock reservation history cannot be deleted'
            USING ERRCODE = '23514';
    END IF;
    IF current_setting(
        'zzerp.finished_shipment_reversal_reservation_id', true
    ) = OLD.id::TEXT
        AND NEW.shipped_quantity <= OLD.shipped_quantity
        AND NEW.released_quantity <= OLD.released_quantity
        AND (to_jsonb(NEW) - ARRAY[
            'shipped_quantity', 'released_quantity', 'updated_at'
        ]) = (to_jsonb(OLD) - ARRAY[
            'shipped_quantity', 'released_quantity', 'updated_at'
        ]) THEN
        RETURN NEW;
    END IF;
    IF (
        NEW.finished_stock_id,
        NEW.production_plan_id,
        NEW.production_plan_item_id,
        NEW.customer_order_item_id,
        NEW.reserved_quantity,
        NEW.created_at
    ) IS DISTINCT FROM (
        OLD.finished_stock_id,
        OLD.production_plan_id,
        OLD.production_plan_item_id,
        OLD.customer_order_item_id,
        OLD.reserved_quantity,
        OLD.created_at
    ) OR NEW.shipped_quantity < OLD.shipped_quantity
        OR NEW.released_quantity < OLD.released_quantity THEN
        RAISE EXCEPTION 'finished stock reservation identity and history are immutable'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_warehouse_operation_history() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'warehouse operation history cannot be deleted'
            USING ERRCODE = '23514';
    END IF;
    IF OLD.status = 'pending' THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'uncertain'
        AND OLD.manual_reviewed_at IS NULL
        AND (to_jsonb(NEW) - ARRAY[
            'manual_reviewed_at', 'manual_reviewed_by', 'manual_review_note'
        ]) = (to_jsonb(OLD) - ARRAY[
            'manual_reviewed_at', 'manual_reviewed_by', 'manual_review_note'
        ]) THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'completed warehouse operation history is immutable'
        USING ERRCODE = '23514';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_qc_submission_movement_quantity
BEFORE INSERT ON production_movement
FOR EACH ROW
WHEN (
    NEW.work_order_batch_id IS NOT NULL
    AND NEW.movement_type IN ('process', 'assembly_output')
)
EXECUTE FUNCTION validate_qc_submission_movement_quantity();

CREATE TRIGGER trg_assembly_material_movement_quantity
BEFORE INSERT ON production_movement
FOR EACH ROW
WHEN (NEW.movement_type IN ('assembly_input', 'assembly_input_restore'))
EXECUTE FUNCTION validate_assembly_material_movement_quantity();

CREATE CONSTRAINT TRIGGER trg_production_position_warehouse_balance
AFTER INSERT OR UPDATE ON warehouse_operation
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
WHEN (
    NEW.source_type = 'production_position'
    AND NEW.status = 'succeeded'
)
EXECUTE FUNCTION validate_production_position_warehouse_operation();

CREATE CONSTRAINT TRIGGER trg_production_inventory_movement_balance
AFTER INSERT ON production_movement
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
WHEN (NEW.movement_type = 'production_inventory')
EXECUTE FUNCTION validate_production_inventory_movement();

CREATE TRIGGER trg_work_order_closure
BEFORE UPDATE OF status
ON work_order
FOR EACH ROW
WHEN (NEW.status = 'closed' AND OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION protect_work_order_closure();

CREATE TRIGGER trg_work_order_movement_items
BEFORE UPDATE OF production_item_id, procedure_id, work_order_type, is_temporary, work_order_name,
    supplier_name, supplier_process_name, remark, flow_node_id, source_flow_node_id
ON work_order
FOR EACH ROW EXECUTE FUNCTION validate_work_order_movement_items();

CREATE TRIGGER trg_supplier_processing_work_order_progress_insert
BEFORE INSERT ON work_order
FOR EACH ROW EXECUTE FUNCTION validate_supplier_processing_work_order_progress();

CREATE TRIGGER trg_supplier_processing_work_order_progress_update
BEFORE UPDATE OF work_order_type, quantity, processed_quantity, completed_quantity, status
ON work_order
FOR EACH ROW EXECUTE FUNCTION validate_supplier_processing_work_order_progress();

CREATE TRIGGER trg_rework_submission_quantity
BEFORE INSERT ON work_order_batch
FOR EACH ROW
WHEN (NEW.rework_source_batch_id IS NOT NULL)
EXECUTE FUNCTION protect_rework_submission_quantity();

CREATE TRIGGER trg_qc_batch_history
BEFORE UPDATE ON work_order_batch
FOR EACH ROW EXECUTE FUNCTION protect_qc_batch_history();

CREATE TRIGGER trg_qc_batch_insert_result_balance
BEFORE INSERT ON work_order_batch
FOR EACH ROW
WHEN (NEW.recorded_at IS NOT NULL)
EXECUTE FUNCTION validate_qc_batch_result_balance();

CREATE TRIGGER trg_qc_batch_insert_destination_balance
BEFORE INSERT ON work_order_batch
FOR EACH ROW
WHEN (NEW.qualified_destination IS NOT NULL)
EXECUTE FUNCTION validate_qc_batch_destination_balance();

CREATE TRIGGER trg_qc_batch_result_balance
BEFORE UPDATE OF recorded_at, qualified_quantity, rework_quantity,
    scrap_quantity, lost_quantity
ON work_order_batch
FOR EACH ROW
WHEN (NEW.recorded_at IS NOT NULL AND OLD.recorded_at IS NULL)
EXECUTE FUNCTION validate_qc_batch_result_balance();

CREATE TRIGGER trg_qc_batch_destination_balance
BEFORE UPDATE OF qualified_destination, destination_decided_at, destination_decided_by
ON work_order_batch
FOR EACH ROW
WHEN (NEW.qualified_destination IS NOT NULL AND OLD.qualified_destination IS NULL)
EXECUTE FUNCTION validate_qc_batch_destination_balance();

CREATE CONSTRAINT TRIGGER trg_supplier_processing_batch_progress
AFTER UPDATE ON work_order_batch
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
WHEN (NEW.qualified_destination IS NOT NULL AND OLD.qualified_destination IS NULL)
EXECUTE FUNCTION validate_supplier_processing_batch_progress();

CREATE TRIGGER trg_assembly_material_movement_update
BEFORE UPDATE OF work_order_id, production_item_id, quantity ON work_order_material
FOR EACH ROW EXECUTE FUNCTION protect_assembly_material_movement_context();

CREATE TRIGGER trg_assembly_material_movement_delete
BEFORE DELETE ON work_order_material
FOR EACH ROW EXECUTE FUNCTION protect_assembly_material_movement_context();

CREATE TRIGGER trg_production_movement_history
BEFORE UPDATE OR DELETE ON production_movement
FOR EACH ROW EXECUTE FUNCTION protect_production_movement_history();

CREATE TRIGGER trg_material_processing_state_history
BEFORE UPDATE OR DELETE ON material_processing_state
FOR EACH ROW EXECUTE FUNCTION protect_append_only_history();

CREATE TRIGGER trg_warehouse_operation_history
BEFORE UPDATE OR DELETE ON warehouse_operation
FOR EACH ROW EXECUTE FUNCTION protect_warehouse_operation_history();

CREATE TRIGGER trg_finished_receipt_history
BEFORE UPDATE OR DELETE ON finished_receipt
FOR EACH ROW EXECUTE FUNCTION protect_finished_receipt_history();

CREATE TRIGGER trg_finished_stock_reservation_history
BEFORE UPDATE OR DELETE ON finished_stock_reservation
FOR EACH ROW EXECUTE FUNCTION protect_finished_stock_reservation_history();

CREATE TRIGGER trg_finished_stock_transaction_history
BEFORE UPDATE OR DELETE ON finished_stock_transaction
FOR EACH ROW EXECUTE FUNCTION protect_inventory_transaction_history();

CREATE TRIGGER trg_procedure_price_revision_history
BEFORE UPDATE OR DELETE ON procedure_price_revision
FOR EACH ROW EXECUTE FUNCTION protect_append_only_history();

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

CREATE TRIGGER trg_procedure_configuration_updated_at
BEFORE UPDATE ON procedure_configuration
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_procedure_configuration_protection
BEFORE UPDATE ON procedure_configuration
FOR EACH ROW EXECUTE FUNCTION protect_procedure_configuration();

CREATE TRIGGER trg_procedure_price_membership_protection
BEFORE INSERT OR UPDATE OR DELETE ON procedure_price
FOR EACH ROW EXECUTE FUNCTION protect_confirmed_procedure_membership();

CREATE TRIGGER trg_procedure_price_updated_at
BEFORE UPDATE ON procedure_price
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_customer_order_updated_at
BEFORE UPDATE ON customer_order
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_production_plan_updated_at
BEFORE UPDATE ON production_plan
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_finished_stock_updated_at
BEFORE UPDATE ON finished_stock
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_finished_stock_reservation_updated_at
BEFORE UPDATE ON finished_stock_reservation
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
        department_id, product_id, product_version, origin_flow_node_id, route_order
    );
CREATE INDEX idx_product_route_task_workshop
    ON product_route_task(workshop_id, product_id, product_version);
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
CREATE INDEX idx_production_route_task_department
    ON production_route_task(
        department_id, production_plan_id, production_plan_item_id
    );
CREATE INDEX idx_warehouse_stock_allocation
    ON warehouse_stock(
        item_code, product_version, item_type, warehouse_code,
        completion_status, last_inbound_date, id
    ) WHERE quantity > 0;
CREATE INDEX idx_warehouse_operation_group
    ON warehouse_operation(operation_group_no, id);
CREATE INDEX idx_warehouse_operation_recent
    ON warehouse_operation(created_at, id);
CREATE INDEX idx_warehouse_operation_status
    ON warehouse_operation(status, created_at, id);
CREATE INDEX idx_warehouse_operation_plan
    ON warehouse_operation(production_plan_id, production_plan_item_id, id);
CREATE INDEX idx_warehouse_operation_work_order
    ON warehouse_operation(work_order_id, work_order_batch_id);
CREATE INDEX idx_warehouse_operation_production_item
    ON warehouse_operation(production_item_id, id);
CREATE INDEX idx_warehouse_operation_processing_state
    ON warehouse_operation(processing_state_id, id);
CREATE INDEX idx_warehouse_operation_stock
    ON warehouse_operation(warehouse_stock_id, id);
CREATE INDEX idx_finished_receipt_pending
ON finished_receipt(status, created_at, id)
    WHERE status = 'pending';
CREATE UNIQUE INDEX uq_finished_receipt_active_qc_batch
    ON finished_receipt(work_order_batch_id)
    WHERE work_order_batch_id IS NOT NULL AND status IN ('pending', 'received');
CREATE UNIQUE INDEX uq_finished_receipt_active_packaging_order
    ON finished_receipt(work_order_id)
    WHERE work_order_id IS NOT NULL AND status IN ('pending', 'received');

CREATE UNIQUE INDEX uq_finished_stock_transaction_receipt
ON finished_stock_transaction(finished_receipt_id)
WHERE transaction_type = 'receipt';
CREATE INDEX idx_finished_stock_reservation_plan
    ON finished_stock_reservation(production_plan_id, production_plan_item_id, id);
CREATE INDEX idx_finished_stock_reservation_order_open
    ON finished_stock_reservation(customer_order_item_id, id)
    WHERE shipped_quantity + released_quantity < reserved_quantity;
CREATE INDEX idx_finished_stock_reservation_recent
    ON finished_stock_reservation(created_at DESC, id DESC);
CREATE INDEX idx_finished_stock_transaction_stock
    ON finished_stock_transaction(finished_stock_id, created_at, id);
CREATE INDEX idx_finished_stock_transaction_order
    ON finished_stock_transaction(customer_order_item_id, created_at, id)
    WHERE customer_order_item_id IS NOT NULL;
CREATE INDEX idx_finished_stock_transaction_recent
    ON finished_stock_transaction(created_at DESC, id DESC);
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
      AND movement_type IN ('process', 'assembly_output');
CREATE UNIQUE INDEX uq_production_movement_assembly_input
    ON production_movement(work_order_material_id)
    WHERE movement_type = 'assembly_input';
CREATE INDEX idx_production_movement_assembly_material
    ON production_movement(work_order_material_id)
    WHERE work_order_material_id IS NOT NULL;
CREATE INDEX idx_repository_department ON repository(department_id);
CREATE INDEX idx_repository_processing_state ON repository(processing_state_id);
CREATE INDEX idx_production_warehouse_storage_line_state
    ON production_warehouse_storage_line(processing_state_id);
CREATE UNIQUE INDEX uq_repository_initial_position
    ON repository(
        production_item_id,
        flow_node_id,
        source_flow_node_id,
        department_id,
        processing_state_id
    )
    WHERE source_work_order_id IS NULL;
CREATE UNIQUE INDEX uq_repository_work_order_output
    ON repository(source_work_order_id, production_item_id, flow_node_id, processing_state_id)
    WHERE source_work_order_id IS NOT NULL;
CREATE INDEX idx_procedure_price_scope
    ON procedure_price(procedure_id, configuration_id);
CREATE INDEX idx_production_item_order_item ON production_item(customer_order_item_id);
CREATE INDEX idx_production_item_bom ON production_item(product_bom_id);
CREATE UNIQUE INDEX uq_production_item_part_origin
    ON production_item(customer_order_item_id, product_bom_id, origin_flow_node_id)
    WHERE product_bom_id IS NOT NULL;
CREATE INDEX idx_work_order_repository ON work_order(repository_id);
CREATE INDEX idx_work_order_source_processing_state ON work_order(source_processing_state_id);
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
CREATE INDEX idx_work_order_open_workbench
    ON work_order(
        work_order_type,
        procedure_id,
        production_item_id,
        flow_node_id,
        source_flow_node_id
    )
    WHERE status = 'open';
CREATE UNIQUE INDEX uq_work_order_supplier_task
ON work_order(production_item_id, flow_node_id)
WHERE work_order_type = 'supplier_processing' AND status <> 'cancelled';
CREATE INDEX idx_work_order_process_position
    ON work_order(production_item_id, flow_node_id, procedure_id, id DESC);
CREATE INDEX idx_work_order_pay_detail_procedure
    ON work_order_pay_detail(procedure_id, work_order_id);
CREATE INDEX idx_work_order_batch_order ON work_order_batch(work_order_id);
CREATE INDEX idx_work_order_batch_rework_source
    ON work_order_batch(rework_source_batch_id);
CREATE INDEX idx_work_order_material_repository ON work_order_material(repository_id);
CREATE INDEX idx_work_order_material_production_item ON work_order_material(production_item_id);
CREATE INDEX idx_work_order_material_open_occupancy
    ON work_order_material(source_department_id, work_order_id)
    WHERE repository_id IS NULL;
CREATE INDEX idx_work_order_batch_pending ON work_order_batch(id DESC, work_order_id)
    WHERE recorded_at IS NULL
        OR (qualified_quantity > 0 AND destination_decided_at IS NULL);
CREATE INDEX idx_work_order_batch_history ON work_order_batch(id DESC)
    WHERE recorded_at IS NOT NULL;
CREATE INDEX idx_work_order_batch_qc_worker_recorded
    ON work_order_batch(qc_worker_id, recorded_at DESC);
CREATE UNIQUE INDEX uq_production_movement_batch_qualified_destination
    ON production_movement(work_order_batch_id)
    WHERE work_order_batch_id IS NOT NULL
      AND movement_type IN ('qc_qualified', 'qc_inventory');
CREATE UNIQUE INDEX uq_production_movement_warehouse_operation
    ON production_movement(warehouse_operation_id)
    WHERE warehouse_operation_id IS NOT NULL;
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
('冲压部', 'stamp'),
('机加部', 'cnc'),
('表面处理部', 'polish'),
('外协部', 'outsource'),
('QC部门', 'qc'),
('装配部', 'assembly'),
('成品部', 'finished'),
('仓库', 'warehouse');

INSERT INTO users (
    username, password, department, is_system, role, permissions
) VALUES
(
    'engineering',
    '1',
    'engineering',
    FALSE,
    'engineer',
    'engineering:product:view,engineering:product:add,engineering:product:edit'
),
(
    'business',
    '1',
    'business',
    FALSE,
    'sales',
    'engineering:product:view,order:view,order:add,order:edit,order:confirm,order:cancel,supplier_processing:view,supplier_processing:create'
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

INSERT INTO workshop (department_id, workshop_name, input_mode)
SELECT department.id, source.workshop_name, source.input_mode
FROM (
    VALUES
        ('stamp', '激光开料车间', 'single'),
        ('stamp', '热锻车间', 'single'),
        ('stamp', '冷锻车间', 'single'),
        ('stamp', '冲床车间', 'single'),
        ('stamp', '回火车间', 'single'),
        ('stamp', '除油车间', 'single'),
        ('stamp', '水磨车间', 'single'),
        ('stamp', '溜磨车间', 'single'),
        ('cnc', 'CNC车间', 'single'),
        ('cnc', 'NC车间', 'single'),
        ('cnc', '钻床车间', 'single'),
        ('cnc', '激光焊接车间', 'single'),
        ('polish', '手磨车间', 'single'),
        ('polish', '砂机车间', 'single'),
        ('polish', '自动平磨车间', 'single'),
        ('polish', '双面水磨车间', 'single'),
        ('polish', '酸洗车间', 'single'),
        ('polish', '电抛车间', 'single'),
        ('polish', '振机车间', 'single'),
        ('polish', '干滚车间', 'single'),
        ('polish', '清光车间', 'single'),
        ('outsource', '蚀字外协', 'single'),
        ('outsource', '电镀外协', 'single'),
        ('assembly', '装配车间', 'multiple'),
        ('assembly', '焊接车间', 'multiple'),
        ('assembly', '装包车间', 'single')
) AS source(department_code, workshop_name, input_mode)
JOIN department
    ON department.department_code = source.department_code;

INSERT INTO procedure (workshop_id, procedure_name)
SELECT workshop.id, source.procedure_name
FROM (
    VALUES
        ('stamp', '激光开料车间', '激光开料'),
        ('stamp', '热锻车间', '热压1'),
        ('stamp', '热锻车间', '热压2'),
        ('stamp', '热锻车间', '热压3'),
        ('stamp', '冷锻车间', '冷锻'),
        ('stamp', '冲床车间', '冲压'),
        ('stamp', '回火车间', '回火'),
        ('stamp', '除油车间', '除油'),
        ('stamp', '水磨车间', '水磨'),
        ('stamp', '溜磨车间', '溜磨'),
        ('cnc', 'CNC车间', 'CNC加工'),
        ('cnc', 'NC车间', 'NC加工'),
        ('cnc', '钻床车间', '钻孔'),
        ('cnc', '激光焊接车间', '激光焊接'),
        ('polish', '手磨车间', '粗1'),
        ('polish', '手磨车间', '粗2'),
        ('polish', '手磨车间', '粗3'),
        ('polish', '砂机车间', '砂机'),
        ('polish', '自动平磨车间', '自动平磨'),
        ('polish', '双面水磨车间', '双面水磨'),
        ('polish', '酸洗车间', '酸洗'),
        ('polish', '电抛车间', '电抛'),
        ('polish', '振机车间', '振机'),
        ('polish', '干滚车间', '干滚'),
        ('polish', '清光车间', '清光'),
        ('outsource', '蚀字外协', '蚀字'),
        ('outsource', '电镀外协', '电镀'),
        ('assembly', '装配车间', '装配'),
        ('assembly', '焊接车间', '焊接'),
        ('assembly', '装包车间', '装包')
) AS source(department_code, workshop_name, procedure_name)
JOIN department
    ON department.department_code = source.department_code
JOIN workshop
    ON workshop.department_id = department.id
    AND workshop.workshop_name = source.workshop_name;

-- 默认业务人员与外协单位。
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

-- ------------------------------------------------------------
-- 可删除的开发业务数据：客户、产品、版本、BOM、流程图与订单
-- ------------------------------------------------------------

INSERT INTO customer (customer_name) VALUES ('Celine');

INSERT INTO product (
    customer_id, product_name, factory_code, customer_code, version
)
SELECT customer.id, 'CH-L43 双C锁扣', 'Z8735', 'Z8735', 1
FROM customer
WHERE customer.customer_name = 'Celine';

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
    '{"schema_version": 5, "nodes": [], "edges": []}'::jsonb
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
    '{"schema_version": 5, "nodes": [], "edges": []}'::jsonb
FROM product
WHERE product.factory_code IN ('Z8737', 'Z8739', 'Z8740', 'Z8711', 'Z8609');

-- Z8711 D10 磁力包扣正式流程：
-- logo件 → 激光开料 → QC ┐
--                         装配 → QC → 装包 → 入库
-- 脚钉（外购）→ 委外加工 → QC ┘
UPDATE product_process_flow AS process_flow
SET
    flow_json = jsonb_build_object(
        'schema_version', 5,
        'nodes', jsonb_build_array(
            jsonb_build_object(
                'id', 'z8711-part-logo',
                'type', 'part',
                'x', 0,
                'y', 0,
                'label', logo_part.part_name,
                'bom_item_id', logo_part.id,
                'part_no', logo_part.part_no
            ),
            jsonb_build_object(
                'id', 'z8711-process-laser',
                'type', 'process',
                'x', 500,
                'y', 0,
                'label', laser_workshop.workshop_name,
                'workshop_id', laser_workshop.id
            ),
            jsonb_build_object(
                'id', 'z8711-qc-logo',
                'type', 'qc',
                'x', 1000,
                'y', 0,
                'label', 'QC'
            ),
            jsonb_build_object(
                'id', 'z8711-part-outsourced-stud',
                'type', 'part',
                'x', 0,
                'y', 500,
                'label', stud_part.part_name,
                'bom_item_id', stud_part.id,
                'part_no', stud_part.part_no
            ),
            jsonb_build_object(
                'id', 'z8711-supplier-processing',
                'type', 'supplier_processing',
                'x', 500,
                'y', 500,
                'label', '委外加工'
            ),
            jsonb_build_object(
                'id', 'z8711-qc-outsourced-stud',
                'type', 'qc',
                'x', 1000,
                'y', 500,
                'label', 'QC'
            ),
            jsonb_build_object(
                'id', 'z8711-assembly-81',
                'type', 'assembly',
                'x', 1500,
                'y', 250,
                'label', assembly_workshop.workshop_name,
                'workshop_id', assembly_workshop.id,
                'output_name', 'logo件-脚钉（外购）装配体',
                'output_pcs', 1,
                'assembly_sequence', 81,
                'assembly_code', 'Z8711-81',
                'assembly_name', 'logo件-脚钉（外购）装配体'
            ),
            jsonb_build_object(
                'id', 'z8711-qc-assembly',
                'type', 'qc',
                'x', 2000,
                'y', 250,
                'label', 'QC'
            ),
            jsonb_build_object(
                'id', 'z8711-process-packaging',
                'type', 'process',
                'x', 2500,
                'y', 250,
                'label', packaging_workshop.workshop_name,
                'workshop_id', packaging_workshop.id
            ),
            jsonb_build_object(
                'id', 'z8711-finished-inbound',
                'type', 'finished_inbound',
                'x', 3000,
                'y', 250,
                'label', '入库'
            )
        ),
        'edges', jsonb_build_array(
            jsonb_build_object(
                'id', 'z8711-edge-logo-laser',
                'edge_type', 'polyline',
                'source_node_id', 'z8711-part-logo',
                'target_node_id', 'z8711-process-laser'
            ),
            jsonb_build_object(
                'id', 'z8711-edge-laser-qc',
                'edge_type', 'polyline',
                'source_node_id', 'z8711-process-laser',
                'target_node_id', 'z8711-qc-logo'
            ),
            jsonb_build_object(
                'id', 'z8711-edge-logo-qc-assembly',
                'edge_type', 'polyline',
                'source_node_id', 'z8711-qc-logo',
                'target_node_id', 'z8711-assembly-81'
            ),
            jsonb_build_object(
                'id', 'z8711-edge-stud-supplier',
                'edge_type', 'polyline',
                'source_node_id', 'z8711-part-outsourced-stud',
                'target_node_id', 'z8711-supplier-processing'
            ),
            jsonb_build_object(
                'id', 'z8711-edge-supplier-qc',
                'edge_type', 'polyline',
                'source_node_id', 'z8711-supplier-processing',
                'target_node_id', 'z8711-qc-outsourced-stud'
            ),
            jsonb_build_object(
                'id', 'z8711-edge-stud-qc-assembly',
                'edge_type', 'polyline',
                'source_node_id', 'z8711-qc-outsourced-stud',
                'target_node_id', 'z8711-assembly-81'
            ),
            jsonb_build_object(
                'id', 'z8711-edge-assembly-qc',
                'edge_type', 'polyline',
                'source_node_id', 'z8711-assembly-81',
                'target_node_id', 'z8711-qc-assembly'
            ),
            jsonb_build_object(
                'id', 'z8711-edge-assembly-qc-packaging',
                'edge_type', 'polyline',
                'source_node_id', 'z8711-qc-assembly',
                'target_node_id', 'z8711-process-packaging'
            ),
            jsonb_build_object(
                'id', 'z8711-edge-packaging-inbound',
                'edge_type', 'polyline',
                'source_node_id', 'z8711-process-packaging',
                'target_node_id', 'z8711-finished-inbound'
            )
        )
    ),
    draft_flow_json = NULL,
    updated_at = CURRENT_TIMESTAMP
FROM product
JOIN product_bom AS logo_part
    ON logo_part.product_id = product.id
    AND logo_part.product_version = 1
    AND logo_part.part_no = 'Z8711-01'
JOIN product_bom AS stud_part
    ON stud_part.product_id = product.id
    AND stud_part.product_version = 1
    AND stud_part.part_no = 'Z8711-02'
JOIN department AS stamp_department
    ON stamp_department.department_code = 'stamp'
JOIN workshop AS laser_workshop
    ON laser_workshop.department_id = stamp_department.id
    AND laser_workshop.workshop_name = '激光开料车间'
JOIN department AS assembly_department
    ON assembly_department.department_code = 'assembly'
JOIN workshop AS assembly_workshop
    ON assembly_workshop.department_id = assembly_department.id
    AND assembly_workshop.workshop_name = '装配车间'
JOIN workshop AS packaging_workshop
    ON packaging_workshop.department_id = assembly_department.id
    AND packaging_workshop.workshop_name = '装包车间'
WHERE process_flow.product_id = product.id
    AND process_flow.product_version = 1
    AND product.factory_code = 'Z8711';

UPDATE product
SET revision = revision + 1,
    updated_at = CURRENT_TIMESTAMP
WHERE factory_code = 'Z8711';

-- 正式流程的部门任务投影，与工程部保存流程时生成的口径一致。
INSERT INTO product_route_task (
    product_id,
    product_version,
    product_bom_id,
    origin_flow_node_id,
    origin_node_type,
    origin_item_code,
    origin_item_name,
    route_flow_node_id,
    route_node_type,
    workshop_id,
    department_id,
    route_order
)
SELECT
    product.id,
    1,
    bom.id,
    route.origin_flow_node_id,
    'part',
    bom.part_no,
    bom.part_name,
    route.route_flow_node_id,
    route.route_node_type,
    workshop.id,
    department.id,
    route.route_order
FROM product
JOIN (
    VALUES
        ('Z8711-01', 'z8711-part-logo', 'z8711-process-laser',
            'process', 'stamp', '激光开料车间', 0),
        ('Z8711-01', 'z8711-part-logo', 'z8711-assembly-81',
            'assembly', 'assembly', '装配车间', 2),
        ('Z8711-02', 'z8711-part-outsourced-stud', 'z8711-supplier-processing',
            'supplier_processing', 'business', NULL, 0),
        ('Z8711-02', 'z8711-part-outsourced-stud', 'z8711-assembly-81',
            'assembly', 'assembly', '装配车间', 2)
) AS route(
    part_no,
    origin_flow_node_id,
    route_flow_node_id,
    route_node_type,
    department_code,
    workshop_name,
    route_order
) ON TRUE
JOIN product_bom AS bom
    ON bom.product_id = product.id
    AND bom.product_version = 1
    AND bom.part_no = route.part_no
JOIN department
    ON department.department_code = route.department_code
LEFT JOIN workshop
    ON workshop.department_id = department.id
    AND workshop.workshop_name = route.workshop_name
WHERE product.factory_code = 'Z8711';

INSERT INTO product_route_task (
    product_id,
    product_version,
    product_bom_id,
    origin_flow_node_id,
    origin_node_type,
    origin_item_code,
    origin_item_name,
    route_flow_node_id,
    route_node_type,
    workshop_id,
    department_id,
    route_order
)
SELECT
    product.id,
    1,
    NULL,
    'z8711-assembly-81',
    'assembly',
    'Z8711-81',
    'logo件-脚钉（外购）装配体',
    route.route_flow_node_id,
    route.route_node_type,
    workshop.id,
    department.id,
    route.route_order
FROM product
JOIN (
    VALUES
        ('z8711-assembly-81', 'assembly', '装配车间', 0),
        ('z8711-process-packaging', 'process', '装包车间', 2)
) AS route(
    route_flow_node_id,
    route_node_type,
    workshop_name,
    route_order
) ON TRUE
JOIN department
    ON department.department_code = 'assembly'
JOIN workshop
    ON workshop.department_id = department.id
    AND workshop.workshop_name = route.workshop_name
WHERE product.factory_code = 'Z8711';

-- 磁力包扣示例订单：客户需求 15 件；生产计划按 20 件确认并开始生产。
INSERT INTO customer_order (
    customer_order_no,
    customer_id,
    status,
    revision,
    remark
)
SELECT
    'ORDER-Z8711-0001',
    customer.id,
    'planned',
    3,
    'D10 磁力包扣流程示例'
FROM customer
WHERE customer.customer_name = 'Celine';

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
    15,
    DATE '2026-09-30',
    NULL
FROM customer_order
JOIN product
    ON product.factory_code = 'Z8711'
WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001';

INSERT INTO production_plan (
    customer_order_id,
    status,
    revision,
    confirmed_at,
    confirmed_by
)
SELECT
    customer_order.id,
    'confirmed',
    3,
    CURRENT_TIMESTAMP,
    'business'
FROM customer_order
WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001';

INSERT INTO production_plan_item (
    production_plan_id,
    customer_order_id,
    customer_order_item_id,
    identity_key,
    item_type,
    product_id,
    product_version,
    product_bom_id,
    flow_node_id,
    item_code,
    item_name,
    unit_requirement,
    gross_required_quantity,
    estimated_inventory_quantity,
    net_required_quantity,
    planned_production_quantity,
    allocated_inventory_quantity,
    sort_order
)
SELECT
    production_plan.id,
    customer_order.id,
    customer_order_item.id,
    'finished:finished_product:' || product.id || ':1:-:z8711-finished-inbound',
    'finished_product',
    product.id,
    1,
    NULL,
    'z8711-finished-inbound',
    product.factory_code,
    product.product_name,
    1,
    15,
    0,
    15,
    15,
    0,
    0
FROM customer_order
JOIN customer_order_item
    ON customer_order_item.customer_order_id = customer_order.id
JOIN product
    ON product.id = customer_order_item.product_id
JOIN production_plan
    ON production_plan.customer_order_id = customer_order.id
WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001';

INSERT INTO production_plan_item (
    production_plan_id,
    customer_order_id,
    customer_order_item_id,
    identity_key,
    item_type,
    product_id,
    product_version,
    product_bom_id,
    flow_node_id,
    item_code,
    item_name,
    unit_requirement,
    gross_required_quantity,
    estimated_inventory_quantity,
    net_required_quantity,
    planned_production_quantity,
    allocated_inventory_quantity,
    sort_order
)
SELECT
    production_plan.id,
    customer_order.id,
    customer_order_item.id,
    'warehouse:assembly:' || product.id || ':1:-:z8711-assembly-81',
    'assembly',
    product.id,
    1,
    NULL,
    'z8711-assembly-81',
    'Z8711-81',
    'logo件-脚钉（外购）装配体',
    1,
    15,
    0,
    15,
    20,
    0,
    1
FROM customer_order
JOIN customer_order_item
    ON customer_order_item.customer_order_id = customer_order.id
JOIN product
    ON product.id = customer_order_item.product_id
JOIN production_plan
    ON production_plan.customer_order_id = customer_order.id
WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001';

INSERT INTO production_plan_item (
    production_plan_id,
    customer_order_id,
    customer_order_item_id,
    identity_key,
    item_type,
    product_id,
    product_version,
    product_bom_id,
    flow_node_id,
    item_code,
    item_name,
    unit_requirement,
    gross_required_quantity,
    estimated_inventory_quantity,
    net_required_quantity,
    planned_production_quantity,
    allocated_inventory_quantity,
    sort_order
)
SELECT
    production_plan.id,
    customer_order.id,
    customer_order_item.id,
    'warehouse:part:' || product.id || ':1:' || bom.id || ':' || part.flow_node_id,
    'part',
    product.id,
    1,
    bom.id,
    part.flow_node_id,
    bom.part_no,
    bom.part_name,
    bom.pcs,
    15 * bom.pcs,
    0,
    15 * bom.pcs,
    20 * bom.pcs,
    0,
    1000 + bom.sort_order * 10
FROM customer_order
JOIN customer_order_item
    ON customer_order_item.customer_order_id = customer_order.id
JOIN product
    ON product.id = customer_order_item.product_id
JOIN product_bom AS bom
    ON bom.product_id = product.id
    AND bom.product_version = customer_order_item.product_version
JOIN (
    VALUES
        ('Z8711-01', 'z8711-part-logo'),
        ('Z8711-02', 'z8711-part-outsourced-stud')
) AS part(part_no, flow_node_id)
    ON part.part_no = bom.part_no
JOIN production_plan
    ON production_plan.customer_order_id = customer_order.id
WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001';

-- 草稿计划的部门路线投影；计划确认时后端会按同一正式流程重新生成。
INSERT INTO production_route_task (
    production_plan_id,
    production_plan_item_id,
    route_flow_node_id,
    route_node_type,
    workshop_id,
    department_id,
    route_order
)
SELECT
    production_plan.id,
    plan_item.id,
    route.route_flow_node_id,
    route.route_node_type,
    workshop.id,
    department.id,
    route.route_order
FROM customer_order
JOIN production_plan
    ON production_plan.customer_order_id = customer_order.id
JOIN production_plan_item AS plan_item
    ON plan_item.production_plan_id = production_plan.id
JOIN (
    VALUES
        ('z8711-part-logo', 'z8711-process-laser',
            'process', 'stamp', '激光开料车间', 0),
        ('z8711-part-logo', 'z8711-assembly-81',
            'assembly', 'assembly', '装配车间', 2),
        ('z8711-part-outsourced-stud', 'z8711-supplier-processing',
            'supplier_processing', 'business', NULL, 0),
        ('z8711-part-outsourced-stud', 'z8711-assembly-81',
            'assembly', 'assembly', '装配车间', 2),
        ('z8711-assembly-81', 'z8711-assembly-81',
            'assembly', 'assembly', '装配车间', 0),
        ('z8711-assembly-81', 'z8711-process-packaging',
            'process', 'assembly', '装包车间', 2)
) AS route(
    origin_flow_node_id,
    route_flow_node_id,
    route_node_type,
    department_code,
    workshop_name,
    route_order
) ON route.origin_flow_node_id = plan_item.flow_node_id
JOIN department
    ON department.department_code = route.department_code
LEFT JOIN workshop
    ON workshop.department_id = department.id
    AND workshop.workshop_name = route.workshop_name
WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001';

-- 计划确认后的生产物料。外购脚钉由业务部后续创建唯一委外工单，
-- 因此只创建生产对象；logo件同时进入激光开料节点。
INSERT INTO material_processing_state (
    product_id,
    product_version,
    item_type,
    product_bom_id,
    origin_flow_node_id,
    completed_flow_node_id,
    resume_flow_node_id,
    procedure_history,
    qc_status,
    display_text,
    state_signature
)
SELECT
    product.id,
    1,
    'part',
    bom.id,
    'z8711-part-logo',
    'z8711-part-logo',
    'z8711-process-laser',
    '[]'::jsonb,
    'none',
    '未加工 · 待激光开料车间',
    encode(
        digest(
            '{"completed_flow_node_id":"z8711-part-logo",'
            || '"item_type":"part",'
            || '"origin_flow_node_id":"z8711-part-logo",'
            || '"procedure_history":[],"product_bom_id":'
            || bom.id::text
            || ',"product_id":'
            || product.id::text
            || ',"product_version":1,"qc_status":"none",'
            || '"resume_flow_node_id":"z8711-process-laser"}',
            'sha256'
        ),
        'hex'
    )
FROM product
JOIN product_bom AS bom
    ON bom.product_id = product.id
    AND bom.product_version = 1
    AND bom.part_no = 'Z8711-01'
WHERE product.factory_code = 'Z8711';

INSERT INTO production_item (
    customer_order_item_id,
    product_id,
    product_version,
    product_bom_id,
    origin_flow_node_id
)
SELECT
    customer_order_item.id,
    product.id,
    1,
    bom.id,
    part.origin_flow_node_id
FROM customer_order
JOIN customer_order_item
    ON customer_order_item.customer_order_id = customer_order.id
JOIN product
    ON product.id = customer_order_item.product_id
JOIN product_bom AS bom
    ON bom.product_id = product.id
    AND bom.product_version = customer_order_item.product_version
JOIN (
    VALUES
        ('Z8711-01', 'z8711-part-logo'),
        ('Z8711-02', 'z8711-part-outsourced-stud')
) AS part(part_no, origin_flow_node_id)
    ON part.part_no = bom.part_no
WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001';

INSERT INTO repository (
    production_item_id,
    processing_state_id,
    flow_node_id,
    source_flow_node_id,
    department_id,
    source_work_order_id,
    quantity
)
SELECT
    production_item.id,
    processing_state.id,
    'z8711-process-laser',
    'z8711-part-logo',
    department.id,
    NULL,
    20
FROM customer_order
JOIN customer_order_item
    ON customer_order_item.customer_order_id = customer_order.id
JOIN production_item
    ON production_item.customer_order_item_id = customer_order_item.id
JOIN product_bom AS bom
    ON bom.id = production_item.product_bom_id
    AND bom.part_no = 'Z8711-01'
JOIN material_processing_state AS processing_state
    ON processing_state.product_id = production_item.product_id
    AND processing_state.product_version = production_item.product_version
    AND processing_state.product_bom_id = production_item.product_bom_id
    AND processing_state.origin_flow_node_id = production_item.origin_flow_node_id
    AND processing_state.resume_flow_node_id = 'z8711-process-laser'
JOIN department
    ON department.department_code = 'stamp'
WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001';

INSERT INTO production_movement (
    production_item_id,
    source_flow_node_id,
    target_flow_node_id,
    source_department_id,
    target_department_id,
    quantity,
    movement_type
)
SELECT
    repository.production_item_id,
    repository.source_flow_node_id,
    repository.flow_node_id,
    NULL,
    repository.department_id,
    repository.quantity,
    'initial'
FROM customer_order
JOIN customer_order_item
    ON customer_order_item.customer_order_id = customer_order.id
JOIN production_item
    ON production_item.customer_order_item_id = customer_order_item.id
JOIN repository
    ON repository.production_item_id = production_item.id
    AND repository.source_work_order_id IS NULL
WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001';

DO $$
BEGIN
    IF (
        SELECT COUNT(*)
        FROM product_process_flow
        JOIN product ON product.id = product_process_flow.product_id
        WHERE product.factory_code = 'Z8711'
            AND product_process_flow.product_version = 1
            AND jsonb_array_length(product_process_flow.flow_json->'nodes') = 10
            AND jsonb_array_length(product_process_flow.flow_json->'edges') = 9
    ) <> 1 THEN
        RAISE EXCEPTION 'Z8711 正式流程初始化不完整';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM product_route_task
        JOIN product ON product.id = product_route_task.product_id
        WHERE product.factory_code = 'Z8711'
            AND product_route_task.product_version = 1
    ) <> 6 THEN
        RAISE EXCEPTION 'Z8711 正式流程任务投影初始化不完整';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM customer_order
        JOIN customer_order_item
            ON customer_order_item.customer_order_id = customer_order.id
        WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001'
            AND customer_order.status = 'planned'
            AND customer_order_item.quantity = 15
    ) <> 1 THEN
        RAISE EXCEPTION 'Z8711 示例订单初始化不完整';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM customer_order
        JOIN production_plan
            ON production_plan.customer_order_id = customer_order.id
        JOIN production_plan_item
            ON production_plan_item.production_plan_id = production_plan.id
        WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001'
            AND production_plan.status = 'confirmed'
            AND production_plan.confirmed_by = 'business'
            AND production_plan_item.item_type = 'part'
            AND production_plan_item.planned_production_quantity = 20
    ) <> 2 THEN
        RAISE EXCEPTION 'Z8711 示例生产计划初始化不完整';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM customer_order
        JOIN production_plan
            ON production_plan.customer_order_id = customer_order.id
        JOIN production_plan_item
            ON production_plan_item.production_plan_id = production_plan.id
        WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001'
            AND production_plan_item.item_type = 'assembly'
            AND production_plan_item.planned_production_quantity = 20
    ) <> 1 THEN
        RAISE EXCEPTION 'Z8711 示例装配计划数量初始化不完整';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM customer_order
        JOIN production_plan
            ON production_plan.customer_order_id = customer_order.id
        JOIN production_route_task
            ON production_route_task.production_plan_id = production_plan.id
        WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001'
    ) <> 6 THEN
        RAISE EXCEPTION 'Z8711 示例生产计划任务投影初始化不完整';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM customer_order
        JOIN customer_order_item
            ON customer_order_item.customer_order_id = customer_order.id
        JOIN production_item
            ON production_item.customer_order_item_id = customer_order_item.id
        WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001'
    ) <> 2 THEN
        RAISE EXCEPTION 'Z8711 示例生产对象初始化不完整';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM customer_order
        JOIN customer_order_item
            ON customer_order_item.customer_order_id = customer_order.id
        JOIN production_item
            ON production_item.customer_order_item_id = customer_order_item.id
        JOIN repository
            ON repository.production_item_id = production_item.id
        JOIN production_movement
            ON production_movement.production_item_id = production_item.id
            AND production_movement.movement_type = 'initial'
        WHERE customer_order.customer_order_no = 'ORDER-Z8711-0001'
            AND repository.quantity = 20
            AND repository.flow_node_id = 'z8711-process-laser'
    ) <> 1 THEN
        RAISE EXCEPTION 'Z8711 logo件初始生产位置初始化不完整';
    END IF;
END;
$$;

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
WHERE department.department_code = 'assembly' AND workshop.workshop_name = '装配车间';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '装包示例工人', department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
WHERE department.department_code = 'assembly' AND workshop.workshop_name = '装包车间';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '焊接示例工人', department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
WHERE department.department_code = 'assembly' AND workshop.workshop_name = '焊接车间';

COMMIT;

