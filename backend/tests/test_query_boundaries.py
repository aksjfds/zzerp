from types import SimpleNamespace

from modules.assembly import work_orders as assembly_work_orders
from modules.planning import part_progress
from modules.planning.part_progress import _group_rows_by_order
from modules.workforce import workers


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def test_assembly_allocation_batches_reservation_queries(monkeypatch):
    rows = [
        SimpleNamespace(repository_id=1, work_order_id=100, quantity=2),
        SimpleNamespace(repository_id=2, work_order_id=101, quantity=7),
    ]

    class Session:
        execute_count = 0

        def execute(self, _statement):
            self.execute_count += 1
            return _Rows(rows)

    session = Session()
    open_id_calls = []
    monkeypatch.setattr(
        assembly_work_orders,
        "assembly_item_unit_quantity",
        lambda _session, _item: 1,
    )
    monkeypatch.setattr(
        assembly_work_orders,
        "open_work_order_ids",
        lambda _session, ids: open_id_calls.append(ids) or frozenset({100}),
    )
    repositories = [
        SimpleNamespace(id=1, source_flow_node_id="source", quantity=6),
        SimpleNamespace(id=2, source_flow_node_id="source", quantity=10),
    ]
    items = [SimpleNamespace(), SimpleNamespace()]

    allocated = assembly_work_orders._allocate_materials(
        session,
        repositories,
        items,
        quantity=8,
    )

    assert allocated == {1: 4, 2: 4}
    assert session.execute_count == 1
    assert open_id_calls == [{100, 101}]


def test_worker_pay_starts_from_monthly_qualified_batches(monkeypatch):
    session = SimpleNamespace(get=lambda _model, _worker_id: SimpleNamespace(id=7))

    class SessionContext:
        def __enter__(self):
            return session

        def __exit__(self, *_args):
            return False

    seen = {}
    monkeypatch.setattr(workers, "SessionLocal", SessionContext)
    monkeypatch.setattr(
        workers,
        "list_qualified_batch_order_ids",
        lambda _session, start, end: (
            seen.update(month=(start, end)) or frozenset({10, 11})
        ),
    )
    monkeypatch.setattr(
        workers,
        "list_work_order_activities",
        lambda _session, ids, **filters: (
            seen.update(ids=ids, filters=filters) or []
        ),
    )
    monkeypatch.setattr(
        workers,
        "list_batch_activities",
        lambda *_args, **_kwargs: [],
    )

    result = workers.worker_pay_summary(7, "2026-07")

    assert seen["ids"] == frozenset({10, 11})
    assert seen["filters"] == {
        "worker_id": 7,
        "work_order_type": "tag",
    }
    assert result["qualified_quantity"] == 0
    assert result["items"] == []


def test_pmc_part_progress_groups_rows_without_splitting_orders():
    rows = [
        {
            "customer_order_id": 7,
            "customer_order_no": "SO-007",
            "customer_name": "客户甲",
            "order_status": "planned",
            "production_item_id": 101,
        },
        {
            "customer_order_id": 8,
            "customer_order_no": "SO-008",
            "customer_name": "客户乙",
            "order_status": "confirmed",
            "production_item_id": 201,
        },
        {
            "customer_order_id": 7,
            "customer_order_no": "SO-007",
            "customer_name": "客户甲",
            "order_status": "planned",
            "production_item_id": 102,
        },
    ]

    grouped = _group_rows_by_order(rows)

    assert [item["customer_order_id"] for item in grouped] == [7, 8]
    assert [
        row["production_item_id"] for row in grouped[0]["parts"]
    ] == [101, 102]


def test_pmc_part_progress_focuses_order_without_hiding_others():
    rows = [
        {
            "customer_order_id": 7,
            "customer_order_no": "SO-007",
            "customer_name": "客户甲",
            "order_status": "planned",
            "production_item_id": 101,
        },
        {
            "customer_order_id": 8,
            "customer_order_no": "SO-008",
            "customer_name": "客户乙",
            "order_status": "confirmed",
            "production_item_id": 201,
        },
    ]

    grouped = _group_rows_by_order(rows, focus_order_id=8)

    assert [item["customer_order_id"] for item in grouped] == [8, 7]


def test_department_production_progress_exposes_requested_columns(
    monkeypatch,
):
    monkeypatch.setattr(
        part_progress,
        "list_part_progress",
        lambda **_kwargs: (
            [
                {
                    "parts": [
                        {
                            "production_item_id": 101,
                            "part_no": "P-001",
                            "part_name": "主体",
                            "customer_order_no": "SO-007",
                            "order_date": "2026-07-28",
                            "target_quantity": 100,
                            "shipped_quantity": 40,
                            "outstanding_quantity": 60,
                            "completion_date": None,
                            "remark": "加急",
                        },
                        {
                            "production_item_id": 102,
                            "part_no": "P-002",
                            "part_name": "弹簧",
                            "customer_order_no": "SO-007",
                            "order_date": "2026-07-28",
                            "target_quantity": 200,
                            "shipped_quantity": 80,
                            "outstanding_quantity": 120,
                            "completion_date": None,
                            "remark": "",
                        },
                    ],
                }
            ],
            1,
            [],
        ),
    )

    rows, total = part_progress.list_department_production_progress(
        "stamp",
        page=2,
        page_size=1,
        keyword=None,
    )

    assert total == 2
    assert rows == [
        {
            "production_item_id": 102,
            "part_no": "P-002",
            "part_name": "弹簧",
            "customer_order_no": "SO-007",
            "order_date": "2026-07-28",
            "order_quantity": 200,
            "shipped_quantity": 80,
            "outstanding_quantity": 120,
            "completion_date": None,
            "remark": "",
        }
    ]
