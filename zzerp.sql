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
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, version),
    CONSTRAINT ck_product_version_number CHECK (version > 0)
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

-- 合并后的生产计划只关联产品，不保存产品版本或物料快照。
CREATE TABLE production_plan (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer(id),
    order_no TEXT NOT NULL,
    order_quantity INT NOT NULL,
    product_id BIGINT NOT NULL,
    production_quantity INT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    revision INT NOT NULL DEFAULT 1,
    confirmed_at TIMESTAMPTZ,
    confirmed_by TEXT,
    completed_at TIMESTAMPTZ,
    completed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_production_plan_order_no UNIQUE (order_no),
    CONSTRAINT uq_production_plan_product UNIQUE (id, product_id),
    CONSTRAINT fk_production_plan_product_customer
        FOREIGN KEY (product_id, customer_id)
        REFERENCES product(id, customer_id),
    CONSTRAINT ck_production_plan_order_quantity CHECK (order_quantity > 0),
    CONSTRAINT ck_production_plan_production_quantity CHECK (production_quantity > 0),
    CONSTRAINT ck_production_plan_revision CHECK (revision > 0),
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

CREATE TABLE production_department (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    CONSTRAINT uq_production_department_name UNIQUE (name)
);

ALTER TABLE users ADD CONSTRAINT fk_users_department
    FOREIGN KEY (department_code) REFERENCES production_department(code);
CREATE INDEX idx_users_department ON users(department_code);

-- 工单只保存安排数量和来源引用，不保存物料/路线/版本快照。
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

CREATE TABLE department_work_order (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    material_node_id TEXT NOT NULL,
    department_node_id TEXT NOT NULL,
    task_quantity INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_department_work_order_plan
        FOREIGN KEY (production_plan_id, product_id)
        REFERENCES production_plan(id, product_id) ON DELETE CASCADE,
    CONSTRAINT fk_department_work_order_route
        FOREIGN KEY (product_id, material_node_id, department_node_id)
        REFERENCES product_department_route(product_id, material_node_id, department_node_id),
    CONSTRAINT uq_department_work_order_plan_route UNIQUE (production_plan_id, material_node_id, department_node_id),
    CONSTRAINT ck_department_work_order_quantity CHECK (task_quantity > 0)
);

CREATE INDEX idx_department_work_order_route ON department_work_order(product_id, material_node_id, department_node_id);
CREATE INDEX idx_department_work_order_product ON department_work_order(product_id);

CREATE TABLE department_work_order_movement (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES department_work_order(id),
    direction TEXT NOT NULL,
    quantity BIGINT NOT NULL,
    note TEXT NOT NULL,
    request_id UUID NOT NULL,
    actor_user_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_department_movement_request UNIQUE (work_order_id, request_id),
    CONSTRAINT ck_department_movement_direction CHECK (direction IN ('receipt', 'issue')),
    CONSTRAINT ck_department_movement_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991)
);

CREATE INDEX idx_department_movement_order ON department_work_order_movement(work_order_id, created_at, id);
CREATE INDEX idx_department_movement_actor ON department_work_order_movement(actor_user_id);

CREATE FUNCTION protect_department_movement_history() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '到料和出料流水不能修改或删除' USING ERRCODE = '23514';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_department_movement_immutable
BEFORE UPDATE OR DELETE ON department_work_order_movement
FOR EACH ROW EXECUTE FUNCTION protect_department_movement_history();

CREATE TRIGGER trg_department_movement_no_truncate
BEFORE TRUNCATE ON department_work_order_movement
FOR EACH STATEMENT EXECUTE FUNCTION protect_department_movement_history();

CREATE FUNCTION protect_recorded_department_work_order() RETURNS TRIGGER AS $$
BEGIN
    IF ROW(NEW.production_plan_id, NEW.product_id, NEW.material_node_id, NEW.department_node_id, NEW.task_quantity)
        IS DISTINCT FROM ROW(OLD.production_plan_id, OLD.product_id, OLD.material_node_id, OLD.department_node_id, OLD.task_quantity)
        AND EXISTS (SELECT 1 FROM department_work_order_movement WHERE work_order_id = OLD.id) THEN
        RAISE EXCEPTION '已有到料或出料流水，不能修改工单来源或任务数量' USING ERRCODE = '23514';
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

CREATE INDEX idx_production_plan_product ON production_plan(product_id);

CREATE INDEX idx_production_plan_updated ON production_plan(updated_at DESC, id DESC);

CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);

CREATE INDEX idx_user_sessions_user ON user_sessions(user_id);

-- 初始化数据：基础资料及可删除的开发示例

INSERT INTO production_department (code, name) VALUES
('stamp', '冲压部'), ('cnc', 'CNC部'), ('grinding', '磨房'),
('outsource', '委外部'), ('vibration', '震机部'), ('laser', '激光部'), ('assembly', '装配部'),
('purchase', '外购部'), ('finished', '成品部');

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

-- 工程示例仅保留 Z8737，末尾初始化其草稿计划及部门工单。
INSERT INTO product (customer_id, product_name, factory_code, customer_code, version)
SELECT customer.id, 'L24.4 椭圆搭扣', 'Z8737', 'FIG6850', 1
FROM customer
WHERE customer.customer_name = 'Celine';

INSERT INTO product_version (product_id, version)
SELECT id, 1 FROM product WHERE factory_code = 'Z8737';

INSERT INTO product_bom (product_id, product_version, part_name, part_no, pcs, remark, sort_order)
SELECT product.id, 1, component.part_name, component.part_no, 1, NULL, component.sort_order
FROM product
CROSS JOIN (VALUES
    ('主体', 'Z8737-01', 1),
    ('过桥', 'Z8737-02', 2),
    ('冬菇头', 'Z8737-03', 3)
) AS component(part_name, part_no, sort_order)
WHERE product.factory_code = 'Z8737';

-- 三路配件汇合到同一激光节点，从该节点起以装配体安排。
INSERT INTO product_process_flow (product_id, product_version, flow_json)
SELECT product.id, 1, jsonb_build_object(
    'schema_version', 8,
    'nodes', jsonb_build_array(
        jsonb_build_object('id', 'part-body', 'type', 'part', 'x', 0, 'y', 0,
            'label', body.part_no || ' · ' || body.part_name, 'bom_item_id', body.id),
        jsonb_build_object('id', 'part-bridge', 'type', 'part', 'x', 0, 'y', 250,
            'label', bridge.part_no || ' · ' || bridge.part_name, 'bom_item_id', bridge.id),
        jsonb_build_object('id', 'part-head', 'type', 'part', 'x', 0, 'y', 500,
            'label', head.part_no || ' · ' || head.part_name, 'bom_item_id', head.id),
        jsonb_build_object('id', 'stamp-body', 'type', 'department', 'x', 500, 'y', 0,
            'label', '冲压部', 'department_code', 'stamp'),
        jsonb_build_object('id', 'cnc-body', 'type', 'department', 'x', 1000, 'y', 0,
            'label', 'CNC部', 'department_code', 'cnc'),
        jsonb_build_object('id', 'stamp-bridge', 'type', 'department', 'x', 500, 'y', 250,
            'label', '冲压部', 'department_code', 'stamp'),
        jsonb_build_object('id', 'purchase-head', 'type', 'department', 'x', 500, 'y', 500,
            'label', '外购部', 'department_code', 'purchase'),
        jsonb_build_object('id', 'laser-merge', 'type', 'department', 'x', 1500, 'y', 250,
            'label', '激光部', 'department_code', 'laser'),
        jsonb_build_object('id', 'vibration-next', 'type', 'department', 'x', 2000, 'y', 250,
            'label', '震机部', 'department_code', 'vibration'),
        jsonb_build_object('id', 'outsource-next', 'type', 'department', 'x', 2500, 'y', 250,
            'label', '委外部', 'department_code', 'outsource'),
        jsonb_build_object('id', 'finished-end', 'type', 'department', 'x', 3000, 'y', 250,
            'label', '成品部', 'department_code', 'finished')
    ),
    'edges', jsonb_build_array(
        jsonb_build_object('id', 'line-1', 'edge_type', 'polyline',
            'source_node_id', 'part-body', 'target_node_id', 'stamp-body'),
        jsonb_build_object('id', 'line-2', 'edge_type', 'polyline',
            'source_node_id', 'stamp-body', 'target_node_id', 'cnc-body'),
        jsonb_build_object('id', 'line-3', 'edge_type', 'polyline',
            'source_node_id', 'cnc-body', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'line-4', 'edge_type', 'polyline',
            'source_node_id', 'part-bridge', 'target_node_id', 'stamp-bridge'),
        jsonb_build_object('id', 'line-5', 'edge_type', 'polyline',
            'source_node_id', 'stamp-bridge', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'line-6', 'edge_type', 'polyline',
            'source_node_id', 'part-head', 'target_node_id', 'purchase-head'),
        jsonb_build_object('id', 'line-7', 'edge_type', 'polyline',
            'source_node_id', 'purchase-head', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'line-8', 'edge_type', 'polyline',
            'source_node_id', 'laser-merge', 'target_node_id', 'vibration-next'),
        jsonb_build_object('id', 'line-9', 'edge_type', 'polyline',
            'source_node_id', 'vibration-next', 'target_node_id', 'outsource-next'),
        jsonb_build_object('id', 'line-10', 'edge_type', 'polyline',
            'source_node_id', 'outsource-next', 'target_node_id', 'finished-end')
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

-- 当前路线投影：汇合前四项配件安排，汇合起四项装配体安排。
INSERT INTO product_department_route (product_id, material_node_id, department_node_id, department_code)
SELECT product.id, route.material_node_id, route.department_node_id, route.department_code
FROM product
CROSS JOIN (VALUES
    ('part-body', 'stamp-body', 'stamp'),
    ('part-body', 'cnc-body', 'cnc'),
    ('part-bridge', 'stamp-bridge', 'stamp'),
    ('part-head', 'purchase-head', 'purchase'),
    ('laser-merge', 'laser-merge', 'laser'),
    ('laser-merge', 'vibration-next', 'vibration'),
    ('laser-merge', 'outsource-next', 'outsource'),
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

-- Z8737 示例草稿计划：订单3000件，安排新生产4000件。
INSERT INTO production_plan (
    customer_id, order_no, order_quantity, product_id, production_quantity, status, revision
)
SELECT customer_id, 'ORDER-Z8737-0001', 3000, id, 4000, 'draft', 1
FROM product
WHERE factory_code = 'Z8737';

-- 使用当前路线投影生成8张部门工单；装配体按生产数量，不累加组成配件用量。
INSERT INTO department_work_order (
    production_plan_id, product_id, material_node_id, department_node_id, task_quantity
)
SELECT plan.id, plan.product_id, route.material_node_id, route.department_node_id,
       plan.production_quantity * CASE WHEN COUNT(part.id) > 1 THEN 1 ELSE MAX(part.pcs) END
FROM production_plan AS plan
JOIN product_department_route AS route ON route.product_id = plan.product_id
JOIN product_route_component AS component
    ON component.product_id = route.product_id
    AND component.material_node_id = route.material_node_id
    AND component.department_node_id = route.department_node_id
JOIN product_bom AS part ON part.id = component.product_bom_id
WHERE plan.order_no = 'ORDER-Z8737-0001'
GROUP BY plan.id, plan.product_id, plan.production_quantity,
         route.material_node_id, route.department_node_id;

COMMIT;

