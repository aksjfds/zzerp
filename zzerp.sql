-- ============================================================
-- ERP 库存流水系统
-- 流程：
-- in -> laser -> stamp -> cnc -> polish -> qc -> out
-- ============================================================

-- ============================================================
-- 库存流水表
-- ============================================================

CREATE TABLE repository (
    id BIGSERIAL PRIMARY KEY,
    -- in / laser / stamp / cnc / polish / qc / out
    repository_name VARCHAR(50) NOT NULL,
    order_id INT NOT NULL,
    item VARCHAR(100) NOT NULL,
    quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0)
);


-- ============================================================
-- 操作日志表
-- ============================================================

CREATE TABLE records (
    id BIGSERIAL PRIMARY KEY,
    order_id INT NOT NULL,
    item VARCHAR(100) NOT NULL,
    from_repository VARCHAR(50),
    to_repository VARCHAR(50),
    -- 仅打磨出库到QC、QC返工到打磨使用，可为空
    worker VARCHAR(100),
    quantity INT NOT NULL CHECK (quantity > 0),
    operator VARCHAR(100),
    note VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 索引
-- ============================================================

CREATE INDEX idx_repository_order_item
ON repository(order_id, item);

CREATE INDEX idx_repository_name
ON repository(repository_name);

CREATE INDEX idx_repository_name_order_item
ON repository(repository_name, order_id, item);

CREATE INDEX idx_records_order_item
ON records(order_id, item);

CREATE INDEX idx_records_from_repo_order_item
ON records(from_repository, order_id, item);

CREATE INDEX idx_records_to_repo_order_item
ON records(to_repository, order_id, item);

CREATE INDEX idx_records_worker
ON records(worker);
