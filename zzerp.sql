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
    part_name TEXT NOT NULL,
    part_no TEXT NOT NULL,
    pcs TEXT NOT NULL,
    remark TEXT,
    sort_order INT NOT NULL CHECK (sort_order > 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_bom_part_no UNIQUE (product_id, part_no)
);

CREATE TABLE product_process_flow (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL UNIQUE REFERENCES product(id) ON DELETE CASCADE,
    flow_json JSONB NOT NULL DEFAULT '{"schema_version": 1, "nodes": [], "edges": []}'::jsonb,
    CHECK (flow_json->>'schema_version' = '1'),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jsonb_typeof(flow_json->'nodes') = 'array'),
    CHECK (jsonb_typeof(flow_json->'edges') = 'array')
);

CREATE INDEX idx_product_customer ON product(customer_name, customer_code);
CREATE INDEX idx_product_bom_product ON product_bom(product_id, sort_order);
CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);

INSERT INTO users (username, password, department, role, permissions) VALUES
(
    'admin',
    '1',
    'sys',
    'supervisor',
    'engineering:product:view,engineering:product:add,engineering:product:edit,engineering:product:delete,sys:user:add'
),
(
    'engineering',
    '1',
    'engineering',
    'engineer',
    'engineering:product:view,engineering:product:add,engineering:product:edit,engineering:product:delete'
);
