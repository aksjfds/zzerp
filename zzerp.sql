-- ============================================================
-- ZZ ERP 工程产品、BOM 与工艺路线
-- ============================================================

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    department TEXT NOT NULL,
    role TEXT NOT NULL,
    permissions TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 工程确认后的可复用产品主数据，不代表订单或生产批次。
CREATE TABLE product (
    id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    factory_code TEXT NOT NULL,
    customer_code TEXT NOT NULL,
    version INT NOT NULL DEFAULT 1 CHECK (version > 0),
    revision INT NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_factory_code UNIQUE (factory_code)
);

CREATE TABLE product_bom (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    product_version INT NOT NULL CHECK (product_version > 0),
    part_name TEXT NOT NULL,
    part_no TEXT NOT NULL,
    pcs INT NOT NULL CHECK (pcs > 0),
    remark TEXT,
    sort_order INT NOT NULL CHECK (sort_order > 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_bom_part_no UNIQUE (product_id, product_version, part_no)
);

CREATE TABLE product_process_flow (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    product_version INT NOT NULL CHECK (product_version > 0),
    flow_json JSONB NOT NULL DEFAULT '{"schema_version": 1, "nodes": [], "edges": []}'::jsonb,
    CHECK (flow_json->>'schema_version' = '1'),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jsonb_typeof(flow_json->'nodes') = 'array'),
    CHECK (jsonb_typeof(flow_json->'edges') = 'array'),
    CONSTRAINT uq_product_process_flow_version UNIQUE (product_id, product_version)
);

CREATE TABLE department (
    id BIGSERIAL PRIMARY KEY,
    department_name TEXT NOT NULL UNIQUE,
    department_code TEXT NOT NULL UNIQUE
);

CREATE TABLE workshop (
    id BIGSERIAL PRIMARY KEY,
    department_id BIGINT NOT NULL REFERENCES department(id),
    workshop_name TEXT NOT NULL,
    UNIQUE (id, department_id),
    UNIQUE (department_id, workshop_name)
);

CREATE TABLE procedure (
    id BIGSERIAL PRIMARY KEY,
    workshop_id BIGINT NOT NULL REFERENCES workshop(id),
    procedure_name TEXT NOT NULL,
    UNIQUE (workshop_id, procedure_name)
);

CREATE TABLE worker (
    id BIGSERIAL PRIMARY KEY,
    worker_name TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    workshop_id BIGINT,
    FOREIGN KEY (workshop_id, department_id) REFERENCES workshop(id, department_id)
);

CREATE TABLE customer_order (
    id BIGSERIAL PRIMARY KEY,
    customer_order_no TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'confirmed', 'planned', 'cancelled', 'closed')),
    revision INT NOT NULL DEFAULT 1 CHECK (revision > 0),
    remark TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customer_order_item (
    id BIGSERIAL PRIMARY KEY,
    customer_order_id BIGINT NOT NULL REFERENCES customer_order(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES product(id),
    product_version INT NOT NULL CHECK (product_version > 0),
    quantity INT NOT NULL CHECK (quantity > 0),
    delivery_date DATE NOT NULL,
    remark TEXT
);

CREATE TABLE production_item (
    id BIGSERIAL PRIMARY KEY,
    customer_order_item_id BIGINT NOT NULL
        REFERENCES customer_order_item(id) ON DELETE CASCADE,
    product_bom_id BIGINT REFERENCES product_bom(id),
    origin_flow_node_id TEXT NOT NULL
);

CREATE TABLE repository (
    id BIGSERIAL PRIMARY KEY,
    production_item_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    flow_node_id TEXT NOT NULL,
    source_flow_node_id TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    UNIQUE (production_item_id, flow_node_id, source_flow_node_id, department_id)
);

CREATE TABLE work_order (
    id BIGSERIAL PRIMARY KEY,
    work_order_no TEXT UNIQUE,
    repository_id BIGINT REFERENCES repository(id) ON DELETE SET NULL,
    production_item_id BIGINT NOT NULL REFERENCES production_item(id),
    procedure_id BIGINT REFERENCES procedure(id),
    flow_node_id TEXT NOT NULL,
    procedure_name TEXT NOT NULL,
    worker_id BIGINT REFERENCES worker(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    completed_quantity INT NOT NULL DEFAULT 0
        CHECK (completed_quantity >= 0 AND completed_quantity <= quantity),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'cancelled')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP
);

CREATE TABLE work_order_material (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    repository_id BIGINT REFERENCES repository(id) ON DELETE SET NULL,
    production_item_id BIGINT NOT NULL REFERENCES production_item(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    UNIQUE (work_order_id, production_item_id)
);

CREATE TABLE work_order_batch (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    submitted_quantity INT NOT NULL CHECK (submitted_quantity > 0),
    flow_node_id TEXT NOT NULL,
    qualified_quantity INT CHECK (qualified_quantity >= 0),
    rework_quantity INT CHECK (rework_quantity >= 0),
    scrap_quantity INT CHECK (scrap_quantity >= 0),
    lost_quantity INT CHECK (lost_quantity >= 0),
    qc_worker_name TEXT,
    defect_reason TEXT,
    recorded_at TIMESTAMP,
    CHECK (
        (recorded_at IS NULL AND qualified_quantity IS NULL
            AND rework_quantity IS NULL AND scrap_quantity IS NULL
            AND lost_quantity IS NULL AND qc_worker_name IS NULL)
        OR
        (recorded_at IS NOT NULL AND qualified_quantity IS NOT NULL
            AND rework_quantity IS NOT NULL AND scrap_quantity IS NOT NULL
            AND lost_quantity IS NOT NULL AND qc_worker_name IS NOT NULL
            AND qualified_quantity + rework_quantity + scrap_quantity + lost_quantity
                = submitted_quantity)
    )
);

CREATE TABLE production_movement (
    id BIGSERIAL PRIMARY KEY,
    production_item_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    source_flow_node_id TEXT,
    target_flow_node_id TEXT,
    source_department_id BIGINT REFERENCES department(id),
    target_department_id BIGINT REFERENCES department(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    movement_type TEXT NOT NULL CHECK (
        movement_type IN (
            'initial', 'process', 'assembly_input', 'assembly_output',
            'qc_qualified', 'qc_rework', 'scrap', 'lost'
        )
    ),
    work_order_id BIGINT REFERENCES work_order(id) ON DELETE SET NULL,
    work_order_batch_id BIGINT REFERENCES work_order_batch(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_product_customer ON product(customer_name, customer_code);
CREATE INDEX idx_product_bom_product ON product_bom(product_id, sort_order);
CREATE INDEX idx_product_bom_version ON product_bom(product_id, product_version, sort_order);
CREATE INDEX idx_customer_order_item_order ON customer_order_item(customer_order_id);
CREATE INDEX idx_production_movement_item_created
    ON production_movement(production_item_id, created_at);
CREATE INDEX idx_production_movement_target_department_created
    ON production_movement(target_department_id, created_at);
CREATE INDEX idx_production_movement_work_order ON production_movement(work_order_id);
CREATE INDEX idx_production_movement_batch ON production_movement(work_order_batch_id);
CREATE INDEX idx_production_movement_target_node ON production_movement(target_flow_node_id);
CREATE INDEX idx_repository_department ON repository(department_id);
CREATE INDEX idx_production_item_order_item ON production_item(customer_order_item_id);
CREATE INDEX idx_repository_production_item ON repository(production_item_id);
CREATE INDEX idx_work_order_repository ON work_order(repository_id);
CREATE INDEX idx_work_order_production_item ON work_order(production_item_id);
CREATE INDEX idx_work_order_batch_order ON work_order_batch(work_order_id);
CREATE INDEX idx_work_order_material_repository ON work_order_material(repository_id);
CREATE INDEX idx_work_order_material_production_item ON work_order_material(production_item_id);
CREATE INDEX idx_work_order_batch_pending ON work_order_batch(recorded_at)
    WHERE recorded_at IS NULL;
CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);

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
    'stamp', '1', 'stamp', 'operator', 'production:view,production:manage'
),
(
    'polish', '1', 'polish', 'operator', 'production:view,production:manage'
),
(
    'qc', '1', 'qc', 'operator', 'production:view,qc:inspect'
),
(
    'assembly', '1', 'assembly', 'operator', 'production:view,production:manage'
);

INSERT INTO department (department_name, department_code) VALUES
('工程部', 'engineering'),
('业务部', 'business'),
('冲压部门', 'stamp'),
('表面处理部门', 'polish'),
('QC部门', 'qc'),
('装配部门', 'assembly');

INSERT INTO workshop (department_id, workshop_name)
SELECT id, '激光开料车间' FROM department WHERE department_code = 'stamp';

INSERT INTO workshop (department_id, workshop_name)
SELECT id, '手磨车间' FROM department WHERE department_code = 'polish';

INSERT INTO procedure (workshop_id, procedure_name)
SELECT id, '激光开料' FROM workshop WHERE workshop_name = '激光开料车间';

INSERT INTO procedure (workshop_id, procedure_name)
SELECT id, '粗光' FROM workshop WHERE workshop_name = '手磨车间';

-- 示例产品：只包含基础信息与 BOM，故意不配置 product_process_flow。
INSERT INTO product (
    customer_name,
    product_name,
    factory_code,
    customer_code,
    version
) VALUES (
    '示例客户',
    '示例狗扣',
    'DEMO-001',
    'CUSTOMER-DEMO-001',
    1
);

INSERT INTO product_bom (
    product_id,
    product_version,
    part_name,
    part_no,
    pcs,
    remark,
    sort_order
)
SELECT id, 1, '主体', 'DEMO-001-01', 1, NULL, 1
FROM product WHERE factory_code = 'DEMO-001';

INSERT INTO product_bom (
    product_id,
    product_version,
    part_name,
    part_no,
    pcs,
    remark,
    sort_order
)
SELECT id, 1, '弹簧', 'DEMO-001-02', 1, '外购', 2
FROM product WHERE factory_code = 'DEMO-001';

-- 示例订单保持草稿状态；未配置流程的产品不能确认订单。
INSERT INTO customer_order (
    customer_order_no,
    customer_name,
    status,
    remark
) VALUES (
    'DEMO-ORDER-001',
    '示例客户',
    'draft',
    '示例草稿订单'
);

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
    100,
    CURRENT_DATE + 30,
    '示例订单明细'
FROM customer_order
JOIN product ON product.factory_code = 'DEMO-001'
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
SELECT 'QC示例工人', id, NULL FROM department WHERE department_code = 'qc';

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '装配示例工人', id, NULL FROM department WHERE department_code = 'assembly';
