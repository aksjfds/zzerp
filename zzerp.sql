DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

GRANT ALL ON SCHEMA public TO CURRENT_USER;
GRANT ALL ON SCHEMA public TO public;

-- ============================================================
-- ZZ ERP 数据库初始化
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

BEGIN;

-- ============================================================
-- 表结构
-- ============================================================

-- ------------------------------------------------------------
-- 认证与会话
-- ------------------------------------------------------------

-- users：保存系统登录账号、所属部门、角色和权限集合。
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    department TEXT NOT NULL,
    role TEXT NOT NULL,
    permissions TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- user_sessions：保存用户登录会话、CSRF 令牌和会话有效期。
CREATE TABLE user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 客户、工程产品、版本、BOM 与工艺路线
-- ------------------------------------------------------------

-- customer：保存工程产品和业务订单共用的客户主数据。
CREATE TABLE customer (
    id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- product：保存工程确认后的可复用产品主数据和当前版本，不代表具体订单或生产批次。
CREATE TABLE product (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    product_name TEXT NOT NULL,
    factory_code TEXT NOT NULL,
    customer_code TEXT NOT NULL,
    version INT NOT NULL DEFAULT 1 CHECK (version > 0),
    revision INT NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_factory_code UNIQUE (factory_code)
);

-- product_version：保存产品的版本清单，供 BOM、流程图和订单锁定具体版本。
CREATE TABLE product_version (
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    version INT NOT NULL CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, version)
);

-- product_bom：保存产品各版本的配件明细、用量、编号及显示顺序。
CREATE TABLE product_bom (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    product_version INT NOT NULL CHECK (product_version > 0),
    part_name TEXT NOT NULL,
    part_no TEXT NOT NULL,
    pcs INT NOT NULL CHECK (pcs > 0),
    remark TEXT,
    sort_order INT NOT NULL CHECK (sort_order > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_product_bom_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version) ON DELETE CASCADE,
    CONSTRAINT uq_product_bom_id_version
        UNIQUE (id, product_id, product_version),
    CONSTRAINT uq_product_bom_part_no UNIQUE (product_id, product_version, part_no),
    CONSTRAINT uq_product_bom_sort_order
        UNIQUE (product_id, product_version, sort_order) DEFERRABLE INITIALLY DEFERRED
);

-- product_process_flow：保存产品各版本的流程图 JSON 配置。
CREATE TABLE product_process_flow (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    product_version INT NOT NULL CHECK (product_version > 0),
    flow_json JSONB NOT NULL DEFAULT '{"schema_version": 3, "nodes": [], "edges": []}'::jsonb,
    draft_flow_json JSONB,
    CHECK (jsonb_typeof(flow_json) = 'object'),
    CHECK (flow_json ? 'schema_version'),
    CHECK (jsonb_typeof(flow_json->'schema_version') = 'number'),
    CHECK (flow_json->>'schema_version' = '3'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (flow_json ? 'nodes'),
    CHECK (jsonb_typeof(flow_json->'nodes') = 'array'),
    CHECK (flow_json ? 'edges'),
    CHECK (jsonb_typeof(flow_json->'edges') = 'array'),
    CHECK (draft_flow_json IS NULL OR jsonb_typeof(draft_flow_json) = 'object'),
    CHECK (draft_flow_json IS NULL OR draft_flow_json->>'schema_version' = '3'),
    CHECK (draft_flow_json IS NULL OR jsonb_typeof(draft_flow_json->'nodes') = 'array'),
    CHECK (draft_flow_json IS NULL OR jsonb_typeof(draft_flow_json->'edges') = 'array'),
    CONSTRAINT fk_product_process_flow_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version) ON DELETE CASCADE,
    CONSTRAINT uq_product_process_flow_version UNIQUE (product_id, product_version)
);

-- ------------------------------------------------------------
-- 部门、车间、工艺、标记与人员
-- ------------------------------------------------------------

-- department：保存系统中的工程、业务、生产、QC、装配和成品等部门。
CREATE TABLE department (
    id BIGSERIAL PRIMARY KEY,
    department_name TEXT NOT NULL UNIQUE,
    department_code TEXT NOT NULL UNIQUE
);

-- workshop：保存部门下属车间，作为工艺和工人的组织范围。
CREATE TABLE workshop (
    id BIGSERIAL PRIMARY KEY,
    department_id BIGINT NOT NULL REFERENCES department(id),
    workshop_name TEXT NOT NULL,
    UNIQUE (id, department_id),
    UNIQUE (department_id, workshop_name)
);

-- procedure：保存车间可执行的工艺；多路输入工艺按装配工单合并全部来源物料。
CREATE TABLE procedure (
    id BIGSERIAL PRIMARY KEY,
    workshop_id BIGINT NOT NULL REFERENCES workshop(id),
    procedure_name TEXT NOT NULL,
    procedure_type TEXT NOT NULL DEFAULT 'standard'
        CHECK (procedure_type IN ('standard', 'purchase_receipt')),
    input_mode TEXT NOT NULL DEFAULT 'single'
        CHECK (input_mode IN ('single', 'multiple')),
    UNIQUE (id, procedure_type),
    UNIQUE (workshop_id, procedure_name)
);

-- procedure_tag：保存工艺下可复用的生产标记名称，不定义固定路线或先后顺序。
CREATE TABLE procedure_tag (
    id BIGSERIAL PRIMARY KEY,
    procedure_id BIGINT NOT NULL REFERENCES procedure(id),
    tag_name TEXT NOT NULL
        CHECK (tag_name = btrim(tag_name) AND tag_name <> ''),
    UNIQUE (id, procedure_id),
    CONSTRAINT uq_procedure_tag_name UNIQUE (procedure_id, tag_name)
);

-- procedure_tag_price：按产品版本中的配件来源节点配置必做标记及计件单价；同时支持 BOM 配件和装配输出。
CREATE TABLE procedure_tag_price (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL,
    origin_flow_node_id TEXT NOT NULL,
    procedure_id BIGINT NOT NULL,
    procedure_tag_id BIGINT NOT NULL,
    unit_price NUMERIC(12, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_procedure_tag_price_tag
        FOREIGN KEY (procedure_tag_id, procedure_id)
        REFERENCES procedure_tag(id, procedure_id),
    CONSTRAINT fk_procedure_tag_price_product_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version) ON DELETE CASCADE,
    CONSTRAINT ck_procedure_tag_price_nonnegative
        CHECK (unit_price >= 0),
    CONSTRAINT uq_procedure_tag_price_part_tag
        UNIQUE (product_id, product_version, origin_flow_node_id, procedure_tag_id)
);

-- procedure_tag_set：保存同一工艺下的无序标记组合；tag_key 确保相同集合只有一条记录。
CREATE TABLE procedure_tag_set (
    id BIGSERIAL PRIMARY KEY,
    procedure_id BIGINT NOT NULL REFERENCES procedure(id),
    tag_key TEXT NOT NULL CHECK (tag_key = btrim(tag_key) AND tag_key <> ''),
    UNIQUE (id, procedure_id),
    CONSTRAINT uq_procedure_tag_set_key UNIQUE (procedure_id, tag_key)
);

-- procedure_tag_set_member：保存标记组合与具体标记之间的成员关系。
CREATE TABLE procedure_tag_set_member (
    id BIGSERIAL PRIMARY KEY,
    tag_set_id BIGINT NOT NULL REFERENCES procedure_tag_set(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES procedure_tag(id),
    UNIQUE (tag_set_id, tag_id)
);

-- worker：保存部门或车间下可分配到工单、QC 批次的工作人员。
CREATE TABLE worker (
    id BIGSERIAL PRIMARY KEY,
    worker_name TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    workshop_id BIGINT,
    FOREIGN KEY (workshop_id, department_id) REFERENCES workshop(id, department_id)
);

-- ------------------------------------------------------------
-- 客户订单
-- ------------------------------------------------------------

-- customer_order：保存客户订单主信息、业务状态和并发修订版本。
CREATE TABLE customer_order (
    id BIGSERIAL PRIMARY KEY,
    customer_order_no TEXT NOT NULL UNIQUE,
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'planned', 'cancelled', 'closed')),
    revision INT NOT NULL DEFAULT 1 CHECK (revision > 0),
    remark TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- customer_order_item：保存客户订单中的产品、锁定版本、订购数量和交期。
CREATE TABLE customer_order_item (
    id BIGSERIAL PRIMARY KEY,
    customer_order_id BIGINT NOT NULL REFERENCES customer_order(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES product(id),
    product_version INT NOT NULL CHECK (product_version > 0),
    quantity INT NOT NULL CHECK (quantity > 0),
    delivery_date DATE NOT NULL,
    remark TEXT,
    CONSTRAINT fk_customer_order_item_product_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version),
    CONSTRAINT uq_customer_order_item_id_version
        UNIQUE (id, product_id, product_version),
    CONSTRAINT uq_customer_order_item_product_version
        UNIQUE (customer_order_id, product_id, product_version)
);

-- production_plan：客户订单确认后自动生成、由业务部另行填写和确认的生产计划。
CREATE TABLE production_plan (
    id BIGSERIAL PRIMARY KEY,
    customer_order_id BIGINT NOT NULL UNIQUE
        REFERENCES customer_order(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'cancelled')),
    revision INT NOT NULL DEFAULT 1 CHECK (revision > 0),
    confirmed_at TIMESTAMPTZ,
    confirmed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (status = 'confirmed' AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)
        OR (status <> 'confirmed')
    )
);

-- production_plan_item：内部保留成品、装配体和普通配件节点；业务部只填写普通配件数量。
CREATE TABLE production_plan_item (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL
        REFERENCES production_plan(id) ON DELETE CASCADE,
    customer_order_item_id BIGINT NOT NULL
        REFERENCES customer_order_item(id) ON DELETE CASCADE,
    identity_key TEXT NOT NULL,
    item_type TEXT NOT NULL
        CHECK (item_type IN ('part', 'assembly', 'finished_product')),
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL CHECK (product_version > 0),
    product_bom_id BIGINT,
    flow_node_id TEXT NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    unit_requirement INT NOT NULL CHECK (unit_requirement > 0),
    gross_required_quantity INT NOT NULL CHECK (gross_required_quantity >= 0),
    estimated_inventory_quantity INT NOT NULL DEFAULT 0
        CHECK (estimated_inventory_quantity >= 0),
    net_required_quantity INT NOT NULL CHECK (net_required_quantity >= 0),
    planned_production_quantity INT NOT NULL
        CHECK (planned_production_quantity >= 0),
    reserved_inventory_quantity INT NOT NULL DEFAULT 0
        CHECK (reserved_inventory_quantity >= 0),
    issued_inventory_quantity INT NOT NULL DEFAULT 0
        CHECK (issued_inventory_quantity >= 0),
    sort_order INT NOT NULL,
    UNIQUE (production_plan_id, customer_order_item_id, identity_key)
);

-- inventory_stock：按产品、版本、物料节点和系统推导的完成节点保存跨订单库存。
CREATE TABLE inventory_stock (
    id BIGSERIAL PRIMARY KEY,
    identity_key TEXT NOT NULL UNIQUE,
    department_code TEXT NOT NULL
        CHECK (department_code IN ('warehouse', 'finished')),
    item_type TEXT NOT NULL
        CHECK (item_type IN ('part', 'assembly', 'finished_product')),
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL CHECK (product_version > 0),
    product_bom_id BIGINT,
    flow_node_id TEXT NOT NULL,
    completed_flow_node_id TEXT NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    reserved_quantity INT NOT NULL DEFAULT 0
        CHECK (reserved_quantity >= 0 AND reserved_quantity <= quantity),
    revision INT NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (department_code = 'finished' AND item_type = 'finished_product')
        OR (department_code = 'warehouse' AND item_type IN ('part', 'assembly'))
    )
);

-- inventory_reservation：生产计划确认时对实物库存的占用和出库状态。
CREATE TABLE inventory_reservation (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL
        REFERENCES production_plan(id) ON DELETE CASCADE,
    production_plan_item_id BIGINT NOT NULL
        REFERENCES production_plan_item(id) ON DELETE CASCADE,
    inventory_stock_id BIGINT NOT NULL REFERENCES inventory_stock(id),
    reserved_quantity INT NOT NULL CHECK (reserved_quantity > 0),
    issued_quantity INT NOT NULL DEFAULT 0
        CHECK (issued_quantity >= 0 AND issued_quantity <= reserved_quantity),
    status TEXT NOT NULL DEFAULT 'reserved'
        CHECK (status IN ('reserved', 'issued', 'released')),
    reserved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    issued_at TIMESTAMPTZ,
    issued_by TEXT,
    released_at TIMESTAMPTZ,
    CHECK (
        (status = 'reserved' AND issued_quantity = 0 AND issued_at IS NULL AND released_at IS NULL)
        OR (status = 'issued' AND issued_quantity > 0 AND issued_at IS NOT NULL AND released_at IS NULL)
        OR (status = 'released' AND issued_quantity = 0 AND released_at IS NOT NULL)
    )
);

-- inventory_receipt：保存生产节点入库及订单成品结余入库的来源快照。
CREATE TABLE inventory_receipt (
    id BIGSERIAL PRIMARY KEY,
    source_customer_order_id BIGINT,
    source_production_item_id BIGINT,
    identity_key TEXT NOT NULL,
    department_code TEXT NOT NULL
        CHECK (department_code IN ('warehouse', 'finished')),
    item_type TEXT NOT NULL
        CHECK (item_type IN ('part', 'assembly', 'finished_product')),
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL CHECK (product_version > 0),
    product_bom_id BIGINT,
    flow_node_id TEXT NOT NULL,
    completed_flow_node_id TEXT NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMPTZ,
    confirmed_by TEXT,
    CHECK (
        (status = 'confirmed' AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)
        OR (status <> 'confirmed' AND confirmed_at IS NULL AND confirmed_by IS NULL)
    ),
    CHECK (
        (department_code = 'finished' AND item_type = 'finished_product')
        OR (department_code = 'warehouse' AND item_type IN ('part', 'assembly'))
    )
);

-- inventory_transaction：记录入库、占用、释放、出库和调整的不可变流水。
CREATE TABLE inventory_transaction (
    id BIGSERIAL PRIMARY KEY,
    inventory_stock_id BIGINT NOT NULL REFERENCES inventory_stock(id),
    production_plan_id BIGINT,
    production_plan_item_id BIGINT,
    inventory_reservation_id BIGINT,
    inventory_receipt_id BIGINT,
    transaction_type TEXT NOT NULL CHECK (
        transaction_type IN ('receipt', 'reserve', 'release', 'issue', 'adjust_in', 'adjust_out')
    ),
    quantity INT NOT NULL CHECK (quantity > 0),
    quantity_before INT NOT NULL CHECK (quantity_before >= 0),
    quantity_after INT NOT NULL CHECK (quantity_after >= 0),
    reserved_before INT NOT NULL CHECK (reserved_before >= 0),
    reserved_after INT NOT NULL CHECK (reserved_after >= 0),
    actor_username TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    product_version INT NOT NULL CHECK (product_version > 0),
    flow_node_id TEXT NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    unit_quantity INT NOT NULL CHECK (unit_quantity > 0),
    pending_quantity INT NOT NULL DEFAULT 0 CHECK (pending_quantity >= 0),
    available_quantity INT NOT NULL DEFAULT 0 CHECK (available_quantity >= 0),
    shipped_quantity INT NOT NULL DEFAULT 0 CHECK (shipped_quantity >= 0),
    transferred_quantity INT NOT NULL DEFAULT 0 CHECK (transferred_quantity >= 0),
    revision INT NOT NULL DEFAULT 1 CHECK (revision > 0),
    received_at TIMESTAMPTZ,
    received_by TEXT,
    last_shipped_at TIMESTAMPTZ,
    last_shipped_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (production_item_id, flow_node_id)
);

-- ------------------------------------------------------------
-- 生产库存、工单、QC 批次与流动记录
-- ------------------------------------------------------------

-- production_item：保存订单确认后生成的具体生产对象，包括 BOM 配件或装配产出。
CREATE TABLE production_item (
    id BIGSERIAL PRIMARY KEY,
    customer_order_item_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    product_version INT NOT NULL CHECK (product_version > 0),
    product_bom_id BIGINT,
    origin_flow_node_id TEXT NOT NULL,
    CONSTRAINT fk_production_item_order_version
        FOREIGN KEY (customer_order_item_id, product_id, product_version)
        REFERENCES customer_order_item(id, product_id, product_version) ON DELETE CASCADE,
    CONSTRAINT fk_production_item_bom_version
        FOREIGN KEY (product_bom_id, product_id, product_version)
        REFERENCES product_bom(id, product_id, product_version)
);

ALTER TABLE finished_order_stock
    ADD CONSTRAINT fk_finished_order_stock_production_item
    FOREIGN KEY (production_item_id) REFERENCES production_item(id) ON DELETE CASCADE;

-- repository：保存生产对象在流程节点中的未打标记可用数量。
CREATE TABLE repository (
    id BIGSERIAL PRIMARY KEY,
    production_item_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    flow_node_id TEXT NOT NULL,
    source_flow_node_id TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    UNIQUE (id, production_item_id),
    UNIQUE (production_item_id, flow_node_id, source_flow_node_id, department_id)
);

-- procedure_tag_stock：保存生产对象在流程节点中已完成非空标记组合的可用数量。
CREATE TABLE procedure_tag_stock (
    id BIGSERIAL PRIMARY KEY,
    production_item_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    flow_node_id TEXT NOT NULL,
    source_flow_node_id TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    tag_set_id BIGINT NOT NULL REFERENCES procedure_tag_set(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    CONSTRAINT uq_procedure_tag_stock_id_production_item
        UNIQUE (id, production_item_id),
    CONSTRAINT uq_procedure_tag_stock_position UNIQUE (
        production_item_id,
        flow_node_id,
        source_flow_node_id,
        department_id,
        tag_set_id
    )
);

-- work_order：保存标记加工、外购入库和装配工单及其执行快照和进度。
CREATE TABLE work_order (
    id BIGSERIAL PRIMARY KEY,
    work_order_no TEXT UNIQUE,
    repository_id BIGINT,
    procedure_tag_stock_id BIGINT,
    production_item_id BIGINT NOT NULL REFERENCES production_item(id),
    procedure_id BIGINT REFERENCES procedure(id),
    applied_tag_set_id BIGINT REFERENCES procedure_tag_set(id),
    source_tag_set_id BIGINT REFERENCES procedure_tag_set(id),
    target_tag_set_id BIGINT REFERENCES procedure_tag_set(id),
    work_order_type TEXT NOT NULL
        CHECK (work_order_type IN ('tag', 'purchase_receipt', 'assembly')),
    flow_node_id TEXT NOT NULL,
    -- 工单创建时记录执行来源快照；装配工单记录自身装配节点，物料来源另见 work_order_material。
    source_flow_node_id TEXT,
    work_order_name TEXT NOT NULL,
    remark TEXT,
    worker_id BIGINT REFERENCES worker(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    processed_quantity INT NOT NULL DEFAULT 0,
    completed_quantity INT NOT NULL DEFAULT 0
        CHECK (completed_quantity >= 0 AND completed_quantity <= quantity),
    CHECK (
        processed_quantity >= completed_quantity
        AND processed_quantity <= quantity
    ),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMPTZ,
    CHECK (
        (status = 'open' AND closed_at IS NULL)
        OR (status IN ('closed', 'cancelled') AND closed_at IS NOT NULL)
    ),
    CHECK (status <> 'closed' OR completed_quantity = quantity),
    CHECK (
        status <> 'cancelled'
        OR (completed_quantity = 0 AND processed_quantity = 0)
    ),
    CHECK (
        (work_order_type = 'assembly'
            AND applied_tag_set_id IS NULL
            AND source_tag_set_id IS NULL
            AND target_tag_set_id IS NULL
            AND source_flow_node_id IS NOT NULL
            AND repository_id IS NULL
            AND procedure_tag_stock_id IS NULL)
        OR (work_order_type = 'tag'
            AND procedure_id IS NOT NULL
            AND applied_tag_set_id IS NOT NULL
            AND target_tag_set_id IS NOT NULL
            AND source_flow_node_id IS NOT NULL
            AND (repository_id IS NULL OR procedure_tag_stock_id IS NULL)
            AND (status <> 'open'
                OR completed_quantity = quantity
                OR repository_id IS NOT NULL
                OR procedure_tag_stock_id IS NOT NULL))
        OR (work_order_type = 'purchase_receipt'
            AND procedure_id IS NOT NULL
            AND applied_tag_set_id IS NULL
            AND source_tag_set_id IS NULL
            AND target_tag_set_id IS NULL
            AND source_flow_node_id IS NOT NULL
            AND procedure_tag_stock_id IS NULL
            AND (status <> 'open' OR repository_id IS NOT NULL))
    ),
    CONSTRAINT fk_work_order_repository_item
        FOREIGN KEY (repository_id, production_item_id)
        REFERENCES repository(id, production_item_id),
    CONSTRAINT fk_work_order_tag_stock_item
        FOREIGN KEY (procedure_tag_stock_id, production_item_id)
        REFERENCES procedure_tag_stock(id, production_item_id)
);

-- work_order_pay_detail：在标记工单开单时冻结各标记的计件单价，避免后续调价改变历史工资。
CREATE TABLE work_order_pay_detail (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    procedure_tag_id BIGINT NOT NULL REFERENCES procedure_tag(id),
    tag_name TEXT NOT NULL
        CHECK (tag_name = btrim(tag_name) AND tag_name <> ''),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (work_order_id, procedure_tag_id)
);

-- work_order_material：保存装配工单占用的来源库存、生产对象和物料数量。
CREATE TABLE work_order_material (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    repository_id BIGINT,
    production_item_id BIGINT NOT NULL REFERENCES production_item(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    CONSTRAINT fk_work_order_material_repository_item
        FOREIGN KEY (repository_id, production_item_id)
        REFERENCES repository(id, production_item_id),
    UNIQUE (work_order_id, production_item_id)
);

-- work_order_batch：保存工单送检批次、QC 结果及返工复检的父子关系。
CREATE TABLE work_order_batch (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    submitted_quantity INT NOT NULL CHECK (submitted_quantity > 0),
    -- 提交时复制 work_order.source_flow_node_id，避免来源库存行删除后丢失到达来源。
    source_flow_node_id TEXT NOT NULL,
    -- 返工复检批次指向产生返工数量的上一批 QC；首次送检保持 NULL。
    rework_source_batch_id BIGINT,
    qualified_quantity INT CHECK (qualified_quantity >= 0),
    rework_quantity INT CHECK (rework_quantity >= 0),
    scrap_quantity INT CHECK (scrap_quantity >= 0),
    lost_quantity INT CHECK (lost_quantity >= 0),
    qc_worker_id BIGINT REFERENCES worker(id),
    qc_worker_name TEXT,
    defect_reason TEXT,
    recorded_at TIMESTAMPTZ,
    UNIQUE (id, work_order_id),
    CONSTRAINT fk_work_order_batch_rework_source
        FOREIGN KEY (rework_source_batch_id, work_order_id)
        REFERENCES work_order_batch(id, work_order_id),
    CHECK (
        (recorded_at IS NULL AND qualified_quantity IS NULL
            AND rework_quantity IS NULL AND scrap_quantity IS NULL
            AND lost_quantity IS NULL AND qc_worker_id IS NULL AND qc_worker_name IS NULL)
        OR
        (recorded_at IS NOT NULL AND qualified_quantity IS NOT NULL
            AND rework_quantity IS NOT NULL AND scrap_quantity IS NOT NULL
            AND lost_quantity IS NOT NULL AND qc_worker_id IS NOT NULL
            AND qc_worker_name IS NOT NULL
            AND qualified_quantity + rework_quantity + scrap_quantity + lost_quantity
                = submitted_quantity)
    )
);

-- production_movement：保存数量在流程节点、部门、标记组合和 QC 结果之间的不可变流动历史。
CREATE TABLE production_movement (
    id BIGSERIAL PRIMARY KEY,
    production_item_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    source_flow_node_id TEXT,
    target_flow_node_id TEXT,
    source_tag_set_id BIGINT REFERENCES procedure_tag_set(id),
    target_tag_set_id BIGINT REFERENCES procedure_tag_set(id),
    source_department_id BIGINT REFERENCES department(id),
    target_department_id BIGINT REFERENCES department(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    movement_type TEXT NOT NULL CHECK (
        movement_type IN (
            'initial', 'process', 'purchase_receipt', 'assembly_input', 'assembly_output',
            'qc_qualified', 'qc_rework', 'qc_dispatch', 'inventory_issue',
            'finished_receipt', 'customer_shipment', 'scrap', 'lost'
        )
    ),
    work_order_id BIGINT REFERENCES work_order(id),
    work_order_batch_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_production_movement_batch_order
        FOREIGN KEY (work_order_batch_id, work_order_id)
        REFERENCES work_order_batch(id, work_order_id),
    CHECK (
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
        OR (movement_type = 'qc_dispatch'
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
    )
);

-- production_operation_undo：保存生产提交前后的库存与工单快照，用于在没有后续流转时安全撤回。
CREATE TABLE production_operation_undo (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    -- 批次删除后仍保留原编号作为撤回审计信息，因此不设置外键。
    work_order_batch_id BIGINT,
    operation_type TEXT NOT NULL
        CHECK (operation_type IN ('processing_completion', 'submission', 'rework_submission')),
    operation_label TEXT NOT NULL,
    department_code TEXT NOT NULL,
    actor_username TEXT NOT NULL,
    snapshot_json JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'applied'
        CHECK (status IN ('applied', 'reversed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reversed_at TIMESTAMPTZ,
    reversed_by TEXT,
    CHECK (
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

CREATE FUNCTION validate_tag_set_integrity() RETURNS TRIGGER AS $$
DECLARE
    checked_tag_set_id BIGINT;
    set_procedure_id BIGINT;
    set_tag_key TEXT;
    actual_tag_key TEXT;
    procedures_match BOOLEAN;
BEGIN
    IF TG_TABLE_NAME = 'procedure_tag_set_member' THEN
        IF TG_OP = 'UPDATE' THEN
            IF (NEW.tag_set_id, NEW.tag_id)
                IS DISTINCT FROM (OLD.tag_set_id, OLD.tag_id) THEN
                RAISE EXCEPTION 'tag set membership identity is immutable'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
    END IF;
    IF TG_TABLE_NAME = 'procedure_tag_set' THEN
        checked_tag_set_id := NEW.id;
    ELSIF TG_OP = 'DELETE' THEN
        checked_tag_set_id := OLD.tag_set_id;
    ELSE
        checked_tag_set_id := NEW.tag_set_id;
    END IF;
    SELECT procedure_id, tag_key
    INTO set_procedure_id, set_tag_key
    FROM procedure_tag_set
    WHERE id = checked_tag_set_id;
    IF NOT FOUND THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
        RETURN NEW;
    END IF;
    SELECT
        string_agg(member.tag_id::TEXT, ',' ORDER BY member.tag_id),
        bool_and(tag.procedure_id = set_procedure_id)
    INTO actual_tag_key, procedures_match
    FROM procedure_tag_set_member AS member
    JOIN procedure_tag AS tag ON tag.id = member.tag_id
    WHERE member.tag_set_id = checked_tag_set_id;
    IF actual_tag_key IS NULL
        OR actual_tag_key IS DISTINCT FROM set_tag_key
        OR procedures_match IS NOT TRUE THEN
        RAISE EXCEPTION 'tag set must contain the canonical tags of one procedure'
            USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_work_order_tag_context() RETURNS TRIGGER AS $$
DECLARE
    order_procedure_type TEXT;
    applied_set_procedure_id BIGINT;
    source_set_procedure_id BIGINT;
    target_set_procedure_id BIGINT;
    source_stock_tag_set_id BIGINT;
    source_tags BIGINT[];
    applied_tags BIGINT[];
    target_tags BIGINT[];
    expected_tags BIGINT[];
BEGIN
    IF NEW.work_order_type = 'assembly' THEN
        IF NEW.status = 'closed' AND EXISTS (
            SELECT 1 FROM work_order_batch
            WHERE work_order_id = NEW.id AND recorded_at IS NULL
        ) THEN
            RAISE EXCEPTION 'assembly work order with pending QC batches cannot be closed'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.status = 'closed' AND EXISTS (
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
            RAISE EXCEPTION 'assembly work order with pending rework cannot be closed'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    SELECT procedure_type INTO order_procedure_type
    FROM procedure WHERE id = NEW.procedure_id;
    IF NEW.work_order_type = 'purchase_receipt' THEN
        IF order_procedure_type IS DISTINCT FROM 'purchase_receipt' THEN
            RAISE EXCEPTION 'purchase work order must use a purchase procedure'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    IF order_procedure_type IS DISTINCT FROM 'standard' THEN
        RAISE EXCEPTION 'tag work order must use a standard procedure'
            USING ERRCODE = '23514';
    END IF;
    SELECT procedure_id INTO applied_set_procedure_id
    FROM procedure_tag_set WHERE id = NEW.applied_tag_set_id;
    SELECT procedure_id INTO target_set_procedure_id
    FROM procedure_tag_set WHERE id = NEW.target_tag_set_id;
    IF NEW.source_tag_set_id IS NOT NULL THEN
        SELECT procedure_id INTO source_set_procedure_id
        FROM procedure_tag_set WHERE id = NEW.source_tag_set_id;
    END IF;
    IF applied_set_procedure_id IS DISTINCT FROM NEW.procedure_id
        OR target_set_procedure_id IS DISTINCT FROM NEW.procedure_id
        OR (NEW.source_tag_set_id IS NOT NULL
            AND source_set_procedure_id IS DISTINCT FROM NEW.procedure_id) THEN
        RAISE EXCEPTION 'work order tags must belong to its procedure'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.repository_id IS NOT NULL AND NEW.source_tag_set_id IS NOT NULL THEN
        RAISE EXCEPTION 'untagged repository source cannot have a source tag set'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.procedure_tag_stock_id IS NOT NULL THEN
        SELECT tag_set_id INTO source_stock_tag_set_id
        FROM procedure_tag_stock WHERE id = NEW.procedure_tag_stock_id;
        IF source_stock_tag_set_id IS DISTINCT FROM NEW.source_tag_set_id THEN
            RAISE EXCEPTION 'tag stock source must match the work order source tag set'
                USING ERRCODE = '23514';
        END IF;
    ELSIF NEW.repository_id IS NULL
        AND NEW.status = 'open'
        AND NEW.completed_quantity < NEW.quantity THEN
        RAISE EXCEPTION 'open tag work order with unsubmitted quantity must retain one inventory source'
            USING ERRCODE = '23514';
    END IF;
    SELECT COALESCE(array_agg(tag_id ORDER BY tag_id), ARRAY[]::BIGINT[])
    INTO source_tags
    FROM procedure_tag_set_member
    WHERE tag_set_id = NEW.source_tag_set_id;
    SELECT COALESCE(array_agg(tag_id ORDER BY tag_id), ARRAY[]::BIGINT[])
    INTO applied_tags
    FROM procedure_tag_set_member
    WHERE tag_set_id = NEW.applied_tag_set_id;
    IF cardinality(applied_tags) = 0 THEN
        RAISE EXCEPTION 'applied tag set must contain at least one tag'
            USING ERRCODE = '23514';
    END IF;
    IF source_tags && applied_tags THEN
        RAISE EXCEPTION 'source tag set already contains an applied tag'
            USING ERRCODE = '23514';
    END IF;
    SELECT ARRAY(
        SELECT DISTINCT tag_id
        FROM unnest(source_tags || applied_tags) AS member_tag(tag_id)
        ORDER BY tag_id
    ) INTO expected_tags;
    SELECT COALESCE(array_agg(tag_id ORDER BY tag_id), ARRAY[]::BIGINT[])
    INTO target_tags
    FROM procedure_tag_set_member
    WHERE tag_set_id = NEW.target_tag_set_id;
    IF target_tags IS DISTINCT FROM expected_tags THEN
        RAISE EXCEPTION 'target tag set must equal source tags plus the applied tags'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'closed' AND EXISTS (
        SELECT 1
        FROM work_order_batch
        WHERE work_order_id = NEW.id
          AND recorded_at IS NULL
    ) THEN
        RAISE EXCEPTION 'tag work order with pending QC batches cannot be closed'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'closed' AND EXISTS (
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
        RAISE EXCEPTION 'tag work order with pending rework cannot be closed'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_production_movement_context() RETURNS TRIGGER AS $$
DECLARE
    order_item_id BIGINT;
    order_type TEXT;
    order_procedure_type TEXT;
    order_flow_node_id TEXT;
    order_status TEXT;
    order_source_tag_set_id BIGINT;
    order_target_tag_set_id BIGINT;
    material_quantity INT;
    material_consumed BIGINT;
    batch_source_flow_node_id TEXT;
    batch_submitted_quantity INT;
    batch_recorded_at TIMESTAMPTZ;
BEGIN
    IF NEW.work_order_id IS NULL
        AND (NEW.source_tag_set_id IS NOT NULL OR NEW.target_tag_set_id IS NOT NULL) THEN
        RAISE EXCEPTION 'standalone movement cannot contain tag sets'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.work_order_id IS NOT NULL THEN
        SELECT
            work_order.production_item_id,
            work_order.work_order_type,
            procedure.procedure_type,
            work_order.flow_node_id,
            work_order.status,
            work_order.source_tag_set_id,
            work_order.target_tag_set_id
        INTO
            order_item_id,
            order_type,
            order_procedure_type,
            order_flow_node_id,
            order_status,
            order_source_tag_set_id,
            order_target_tag_set_id
        FROM work_order
        LEFT JOIN procedure
            ON procedure.id = work_order.procedure_id
        WHERE work_order.id = NEW.work_order_id
        FOR UPDATE OF work_order;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'movement must reference an existing work order'
                USING ERRCODE = '23503';
        ELSE
            IF NEW.movement_type IN (
                'process', 'purchase_receipt', 'assembly_input', 'assembly_output'
            ) AND order_status <> 'open' THEN
                RAISE EXCEPTION 'submission movement requires an open work order'
                    USING ERRCODE = '23514';
            END IF;
            IF NEW.movement_type = 'assembly_input' THEN
                IF order_type <> 'assembly' THEN
                    RAISE EXCEPTION 'assembly input requires an assembly work order'
                        USING ERRCODE = '23514';
                END IF;
                SELECT quantity
                INTO material_quantity
                FROM work_order_material
                WHERE work_order_id = NEW.work_order_id
                  AND production_item_id = NEW.production_item_id
                FOR UPDATE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'assembly input must belong to the work order materials'
                        USING ERRCODE = '23514';
                END IF;
                SELECT COALESCE(SUM(quantity), 0)
                INTO material_consumed
                FROM production_movement
                WHERE work_order_id = NEW.work_order_id
                  AND production_item_id = NEW.production_item_id
                  AND movement_type = 'assembly_input';
                IF material_consumed + NEW.quantity > material_quantity THEN
                    RAISE EXCEPTION 'assembly input quantity exceeds its remaining material allocation'
                        USING ERRCODE = '23514';
                END IF;
            ELSE
                IF (NEW.movement_type = 'assembly_output' AND order_type <> 'assembly')
                    OR (NEW.movement_type = 'process'
                        AND (order_type <> 'tag' OR order_procedure_type <> 'standard'))
                    OR (NEW.movement_type = 'purchase_receipt'
                        AND (order_type <> 'purchase_receipt'
                            OR order_procedure_type <> 'purchase_receipt')) THEN
                    RAISE EXCEPTION 'movement type must match the work order type'
                        USING ERRCODE = '23514';
                END IF;
                IF order_item_id <> NEW.production_item_id THEN
                    RAISE EXCEPTION 'movement production item must match the work order'
                        USING ERRCODE = '23514';
                END IF;
            END IF;
            IF NEW.movement_type IN (
                'process', 'purchase_receipt', 'assembly_input', 'assembly_output'
            ) AND NEW.source_flow_node_id IS DISTINCT FROM order_flow_node_id THEN
                RAISE EXCEPTION 'work order movement source node must match the work order'
                    USING ERRCODE = '23514';
            END IF;
            IF order_type = 'tag' THEN
                IF (NEW.movement_type = 'process' AND (
                        NEW.source_tag_set_id IS DISTINCT FROM order_source_tag_set_id
                        OR NEW.target_tag_set_id IS DISTINCT FROM order_target_tag_set_id))
                    OR (NEW.movement_type = 'qc_qualified' AND (
                        NEW.source_tag_set_id IS DISTINCT FROM order_target_tag_set_id
                        OR NEW.target_tag_set_id IS DISTINCT FROM order_target_tag_set_id))
                    OR (NEW.movement_type = 'qc_rework' AND (
                        NEW.source_tag_set_id IS DISTINCT FROM order_target_tag_set_id
                        OR NEW.target_tag_set_id IS DISTINCT FROM order_source_tag_set_id))
                    OR (NEW.movement_type = 'qc_dispatch' AND (
                        NEW.source_tag_set_id IS DISTINCT FROM order_target_tag_set_id
                        OR NEW.target_tag_set_id IS NOT NULL))
                    OR (NEW.movement_type IN ('scrap', 'lost') AND (
                        NEW.source_tag_set_id IS DISTINCT FROM order_target_tag_set_id
                        OR NEW.target_tag_set_id IS NOT NULL)) THEN
                    RAISE EXCEPTION 'movement tag sets must match the work order snapshot'
                        USING ERRCODE = '23514';
                END IF;
            ELSIF NEW.source_tag_set_id IS NOT NULL OR NEW.target_tag_set_id IS NOT NULL THEN
                RAISE EXCEPTION 'non-tag work order movement cannot contain tag sets'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
    END IF;

    IF NEW.work_order_batch_id IS NOT NULL THEN
        IF NEW.work_order_id IS NULL THEN
            RAISE EXCEPTION 'batch movement must retain its work order'
                USING ERRCODE = '23514';
        END IF;
        SELECT source_flow_node_id, submitted_quantity, recorded_at
        INTO batch_source_flow_node_id, batch_submitted_quantity, batch_recorded_at
        FROM work_order_batch
        WHERE id = NEW.work_order_batch_id
          AND work_order_id = NEW.work_order_id
        FOR UPDATE;
        IF batch_source_flow_node_id IS NULL THEN
            RAISE EXCEPTION 'movement batch must belong to the referenced work order'
                USING ERRCODE = '23514';
        END IF;
        IF batch_recorded_at IS NOT NULL
            AND NEW.movement_type <> 'qc_dispatch' THEN
            RAISE EXCEPTION 'completed QC batch cannot receive new movements'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.movement_type = 'qc_dispatch' AND batch_recorded_at IS NULL THEN
            RAISE EXCEPTION 'QC batch must be inspected before dispatch'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.movement_type IN ('process', 'purchase_receipt', 'assembly_output') THEN
            IF NEW.quantity <> batch_submitted_quantity THEN
                RAISE EXCEPTION 'submission movement must match its QC batch quantity'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION protect_assembly_material_movement_context() RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM production_movement
        WHERE work_order_id = OLD.work_order_id
          AND production_item_id = OLD.production_item_id
          AND movement_type = 'assembly_input'
    ) THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'assembly material identity is retained by movement history'
                USING ERRCODE = '23514';
        END IF;
        IF (NEW.work_order_id, NEW.production_item_id, NEW.quantity)
            IS DISTINCT FROM (OLD.work_order_id, OLD.production_item_id, OLD.quantity) THEN
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
        NEW.applied_tag_set_id,
        NEW.source_tag_set_id,
        NEW.target_tag_set_id,
        NEW.work_order_type,
        NEW.work_order_name,
        NEW.remark,
        NEW.flow_node_id,
        NEW.source_flow_node_id
    ) IS DISTINCT FROM (
        OLD.procedure_id,
        OLD.applied_tag_set_id,
        OLD.source_tag_set_id,
        OLD.target_tag_set_id,
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

CREATE FUNCTION validate_batch_movement_context() RETURNS TRIGGER AS $$
DECLARE
    order_type TEXT;
    order_status TEXT;
    order_source_flow_node_id TEXT;
    order_ready_quantity INT;
    submission_count INT;
    submission_quantity BIGINT;
    moved_qualified BIGINT;
    moved_rework BIGINT;
    moved_scrap BIGINT;
    moved_lost BIGINT;
    source_batch_rework_quantity INT;
    source_batch_recorded_at TIMESTAMPTZ;
    source_batch_resubmitted BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT
            work_order.work_order_type,
            work_order.status,
            work_order.source_flow_node_id,
            work_order.processed_quantity - work_order.completed_quantity
        INTO
            order_type,
            order_status,
            order_source_flow_node_id,
            order_ready_quantity
        FROM work_order
        WHERE work_order.id = NEW.work_order_id
        FOR UPDATE OF work_order;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'QC batch must reference an existing work order'
                USING ERRCODE = '23503';
        END IF;
        IF order_type NOT IN ('tag', 'purchase_receipt', 'assembly') OR order_status <> 'open' THEN
            RAISE EXCEPTION 'QC batch requires an open production work order'
                USING ERRCODE = '23514';
        END IF;
        IF order_source_flow_node_id IS NULL
            OR NEW.source_flow_node_id IS DISTINCT FROM order_source_flow_node_id THEN
            RAISE EXCEPTION 'QC batch source must match the work order source position'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.recorded_at IS NOT NULL THEN
            RAISE EXCEPTION 'new QC batch must begin in pending state'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.rework_source_batch_id IS NULL THEN
            IF order_type <> 'assembly'
                AND NEW.submitted_quantity > order_ready_quantity THEN
                RAISE EXCEPTION 'QC batch quantity exceeds the processed quantity awaiting inspection'
                    USING ERRCODE = '23514';
            END IF;
        ELSE
            IF order_type NOT IN ('tag', 'assembly') THEN
                RAISE EXCEPTION 'only production work orders can resubmit rework batches'
                    USING ERRCODE = '23514';
            END IF;
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
        END IF;
        RETURN NEW;
    END IF;

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

    IF NEW.recorded_at IS NOT NULL THEN
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

CREATE TRIGGER trg_production_movement_context
BEFORE INSERT
ON production_movement
FOR EACH ROW EXECUTE FUNCTION validate_production_movement_context();

CREATE CONSTRAINT TRIGGER trg_procedure_tag_set_integrity
AFTER INSERT OR UPDATE ON procedure_tag_set
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION validate_tag_set_integrity();

CREATE CONSTRAINT TRIGGER trg_procedure_tag_set_member_integrity
AFTER INSERT OR UPDATE OR DELETE ON procedure_tag_set_member
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION validate_tag_set_integrity();

CREATE TRIGGER trg_work_order_tag_context
BEFORE INSERT OR UPDATE OF repository_id, procedure_tag_stock_id, procedure_id,
    applied_tag_set_id, source_tag_set_id, target_tag_set_id, work_order_type, status
ON work_order
FOR EACH ROW EXECUTE FUNCTION validate_work_order_tag_context();

CREATE TRIGGER trg_work_order_movement_items
BEFORE UPDATE OF production_item_id, procedure_id, applied_tag_set_id, source_tag_set_id, target_tag_set_id, work_order_type, work_order_name, remark, flow_node_id, source_flow_node_id
ON work_order
FOR EACH ROW EXECUTE FUNCTION validate_work_order_movement_items();

CREATE TRIGGER trg_batch_movement_context
BEFORE INSERT OR UPDATE ON work_order_batch
FOR EACH ROW EXECUTE FUNCTION validate_batch_movement_context();

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

CREATE TRIGGER trg_procedure_tag_price_updated_at
BEFORE UPDATE ON procedure_tag_price
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
CREATE INDEX idx_customer_order_item_order ON customer_order_item(customer_order_id);
CREATE INDEX idx_customer_order_customer ON customer_order(customer_id);
CREATE INDEX idx_customer_order_status ON customer_order(status, id);
CREATE INDEX idx_customer_order_updated ON customer_order(updated_at DESC, id DESC);
CREATE INDEX idx_customer_order_item_product_version
    ON customer_order_item(product_id, product_version);
CREATE INDEX idx_production_plan_status ON production_plan(status, id);
CREATE INDEX idx_production_plan_item_plan
    ON production_plan_item(production_plan_id, sort_order);
CREATE INDEX idx_production_plan_item_order_item
    ON production_plan_item(customer_order_item_id);
CREATE INDEX idx_inventory_stock_component
    ON inventory_stock(
        product_id, product_version, item_type, product_bom_id, flow_node_id
    );
CREATE INDEX idx_inventory_stock_department
    ON inventory_stock(department_code, item_type);
CREATE INDEX idx_inventory_reservation_plan
    ON inventory_reservation(production_plan_id, status);
CREATE INDEX idx_inventory_reservation_item
    ON inventory_reservation(production_plan_item_id);
CREATE INDEX idx_inventory_reservation_stock
    ON inventory_reservation(inventory_stock_id, status);
CREATE INDEX idx_inventory_receipt_status
    ON inventory_receipt(department_code, status, id);
CREATE INDEX idx_inventory_transaction_stock
    ON inventory_transaction(inventory_stock_id, id);
CREATE INDEX idx_inventory_transaction_plan
    ON inventory_transaction(production_plan_id, id);
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
    ON production_movement(work_order_id, production_item_id)
    WHERE movement_type = 'assembly_input';
CREATE INDEX idx_repository_department ON repository(department_id);
CREATE INDEX idx_procedure_tag_set_member_tag
    ON procedure_tag_set_member(tag_id, tag_set_id);
CREATE INDEX idx_procedure_tag_price_procedure
    ON procedure_tag_price(
        procedure_id, product_id, product_version, origin_flow_node_id
    );
CREATE INDEX idx_procedure_tag_stock_department
    ON procedure_tag_stock(department_id, tag_set_id);
CREATE INDEX idx_production_item_order_item ON production_item(customer_order_item_id);
CREATE INDEX idx_production_item_bom ON production_item(product_bom_id);
CREATE INDEX idx_work_order_repository ON work_order(repository_id);
CREATE INDEX idx_work_order_production_item ON work_order(production_item_id);
CREATE INDEX idx_work_order_worker_activity
    ON work_order(worker_id, COALESCE(closed_at, created_at) DESC, id DESC);
CREATE INDEX idx_work_order_applied_tag_set
    ON work_order(applied_tag_set_id, id DESC);
CREATE INDEX idx_work_order_tag_stock ON work_order(procedure_tag_stock_id);
CREATE INDEX idx_work_order_repository_open ON work_order(repository_id)
    WHERE status = 'open';
CREATE INDEX idx_work_order_tag_stock_open ON work_order(procedure_tag_stock_id)
    WHERE status = 'open';
CREATE INDEX idx_work_order_item_node_status
    ON work_order(production_item_id, flow_node_id, status);
CREATE INDEX idx_work_order_tag_position
    ON work_order(
        production_item_id,
        flow_node_id,
        source_flow_node_id,
        target_tag_set_id,
        id DESC
    ) WHERE work_order_type = 'tag';
CREATE INDEX idx_work_order_pay_detail_order
    ON work_order_pay_detail(work_order_id);
CREATE INDEX idx_work_order_batch_order ON work_order_batch(work_order_id);
CREATE INDEX idx_work_order_batch_rework_source
    ON work_order_batch(rework_source_batch_id);
CREATE INDEX idx_work_order_material_repository ON work_order_material(repository_id);
CREATE INDEX idx_work_order_material_production_item ON work_order_material(production_item_id);
CREATE INDEX idx_work_order_batch_pending ON work_order_batch(id DESC, work_order_id)
    WHERE recorded_at IS NULL;
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
        source_tag_set_id,
        target_tag_set_id,
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

INSERT INTO users (username, password, department, role, permissions) VALUES
(
    'admin',
    '1',
    'sys',
    'supervisor',
    'engineering:product:view,engineering:product:add,engineering:product:edit,engineering:product:delete,order:view,order:add,order:edit,order:confirm,order:cancel,production:view,production:manage,qc:inspect,sys:user:add'
),
(
    'engineering',
    '1',
    'engineering',
    'engineer',
    'engineering:product:view,engineering:product:add,engineering:product:edit,engineering:product:delete'
),
(
    'business',
    '1',
    'business',
    'sales',
    'engineering:product:view,order:view,order:add,order:edit,order:confirm,order:cancel'
),
(
    'pmc',
    '1',
    'pmc',
    'pmc',
    'engineering:product:view,order:view,production:view'
),
(
    'stamp', '1', 'stamp', 'operator', 'production:view,production:manage'
),
(
    'cnc', '1', 'cnc', 'operator', 'production:view,production:manage'
),
(
    'polish', '1', 'polish', 'operator', 'production:view,production:manage'
),
(
    'outsource', '1', 'outsource', 'operator', 'production:view,production:manage'
),
(
    'purchasing', '1', 'purchasing', 'operator', 'production:view,production:manage'
),
(
    'qc', '1', 'qc', 'operator', 'production:view,qc:inspect'
),
(
    'assembly', '1', 'assembly', 'operator', 'production:view,production:manage'
),
(
    'finished', '1', 'finished', 'operator', 'production:view,production:manage'
),
(
    'warehouse', '1', 'warehouse', 'operator', 'production:view,production:manage'
);

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
        ('stamp', '热锻车间', '热压', 'standard'),
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
        ('polish', '手磨车间', '粗光', 'standard'),
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
  AND department.department_code = 'assembly'
  AND procedure.procedure_name = '焊接';

-- 标记只作为开工单时的名称建议，不定义固定路线或先后顺序。
INSERT INTO procedure_tag (
    procedure_id,
    tag_name
)
SELECT id, '全工序'
FROM procedure
WHERE procedure_name IN (
    '激光开料',
    '水磨',
    '溜磨',
    '冷锻',
    '冲压',
    '回火',
    '除油',
    'CNC加工',
    'NC加工',
    '钻孔',
    '激光焊接',
    '砂机',
    '自动平磨',
    '双面水磨',
    '酸洗',
    '干滚',
    '电抛',
    '振机',
    '清光',
    '蚀字',
    '电镀',
    '装包',
    '焊接'
);

INSERT INTO procedure_tag (
    procedure_id,
    tag_name
)
SELECT
    procedure.id,
    tag.tag_name
FROM procedure
CROSS JOIN (
    VALUES
        ('热压1'),
        ('热压2'),
        ('热压3')
) AS tag(tag_name)
WHERE procedure.procedure_name = '热压';

INSERT INTO procedure_tag (
    procedure_id,
    tag_name
)
SELECT
    procedure.id,
    tag.tag_name
FROM procedure
CROSS JOIN (
    VALUES
        ('粗1'),
        ('粗2'),
        ('粗3'),
        ('粗4')
) AS tag(tag_name)
WHERE procedure.procedure_name = '粗光';








INSERT INTO customer (customer_name) VALUES ('Celine');



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
    '{"schema_version": 3, "nodes": [], "edges": []}'::jsonb
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
        ('Z8711', '脚钉',            'Z8711-02', NULL,   2),
        ('Z8711', '脚钉（外购）',    'Z8711-03', '外购', 3),
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
    '{"schema_version": 3, "nodes": [], "edges": []}'::jsonb
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
