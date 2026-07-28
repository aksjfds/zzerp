import pytest

from departments.contracts import CAP_REPOSITORIES
from departments.registry import department_api, department_manifests
from modules.errors import DomainError
from routers import work_orders as work_order_routes
from schemas.production import AssemblyWorkOrderCreate, WorkOrderCreate


def test_department_manifest_exposes_execution_modules_and_capabilities():
    manifests = {item["code"]: item for item in department_manifests()}

    assert manifests["assembly"]["execution_module"] == "assembly"
    assert "assembly" in manifests["assembly"]["capabilities"]
    assert manifests["qc"]["execution_module"] == "quality"
    assert "quality" in manifests["qc"]["capabilities"]
    assert "special_printing" in manifests["polish"]["capabilities"]
    assert "production_progress" in manifests["stamp"]["capabilities"]
    assert "production_progress" in manifests["cnc"]["capabilities"]
    assert "production_progress" in manifests["polish"]["capabilities"]
    assert "production_progress" in manifests["assembly"]["capabilities"]
    assert "production_progress" in manifests["warehouse"]["capabilities"]
    assert "production_progress" not in manifests["qc"]["capabilities"]


def test_department_production_progress_forwards_department_context(
    monkeypatch,
):
    seen = {}
    monkeypatch.setattr(
        "departments.capabilities.production_progress.planning"
        ".list_department_production_progress",
        lambda *args: seen.update(args=args) or ([{"part_no": "P-001"}], 1),
    )

    result = department_api("stamp").list_production_progress(
        2,
        50,
        "P-001",
    )

    assert result == ([{"part_no": "P-001"}], 1)
    assert seen["args"] == ("stamp", 2, 50, "P-001")


def test_assembly_department_forwards_actor_context(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "departments.capabilities.assembly.assembly.create_assembly_work_order",
        lambda *args: seen.update(args=args) or {"id": 12},
    )

    result = department_api("assembly").create_assembly_work_order(
        [1, 2],
        5,
        7,
        "remark",
        "sys",
    )

    assert result == {"id": 12}
    assert seen["args"] == ([1, 2], 5, 7, "remark", "sys")


def test_qc_department_forwards_actor_context(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        "departments.capabilities.quality.quality.dispatch_qc_batch",
        lambda *args: seen.update(args=args) or {"quantity": 3},
    )

    result = department_api("qc").dispatch_qc_batch(8, 3, "qc")

    assert result == {"quantity": 3}
    assert seen["args"] == (8, 3, "qc")


def test_department_rejects_undeclared_capability():
    with pytest.raises(DomainError) as error:
        department_api("qc", CAP_REPOSITORIES)
    assert error.value.code == "department_capability_not_supported"
    assert error.value.status_code == 404


def test_work_order_routes_call_department_facades_with_stable_signatures(
    monkeypatch,
):
    calls = {}

    class FakeDepartment:
        def create_source_work_order(self, *args):
            calls["source"] = args
            return {"id": 1}

        def create_assembly_work_order(self, *args):
            calls["assembly"] = args
            return {"id": 2}

    fake = FakeDepartment()
    monkeypatch.setattr(
        work_order_routes,
        "department_api",
        lambda _code, _capability=None: fake,
    )
    monkeypatch.setattr(
        work_order_routes,
        "department_api_for_any",
        lambda _code, _capabilities: fake,
    )
    work_order_routes.work_order_create(
        WorkOrderCreate(repository_id=4, quantity=3),
        {"department": "stamp"},
    )
    work_order_routes.assembly_work_order_create(
        AssemblyWorkOrderCreate(repository_ids=[4, 5], quantity=2),
        {"department": "assembly"},
    )

    assert calls["source"] == (4, None, [], 3, None, None)
    assert calls["assembly"] == ([4, 5], 2, None, None, "assembly")
