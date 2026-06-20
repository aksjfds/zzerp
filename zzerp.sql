-- ============================================================
-- ZZ ERP 产品流转系统
-- ============================================================

CREATE TABLE worker (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    UNIQUE (name, department)
);


-- 产品当前所在部门库存
CREATE TABLE repository (
    id BIGSERIAL PRIMARY KEY,
    -- in / laser / stamp / cnc / polish / qc / out
    department TEXT NOT NULL,
    -- 产品的本厂编码
    zz_code TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    UNIQUE (department, zz_code, product_name)
);


-- 产品
CREATE TABLE product (
    id BIGSERIAL PRIMARY KEY,
    zz_code TEXT NOT NULL,
    -- L46狗扣-主体或L46狗扣-拉环
    product_name TEXT NOT NULL,
    -- in / laser / stamp / cnc / polish / qc / out
    process TEXT[] NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (zz_code, product_name)
);


-- 每个部门的细分工艺
CREATE TABLE procedure (
    id BIGSERIAL PRIMARY KEY,
    procedure_name TEXT NOT NULL,
    department TEXT NOT NULL,
    UNIQUE (department, procedure_name)
);


-- 产品流转记录
CREATE TABLE records (
    id BIGSERIAL PRIMARY KEY,
    zz_code TEXT NOT NULL,
    product TEXT NOT NULL,
    from_repository TEXT NOT NULL,
    to_repository TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


-- 部门主管分配给工人的任务
CREATE TABLE tasks (
    id BIGSERIAL PRIMARY KEY,
    zz_code TEXT NOT NULL,
    product TEXT NOT NULL,
    worker TEXT NOT NULL,
    department TEXT NOT NULL,
    procedure TEXT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    ok INT NOT NULL DEFAULT 0 CHECK (ok >= 0 AND ok <= quantity),
    status BOOLEAN NOT NULL DEFAULT FALSE,
    note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
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


INSERT INTO users (username, password, department, role, permissions) VALUES
('admin', 'admin123', 'sys', 'supervisor', 'product:view,product:add,record:view,sys:user:add'),
('laser_lead', 'laser123', 'laser', 'supervisor', 'task:view,task:assign,task:complete'),
('stamp_lead', 'stamp123', 'stamp', 'supervisor', 'task:view,task:assign,task:complete'),
('cnc_lead', 'cnc123', 'cnc', 'supervisor', 'task:view,task:assign,task:complete'),
('polish_lead', 'polish123', 'polish', 'supervisor', 'task:view,task:assign,task:complete'),
('qc_lead', 'qc123', 'qc', 'supervisor', 'task:view,task:assign,task:complete');


-- ============================================================
-- 索引
-- ============================================================

CREATE INDEX idx_worker_department
ON worker(department);

CREATE INDEX idx_repository_department
ON repository(department);

CREATE INDEX idx_repository_product
ON repository(zz_code, product_name);

CREATE INDEX idx_repository_department_product
ON repository(department, zz_code, product_name);

CREATE INDEX idx_product_zz_code
ON product(zz_code);

CREATE INDEX idx_product_name
ON product(product_name);

CREATE INDEX idx_procedure_department
ON procedure(department);

CREATE INDEX idx_records_product
ON records(zz_code, product);

CREATE INDEX idx_records_from_repository
ON records(from_repository, zz_code, product);

CREATE INDEX idx_records_to_repository
ON records(to_repository, zz_code, product);

CREATE INDEX idx_records_created_at
ON records(created_at DESC);

CREATE INDEX idx_tasks_department_status
ON tasks(department, status);

CREATE INDEX idx_tasks_worker
ON tasks(worker);

CREATE INDEX idx_tasks_product
ON tasks(zz_code, product);

CREATE INDEX idx_users_department_role
ON users(department, role);
