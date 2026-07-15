-- ============================================================
-- ZZ ERP 工程产品、BOM 与工艺路线
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

BEGIN;

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    department TEXT NOT NULL,
    role TEXT NOT NULL,
    permissions TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_factory_code UNIQUE (factory_code)
);

CREATE TABLE product_version (
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    version INT NOT NULL CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id, version)
);

ALTER TABLE product
ADD CONSTRAINT fk_product_current_version
FOREIGN KEY (id, version)
REFERENCES product_version(product_id, version)
DEFERRABLE INITIALLY DEFERRED;

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

CREATE TABLE product_process_flow (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    product_version INT NOT NULL CHECK (product_version > 0),
    flow_json JSONB NOT NULL DEFAULT '{"schema_version": 1, "nodes": [], "edges": []}'::jsonb,
    CHECK (jsonb_typeof(flow_json) = 'object'),
    CHECK (flow_json ? 'schema_version'),
    CHECK (jsonb_typeof(flow_json->'schema_version') = 'number'),
    CHECK (flow_json->>'schema_version' = '1'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (flow_json ? 'nodes'),
    CHECK (jsonb_typeof(flow_json->'nodes') = 'array'),
    CHECK (flow_json ? 'edges'),
    CHECK (jsonb_typeof(flow_json->'edges') = 'array'),
    CONSTRAINT fk_product_process_flow_version
        FOREIGN KEY (product_id, product_version)
        REFERENCES product_version(product_id, version) ON DELETE CASCADE,
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
    procedure_type TEXT NOT NULL DEFAULT 'standard'
        CHECK (procedure_type IN ('standard', 'purchase_receipt')),
    UNIQUE (id, procedure_type),
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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
        UNIQUE (id, product_id, product_version)
);

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

CREATE TABLE work_order (
    id BIGSERIAL PRIMARY KEY,
    work_order_no TEXT UNIQUE,
    repository_id BIGINT,
    production_item_id BIGINT NOT NULL REFERENCES production_item(id),
    procedure_id BIGINT,
    procedure_type TEXT NOT NULL
        CHECK (procedure_type IN ('standard', 'purchase_receipt', 'assembly')),
    flow_node_id TEXT NOT NULL,
    procedure_name TEXT NOT NULL,
    worker_id BIGINT REFERENCES worker(id),
    quantity INT NOT NULL CHECK (quantity > 0),
    completed_quantity INT NOT NULL DEFAULT 0
        CHECK (completed_quantity >= 0 AND completed_quantity <= quantity),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMPTZ,
    CHECK (
        (status = 'open' AND closed_at IS NULL)
        OR (status IN ('closed', 'cancelled') AND closed_at IS NOT NULL)
    ),
    CHECK (status <> 'closed' OR completed_quantity = quantity),
    CHECK (status <> 'cancelled' OR completed_quantity = 0),
    CHECK (
        (procedure_id IS NULL AND procedure_type = 'assembly')
        OR (procedure_id IS NOT NULL AND procedure_type IN ('standard', 'purchase_receipt'))
    ),
    CONSTRAINT fk_work_order_repository_item
        FOREIGN KEY (repository_id, production_item_id)
        REFERENCES repository(id, production_item_id),
    CONSTRAINT fk_work_order_procedure_type
        FOREIGN KEY (procedure_id, procedure_type)
        REFERENCES procedure(id, procedure_type)
);

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

CREATE TABLE work_order_batch (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id) ON DELETE CASCADE,
    submitted_quantity INT NOT NULL CHECK (submitted_quantity > 0),
    flow_node_id TEXT NOT NULL,
    qualified_quantity INT CHECK (qualified_quantity >= 0),
    rework_quantity INT CHECK (rework_quantity >= 0),
    scrap_quantity INT CHECK (scrap_quantity >= 0),
    lost_quantity INT CHECK (lost_quantity >= 0),
    qc_worker_id BIGINT REFERENCES worker(id),
    qc_worker_name TEXT,
    defect_reason TEXT,
    recorded_at TIMESTAMPTZ,
    UNIQUE (id, work_order_id),
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
            'initial', 'process', 'purchase_receipt', 'assembly_input', 'assembly_output',
            'qc_qualified', 'qc_rework', 'scrap', 'lost'
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
            AND source_department_id IS NOT NULL
            AND (target_flow_node_id IS NULL) = (target_department_id IS NULL)
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
    )
);

CREATE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = clock_timestamp();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION validate_production_movement_context() RETURNS TRIGGER AS $$
DECLARE
    order_item_id BIGINT;
    order_type TEXT;
    order_flow_node_id TEXT;
    order_status TEXT;
    material_quantity INT;
    batch_flow_node_id TEXT;
    batch_submitted_quantity INT;
    batch_recorded_at TIMESTAMPTZ;
BEGIN
    IF NEW.work_order_id IS NOT NULL THEN
        SELECT production_item_id, procedure_type, flow_node_id, status
        INTO order_item_id, order_type, order_flow_node_id, order_status
        FROM work_order
        WHERE id = NEW.work_order_id
        FOR UPDATE;

        IF order_item_id IS NOT NULL THEN
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
                IF NEW.quantity <> material_quantity THEN
                    RAISE EXCEPTION 'assembly input quantity must match its material allocation'
                        USING ERRCODE = '23514';
                END IF;
            ELSE
                IF (NEW.movement_type = 'assembly_output' AND order_type <> 'assembly')
                    OR (NEW.movement_type = 'process' AND order_type <> 'standard')
                    OR (NEW.movement_type = 'purchase_receipt'
                        AND order_type <> 'purchase_receipt') THEN
                    RAISE EXCEPTION 'movement type must match the work order procedure type'
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
                RAISE EXCEPTION 'submission movement source node must match the work order'
                    USING ERRCODE = '23514';
            END IF;
        END IF;
    END IF;

    IF NEW.work_order_batch_id IS NOT NULL THEN
        IF NEW.work_order_id IS NULL THEN
            RAISE EXCEPTION 'batch movement must retain its work order'
                USING ERRCODE = '23514';
        END IF;
        SELECT flow_node_id, submitted_quantity, recorded_at
        INTO batch_flow_node_id, batch_submitted_quantity, batch_recorded_at
        FROM work_order_batch
        WHERE id = NEW.work_order_batch_id
          AND work_order_id = NEW.work_order_id
        FOR UPDATE;
        IF batch_flow_node_id IS NULL THEN
            RAISE EXCEPTION 'movement batch must belong to the referenced work order'
                USING ERRCODE = '23514';
        END IF;
        IF batch_recorded_at IS NOT NULL THEN
            RAISE EXCEPTION 'completed QC batch cannot receive new movements'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.movement_type IN ('process', 'purchase_receipt', 'assembly_output') THEN
            IF NEW.target_flow_node_id IS DISTINCT FROM batch_flow_node_id
                OR NEW.quantity <> batch_submitted_quantity THEN
                RAISE EXCEPTION 'submission movement must match its QC batch node and quantity'
                    USING ERRCODE = '23514';
            END IF;
        ELSIF NEW.movement_type IN ('qc_qualified', 'qc_rework', 'scrap', 'lost')
            AND NEW.source_flow_node_id IS DISTINCT FROM batch_flow_node_id THEN
            RAISE EXCEPTION 'QC movement source node must match its batch'
                USING ERRCODE = '23514';
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
        NEW.procedure_type,
        NEW.procedure_name,
        NEW.flow_node_id
    ) IS DISTINCT FROM (
        OLD.procedure_id,
        OLD.procedure_type,
        OLD.procedure_name,
        OLD.flow_node_id
    ) AND EXISTS (
        SELECT 1
        FROM production_movement
        WHERE work_order_id = NEW.id
    ) THEN
        RAISE EXCEPTION 'work order procedure snapshot is retained by movement history'
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
    submission_count INT;
    submission_quantity BIGINT;
    moved_qualified BIGINT;
    moved_rework BIGINT;
    moved_scrap BIGINT;
    moved_lost BIGINT;
BEGIN
    IF OLD.recorded_at IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'completed QC batch history is immutable'
            USING ERRCODE = '23514';
    END IF;
    IF (NEW.work_order_id, NEW.flow_node_id, NEW.submitted_quantity)
        IS DISTINCT FROM (OLD.work_order_id, OLD.flow_node_id, OLD.submitted_quantity)
        AND EXISTS (
            SELECT 1
            FROM production_movement
            WHERE work_order_batch_id = NEW.id
        ) THEN
        RAISE EXCEPTION 'batch work order, node and submitted quantity are retained by movement history'
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
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'production movement history is immutable'
            USING ERRCODE = '23514';
    END IF;
    IF OLD.movement_type <> 'initial'
        OR OLD.work_order_id IS NOT NULL
        OR OLD.work_order_batch_id IS NOT NULL THEN
        RAISE EXCEPTION 'work order and QC movement history cannot be deleted'
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

CREATE TRIGGER trg_production_movement_context
BEFORE INSERT
ON production_movement
FOR EACH ROW EXECUTE FUNCTION validate_production_movement_context();

CREATE TRIGGER trg_work_order_movement_items
BEFORE UPDATE OF production_item_id, procedure_id, procedure_type, procedure_name, flow_node_id
ON work_order
FOR EACH ROW EXECUTE FUNCTION validate_work_order_movement_items();

CREATE TRIGGER trg_batch_movement_context
BEFORE UPDATE ON work_order_batch
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

CREATE TRIGGER trg_product_updated_at
BEFORE UPDATE ON product
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_product_bom_updated_at
BEFORE UPDATE ON product_bom
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_product_process_flow_updated_at
BEFORE UPDATE ON product_process_flow
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_customer_order_updated_at
BEFORE UPDATE ON customer_order
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_product_customer_name_trgm
    ON product USING GIN (customer_name gin_trgm_ops);
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
CREATE INDEX idx_customer_order_updated ON customer_order(updated_at DESC, id DESC);
CREATE INDEX idx_customer_order_item_product_version
    ON customer_order_item(product_id, product_version);
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
CREATE INDEX idx_production_item_order_item ON production_item(customer_order_item_id);
CREATE INDEX idx_production_item_bom ON production_item(product_bom_id);
CREATE INDEX idx_work_order_repository ON work_order(repository_id);
CREATE INDEX idx_work_order_production_item ON work_order(production_item_id);
CREATE INDEX idx_work_order_worker_activity
    ON work_order(worker_id, COALESCE(closed_at, created_at) DESC, id DESC);
CREATE INDEX idx_work_order_procedure ON work_order(procedure_id, id DESC);
CREATE INDEX idx_work_order_repository_open ON work_order(repository_id)
    WHERE status = 'open';
CREATE INDEX idx_work_order_item_node_status
    ON work_order(production_item_id, flow_node_id, status);
CREATE INDEX idx_work_order_batch_order ON work_order_batch(work_order_id);
CREATE INDEX idx_work_order_material_repository ON work_order_material(repository_id);
CREATE INDEX idx_work_order_material_production_item ON work_order_material(production_item_id);
CREATE INDEX idx_work_order_batch_pending ON work_order_batch(id DESC, work_order_id)
    WHERE recorded_at IS NULL;
CREATE INDEX idx_work_order_batch_qc_worker_recorded
    ON work_order_batch(qc_worker_id, recorded_at DESC);
CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX idx_user_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_worker_department_name ON worker(department_id, worker_name, id);
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
),
(
    'warehouse', '1', 'warehouse', 'operator', 'production:view,production:manage'
);

INSERT INTO department (department_name, department_code) VALUES
('工程部', 'engineering'),
('业务部', 'business'),
('冲压部门', 'stamp'),
('表面处理部门', 'polish'),
('QC部门', 'qc'),
('装配部门', 'assembly'),
('仓库部门', 'warehouse');

INSERT INTO workshop (department_id, workshop_name)
SELECT id, '激光开料车间' FROM department WHERE department_code = 'stamp';

INSERT INTO workshop (department_id, workshop_name)
SELECT id, '手磨车间' FROM department WHERE department_code = 'polish';

INSERT INTO workshop (department_id, workshop_name)
SELECT id, '外购件管理' FROM department WHERE department_code = 'warehouse';

INSERT INTO procedure (workshop_id, procedure_name)
SELECT id, '激光开料' FROM workshop WHERE workshop_name = '激光开料车间';

INSERT INTO procedure (workshop_id, procedure_name)
SELECT id, '粗光' FROM workshop WHERE workshop_name = '手磨车间';

INSERT INTO procedure (workshop_id, procedure_name, procedure_type)
SELECT id, '外购入库', 'purchase_receipt'
FROM workshop WHERE workshop_name = '外购件管理';

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

INSERT INTO product_version (product_id, version)
SELECT id, 1 FROM product WHERE factory_code = 'DEMO-001';

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

INSERT INTO worker (worker_name, department_id, workshop_id)
SELECT '仓库示例员工', department.id, workshop.id
FROM department
JOIN workshop ON workshop.department_id = department.id
WHERE department.department_code = 'warehouse' AND workshop.workshop_name = '外购件管理';

COMMIT;
