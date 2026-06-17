-- ============================================================
-- ERP 库存流水系统
-- 流程：
-- in -> laser -> stamp -> cnc -> polish -> qc -> out
-- ============================================================

-- ============================================================
-- 库存流水表
-- ============================================================

CREATE TABLE inventory_transaction (
    id BIGSERIAL PRIMARY KEY,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

    order_id INT NOT NULL,

    item VARCHAR(100) NOT NULL,

    -- in / laser / stamp / cnc / polish / qc / out
    repository VARCHAR(50) NOT NULL,

    -- 仅打磨工序使用，可为空
    worker VARCHAR(100),

    inbound INT NOT NULL DEFAULT 0 CHECK (inbound >= 0),

    outbound INT NOT NULL DEFAULT 0 CHECK (outbound >= 0),
);


-- ============================================================
-- 操作日志表
-- ============================================================

CREATE TABLE inventory_log (
    id BIGSERIAL PRIMARY KEY,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP

    order_id INT NOT NULL,

    item VARCHAR(100) NOT NULL,

    from_repository VARCHAR(50),

    to_repository VARCHAR(50),

    quantity INT NOT NULL CHECK (quantity > 0),

    operator VARCHAR(100),

    note VARCHAR(255),
);


-- ============================================================
-- 索引
-- ============================================================

CREATE INDEX idx_inventory_order_item
ON inventory_transaction(order_id, item);

CREATE INDEX idx_inventory_repository
ON inventory_transaction(repository);

CREATE INDEX idx_inventory_repo_order_item
ON inventory_transaction(repository, order_id, item);