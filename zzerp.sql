-- MES 开发数据库唯一破坏性重建基线。
-- 保留工程设计、统一生产计划及账号认证。
-- 配件节点和部门节点通过连线形成当前生产路线。

BEGIN;

DROP SCHEMA public CASCADE;

CREATE SCHEMA public;

GRANT ALL ON SCHEMA public TO CURRENT_USER;

GRANT USAGE ON SCHEMA public TO PUBLIC;

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
    user_id BIGINT NOT NULL,
    token_hash TEXT NOT NULL,
    csrf_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_sessions_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_user_sessions_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE
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
    customer_id BIGINT NOT NULL,
    product_name TEXT NOT NULL,
    factory_code TEXT NOT NULL,
    customer_code TEXT NOT NULL,
    revision INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_factory_code UNIQUE (factory_code),
    CONSTRAINT uq_product_customer_context UNIQUE (id, customer_id),
    CONSTRAINT ck_product_revision CHECK (revision > 0),
    CONSTRAINT fk_product_customer FOREIGN KEY (customer_id)
        REFERENCES customer(id)
);

CREATE TABLE product_appearance (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    appearance_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_product_appearance_product FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE,
    CONSTRAINT uq_product_appearance_name UNIQUE (product_id, appearance_name),
    CONSTRAINT uq_product_appearance_product UNIQUE (product_id, id),
    CONSTRAINT ck_product_appearance_name CHECK (appearance_name ~ '[^[:space:]]')
);

CREATE TABLE product_bom (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    part_name TEXT NOT NULL,
    part_no TEXT NOT NULL,
    pcs INT NOT NULL,
    remark TEXT,
    sort_order INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_bom_product UNIQUE (id, product_id),
    CONSTRAINT uq_product_bom_part_no UNIQUE (product_id, part_no),
    CONSTRAINT uq_product_bom_sort_order
        UNIQUE (product_id, sort_order) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_product_bom_pcs CHECK (pcs > 0),
    CONSTRAINT ck_product_bom_sort_order CHECK (sort_order > 0),
    CONSTRAINT fk_product_bom_product FOREIGN KEY (product_id)
        REFERENCES product(id) ON DELETE CASCADE
);

CREATE TABLE product_process_flow (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    appearance_id BIGINT NOT NULL,
    flow_json JSONB NOT NULL DEFAULT '{"schema_version": 8, "nodes": [], "edges": []}'::jsonb,
    draft_flow_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_process_flow_structure CHECK (
        (jsonb_typeof(flow_json) = 'object'
            AND jsonb_typeof(flow_json->'schema_version') = 'number'
            AND flow_json->>'schema_version' = '8'
            AND jsonb_typeof(flow_json->'nodes') = 'array'
            AND jsonb_typeof(flow_json->'edges') = 'array') IS TRUE
    ),
    CONSTRAINT ck_process_flow_draft_structure CHECK (
        draft_flow_json IS NULL OR (jsonb_typeof(draft_flow_json) = 'object'
            AND jsonb_typeof(draft_flow_json->'schema_version') = 'number'
            AND draft_flow_json->>'schema_version' = '8'
            AND jsonb_typeof(draft_flow_json->'nodes') = 'array'
            AND jsonb_typeof(draft_flow_json->'edges') = 'array') IS TRUE
    ),
    CONSTRAINT fk_product_process_flow_appearance
        FOREIGN KEY (product_id, appearance_id)
        REFERENCES product_appearance(product_id, id) ON DELETE CASCADE,
    CONSTRAINT uq_product_process_flow_appearance UNIQUE (product_id, appearance_id),
    CONSTRAINT fk_product_process_flow_product FOREIGN KEY (product_id)
        REFERENCES product(id) ON DELETE CASCADE
);

-- 计划头保存订单和状态，产品明细分别保存数量，不保存版本或物料快照。
CREATE TABLE production_plan (
    id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    order_no TEXT NOT NULL,
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
    CONSTRAINT ck_production_plan_status
        CHECK (status IN ('draft', 'confirmed', 'cancelled', 'completed')),
    CONSTRAINT ck_production_plan_confirmation CHECK (
        (status IN ('confirmed', 'completed') AND confirmed_at IS NOT NULL AND confirmed_by IS NOT NULL)
        OR status IN ('draft', 'cancelled')
    ),
    CONSTRAINT ck_production_plan_completion CHECK (
        (status = 'completed' AND completed_at IS NOT NULL AND completed_by IS NOT NULL)
        OR (status <> 'completed' AND completed_at IS NULL AND completed_by IS NULL)
    ),
    CONSTRAINT fk_production_plan_customer FOREIGN KEY (customer_id)
        REFERENCES customer(id)
);

CREATE TABLE production_plan_item (
    production_plan_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    appearance_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    order_quantity INT NOT NULL,
    production_quantity INT NOT NULL,
    PRIMARY KEY (production_plan_id, product_id, appearance_id),
    CONSTRAINT fk_production_plan_item_plan FOREIGN KEY (production_plan_id, customer_id)
        REFERENCES production_plan(id, customer_id) ON DELETE CASCADE,
    CONSTRAINT fk_production_plan_item_product_customer FOREIGN KEY (product_id, customer_id)
        REFERENCES product(id, customer_id),
    CONSTRAINT ck_production_plan_item_order_quantity CHECK (order_quantity > 0),
    CONSTRAINT ck_production_plan_item_production_quantity CHECK (production_quantity > 0),
    CONSTRAINT fk_production_plan_item_appearance FOREIGN KEY (product_id, appearance_id)
        REFERENCES product_appearance(product_id, id)
);

CREATE TABLE production_department (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    CONSTRAINT uq_production_department_name UNIQUE (name)
);

ALTER TABLE users ADD CONSTRAINT fk_users_department
    FOREIGN KEY (department_code) REFERENCES production_department(code);

-- 当前正式图的查询投影，由工程模块维护，不保存历史或版本快照。
CREATE TABLE product_department_route (
    product_id BIGINT NOT NULL,
    appearance_id BIGINT NOT NULL,
    material_node_id TEXT NOT NULL,
    department_node_id TEXT NOT NULL,
    department_code TEXT NOT NULL,
    PRIMARY KEY (product_id, appearance_id, material_node_id, department_node_id),
    CONSTRAINT fk_product_department_route_product FOREIGN KEY (product_id)
        REFERENCES product(id) ON DELETE CASCADE,
    CONSTRAINT fk_product_department_route_department FOREIGN KEY (department_code)
        REFERENCES production_department(code),
    CONSTRAINT fk_product_department_route_appearance FOREIGN KEY (product_id, appearance_id)
        REFERENCES product_appearance(product_id, id) ON DELETE CASCADE
);

CREATE TABLE product_route_component (
    product_id BIGINT NOT NULL,
    appearance_id BIGINT NOT NULL,
    material_node_id TEXT NOT NULL,
    department_node_id TEXT NOT NULL,
    product_bom_id BIGINT NOT NULL,
    PRIMARY KEY (product_id, appearance_id, material_node_id, department_node_id, product_bom_id),
    CONSTRAINT fk_product_route_component_route
        FOREIGN KEY (product_id, appearance_id, material_node_id, department_node_id)
        REFERENCES product_department_route(product_id, appearance_id, material_node_id, department_node_id) ON DELETE CASCADE,
    CONSTRAINT fk_product_route_component_bom
        FOREIGN KEY (product_bom_id, product_id) REFERENCES product_bom(id, product_id)
);

-- 工单只保存安排数量和来源引用，不保存物料/路线/版本快照。
CREATE TABLE department_work_order (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    appearance_id BIGINT NOT NULL,
    material_node_id TEXT NOT NULL,
    department_node_id TEXT NOT NULL,
    task_quantity INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_department_work_order_plan
        FOREIGN KEY (production_plan_id, product_id, appearance_id)
        REFERENCES production_plan_item(production_plan_id, product_id, appearance_id) ON DELETE CASCADE,
    CONSTRAINT fk_department_work_order_route
        FOREIGN KEY (product_id, appearance_id, material_node_id, department_node_id)
        REFERENCES product_department_route(product_id, appearance_id, material_node_id, department_node_id),
    CONSTRAINT uq_department_work_order_plan_route UNIQUE (production_plan_id, product_id, appearance_id, material_node_id, department_node_id),
    CONSTRAINT ck_department_work_order_quantity CHECK (task_quantity > 0)
);

CREATE TABLE department_work_order_movement (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL,
    direction TEXT NOT NULL,
    quantity BIGINT NOT NULL,
    note TEXT NOT NULL,
    request_id UUID NOT NULL,
    actor_user_id BIGINT NOT NULL,
    receipt_source TEXT,
    ticket_id BIGINT,
    input_material_node_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_department_movement_request UNIQUE (work_order_id, request_id),
    CONSTRAINT ck_department_movement_direction CHECK (direction IN ('receipt', 'issue')),
    CONSTRAINT ck_department_movement_quantity CHECK (quantity > 0 AND quantity <= 9007199254740991),
    CONSTRAINT ck_unattributed_receipt_note CHECK (receipt_source IS DISTINCT FROM 'external' OR note ~ '[^[:space:]]'),
    CONSTRAINT ck_department_movement_source CHECK (
        (direction = 'issue' AND receipt_source IS NULL AND ticket_id IS NULL AND input_material_node_id IS NULL)
        OR (direction = 'receipt' AND receipt_source IS NOT NULL AND input_material_node_id IS NOT NULL
            AND ((receipt_source = 'external' AND ticket_id IS NULL) OR (receipt_source = 'ticket' AND ticket_id IS NOT NULL)))),
    CONSTRAINT fk_department_movement_order FOREIGN KEY (work_order_id)
        REFERENCES department_work_order(id),
    CONSTRAINT fk_department_movement_actor FOREIGN KEY (actor_user_id)
        REFERENCES users(id)
);

CREATE TABLE department_handoff_ticket (
    id BIGSERIAL PRIMARY KEY,
    issue_movement_id BIGINT NOT NULL,
    target_work_order_id BIGINT NOT NULL,
    CONSTRAINT uq_handoff_issue UNIQUE (issue_movement_id),
    CONSTRAINT fk_handoff_issue FOREIGN KEY (issue_movement_id)
        REFERENCES department_work_order_movement(id),
    CONSTRAINT fk_handoff_target FOREIGN KEY (target_work_order_id)
        REFERENCES department_work_order(id)
);

ALTER TABLE department_work_order_movement
ADD CONSTRAINT fk_department_movement_ticket
FOREIGN KEY (ticket_id) REFERENCES department_handoff_ticket(id);

CREATE TABLE department_movement_receipt_link (
    issue_movement_id BIGINT NOT NULL,
    receipt_movement_id BIGINT NOT NULL,
    PRIMARY KEY (issue_movement_id, receipt_movement_id),
    CONSTRAINT fk_movement_link_issue FOREIGN KEY (issue_movement_id)
        REFERENCES department_work_order_movement(id),
    CONSTRAINT fk_movement_link_receipt FOREIGN KEY (receipt_movement_id)
        REFERENCES department_work_order_movement(id)
);

CREATE FUNCTION validate_handoff_ticket() RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM department_work_order_movement AS issue
        JOIN department_work_order AS source ON source.id = issue.work_order_id
        JOIN department_work_order AS target ON target.id = NEW.target_work_order_id
        WHERE issue.id = NEW.issue_movement_id AND issue.direction = 'issue'
            AND source.production_plan_id = target.production_plan_id AND source.product_id = target.product_id AND source.appearance_id = target.appearance_id
    ) THEN
        RAISE EXCEPTION '交接票必须引用同计划的出料和目标工单' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$function$;
CREATE TRIGGER trg_validate_handoff_ticket BEFORE INSERT ON department_handoff_ticket
FOR EACH ROW EXECUTE FUNCTION validate_handoff_ticket();

CREATE FUNCTION validate_movement_receipt_link() RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
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
$function$;
CREATE TRIGGER trg_validate_movement_receipt_link BEFORE INSERT ON department_movement_receipt_link
FOR EACH ROW EXECUTE FUNCTION validate_movement_receipt_link();

CREATE FUNCTION validate_ticket_receipt() RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
DECLARE
    issue_quantity BIGINT;
    received_quantity NUMERIC;
    target_order_id BIGINT;
    source_material_id TEXT;
BEGIN
    IF NEW.receipt_source IS DISTINCT FROM 'ticket' THEN
        RETURN NEW;
    END IF;

    SELECT issue.quantity, ticket.target_work_order_id, source.material_node_id
    INTO issue_quantity, target_order_id, source_material_id
    FROM department_handoff_ticket AS ticket
    JOIN department_work_order_movement AS issue ON issue.id = ticket.issue_movement_id
    JOIN department_work_order AS source ON source.id = issue.work_order_id
    WHERE ticket.id = NEW.ticket_id
    FOR UPDATE OF ticket;

    IF NOT FOUND THEN
        RAISE EXCEPTION '交接票不存在' USING ERRCODE = '23514';
    END IF;
    IF target_order_id <> NEW.work_order_id
        OR source_material_id IS DISTINCT FROM NEW.input_material_node_id THEN
        RAISE EXCEPTION '到料必须引用发给本工单的交接票及来源物料' USING ERRCODE = '23514';
    END IF;
    IF NEW.quantity < issue_quantity AND NEW.note !~ '[^[:space:]]' THEN
        RAISE EXCEPTION '登记到料数量小于交接票数量，必须填写备注' USING ERRCODE = '23514';
    END IF;

    SELECT COALESCE(SUM(quantity), 0) INTO received_quantity
    FROM department_work_order_movement WHERE ticket_id = NEW.ticket_id;
    IF received_quantity + NEW.quantity > issue_quantity THEN
        RAISE EXCEPTION '累计交接到料不能超过上游出料数量' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$function$;
CREATE TRIGGER trg_validate_ticket_receipt BEFORE INSERT ON department_work_order_movement
FOR EACH ROW EXECUTE FUNCTION validate_ticket_receipt();

CREATE FUNCTION protect_department_movement_history() RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
BEGIN
    RAISE EXCEPTION '到料和出料流水不能修改或删除' USING ERRCODE = '23514';
END;
$function$;

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

CREATE FUNCTION protect_recorded_department_work_order() RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
BEGIN
    IF ROW(NEW.production_plan_id, NEW.product_id, NEW.appearance_id, NEW.material_node_id, NEW.department_node_id, NEW.task_quantity)
        IS DISTINCT FROM ROW(OLD.production_plan_id, OLD.product_id, OLD.appearance_id, OLD.material_node_id, OLD.department_node_id, OLD.task_quantity)
        AND EXISTS (SELECT 1 FROM department_work_order_movement WHERE work_order_id = OLD.id) THEN
        RAISE EXCEPTION '已有到料或出料流水，不能修改工单来源或任务数量' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$function$;

CREATE TRIGGER trg_recorded_department_work_order
BEFORE UPDATE ON department_work_order
FOR EACH ROW EXECUTE FUNCTION protect_recorded_department_work_order();

-- 表约束补充


-- 通用更新时间函数

CREATE FUNCTION set_updated_at() RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $function$
BEGIN
    NEW.updated_at = clock_timestamp();
    RETURN NEW;
END;
$function$;

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

-- 查询索引：依据筛选、分页排序、聚合及外键引用路径配置。

CREATE INDEX idx_production_plan_item_product ON production_plan_item(product_id, appearance_id);

CREATE INDEX idx_users_department ON users(department_code);

CREATE INDEX idx_product_department_route_department ON product_department_route(department_code, product_id);

CREATE INDEX idx_product_route_component_bom ON product_route_component(product_bom_id);

CREATE INDEX idx_department_work_order_route ON department_work_order(product_id, appearance_id, material_node_id, department_node_id);

CREATE INDEX idx_department_movement_actor ON department_work_order_movement(actor_user_id);

CREATE INDEX idx_department_movement_ticket ON department_work_order_movement(ticket_id) INCLUDE (quantity)
    WHERE ticket_id IS NOT NULL;

CREATE INDEX idx_handoff_target ON department_handoff_ticket(target_work_order_id, id);

CREATE INDEX idx_movement_link_receipt ON department_movement_receipt_link(receipt_movement_id);

CREATE INDEX idx_customer_name_trgm
    ON customer USING GIN (customer_name gin_trgm_ops);

CREATE INDEX idx_product_customer ON product(customer_id, updated_at DESC, id DESC);

CREATE INDEX idx_product_product_name_trgm
    ON product USING GIN (product_name gin_trgm_ops);

CREATE INDEX idx_product_factory_code_trgm
    ON product USING GIN (factory_code gin_trgm_ops);

CREATE INDEX idx_product_customer_code_trgm
    ON product USING GIN (customer_code gin_trgm_ops);

CREATE INDEX idx_product_updated ON product(updated_at DESC, id DESC);

CREATE INDEX idx_product_bom_product ON product_bom(product_id, sort_order);

CREATE INDEX idx_production_plan_customer ON production_plan(customer_id);

CREATE INDEX idx_production_plan_updated ON production_plan(updated_at DESC, id DESC);

CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);

CREATE INDEX idx_user_sessions_user ON user_sessions(user_id);

-- 固定UTC后截断，保持同秒ID顺序并避免会话时区影响表达式索引。
CREATE INDEX idx_department_movement_order_time
    ON department_work_order_movement(work_order_id, date_trunc('second', created_at AT TIME ZONE 'UTC'), id)
    INCLUDE (direction, input_material_node_id, quantity);

CREATE INDEX idx_department_movement_time
    ON department_work_order_movement(date_trunc('second', created_at AT TIME ZONE 'UTC'), id);

CREATE INDEX idx_department_movement_input_time
    ON department_work_order_movement(work_order_id, input_material_node_id, date_trunc('second', created_at AT TIME ZONE 'UTC'), id)
    WHERE direction = 'receipt';

CREATE INDEX idx_production_plan_order_no_trgm
    ON production_plan USING GIN (order_no gin_trgm_ops);

-- 初始化数据：基础资料及可删除的开发示例

INSERT INTO production_department (code, name) VALUES
('stamp', '冲压部'), ('cnc', 'CNC部'), ('grinding', '磨房'),
('outsource', '委外部'), ('vibration', '震机部'), ('laser', '激光部'), ('assembly', '装配部'),
('purchase', '外购部'), ('finished', '成品部');

-- 开发账号密码为 1；仅保存独立盐的 PBKDF2 哈希，不接受明文密码记录。
INSERT INTO users (username, password, is_system, role, department_code, permissions) VALUES
('engineering', 'pbkdf2_sha256$600000$ed5ad952d0aa1ee4731d7ad0d1593af7$a9e5ed8434be44a3c28740be8ff49482f98ab7887a1ef083928e20f908c183a3', FALSE, 'engineer', NULL, 'engineering:product:view,engineering:product:add,engineering:product:edit'),
('business', 'pbkdf2_sha256$600000$edff80b45adf39a088ebf1a157195202$af44f671e577b79c27732e177671a3c152b98db8be881362e179e998522f360a', FALSE, 'planner', NULL, 'engineering:product:view,plan:view,plan:add,plan:edit,plan:confirm,plan:cancel'),
('stamp', 'pbkdf2_sha256$600000$fc3163d0286970e09ff13bac97089c9a$3dd754d86181ff65efd2a70a66be523970fb92f1162a3ed3aef4eb6f1669d78a', FALSE, 'production', 'stamp', 'department:work-order:view,department:work-order:operate'),
('cnc', 'pbkdf2_sha256$600000$002437879a63b803e5e4eb33cb03261b$9e960cf82a540a2f80651e7d38cc426f8adeab44e58cad091a1d3992a5485b21', FALSE, 'production', 'cnc', 'department:work-order:view,department:work-order:operate'),
('grinding', 'pbkdf2_sha256$600000$32f9edca4a3310e80a81608b4ee85413$23042f5da83f6a3acf96c4f28066a4eb5458939bef731ae6966fc5c6f239043a', FALSE, 'production', 'grinding', 'department:work-order:view,department:work-order:operate'),
('outsource', 'pbkdf2_sha256$600000$00e9d0b1785152f36f1dc2139c2dc52c$a285b4ecfb5e0f0e967956611bdc6dc43bd7fe4801abafc4a122e23890f12d4d', FALSE, 'production', 'outsource', 'department:work-order:view,department:work-order:operate'),
('vibration', 'pbkdf2_sha256$600000$6d149bc2b07f42bdb37101480e8fc517$4e2c1ea158d9bbbde2dffbde25c1062f798be3aecb8b32df910d078441772c68', FALSE, 'production', 'vibration', 'department:work-order:view,department:work-order:operate'),
('laser', 'pbkdf2_sha256$600000$c2c307e843872729263771fec2deb97c$0c132f64ee218b0385f2950542ca20acda5d6c767d51f1a0e2995765daf4099c', FALSE, 'production', 'laser', 'department:work-order:view,department:work-order:operate'),
('assembly', 'pbkdf2_sha256$600000$1e8c6eb34c8c060ddbfe6a5cde6670b7$bb32c761f56ca4e86a1e6e9eed687bee770bff66bce99d28303aa3463da7e0cf', FALSE, 'production', 'assembly', 'department:work-order:view,department:work-order:operate'),
('purchase', 'pbkdf2_sha256$600000$40b9598e596e574fb26c82d7b5e75828$ab4ef8c103856e43b2824bb0d35f75df484e4ade7a3269db958e16343b9e95d5', FALSE, 'production', 'purchase', 'department:work-order:view,department:work-order:operate'),
('finished', 'pbkdf2_sha256$600000$98f0574c6dbf5b71cba0ef21dba72a59$5880c2401af0200df4b865cee34d1c05f685e44a927a98235e0263cc1418eb81', FALSE, 'production', 'finished', 'department:work-order:view,department:work-order:operate');

-- 工程示例包含 Z8737 及下方的 Z8738，末尾初始化草稿计划及部门工单。
INSERT INTO customer (customer_name) VALUES ('Celine');

INSERT INTO product (customer_id, product_name, factory_code, customer_code)
SELECT customer.id, 'L24.4 椭圆搭扣', 'Z8737', 'FIG6850'
FROM customer
WHERE customer.customer_name = 'Celine';

INSERT INTO product_appearance (product_id, appearance_name)
SELECT id, '标准外观' FROM product WHERE factory_code = 'Z8737';

INSERT INTO product_bom (product_id, part_name, part_no, pcs, remark, sort_order)
SELECT product.id, component.part_name, component.part_no, 1, NULL, component.sort_order
FROM product
CROSS JOIN (VALUES
    ('主体', 'Z8737-01', 1),
    ('过桥', 'Z8737-02', 2),
    ('冬菇头', 'Z8737-03', 3)
) AS component(part_name, part_no, sort_order)
WHERE product.factory_code = 'Z8737';

-- 三路配件独立加工后汇合到同一激光节点，汇合后使用装配体身份。
INSERT INTO product_process_flow (product_id, appearance_id, flow_json)
SELECT product.id, (SELECT id FROM product_appearance WHERE product_id = product.id), jsonb_build_object(
    'schema_version', 8,
    'nodes', jsonb_build_array(
        jsonb_build_object('id', 'part-body', 'type', 'part', 'x', 0, 'y', 0,
            'label', body.part_no || ' · ' || body.part_name, 'bom_item_id', body.id),
        jsonb_build_object('id', 'part-bridge', 'type', 'part', 'x', 0, 'y', 500,
            'label', bridge.part_no || ' · ' || bridge.part_name, 'bom_item_id', bridge.id),
        jsonb_build_object('id', 'part-head', 'type', 'part', 'x', 0, 'y', 1000,
            'label', head.part_no || ' · ' || head.part_name, 'bom_item_id', head.id),
        jsonb_build_object('id', 'stamp-body', 'type', 'department', 'x', 500, 'y', 0,
            'label', '冲压部', 'department_code', 'stamp'),
        jsonb_build_object('id', 'cnc-body', 'type', 'department', 'x', 1000, 'y', 0,
            'label', 'CNC部', 'department_code', 'cnc'),
        jsonb_build_object('id', 'grinding-body-before', 'type', 'department', 'x', 1500, 'y', 0,
            'label', '磨房', 'department_code', 'grinding'),
        jsonb_build_object('id', 'outsource-body', 'type', 'department', 'x', 2000, 'y', 0,
            'label', '委外部', 'department_code', 'outsource'),
        jsonb_build_object('id', 'grinding-body-after', 'type', 'department', 'x', 2500, 'y', 0,
            'label', '磨房', 'department_code', 'grinding'),
        jsonb_build_object('id', 'stamp-bridge', 'type', 'department', 'x', 500, 'y', 500,
            'label', '冲压部', 'department_code', 'stamp'),
        jsonb_build_object('id', 'cnc-bridge', 'type', 'department', 'x', 1000, 'y', 500,
            'label', 'CNC部', 'department_code', 'cnc'),
        jsonb_build_object('id', 'grinding-bridge', 'type', 'department', 'x', 1500, 'y', 500,
            'label', '磨房', 'department_code', 'grinding'),
        jsonb_build_object('id', 'purchase-head', 'type', 'department', 'x', 500, 'y', 1000,
            'label', '外购部', 'department_code', 'purchase'),
        jsonb_build_object('id', 'grinding-head', 'type', 'department', 'x', 1000, 'y', 1000,
            'label', '磨房', 'department_code', 'grinding'),
        jsonb_build_object('id', 'laser-merge', 'type', 'department', 'x', 3000, 'y', 500,
            'label', '激光部', 'department_code', 'laser'),
        jsonb_build_object('id', 'grinding-assembly', 'type', 'department', 'x', 3500, 'y', 500,
            'label', '磨房', 'department_code', 'grinding'),
        jsonb_build_object('id', 'vibration-next', 'type', 'department', 'x', 4000, 'y', 500,
            'label', '震机部', 'department_code', 'vibration'),
        jsonb_build_object('id', 'outsource-next', 'type', 'department', 'x', 4500, 'y', 500,
            'label', '委外部', 'department_code', 'outsource'),
        jsonb_build_object('id', 'finished-end', 'type', 'department', 'x', 5000, 'y', 500,
            'label', '成品部', 'department_code', 'finished')
    ),
    'edges', jsonb_build_array(
        jsonb_build_object('id', 'line-1', 'edge_type', 'polyline',
            'source_node_id', 'part-body', 'target_node_id', 'stamp-body'),
        jsonb_build_object('id', 'line-2', 'edge_type', 'polyline',
            'source_node_id', 'stamp-body', 'target_node_id', 'cnc-body'),
        jsonb_build_object('id', 'line-3', 'edge_type', 'polyline',
            'source_node_id', 'cnc-body', 'target_node_id', 'grinding-body-before'),
        jsonb_build_object('id', 'line-4', 'edge_type', 'polyline',
            'source_node_id', 'grinding-body-before', 'target_node_id', 'outsource-body'),
        jsonb_build_object('id', 'line-5', 'edge_type', 'polyline',
            'source_node_id', 'outsource-body', 'target_node_id', 'grinding-body-after'),
        jsonb_build_object('id', 'line-6', 'edge_type', 'polyline',
            'source_node_id', 'grinding-body-after', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'line-7', 'edge_type', 'polyline',
            'source_node_id', 'part-bridge', 'target_node_id', 'stamp-bridge'),
        jsonb_build_object('id', 'line-8', 'edge_type', 'polyline',
            'source_node_id', 'stamp-bridge', 'target_node_id', 'cnc-bridge'),
        jsonb_build_object('id', 'line-9', 'edge_type', 'polyline',
            'source_node_id', 'cnc-bridge', 'target_node_id', 'grinding-bridge'),
        jsonb_build_object('id', 'line-10', 'edge_type', 'polyline',
            'source_node_id', 'grinding-bridge', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'line-11', 'edge_type', 'polyline',
            'source_node_id', 'part-head', 'target_node_id', 'purchase-head'),
        jsonb_build_object('id', 'line-12', 'edge_type', 'polyline',
            'source_node_id', 'purchase-head', 'target_node_id', 'grinding-head'),
        jsonb_build_object('id', 'line-13', 'edge_type', 'polyline',
            'source_node_id', 'grinding-head', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'line-14', 'edge_type', 'polyline',
            'source_node_id', 'laser-merge', 'target_node_id', 'grinding-assembly'),
        jsonb_build_object('id', 'line-15', 'edge_type', 'polyline',
            'source_node_id', 'grinding-assembly', 'target_node_id', 'vibration-next'),
        jsonb_build_object('id', 'line-16', 'edge_type', 'polyline',
            'source_node_id', 'vibration-next', 'target_node_id', 'outsource-next'),
        jsonb_build_object('id', 'line-17', 'edge_type', 'polyline',
            'source_node_id', 'outsource-next', 'target_node_id', 'finished-end')
    )
)
FROM product
JOIN product_bom AS body ON body.product_id = product.id
    AND body.part_no = 'Z8737-01'
JOIN product_bom AS bridge ON bridge.product_id = product.id
    AND bridge.part_no = 'Z8737-02'
JOIN product_bom AS head ON head.product_id = product.id
    AND head.part_no = 'Z8737-03'
WHERE product.factory_code = 'Z8737';

-- 当前路线投影：汇合前10项配件安排，汇合起5项装配体安排。
INSERT INTO product_department_route (product_id, appearance_id, material_node_id, department_node_id, department_code)
SELECT product.id, (SELECT id FROM product_appearance WHERE product_id = product.id), route.material_node_id, route.department_node_id, route.department_code
FROM product
CROSS JOIN (VALUES
    ('part-body', 'stamp-body', 'stamp'),
    ('part-body', 'cnc-body', 'cnc'),
    ('part-body', 'grinding-body-before', 'grinding'),
    ('part-body', 'outsource-body', 'outsource'),
    ('part-body', 'grinding-body-after', 'grinding'),
    ('part-bridge', 'stamp-bridge', 'stamp'),
    ('part-bridge', 'cnc-bridge', 'cnc'),
    ('part-bridge', 'grinding-bridge', 'grinding'),
    ('part-head', 'purchase-head', 'purchase'),
    ('part-head', 'grinding-head', 'grinding'),
    ('laser-merge', 'laser-merge', 'laser'),
    ('laser-merge', 'grinding-assembly', 'grinding'),
    ('laser-merge', 'vibration-next', 'vibration'),
    ('laser-merge', 'outsource-next', 'outsource'),
    ('laser-merge', 'finished-end', 'finished')
) AS route(material_node_id, department_node_id, department_code)
WHERE product.factory_code = 'Z8737';

INSERT INTO product_route_component (product_id, appearance_id, material_node_id, department_node_id, product_bom_id)
SELECT route.product_id, route.appearance_id, route.material_node_id, route.department_node_id, part.id
FROM product_department_route AS route
JOIN product_bom AS part ON part.product_id = route.product_id
WHERE (route.material_node_id = 'part-body' AND part.part_no = 'Z8737-01')
    OR (route.material_node_id = 'part-bridge' AND part.part_no = 'Z8737-02')
    OR (route.material_node_id = 'part-head' AND part.part_no = 'Z8737-03')
    OR route.material_node_id = 'laser-merge';

-- Z8738：面盖、底座先激光汇合，再与连接环在装配部二次汇合。
INSERT INTO product (customer_id, product_name, factory_code, customer_code)
SELECT id, '双段装配搭扣', 'Z8738', 'DEMO-Z8738'
FROM customer WHERE customer_name = 'Celine';

INSERT INTO product_appearance (product_id, appearance_name)
SELECT id, '标准外观' FROM product WHERE factory_code = 'Z8738';

INSERT INTO product_bom (product_id, part_name, part_no, pcs, remark, sort_order)
SELECT product.id, component.part_name, component.part_no, 1, NULL, component.sort_order
FROM product
CROSS JOIN (VALUES
    ('面盖', 'Z8738-01', 1),
    ('底座', 'Z8738-02', 2),
    ('连接环', 'Z8738-03', 3)
) AS component(part_name, part_no, sort_order)
WHERE product.factory_code = 'Z8738';

INSERT INTO product_process_flow (product_id, appearance_id, flow_json)
SELECT product.id, (SELECT id FROM product_appearance WHERE product_id = product.id), jsonb_build_object(
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
    AND cover.part_no = 'Z8738-01'
JOIN product_bom AS base ON base.product_id = product.id
    AND base.part_no = 'Z8738-02'
JOIN product_bom AS ring ON ring.product_id = product.id
    AND ring.part_no = 'Z8738-03'
WHERE product.factory_code = 'Z8738';

INSERT INTO product_department_route (product_id, appearance_id, material_node_id, department_node_id, department_code)
SELECT product.id, (SELECT id FROM product_appearance WHERE product_id = product.id), route.material_node_id, route.department_node_id, route.department_code
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

INSERT INTO product_route_component (product_id, appearance_id, material_node_id, department_node_id, product_bom_id)
SELECT route.product_id, route.appearance_id, route.material_node_id, route.department_node_id, part.id
FROM product_department_route AS route
JOIN product AS product ON product.id = route.product_id
JOIN product_bom AS part ON part.product_id = route.product_id
WHERE product.factory_code = 'Z8738' AND (
    (route.material_node_id = 'part-cover' AND part.part_no = 'Z8738-01')
    OR (route.material_node_id = 'part-base' AND part.part_no = 'Z8738-02')
    OR (route.material_node_id = 'part-ring' AND part.part_no = 'Z8738-03')
    OR (route.material_node_id = 'laser-primary' AND part.part_no IN ('Z8738-01', 'Z8738-02'))
    OR route.material_node_id = 'assembly-final'
);

-- 同一产品的银色外观共用原BOM，流程省去CNC、磨房和委外等路径。
INSERT INTO product_appearance (product_id, appearance_name)
SELECT id, '银色' FROM product WHERE factory_code = 'Z8737';

INSERT INTO product_process_flow (product_id, appearance_id, flow_json)
SELECT product.id, appearance.id, jsonb_build_object(
    'schema_version', 8,
    'nodes', jsonb_build_array(
        jsonb_build_object('id', 'part-body', 'type', 'part', 'x', 0, 'y', 0,
            'label', body.part_no || ' · ' || body.part_name, 'bom_item_id', body.id),
        jsonb_build_object('id', 'part-bridge', 'type', 'part', 'x', 0, 'y', 500,
            'label', bridge.part_no || ' · ' || bridge.part_name, 'bom_item_id', bridge.id),
        jsonb_build_object('id', 'part-head', 'type', 'part', 'x', 0, 'y', 1000,
            'label', head.part_no || ' · ' || head.part_name, 'bom_item_id', head.id),
        jsonb_build_object('id', 'stamp-body', 'type', 'department', 'x', 600, 'y', 0,
            'label', '冲压部', 'department_code', 'stamp'),
        jsonb_build_object('id', 'stamp-bridge', 'type', 'department', 'x', 600, 'y', 500,
            'label', '冲压部', 'department_code', 'stamp'),
        jsonb_build_object('id', 'purchase-head', 'type', 'department', 'x', 600, 'y', 1000,
            'label', '外购部', 'department_code', 'purchase'),
        jsonb_build_object('id', 'laser-merge', 'type', 'department', 'x', 1200, 'y', 0,
            'label', '激光部', 'department_code', 'laser'),
        jsonb_build_object('id', 'finished-end', 'type', 'department', 'x', 1200, 'y', 500,
            'label', '成品部', 'department_code', 'finished')
    ),
    'edges', jsonb_build_array(
        jsonb_build_object('id', 'silver-line-1', 'edge_type', 'polyline', 'source_node_id', 'part-body', 'target_node_id', 'stamp-body'),
        jsonb_build_object('id', 'silver-line-2', 'edge_type', 'polyline', 'source_node_id', 'part-bridge', 'target_node_id', 'stamp-bridge'),
        jsonb_build_object('id', 'silver-line-3', 'edge_type', 'polyline', 'source_node_id', 'part-head', 'target_node_id', 'purchase-head'),
        jsonb_build_object('id', 'silver-line-4', 'edge_type', 'polyline', 'source_node_id', 'stamp-body', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'silver-line-5', 'edge_type', 'polyline', 'source_node_id', 'stamp-bridge', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'silver-line-6', 'edge_type', 'polyline', 'source_node_id', 'purchase-head', 'target_node_id', 'laser-merge'),
        jsonb_build_object('id', 'silver-line-7', 'edge_type', 'polyline', 'source_node_id', 'laser-merge', 'target_node_id', 'finished-end')
    )
)
FROM product
JOIN product_appearance AS appearance ON appearance.product_id = product.id AND appearance.appearance_name = '银色'
JOIN product_bom AS body ON body.product_id = product.id AND body.part_no = 'Z8737-01'
JOIN product_bom AS bridge ON bridge.product_id = product.id AND bridge.part_no = 'Z8737-02'
JOIN product_bom AS head ON head.product_id = product.id AND head.part_no = 'Z8737-03'
WHERE product.factory_code = 'Z8737';

INSERT INTO product_department_route (product_id, appearance_id, material_node_id, department_node_id, department_code)
SELECT appearance.product_id, appearance.id, route.material_node_id, route.department_node_id, route.department_code
FROM product_appearance AS appearance
JOIN product ON product.id = appearance.product_id
CROSS JOIN (VALUES
    ('part-body', 'stamp-body', 'stamp'),
    ('part-bridge', 'stamp-bridge', 'stamp'),
    ('part-head', 'purchase-head', 'purchase'),
    ('laser-merge', 'laser-merge', 'laser'),
    ('laser-merge', 'finished-end', 'finished')
) AS route(material_node_id, department_node_id, department_code)
WHERE product.factory_code = 'Z8737' AND appearance.appearance_name = '银色';

INSERT INTO product_route_component (product_id, appearance_id, material_node_id, department_node_id, product_bom_id)
SELECT route.product_id, route.appearance_id, route.material_node_id, route.department_node_id, part.id
FROM product_department_route AS route
JOIN product_appearance AS appearance ON appearance.id = route.appearance_id
JOIN product_bom AS part ON part.product_id = route.product_id
WHERE appearance.appearance_name = '银色' AND (
    (route.material_node_id = 'part-body' AND part.part_no = 'Z8737-01')
    OR (route.material_node_id = 'part-bridge' AND part.part_no = 'Z8737-02')
    OR (route.material_node_id = 'part-head' AND part.part_no = 'Z8737-03')
    OR route.material_node_id = 'laser-merge'
);

-- 两个相同草稿计划，各包含两个产品、三条产品/外观明细，数量独立。
INSERT INTO production_plan (customer_id, order_no, status, revision)
SELECT customer.id, seed.order_no, 'draft', 1 FROM customer
CROSS JOIN (VALUES ('ORDER-Z8737-0001'), ('ORDER-Z8737-0002')) AS seed(order_no)
WHERE customer.customer_name = 'Celine';

INSERT INTO production_plan_item (production_plan_id, product_id, appearance_id, customer_id, order_quantity, production_quantity)
SELECT plan.id, product.id, appearance.id, plan.customer_id, item.order_quantity, item.production_quantity
FROM production_plan AS plan
JOIN product ON product.customer_id = plan.customer_id
JOIN (VALUES ('Z8737', '标准外观', 3000, 4000), ('Z8737', '银色', 500, 600), ('Z8738', '标准外观', 1000, 1200))
    AS item(factory_code, appearance_name, order_quantity, production_quantity) ON item.factory_code = product.factory_code
JOIN product_appearance AS appearance ON appearance.product_id = product.id AND appearance.appearance_name = item.appearance_name
WHERE plan.order_no IN ('ORDER-Z8737-0001', 'ORDER-Z8737-0002');

-- 每个计划26张，共52张部门工单；装配体按各产品生产数量安排。
INSERT INTO department_work_order (
    production_plan_id, product_id, appearance_id, material_node_id, department_node_id, task_quantity
)
SELECT plan.id, item.product_id, item.appearance_id, route.material_node_id, route.department_node_id,
       item.production_quantity * CASE WHEN COUNT(part.id) > 1 THEN 1 ELSE MAX(part.pcs) END
FROM production_plan AS plan
JOIN production_plan_item AS item ON item.production_plan_id = plan.id
JOIN product_department_route AS route ON route.product_id = item.product_id AND route.appearance_id = item.appearance_id
JOIN product_route_component AS component
    ON component.product_id = route.product_id AND component.appearance_id = route.appearance_id
    AND component.material_node_id = route.material_node_id
    AND component.department_node_id = route.department_node_id
JOIN product_bom AS part ON part.id = component.product_bom_id
WHERE plan.order_no IN ('ORDER-Z8737-0001', 'ORDER-Z8737-0002')
GROUP BY plan.id, item.product_id, item.appearance_id, item.production_quantity,
         route.material_node_id, route.department_node_id;

COMMIT;

