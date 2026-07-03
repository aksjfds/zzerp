-- ============================================================
-- ZZ ERP 核心业务数据库
-- 阶段一：产品、BOM、路线、客户订单与生产计划
-- ============================================================

CREATE TABLE department (
    id BIGSERIAL PRIMARY KEY,
    department_code TEXT NOT NULL UNIQUE,
    department_name TEXT NOT NULL UNIQUE,
    department_type TEXT NOT NULL
        CHECK (department_type IN ('system', 'office', 'production', 'quality')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE workshop (
    id BIGSERIAL PRIMARY KEY,
    department_id BIGINT NOT NULL REFERENCES department(id),
    workshop_code TEXT NOT NULL,
    workshop_name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (id, department_id),
    UNIQUE (department_id, workshop_code),
    UNIQUE (department_id, workshop_name)
);


CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    department_id BIGINT NOT NULL REFERENCES department(id),
    role TEXT NOT NULL,
    permissions TEXT NOT NULL DEFAULT '',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE user_workshop_permission (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workshop_id BIGINT NOT NULL REFERENCES workshop(id),
    can_view BOOLEAN NOT NULL DEFAULT TRUE,
    can_create_work_order BOOLEAN NOT NULL DEFAULT FALSE,
    can_report BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (user_id, workshop_id)
);


CREATE TABLE user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE product (
    id BIGSERIAL PRIMARY KEY,
    factory_code TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'inactive')),
    next_semi_finished_no INT NOT NULL DEFAULT 1
        CHECK (next_semi_finished_no > 0),
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    published_by BIGINT REFERENCES users(id),
    published_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE product_customer_code (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id),
    customer_name TEXT NOT NULL,
    customer_product_code TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (id, product_id),
    UNIQUE (id, product_id, customer_name),
    UNIQUE (id, customer_name),
    UNIQUE (customer_name, customer_product_code),
    UNIQUE (product_id, customer_name, customer_product_code)
);


CREATE TABLE customer_surface_treatment (
    id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    treatment_name TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (id, customer_name),
    UNIQUE (customer_name, treatment_name)
);


CREATE TABLE product_customer_treatment (
    id BIGSERIAL PRIMARY KEY,
    product_customer_code_id BIGINT NOT NULL,
    treatment_id BIGINT NOT NULL,
    customer_name TEXT NOT NULL,
    FOREIGN KEY (product_customer_code_id, customer_name)
        REFERENCES product_customer_code(id, customer_name) ON DELETE CASCADE,
    FOREIGN KEY (treatment_id, customer_name)
        REFERENCES customer_surface_treatment(id, customer_name),
    UNIQUE (product_customer_code_id, treatment_id)
);


CREATE TABLE material (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id),
    material_code TEXT NOT NULL UNIQUE,
    material_name TEXT NOT NULL,
    material_type TEXT NOT NULL
        CHECK (material_type IN ('finished', 'semi_finished', 'self_made', 'purchased')),
    material_grade TEXT,
    specification TEXT,
    note TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (id, product_id)
);


CREATE UNIQUE INDEX uq_material_finished_product
ON material(product_id)
WHERE material_type = 'finished';


CREATE TABLE product_released_semi_number (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    sequence_no INT NOT NULL CHECK (sequence_no > 0),
    UNIQUE (product_id, sequence_no)
);


CREATE TABLE product_bom_version (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id),
    version_no INT NOT NULL CHECK (version_no > 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'inactive')),
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    published_by BIGINT REFERENCES users(id),
    published_at TIMESTAMP,
    UNIQUE (id, product_id),
    UNIQUE (product_id, version_no)
);


CREATE UNIQUE INDEX uq_product_bom_published
ON product_bom_version(product_id)
WHERE status = 'published';


CREATE TABLE product_bom_item (
    id BIGSERIAL PRIMARY KEY,
    bom_version_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    material_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL DEFAULT 'pcs' CHECK (unit = 'pcs'),
    FOREIGN KEY (bom_version_id, product_id)
        REFERENCES product_bom_version(id, product_id) ON DELETE CASCADE,
    FOREIGN KEY (material_id, product_id)
        REFERENCES material(id, product_id),
    UNIQUE (bom_version_id, material_id)
);


CREATE TABLE semi_finished_version (
    id BIGSERIAL PRIMARY KEY,
    semi_finished_material_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    version_no INT NOT NULL CHECK (version_no > 0),
    quantity_per_finished INT NOT NULL DEFAULT 1
        CHECK (quantity_per_finished > 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'inactive')),
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    published_by BIGINT REFERENCES users(id),
    published_at TIMESTAMP,
    FOREIGN KEY (semi_finished_material_id, product_id)
        REFERENCES material(id, product_id),
    UNIQUE (id, semi_finished_material_id),
    UNIQUE (id, product_id),
    UNIQUE (semi_finished_material_id, version_no)
);


CREATE UNIQUE INDEX uq_semi_finished_version_published
ON semi_finished_version(semi_finished_material_id)
WHERE status = 'published';


CREATE TABLE semi_finished_input (
    id BIGSERIAL PRIMARY KEY,
    semi_finished_version_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    input_material_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL DEFAULT 'pcs' CHECK (unit = 'pcs'),
    FOREIGN KEY (semi_finished_version_id, product_id)
        REFERENCES semi_finished_version(id, product_id) ON DELETE CASCADE,
    FOREIGN KEY (input_material_id, product_id)
        REFERENCES material(id, product_id),
    UNIQUE (semi_finished_version_id, input_material_id)
);


CREATE TABLE material_route_version (
    id BIGSERIAL PRIMARY KEY,
    material_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    version_no INT NOT NULL CHECK (version_no > 0),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'inactive')),
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    published_by BIGINT REFERENCES users(id),
    published_at TIMESTAMP,
    FOREIGN KEY (material_id, product_id)
        REFERENCES material(id, product_id),
    UNIQUE (id, material_id),
    UNIQUE (material_id, version_no)
);


CREATE UNIQUE INDEX uq_material_route_published
ON material_route_version(material_id)
WHERE status = 'published';


CREATE TABLE material_route_step (
    id BIGSERIAL PRIMARY KEY,
    route_version_id BIGINT NOT NULL
        REFERENCES material_route_version(id) ON DELETE CASCADE,
    sequence_no INT NOT NULL CHECK (sequence_no > 0),
    step_type TEXT NOT NULL CHECK (step_type IN ('internal', 'external_surface')),
    department_id BIGINT REFERENCES department(id),
    workshop_id BIGINT,
    FOREIGN KEY (workshop_id, department_id)
        REFERENCES workshop(id, department_id),
    UNIQUE (route_version_id, sequence_no),
    CHECK (
        (
            step_type = 'internal'
            AND department_id IS NOT NULL
            AND workshop_id IS NOT NULL
        )
        OR (
            step_type = 'external_surface'
            AND department_id IS NULL
            AND workshop_id IS NULL
        )
    )
);


CREATE UNIQUE INDEX uq_material_route_external_surface
ON material_route_step(route_version_id)
WHERE step_type = 'external_surface';


CREATE TABLE customer_order (
    id BIGSERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    purchase_order_no TEXT NOT NULL,
    version_no INT NOT NULL DEFAULT 1 CHECK (version_no > 0),
    previous_version_id BIGINT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (
            status IN (
                'draft',
                'confirmed',
                'planned',
                'completed',
                'cancelled',
                'superseded'
            )
        ),
    order_date DATE NOT NULL,
    note TEXT,
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    confirmed_by BIGINT REFERENCES users(id),
    confirmed_at TIMESTAMP,
    UNIQUE (id, customer_name),
    UNIQUE (id, customer_name, purchase_order_no),
    UNIQUE (customer_name, purchase_order_no, version_no),
    FOREIGN KEY (previous_version_id, customer_name, purchase_order_no)
        REFERENCES customer_order(id, customer_name, purchase_order_no)
);


CREATE TABLE customer_order_item (
    id BIGSERIAL PRIMARY KEY,
    customer_order_id BIGINT NOT NULL,
    customer_name TEXT NOT NULL,
    product_id BIGINT NOT NULL REFERENCES product(id),
    product_customer_code_id BIGINT NOT NULL,
    treatment_id BIGINT REFERENCES customer_surface_treatment(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    delivery_date DATE NOT NULL,
    FOREIGN KEY (customer_order_id, customer_name)
        REFERENCES customer_order(id, customer_name) ON DELETE CASCADE,
    FOREIGN KEY (product_customer_code_id, product_id, customer_name)
        REFERENCES product_customer_code(id, product_id, customer_name),
    FOREIGN KEY (treatment_id, customer_name)
        REFERENCES customer_surface_treatment(id, customer_name),
    UNIQUE (id, customer_order_id),
    UNIQUE (id, product_id)
);


CREATE SEQUENCE production_plan_no_seq;


CREATE TABLE production_plan (
    id BIGSERIAL PRIMARY KEY,
    plan_no TEXT NOT NULL UNIQUE DEFAULT (
        'PP' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' ||
        LPAD(NEXTVAL('production_plan_no_seq')::TEXT, 6, '0')
    ),
    customer_order_id BIGINT NOT NULL REFERENCES customer_order(id),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'released', 'producing', 'completed', 'cancelled')),
    start_date DATE NOT NULL,
    completion_date DATE NOT NULL,
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    released_by BIGINT REFERENCES users(id),
    released_at TIMESTAMP,
    UNIQUE (id, customer_order_id),
    CHECK (completion_date >= start_date)
);


CREATE TABLE production_plan_order_item (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL,
    customer_order_id BIGINT NOT NULL,
    customer_order_item_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    order_required_quantity INT NOT NULL CHECK (order_required_quantity > 0),
    planned_finished_quantity INT NOT NULL CHECK (planned_finished_quantity > 0),
    stock_quantity INT GENERATED ALWAYS AS (
        GREATEST(planned_finished_quantity - order_required_quantity, 0)
    ) STORED,
    product_bom_version_id BIGINT NOT NULL,
    FOREIGN KEY (production_plan_id, customer_order_id)
        REFERENCES production_plan(id, customer_order_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_order_item_id, customer_order_id)
        REFERENCES customer_order_item(id, customer_order_id),
    FOREIGN KEY (customer_order_item_id, product_id)
        REFERENCES customer_order_item(id, product_id),
    FOREIGN KEY (product_bom_version_id, product_id)
        REFERENCES product_bom_version(id, product_id),
    UNIQUE (id, product_id),
    UNIQUE (production_plan_id, customer_order_item_id),
    CHECK (planned_finished_quantity >= order_required_quantity)
);


CREATE TABLE production_plan_material (
    id BIGSERIAL PRIMARY KEY,
    production_plan_order_item_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    material_id BIGINT NOT NULL,
    theoretical_quantity INT NOT NULL CHECK (theoretical_quantity > 0),
    planned_quantity INT NOT NULL CHECK (planned_quantity > 0),
    adjustment_reason TEXT,
    semi_finished_version_id BIGINT,
    route_version_id BIGINT,
    FOREIGN KEY (production_plan_order_item_id, product_id)
        REFERENCES production_plan_order_item(id, product_id) ON DELETE CASCADE,
    FOREIGN KEY (material_id, product_id)
        REFERENCES material(id, product_id),
    FOREIGN KEY (semi_finished_version_id, material_id)
        REFERENCES semi_finished_version(id, semi_finished_material_id),
    FOREIGN KEY (route_version_id, material_id)
        REFERENCES material_route_version(id, material_id),
    UNIQUE (production_plan_order_item_id, material_id),
    CHECK (
        planned_quantity = theoretical_quantity
        OR NULLIF(BTRIM(adjustment_reason), '') IS NOT NULL
    )
);


CREATE TABLE production_plan_change_log (
    id BIGSERIAL PRIMARY KEY,
    production_plan_id BIGINT NOT NULL REFERENCES production_plan(id),
    changed_by BIGINT NOT NULL REFERENCES users(id),
    changed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    change_type TEXT NOT NULL,
    old_data JSONB NOT NULL,
    new_data JSONB NOT NULL
);


CREATE TABLE material_inventory (
    id BIGSERIAL PRIMARY KEY,
    material_id BIGINT NOT NULL REFERENCES material(id),
    workshop_id BIGINT REFERENCES workshop(id),
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE NULLS NOT DISTINCT (material_id, workshop_id)
);


-- 生产计划下达后生成现场流转对象。
-- 它与产品主档分表，避免概念冲突。
CREATE TABLE production_item (
    id BIGSERIAL PRIMARY KEY,
    production_plan_material_id BIGINT NOT NULL UNIQUE
        REFERENCES production_plan_material(id),
    order_id TEXT NOT NULL,
    zz_code TEXT NOT NULL,
    product_name TEXT NOT NULL,
    delivery_date DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (order_id, zz_code, production_plan_material_id)
);


CREATE TABLE product_department_step (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    sequence_no INT NOT NULL CHECK (sequence_no > 0),
    department TEXT NOT NULL,
    UNIQUE (product_id, sequence_no)
);


CREATE TABLE repository (
    id BIGSERIAL PRIMARY KEY,
    department TEXT NOT NULL,
    product_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    UNIQUE (department, product_id)
);


CREATE TABLE procedure (
    id BIGSERIAL PRIMARY KEY,
    procedure_name TEXT NOT NULL,
    department TEXT NOT NULL,
    UNIQUE (department, procedure_name)
);


CREATE TABLE worker (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (department, name)
);


CREATE TABLE polish_process_preset (
    id BIGSERIAL PRIMARY KEY,
    preset_name TEXT NOT NULL UNIQUE,
    process_flow TEXT[] NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE polish_process (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL UNIQUE
        REFERENCES production_item(id) ON DELETE CASCADE,
    preset_id BIGINT REFERENCES polish_process_preset(id) ON DELETE SET NULL,
    process_flow TEXT[] NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE work_order (
    id BIGSERIAL PRIMARY KEY,
    work_order_no TEXT UNIQUE,
    product_id BIGINT NOT NULL REFERENCES production_item(id),
    department TEXT NOT NULL,
    process_name TEXT NOT NULL,
    worker_id BIGINT NOT NULL REFERENCES worker(id),
    issued_quantity INT NOT NULL CHECK (issued_quantity > 0),
    work_order_type TEXT NOT NULL DEFAULT 'normal'
        CHECK (work_order_type IN ('normal', 'rework')),
    rework_request_id BIGINT,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed')),
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP,
    note TEXT
);


CREATE TABLE polish_cleaning_batch (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id),
    batch_no INT NOT NULL CHECK (batch_no > 0),
    quantity INT NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL CHECK (status IN ('cleaning', 'completed')),
    sent_by BIGINT NOT NULL REFERENCES users(id),
    sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_by BIGINT REFERENCES users(id),
    completed_at TIMESTAMP,
    UNIQUE (work_order_id, batch_no)
);


CREATE TABLE work_order_batch (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id),
    batch_no INT NOT NULL CHECK (batch_no > 0),
    submitted_quantity INT NOT NULL CHECK (submitted_quantity > 0),
    ok_quantity INT CHECK (ok_quantity >= 0),
    rework_quantity INT CHECK (rework_quantity >= 0),
    scrap_quantity INT CHECK (scrap_quantity >= 0),
    lost_quantity INT CHECK (lost_quantity >= 0),
    qc_worker_id BIGINT REFERENCES worker(id),
    defect_reason TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending_qc', 'completed')),
    submitted_by BIGINT NOT NULL REFERENCES users(id),
    submitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    inspected_by BIGINT REFERENCES users(id),
    inspected_at TIMESTAMP,
    UNIQUE (work_order_id, batch_no),
    CHECK (
        status <> 'completed'
        OR submitted_quantity = COALESCE(ok_quantity, 0)
            + COALESCE(rework_quantity, 0)
            + COALESCE(scrap_quantity, 0)
            + COALESCE(lost_quantity, 0)
    )
);


CREATE TABLE rework_request (
    id BIGSERIAL PRIMARY KEY,
    source_work_order_id BIGINT NOT NULL REFERENCES work_order(id),
    source_batch_id BIGINT REFERENCES work_order_batch(id),
    product_id BIGINT NOT NULL REFERENCES production_item(id),
    source_department TEXT NOT NULL,
    target_department TEXT NOT NULL,
    target_process_name TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'closed')),
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP
);


ALTER TABLE work_order
ADD CONSTRAINT fk_work_order_rework_request
FOREIGN KEY (rework_request_id) REFERENCES rework_request(id);


CREATE TABLE records (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL
        REFERENCES production_item(id) ON DELETE CASCADE,
    from_repository TEXT NOT NULL,
    to_repository TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE OR REPLACE FUNCTION validate_product_bom_item()
RETURNS TRIGGER AS $$
DECLARE
    resolved_type TEXT;
BEGIN
    SELECT material_type
    INTO resolved_type
    FROM material
    WHERE id = NEW.material_id;

    IF resolved_type NOT IN ('self_made', 'purchased') THEN
        RAISE EXCEPTION '产品BOM只能包含自制配件或外购配件';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_product_bom_item
BEFORE INSERT OR UPDATE ON product_bom_item
FOR EACH ROW EXECUTE FUNCTION validate_product_bom_item();


CREATE OR REPLACE FUNCTION validate_semi_finished_version()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM material
        WHERE id = NEW.semi_finished_material_id
          AND material_type = 'semi_finished'
    ) THEN
        RAISE EXCEPTION '半成品组成版本只能关联半成品物料';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_semi_finished_version
BEFORE INSERT OR UPDATE ON semi_finished_version
FOR EACH ROW EXECUTE FUNCTION validate_semi_finished_version();


CREATE OR REPLACE FUNCTION validate_semi_finished_input()
RETURNS TRIGGER AS $$
DECLARE
    output_material_id BIGINT;
    input_type TEXT;
BEGIN
    SELECT semi_finished_material_id
    INTO output_material_id
    FROM semi_finished_version
    WHERE id = NEW.semi_finished_version_id;

    SELECT material_type
    INTO input_type
    FROM material
    WHERE id = NEW.input_material_id;

    IF input_type = 'finished' THEN
        RAISE EXCEPTION '成品不能作为半成品的输入物料';
    END IF;

    IF output_material_id = NEW.input_material_id THEN
        RAISE EXCEPTION '半成品不能直接包含自身';
    END IF;

    IF EXISTS (
        WITH RECURSIVE dependencies(material_id) AS (
            SELECT NEW.input_material_id
            UNION
            SELECT child.input_material_id
            FROM dependencies parent
            JOIN semi_finished_version version
              ON version.semi_finished_material_id = parent.material_id
            JOIN semi_finished_input child
              ON child.semi_finished_version_id = version.id
        )
        SELECT 1
        FROM dependencies
        WHERE material_id = output_material_id
    ) THEN
        RAISE EXCEPTION '半成品组成不能形成循环引用';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_semi_finished_input
BEFORE INSERT OR UPDATE ON semi_finished_input
FOR EACH ROW EXECUTE FUNCTION validate_semi_finished_input();


CREATE OR REPLACE FUNCTION validate_material_route_version()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM material
        WHERE id = NEW.material_id
          AND material_type = 'purchased'
    ) THEN
        RAISE EXCEPTION '外购配件不能配置内部生产路线';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_material_route_version
BEFORE INSERT OR UPDATE ON material_route_version
FOR EACH ROW EXECUTE FUNCTION validate_material_route_version();


CREATE OR REPLACE FUNCTION validate_material_route_step()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.step_type = 'external_surface' AND EXISTS (
        SELECT 1 FROM material_route_step
        WHERE route_version_id = NEW.route_version_id
          AND sequence_no > NEW.sequence_no
          AND id IS DISTINCT FROM NEW.id
    ) THEN
        RAISE EXCEPTION '外厂表面处理必须是物料路线最后一步';
    END IF;

    IF NEW.step_type = 'internal' AND EXISTS (
        SELECT 1 FROM material_route_step
        WHERE route_version_id = NEW.route_version_id
          AND step_type = 'external_surface'
          AND sequence_no < NEW.sequence_no
          AND id IS DISTINCT FROM NEW.id
    ) THEN
        RAISE EXCEPTION '外厂表面处理后不能再添加内部生产步骤';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_material_route_step
BEFORE INSERT OR UPDATE ON material_route_step
FOR EACH ROW EXECUTE FUNCTION validate_material_route_step();


CREATE OR REPLACE FUNCTION validate_customer_order_item_treatment()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.treatment_id IS NOT NULL AND NOT EXISTS (
        SELECT 1
        FROM product_customer_treatment
        WHERE product_customer_code_id = NEW.product_customer_code_id
          AND treatment_id = NEW.treatment_id
    ) THEN
        RAISE EXCEPTION '该客户产品未启用所选表面处理';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_customer_order_item_treatment
BEFORE INSERT OR UPDATE ON customer_order_item
FOR EACH ROW EXECUTE FUNCTION validate_customer_order_item_treatment();


CREATE OR REPLACE FUNCTION protect_customer_order()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION '客户订单不能删除，只能取消';
    END IF;

    IF OLD.status = 'draft' THEN
        IF NEW.status = 'draft'
           AND (TO_JSONB(NEW) - ARRAY['order_date', 'note'])
               IS NOT DISTINCT FROM
               (TO_JSONB(OLD) - ARRAY['order_date', 'note'])
        THEN
            RETURN NEW;
        END IF;
        IF NEW.status = 'confirmed'
           AND (TO_JSONB(NEW) - ARRAY['status', 'confirmed_by', 'confirmed_at'])
               IS NOT DISTINCT FROM
               (TO_JSONB(OLD) - ARRAY['status', 'confirmed_by', 'confirmed_at'])
        THEN
            RETURN NEW;
        END IF;
        IF NEW.status = 'cancelled'
           AND (TO_JSONB(NEW) - 'status') IS NOT DISTINCT FROM
               (TO_JSONB(OLD) - 'status')
        THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION '草稿订单只能确认或取消';
    END IF;

    IF OLD.status = 'confirmed'
       AND NEW.status IN ('planned', 'cancelled', 'superseded')
       AND (TO_JSONB(NEW) - 'status') IS NOT DISTINCT FROM
           (TO_JSONB(OLD) - 'status')
    THEN
        RETURN NEW;
    END IF;

    IF OLD.status = 'planned'
       AND NEW.status IN ('completed', 'cancelled')
       AND (TO_JSONB(NEW) - 'status') IS NOT DISTINCT FROM
           (TO_JSONB(OLD) - 'status')
    THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION '当前客户订单状态不允许修改';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_customer_order
BEFORE UPDATE OR DELETE ON customer_order
FOR EACH ROW EXECUTE FUNCTION protect_customer_order();


CREATE OR REPLACE FUNCTION protect_customer_order_item()
RETURNS TRIGGER AS $$
DECLARE
    parent_id BIGINT;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.customer_order_id IS DISTINCT FROM
       NEW.customer_order_id THEN
        RAISE EXCEPTION '订单明细不能移动到其他订单';
    END IF;
    parent_id := CASE WHEN TG_OP = 'DELETE'
        THEN OLD.customer_order_id ELSE NEW.customer_order_id END;
    IF TG_OP = 'DELETE' AND NOT EXISTS (
        SELECT 1 FROM customer_order WHERE id = parent_id
    ) THEN
        RETURN OLD;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM customer_order
        WHERE id = parent_id AND status = 'draft'
    ) THEN
        RAISE EXCEPTION '只有草稿客户订单允许修改明细';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_customer_order_item
BEFORE INSERT OR UPDATE OR DELETE ON customer_order_item
FOR EACH ROW EXECUTE FUNCTION protect_customer_order_item();


CREATE OR REPLACE FUNCTION protect_product_record()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status <> 'draft' THEN
            RAISE EXCEPTION '已发布或已停用产品不能删除';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.status = 'inactive' THEN
        RAISE EXCEPTION '已停用产品不能修改';
    END IF;

    IF OLD.status = 'published' THEN
        IF NEW.status <> 'inactive'
           OR (TO_JSONB(NEW) - 'status') IS DISTINCT FROM
              (TO_JSONB(OLD) - 'status') THEN
            RAISE EXCEPTION '已发布产品只能停用';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.status = 'draft' THEN
        RETURN NEW;
    END IF;
    IF NEW.status = 'published'
       AND (TO_JSONB(NEW) - ARRAY['status', 'published_by', 'published_at'])
           IS NOT DISTINCT FROM
           (TO_JSONB(OLD) - ARRAY['status', 'published_by', 'published_at'])
       AND NEW.published_by IS NOT NULL
       AND NEW.published_at IS NOT NULL THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION '无效的产品状态流转';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_product_record
BEFORE UPDATE OR DELETE ON product
FOR EACH ROW EXECUTE FUNCTION protect_product_record();


CREATE OR REPLACE FUNCTION protect_version_record()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status <> 'draft' THEN
            RAISE EXCEPTION '已发布或已停用版本不能删除';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.status = 'inactive' THEN
        RAISE EXCEPTION '已停用版本不能修改';
    END IF;

    IF OLD.status = 'published' THEN
        IF NEW.status <> 'inactive'
           OR (TO_JSONB(NEW) - 'status') IS DISTINCT FROM
              (TO_JSONB(OLD) - 'status') THEN
            RAISE EXCEPTION '已发布版本只能停用';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_product_bom_version
BEFORE UPDATE OR DELETE ON product_bom_version
FOR EACH ROW EXECUTE FUNCTION protect_version_record();

CREATE TRIGGER trg_protect_semi_finished_version
BEFORE UPDATE OR DELETE ON semi_finished_version
FOR EACH ROW EXECUTE FUNCTION protect_version_record();

CREATE TRIGGER trg_protect_material_route_version
BEFORE UPDATE OR DELETE ON material_route_version
FOR EACH ROW EXECUTE FUNCTION protect_version_record();


CREATE OR REPLACE FUNCTION protect_product_bom_item()
RETURNS TRIGGER AS $$
DECLARE
    parent_id BIGINT;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.bom_version_id IS DISTINCT FROM
       NEW.bom_version_id THEN
        RAISE EXCEPTION 'BOM明细不能移动到其他版本';
    END IF;
    parent_id := CASE WHEN TG_OP = 'DELETE'
        THEN OLD.bom_version_id ELSE NEW.bom_version_id END;
    IF TG_OP = 'DELETE' AND NOT EXISTS (
        SELECT 1 FROM product_bom_version WHERE id = parent_id
    ) THEN
        RETURN OLD;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM product_bom_version
        WHERE id = parent_id AND status = 'draft'
    ) THEN
        RAISE EXCEPTION '只有草稿BOM版本允许修改明细';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_product_bom_item
BEFORE INSERT OR UPDATE OR DELETE ON product_bom_item
FOR EACH ROW EXECUTE FUNCTION protect_product_bom_item();


CREATE OR REPLACE FUNCTION protect_semi_finished_input()
RETURNS TRIGGER AS $$
DECLARE
    parent_id BIGINT;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.semi_finished_version_id IS DISTINCT FROM
       NEW.semi_finished_version_id THEN
        RAISE EXCEPTION '半成品输入不能移动到其他版本';
    END IF;
    parent_id := CASE WHEN TG_OP = 'DELETE'
        THEN OLD.semi_finished_version_id ELSE NEW.semi_finished_version_id END;
    IF TG_OP = 'DELETE' AND NOT EXISTS (
        SELECT 1 FROM semi_finished_version WHERE id = parent_id
    ) THEN
        RETURN OLD;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM semi_finished_version
        WHERE id = parent_id AND status = 'draft'
    ) THEN
        RAISE EXCEPTION '只有草稿半成品版本允许修改输入物料';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_semi_finished_input
BEFORE INSERT OR UPDATE OR DELETE ON semi_finished_input
FOR EACH ROW EXECUTE FUNCTION protect_semi_finished_input();


CREATE OR REPLACE FUNCTION protect_material_route_step()
RETURNS TRIGGER AS $$
DECLARE
    parent_id BIGINT;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.route_version_id IS DISTINCT FROM
       NEW.route_version_id THEN
        RAISE EXCEPTION '路线步骤不能移动到其他版本';
    END IF;
    parent_id := CASE WHEN TG_OP = 'DELETE'
        THEN OLD.route_version_id ELSE NEW.route_version_id END;
    IF TG_OP = 'DELETE' AND NOT EXISTS (
        SELECT 1 FROM material_route_version WHERE id = parent_id
    ) THEN
        RETURN OLD;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM material_route_version
        WHERE id = parent_id AND status = 'draft'
    ) THEN
        RAISE EXCEPTION '只有草稿路线版本允许修改步骤';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_material_route_step
BEFORE INSERT OR UPDATE OR DELETE ON material_route_step
FOR EACH ROW EXECUTE FUNCTION protect_material_route_step();


CREATE OR REPLACE FUNCTION protect_production_plan()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION '生产计划不能删除，只能取消';
    END IF;
    IF OLD.status = 'draft' AND NEW.status = 'draft'
       AND (TO_JSONB(NEW) - ARRAY['start_date', 'completion_date'])
           IS NOT DISTINCT FROM
           (TO_JSONB(OLD) - ARRAY['start_date', 'completion_date'])
    THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'draft' AND NEW.status = 'released'
       AND (TO_JSONB(NEW) - ARRAY['status', 'released_by', 'released_at'])
           IS NOT DISTINCT FROM
           (TO_JSONB(OLD) - ARRAY['status', 'released_by', 'released_at'])
    THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'draft' AND NEW.status = 'cancelled'
       AND (TO_JSONB(NEW) - 'status') IS NOT DISTINCT FROM
           (TO_JSONB(OLD) - 'status')
    THEN
        RETURN NEW;
    END IF;
    IF OLD.status = 'released' AND NEW.status IN ('producing', 'cancelled')
       AND (TO_JSONB(NEW) - 'status') IS NOT DISTINCT FROM
           (TO_JSONB(OLD) - 'status')
    THEN
        IF NEW.status = 'cancelled' AND EXISTS (
            SELECT 1
            FROM production_item production
            JOIN production_plan_material material
              ON material.id = production.production_plan_material_id
            JOIN production_plan_order_item item
              ON item.id = material.production_plan_order_item_id
            WHERE item.production_plan_id = OLD.id
        ) THEN
            RAISE EXCEPTION '必须先撤销未开工的现场生产对象';
        END IF;
        RETURN NEW;
    END IF;
    IF OLD.status = 'producing' AND NEW.status = 'completed'
       AND (TO_JSONB(NEW) - 'status') IS NOT DISTINCT FROM
           (TO_JSONB(OLD) - 'status')
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION '当前生产计划状态不允许修改';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_production_plan
BEFORE UPDATE OR DELETE ON production_plan
FOR EACH ROW EXECUTE FUNCTION protect_production_plan();


CREATE OR REPLACE FUNCTION protect_production_plan_order_item()
RETURNS TRIGGER AS $$
DECLARE
    parent_id BIGINT;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.production_plan_id IS DISTINCT FROM
       NEW.production_plan_id THEN
        RAISE EXCEPTION '计划订单明细不能移动到其他生产计划';
    END IF;
    parent_id := CASE WHEN TG_OP = 'DELETE'
        THEN OLD.production_plan_id ELSE NEW.production_plan_id END;
    IF NOT EXISTS (
        SELECT 1 FROM production_plan
        WHERE id = parent_id AND status = 'draft'
    ) THEN
        RAISE EXCEPTION '只有草稿生产计划允许修改订单明细';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_production_plan_order_item
BEFORE INSERT OR UPDATE OR DELETE ON production_plan_order_item
FOR EACH ROW EXECUTE FUNCTION protect_production_plan_order_item();


CREATE OR REPLACE FUNCTION validate_production_plan_order_item()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM product_bom_version
        WHERE id = NEW.product_bom_version_id
          AND status = 'published'
    ) THEN
        RAISE EXCEPTION '生产计划只能锁定当前已发布BOM版本';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_production_plan_order_item
BEFORE INSERT OR UPDATE ON production_plan_order_item
FOR EACH ROW EXECUTE FUNCTION validate_production_plan_order_item();


CREATE OR REPLACE FUNCTION protect_production_plan_material()
RETURNS TRIGGER AS $$
DECLARE
    parent_id BIGINT;
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.production_plan_order_item_id IS DISTINCT FROM
       NEW.production_plan_order_item_id THEN
        RAISE EXCEPTION '计划物料不能移动到其他订单明细';
    END IF;
    parent_id := CASE WHEN TG_OP = 'DELETE'
        THEN OLD.production_plan_order_item_id
        ELSE NEW.production_plan_order_item_id END;
    IF NOT EXISTS (
        SELECT 1
        FROM production_plan_order_item item
        JOIN production_plan plan ON plan.id = item.production_plan_id
        WHERE item.id = parent_id AND plan.status = 'draft'
    ) THEN
        RAISE EXCEPTION '只有草稿生产计划允许修改计划物料';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_production_plan_material
BEFORE INSERT OR UPDATE OR DELETE ON production_plan_material
FOR EACH ROW EXECUTE FUNCTION protect_production_plan_material();


CREATE OR REPLACE FUNCTION validate_production_plan_material()
RETURNS TRIGGER AS $$
DECLARE
    resolved_type TEXT;
BEGIN
    SELECT material_type INTO resolved_type
    FROM material WHERE id = NEW.material_id;
    IF resolved_type = 'semi_finished' AND NEW.semi_finished_version_id IS NULL THEN
        RAISE EXCEPTION '半成品计划物料必须锁定组成版本';
    END IF;
    IF resolved_type <> 'semi_finished' AND NEW.semi_finished_version_id IS NOT NULL THEN
        RAISE EXCEPTION '非半成品物料不能关联半成品组成版本';
    END IF;
    IF resolved_type = 'purchased' AND NEW.route_version_id IS NOT NULL THEN
        RAISE EXCEPTION '外购配件不能关联生产路线';
    END IF;
    IF resolved_type <> 'purchased' AND NEW.route_version_id IS NULL THEN
        RAISE EXCEPTION '非外购生产物料必须锁定路线版本';
    END IF;
    IF NEW.semi_finished_version_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM semi_finished_version
        WHERE id = NEW.semi_finished_version_id AND status = 'published'
    ) THEN
        RAISE EXCEPTION '生产计划只能锁定当前已发布半成品版本';
    END IF;
    IF NEW.route_version_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM material_route_version
        WHERE id = NEW.route_version_id AND status = 'published'
    ) THEN
        RAISE EXCEPTION '生产计划只能锁定当前已发布路线版本';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_production_plan_material
BEFORE INSERT OR UPDATE ON production_plan_material
FOR EACH ROW EXECUTE FUNCTION validate_production_plan_material();


CREATE OR REPLACE FUNCTION protect_production_plan_change_log()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '生产计划变更记录不能修改或删除';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_production_plan_change_log
BEFORE UPDATE OR DELETE ON production_plan_change_log
FOR EACH ROW EXECUTE FUNCTION protect_production_plan_change_log();


CREATE INDEX idx_workshop_department
ON workshop(department_id, active);

CREATE INDEX idx_user_session_expiry
ON user_sessions(expires_at);

CREATE INDEX idx_product_customer_name
ON product_customer_code(customer_name, active);

CREATE INDEX idx_material_product_type
ON material(product_id, material_type, active);

CREATE INDEX idx_customer_order_status
ON customer_order(customer_name, status, order_date DESC);

CREATE INDEX idx_customer_order_item_product
ON customer_order_item(product_id, delivery_date);

CREATE INDEX idx_production_plan_status
ON production_plan(status, start_date, completion_date);

CREATE INDEX idx_plan_material_material
ON production_plan_material(material_id);

CREATE INDEX idx_production_item_plan_material
ON production_item(production_plan_material_id);

CREATE INDEX idx_repository_department_product
ON repository(department, product_id);

CREATE INDEX idx_work_order_department_status
ON work_order(department, status, created_at DESC);

CREATE INDEX idx_work_order_batch_status
ON work_order_batch(status, submitted_at);

CREATE INDEX idx_rework_request_departments
ON rework_request(source_department, target_department, status);


INSERT INTO department (
    department_code,
    department_name,
    department_type
) VALUES
('sys', '系统管理', 'system'),
('engineering', '工程部', 'office'),
('business', '业务部', 'office'),
('planning', '生产计划部', 'office'),
('stamp', '冲压部门', 'production'),
('cnc', '机加部门', 'production'),
('polish', '表面处理部门', 'production'),
('assembly', '装配部门', 'production'),
('finished', '成品部门', 'production'),
('qc', 'QC部门', 'quality');


INSERT INTO users (
    username,
    password,
    department_id,
    role,
    permissions
) VALUES
(
    'admin',
    '1',
    (SELECT id FROM department WHERE department_code = 'sys'),
    'supervisor',
    'master:manage,product:manage,order:manage,plan:manage,'
    || 'task:view,task:assign,task:complete,record:view'
),
(
    'engineering',
    '1',
    (SELECT id FROM department WHERE department_code = 'engineering'),
    'clerk',
    'product:view,product:edit,bom:edit,route:edit'
),
(
    'business',
    '1',
    (SELECT id FROM department WHERE department_code = 'business'),
    'clerk',
    'product:view,order:view,order:edit'
),
(
    'planning',
    '1',
    (SELECT id FROM department WHERE department_code = 'planning'),
    'clerk',
    'product:view,order:view,plan:view,plan:edit'
),
(
    'stamp',
    '1',
    (SELECT id FROM department WHERE department_code = 'stamp'),
    'supervisor',
    'task:view,task:assign,task:complete,record:view'
),
(
    'cnc',
    '1',
    (SELECT id FROM department WHERE department_code = 'cnc'),
    'supervisor',
    'task:view,task:assign,task:complete,record:view'
),
(
    'polish',
    '1',
    (SELECT id FROM department WHERE department_code = 'polish'),
    'supervisor',
    'task:view,task:assign,task:complete,record:view'
),
(
    'assembly',
    '1',
    (SELECT id FROM department WHERE department_code = 'assembly'),
    'supervisor',
    'task:view,task:assign,task:complete,record:view'
),
(
    'finished',
    '1',
    (SELECT id FROM department WHERE department_code = 'finished'),
    'supervisor',
    'task:view,task:assign,task:complete,record:view'
),
(
    'qc',
    '1',
    (SELECT id FROM department WHERE department_code = 'qc'),
    'supervisor',
    'task:view,task:assign,task:complete,record:view'
);


INSERT INTO product (
    factory_code,
    product_name,
    status,
    created_by
) VALUES (
    'Z8412',
    'ET-MO199-L44.50狗扣',
    'draft',
    (SELECT id FROM users WHERE username = 'engineering')
)
ON CONFLICT (factory_code) DO NOTHING;


INSERT INTO product_customer_code (
    product_id,
    customer_name,
    customer_product_code
)
SELECT
    id,
    'ET',
    'MO199'
FROM product
WHERE factory_code = 'Z8412'
ON CONFLICT (customer_name, customer_product_code) DO NOTHING;


INSERT INTO material (
    product_id,
    material_code,
    material_name,
    material_type,
    material_grade,
    specification,
    note
)
SELECT
    product.id,
    seed.material_code,
    seed.material_name,
    seed.material_type,
    seed.material_grade,
    seed.specification,
    seed.note
FROM product
CROSS JOIN (
    VALUES
    (
        'Z8412',
        'ET-MO199-L44.50狗扣',
        'finished',
        NULL,
        NULL,
        NULL
    ),
    (
        'Z8412-01',
        '主体',
        'self_made',
        '316L',
        '32.42*13.03*Ø6.55',
        'Z8412/Z8311两款共用'
    ),
    (
        'Z8412-02',
        '利仔',
        'self_made',
        '316L',
        '15.10*8.50*3.30',
        'Z8412/Z8311两款共用'
    ),
    (
        'Z8412-03',
        '拉环',
        'self_made',
        '316L',
        'Ø16.50*16.00*7.55',
        'Z8412/Z8311两款共用'
    ),
    (
        'Z8412-04',
        '卜头螺丝',
        'self_made',
        '316L',
        'Ø4.80*6.90*M4（细牙）',
        NULL
    ),
    (
        'Z8412-05',
        '弹簧',
        'self_made',
        '304',
        'Ø1.95*13.00*线径0.25',
        'Z8412/Z8311两款共用'
    ),
    (
        'Z8412-06',
        '卡环',
        'self_made',
        '316L',
        'Ø3.00*1.00',
        NULL
    )
) AS seed (
    material_code,
    material_name,
    material_type,
    material_grade,
    specification,
    note
)
WHERE product.factory_code = 'Z8412'
ON CONFLICT (material_code) DO NOTHING;
