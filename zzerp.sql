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

CREATE TABLE repository (
    id BIGSERIAL PRIMARY KEY,
    customer_order_item_id BIGINT NOT NULL
        REFERENCES customer_order_item(id) ON DELETE CASCADE,
    product_bom_id BIGINT NOT NULL REFERENCES product_bom(id),
    flow_node_id TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    quantity INT NOT NULL CHECK (quantity > 0)
);

CREATE INDEX idx_product_customer ON product(customer_name, customer_code);
CREATE INDEX idx_product_bom_product ON product_bom(product_id, sort_order);
CREATE INDEX idx_product_bom_version ON product_bom(product_id, product_version, sort_order);
CREATE INDEX idx_customer_order_item_order ON customer_order_item(customer_order_id);
CREATE INDEX idx_repository_department ON repository(department_id);
CREATE INDEX idx_repository_order_item ON repository(customer_order_item_id);
CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);

INSERT INTO users (username, password, department, role, permissions) VALUES
(
    'admin',
    '1',
    'sys',
    'supervisor',
    'engineering:product:view,engineering:product:add,engineering:product:edit,engineering:product:delete,order:view,order:add,order:edit,order:confirm,order:cancel,production:view,sys:user:add'
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
    'stamp', '1', 'stamp', 'operator', 'production:view'
),
(
    'polish', '1', 'polish', 'operator', 'production:view'
),
(
    'qc', '1', 'qc', 'operator', 'production:view'
),
(
    'assembly', '1', 'assembly', 'operator', 'production:view'
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
