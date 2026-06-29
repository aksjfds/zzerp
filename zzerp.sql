-- ============================================================
-- ZZ ERP 产品流转与工单系统
-- ============================================================

CREATE TABLE worker (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (name, department)
);


CREATE TABLE procedure (
    id BIGSERIAL PRIMARY KEY,
    procedure_name TEXT NOT NULL,
    department TEXT NOT NULL,
    UNIQUE (department, procedure_name)
);


CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    department TEXT NOT NULL,
    role TEXT NOT NULL,
    permissions TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- 每一行代表一个订单产品。
CREATE TABLE product (
    id BIGSERIAL PRIMARY KEY,
    order_id TEXT NOT NULL,
    zz_code TEXT NOT NULL,
    product_name TEXT NOT NULL,
    delivery_date DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (order_id, zz_code, product_name)
);


-- 产品正式经过的部门顺序，例如 laser -> polish -> qc。
CREATE TABLE product_department_step (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    sequence_no INT NOT NULL CHECK (sequence_no > 0),
    department TEXT NOT NULL,
    UNIQUE (product_id, sequence_no)
);


-- 产品正式归属各部门的数量。内部送检不会改变此表的部门。
CREATE TABLE repository (
    id BIGSERIAL PRIMARY KEY,
    department TEXT NOT NULL,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    UNIQUE (department, product_id)
);


-- 一个订单产品在某部门内需要执行的有序工艺。
CREATE TABLE department_process (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    department TEXT NOT NULL,
    sequence_no INT NOT NULL CHECK (sequence_no > 0),
    process_name TEXT NOT NULL,
    requires_qc BOOLEAN NOT NULL DEFAULT FALSE,
    available_quantity INT NOT NULL DEFAULT 0 CHECK (available_quantity >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (product_id, department, sequence_no),
    UNIQUE (product_id, department, process_name)
);


-- 每张工单只对应一个工艺、一个工人和一次领取数量。
CREATE TABLE work_order (
    id BIGSERIAL PRIMARY KEY,
    work_order_no TEXT UNIQUE,
    product_id BIGINT NOT NULL REFERENCES product(id),
    process_id BIGINT NOT NULL REFERENCES department_process(id),
    worker_id BIGINT NOT NULL REFERENCES worker(id),
    issued_quantity INT NOT NULL CHECK (issued_quantity > 0),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_by BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP,
    note TEXT
);


-- 需要 QC 时先建立 pending_qc 批次，由 QC 补全结果。
-- 不需要 QC 时由部门主管直接建立 completed 批次。
CREATE TABLE work_order_batch (
    id BIGSERIAL PRIMARY KEY,
    work_order_id BIGINT NOT NULL REFERENCES work_order(id),
    batch_no INT NOT NULL CHECK (batch_no > 0),
    submitted_quantity INT NOT NULL CHECK (submitted_quantity > 0),
    ok_quantity INT,
    rework_quantity INT,
    scrap_quantity INT,
    lost_quantity INT,
    qc_worker_id BIGINT REFERENCES worker(id),
    defect_reason TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending_qc', 'completed')),
    submitted_by BIGINT NOT NULL REFERENCES users(id),
    submitted_at TIMESTAMP NOT NULL DEFAULT NOW(),
    inspected_by BIGINT REFERENCES users(id),
    inspected_at TIMESTAMP,
    UNIQUE (work_order_id, batch_no),
    CHECK (ok_quantity IS NULL OR ok_quantity >= 0),
    CHECK (rework_quantity IS NULL OR rework_quantity >= 0),
    CHECK (scrap_quantity IS NULL OR scrap_quantity >= 0),
    CHECK (lost_quantity IS NULL OR lost_quantity >= 0)
);


-- pending_qc 阶段只允许分配或重新分配 QC 工人；完成后的批次永久不可修改或删除。
CREATE OR REPLACE FUNCTION protect_work_order_batch_result()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION '工单批次不允许删除';
    END IF;
    IF OLD.status = 'completed' THEN
        RAISE EXCEPTION '已完成的工单批次不允许修改';
    END IF;
    IF NEW.status = 'pending_qc' THEN
        IF ROW(
            NEW.work_order_id,
            NEW.batch_no,
            NEW.submitted_quantity,
            NEW.ok_quantity,
            NEW.rework_quantity,
            NEW.scrap_quantity,
            NEW.lost_quantity,
            NEW.defect_reason,
            NEW.submitted_by,
            NEW.submitted_at,
            NEW.inspected_by,
            NEW.inspected_at
        ) IS DISTINCT FROM ROW(
            OLD.work_order_id,
            OLD.batch_no,
            OLD.submitted_quantity,
            OLD.ok_quantity,
            OLD.rework_quantity,
            OLD.scrap_quantity,
            OLD.lost_quantity,
            OLD.defect_reason,
            OLD.submitted_by,
            OLD.submitted_at,
            OLD.inspected_by,
            OLD.inspected_at
        ) THEN
            RAISE EXCEPTION '待质检批次只允许变更 QC 工人';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.status <> 'completed' THEN
        RAISE EXCEPTION '待质检批次只能更新为已完成';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_work_order_batch_result
BEFORE UPDATE OR DELETE ON work_order_batch
FOR EACH ROW EXECUTE FUNCTION protect_work_order_batch_result();


-- 只记录正式部门流转；部门内部送检由工单批次追踪。
CREATE TABLE records (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    from_repository TEXT NOT NULL,
    to_repository TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


CREATE TABLE user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


INSERT INTO users (username, password, department, role, permissions) VALUES
('admin', '1', 'sys', 'supervisor', 'product:view,product:add,record:view,sys:user:add'),
('polish', '1', 'polish', 'supervisor', 'task:view,task:assign,task:complete'),
('qc', '1', 'qc', 'supervisor', 'task:view,task:assign,task:complete');


CREATE INDEX idx_department_step_product
ON product_department_step(product_id, sequence_no);

CREATE INDEX idx_repository_department
ON repository(department);

CREATE INDEX idx_department_process_product
ON department_process(product_id, department, sequence_no);

CREATE INDEX idx_work_order_department_process
ON work_order(process_id, status);

CREATE INDEX idx_work_order_worker
ON work_order(worker_id, status);

CREATE INDEX idx_work_order_batch_status
ON work_order_batch(status, submitted_at);

CREATE INDEX idx_records_product
ON records(product_id, created_at DESC);

CREATE INDEX idx_worker_department
ON worker(department, active);

CREATE INDEX idx_users_department_role
ON users(department, role);

CREATE INDEX idx_user_sessions_user_id
ON user_sessions(user_id);

CREATE INDEX idx_user_sessions_expires_at
ON user_sessions(expires_at);
