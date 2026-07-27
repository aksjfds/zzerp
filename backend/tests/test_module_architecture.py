import ast
from pathlib import Path


BACKEND_SRC = Path(__file__).resolve().parents[1] / "src"
ROUTERS = BACKEND_SRC / "routers"
MODULES = (
    "identity",
    "organization",
    "engineering",
    "sales",
    "production_core",
    "standard_execution",
    "purchasing",
    "assembly",
    "quality",
    "workforce",
    "planning",
)
DEPARTMENTS = ("stamp", "cnc", "polish", "warehouse", "assembly", "qc")
FOREIGN_ORM_FREE_MODULES = {
    "assembly",
    "engineering",
    "identity",
    "organization",
    "purchasing",
    "quality",
    "sales",
    "standard_execution",
    "workforce",
}
FORBIDDEN_ROUTER_IMPORTS = ("services", "models", "repositories", "database")
PERSISTENCE_FILES = tuple((BACKEND_SRC / "modules").glob("*/persistence.py"))


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def test_http_routers_only_enter_business_logic_through_module_apis():
    violations = []
    for path in ROUTERS.glob("*.py"):
        for imported in _imports(path):
            if any(
                imported == name or imported.startswith(f"{name}.")
                for name in FORBIDDEN_ROUTER_IMPORTS
            ):
                violations.append(f"{path.name}: {imported}")
    assert violations == []


def test_http_routers_do_not_import_module_internals():
    violations = []
    for path in ROUTERS.glob("*.py"):
        for imported in _imports(path):
            parts = imported.split(".")
            if len(parts) < 2 or parts[0] != "modules":
                continue
            if len(parts) < 3:
                violations.append(f"{path.name}: {imported}")
                continue
            surface = parts[2]
            if surface != "api":
                violations.append(f"{path.name}: {imported}")
    assert violations == []


def test_every_business_module_has_a_public_api_and_descriptor():
    for name in MODULES:
        module = BACKEND_SRC / "modules" / name
        assert (module / "__init__.py").is_file()
        assert (module / "api.py").is_file()
        assert (module / "descriptor.py").is_file()


def test_module_api_catalog_is_complete_and_versioned():
    from modules.registry import MODULES as REGISTERED_MODULES

    for name, descriptor in REGISTERED_MODULES.items():
        module = BACKEND_SRC / "modules" / name
        actual_collaboration_apis = {
            f"modules.{name}.{path.stem}"
            for path in module.glob("*_api.py")
        }
        assert descriptor.public_api == f"modules.{name}.api"
        assert descriptor.api_version.isdigit()
        assert set(descriptor.collaboration_apis) == actual_collaboration_apis


def test_every_production_department_is_an_independent_registered_package():
    from departments.registry import DEPARTMENT_MODULES

    for code in DEPARTMENTS:
        department = BACKEND_SRC / "departments" / code
        assert (department / "__init__.py").is_file()
        assert (department / "api.py").is_file()
        assert type(DEPARTMENT_MODULES[code]).__module__ == f"departments.{code}.api"


def test_every_declared_department_capability_has_a_public_method():
    from departments.contracts import CAPABILITY_METHODS
    from departments.registry import DEPARTMENT_MODULES

    violations = []
    contract_methods = {
        method
        for methods in CAPABILITY_METHODS.values()
        for method in methods
    }
    for code, module in DEPARTMENT_MODULES.items():
        expected_methods = {
            method
            for capability in module.descriptor.capabilities
            for method in CAPABILITY_METHODS[capability]
        }
        actual_methods = {
            method
            for method in contract_methods
            if callable(getattr(module, method, None))
        }
        if actual_methods != expected_methods:
            violations.append(
                f"{code}: expected={sorted(expected_methods)}, "
                f"actual={sorted(actual_methods)}"
            )
        for capability in module.descriptor.capabilities:
            for method in CAPABILITY_METHODS[capability]:
                if not callable(getattr(module, method, None)):
                    violations.append(f"{code}:{capability}:{method}")
    assert violations == []


def test_frontend_and_backend_department_capabilities_match():
    import re

    from departments.registry import DEPARTMENT_MODULES

    frontend_root = (
        BACKEND_SRC.parents[1]
        / "frontend"
        / "src"
        / "features"
        / "departments"
    )
    frontend = {}
    for code in DEPARTMENTS:
        source = (frontend_root / code / "index.ts").read_text(encoding="utf-8")
        match = re.search(r"capabilities:\s*\[(.*?)\]", source, re.DOTALL)
        assert match is not None
        frontend[code] = set(re.findall(r"'([^']+)'", match.group(1)))

    backend = {
        code: set(module.descriptor.capabilities)
        for code, module in DEPARTMENT_MODULES.items()
    }
    assert frontend == backend


def test_modules_and_departments_do_not_call_legacy_layers():
    violations = []
    for root in (BACKEND_SRC / "modules", BACKEND_SRC / "departments"):
        for path in root.rglob("*.py"):
            for imported in _imports(path):
                if imported == "services" or imported.startswith("services."):
                    violations.append(f"{path.relative_to(BACKEND_SRC)}: {imported}")
                if imported == "repositories" or imported.startswith("repositories."):
                    violations.append(f"{path.relative_to(BACKEND_SRC)}: {imported}")
    assert violations == []


def test_business_modules_only_collaborate_through_public_apis():
    violations = []
    modules_root = BACKEND_SRC / "modules"
    shared_kernel = {"contracts", "errors"}
    for path in modules_root.rglob("*.py"):
        relative = path.relative_to(modules_root)
        if len(relative.parts) < 2:
            continue
        owner = relative.parts[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                candidates = [(node.module, [alias.name for alias in node.names])]
            elif isinstance(node, ast.Import):
                candidates = [(alias.name, []) for alias in node.names]
            else:
                continue

            for imported, imported_names in candidates:
                parts = imported.split(".")
                if len(parts) < 2 or parts[0] != "modules":
                    continue
                target = parts[1]
                if target == owner or target in shared_kernel:
                    continue

                if len(parts) >= 3:
                    surface = parts[2]
                    is_public_api = surface == "api" or surface.endswith("_api")
                else:
                    is_public_api = bool(imported_names) and all(
                        name == "api" or name.endswith("_api")
                        for name in imported_names
                    )
                if not is_public_api:
                    violations.append(
                        f"{path.relative_to(BACKEND_SRC)}:{node.lineno}: {imported}"
                    )
    assert violations == []


def test_cross_module_api_dependencies_are_declared():
    from modules.registry import MODULES as REGISTERED_MODULES

    violations = []
    modules_root = BACKEND_SRC / "modules"
    for path in modules_root.rglob("*.py"):
        relative = path.relative_to(modules_root)
        if len(relative.parts) < 2:
            continue
        owner = relative.parts[0]
        descriptor = REGISTERED_MODULES[owner]
        for imported in _imports(path):
            parts = imported.split(".")
            if len(parts) < 2 or parts[0] != "modules":
                continue
            target = parts[1]
            if target in {owner, "contracts", "errors"}:
                continue
            if target not in descriptor.collaborates_with:
                violations.append(
                    f"{path.relative_to(BACKEND_SRC)}: undeclared dependency {target}"
                )
    assert violations == []


def test_cross_module_orm_reads_match_the_explicit_access_manifest():
    from modules.ownership import TABLE_OWNERS
    from modules.read_access import READ_MODEL_ACCESS
    from modules.registry import MODULES as REGISTERED_MODULES

    class_tables = {}
    for path in PERSISTENCE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            for statement in node.body:
                if not isinstance(statement, ast.Assign):
                    continue
                if not any(
                    isinstance(target, ast.Name) and target.id == "__tablename__"
                    for target in statement.targets
                ):
                    continue
                if isinstance(statement.value, ast.Constant):
                    class_tables[node.name] = statement.value.value

    actual_access = {name: set() for name in REGISTERED_MODULES}
    invalid_model_imports = []
    modules_root = BACKEND_SRC / "modules"
    for path in modules_root.rglob("*.py"):
        relative = path.relative_to(modules_root)
        if len(relative.parts) < 2:
            continue
        module_name = relative.parts[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module == "models" or node.module.startswith("models."):
                invalid_model_imports.append(
                    f"{path.relative_to(BACKEND_SRC)}:{node.lineno}: {node.module}"
                )
                continue
            parts = node.module.split(".")
            if (
                len(parts) != 3
                or parts[0] != "modules"
                or parts[2] != "model_api"
            ):
                continue
            target_owner = parts[1]
            for alias in node.names:
                table_name = class_tables.get(alias.name)
                if table_name and TABLE_OWNERS[table_name] != target_owner:
                    invalid_model_imports.append(
                        f"{path.relative_to(BACKEND_SRC)}:{node.lineno}: {alias.name}"
                    )
                elif table_name and target_owner == module_name:
                    invalid_model_imports.append(
                        f"{path.relative_to(BACKEND_SRC)}:{node.lineno}: "
                        f"owner must import persistence directly: {alias.name}"
                    )
                elif table_name:
                    actual_access[module_name].add(table_name)

    assert invalid_model_imports == []
    declared_access = {
        name: set(READ_MODEL_ACCESS.get(name, ())) for name in REGISTERED_MODULES
    }
    assert declared_access == actual_access
    for module_name, table_names in declared_access.items():
        descriptor = REGISTERED_MODULES[module_name]
        for table_name in table_names:
            owner = TABLE_OWNERS[table_name]
            assert owner != module_name
            assert owner in descriptor.collaborates_with


def test_runtime_context_contracts_are_persistence_free():
    violations = []
    for path in (BACKEND_SRC / "modules").glob("*/context_api.py"):
        for imported in _imports(path):
            if (
                imported == "database"
                or imported == "sqlalchemy"
                or imported.startswith("sqlalchemy.")
                or imported.endswith(".persistence")
                or imported.endswith(".model_api")
            ):
                violations.append(f"{path.relative_to(BACKEND_SRC)}: {imported}")
    assert violations == []


def test_projection_isolated_modules_remain_foreign_orm_free():
    from modules.read_access import READ_MODEL_ACCESS

    assert {
        name: sorted(READ_MODEL_ACCESS.get(name, ()))
        for name in FOREIGN_ORM_FREE_MODULES
        if READ_MODEL_ACCESS.get(name)
    } == {}


def test_python_module_import_graph_has_no_cycles():
    modules_root = BACKEND_SRC / "modules"
    paths = list(modules_root.rglob("*.py"))

    def module_name(path: Path) -> str:
        relative = path.relative_to(BACKEND_SRC).with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    local_modules = {module_name(path): path for path in paths}
    graph = {name: set() for name in local_modules}
    for name, path in local_modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            candidates = []
            if isinstance(node, ast.Import):
                candidates.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                candidates.append(node.module)
                candidates.extend(
                    f"{node.module}.{alias.name}" for alias in node.names
                )
            graph[name].update(
                candidate
                for candidate in candidates
                if candidate in local_modules and candidate != name
            )

    visiting = set()
    visited = set()
    stack = []
    cycles = []

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            start = stack.index(name)
            cycles.append(" -> ".join(stack[start:] + [name]))
            return
        visiting.add(name)
        stack.append(name)
        for dependency in graph[name]:
            visit(dependency)
        stack.pop()
        visiting.remove(name)
        visited.add(name)

    for name in graph:
        visit(name)
    assert cycles == []


def test_legacy_service_and_repository_layers_have_been_removed():
    remaining = []
    for directory in ("services", "repositories"):
        remaining.extend(
            str(path.relative_to(BACKEND_SRC))
            for path in (BACKEND_SRC / directory).glob("*.py")
        )
    assert remaining == []


def test_top_level_models_compatibility_modules_have_been_removed():
    remaining = sorted(
        path.name for path in (BACKEND_SRC / "models").glob("*.py")
    )
    assert remaining == []


def test_every_orm_table_has_exactly_one_declared_module_owner():
    physical_owners = {}
    duplicates = []
    for path in PERSISTENCE_FILES:
        physical_owner = path.parent.name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "__tablename__"
                for target in node.targets
            ):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                table_name = node.value.value
                if table_name in physical_owners:
                    duplicates.append(table_name)
                physical_owners[table_name] = physical_owner

    ownership_path = BACKEND_SRC / "modules" / "ownership.py"
    ownership_tree = ast.parse(
        ownership_path.read_text(encoding="utf-8"),
        filename=str(ownership_path),
    )
    declared = {}
    for node in ast.walk(ownership_tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "TABLE_OWNERS"
            for target in node.targets
        ):
            continue
        if isinstance(node.value, ast.Dict):
            declared = {
                key.value: value.value
                for key, value in zip(node.value.keys, node.value.values)
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                )
            }
    assert duplicates == []
    assert declared == physical_owners


def test_only_owning_module_constructs_persisted_records():
    ownership_path = BACKEND_SRC / "modules" / "ownership.py"
    ownership_tree = ast.parse(
        ownership_path.read_text(encoding="utf-8"),
        filename=str(ownership_path),
    )
    table_owners = {}
    for node in ast.walk(ownership_tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "TABLE_OWNERS"
            for target in node.targets
        ):
            continue
        if isinstance(node.value, ast.Dict):
            table_owners = {
                key.value: value.value
                for key, value in zip(node.value.keys, node.value.values)
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                )
            }

    class_owners = {}
    for path in PERSISTENCE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            table_name = None
            for statement in node.body:
                if not isinstance(statement, ast.Assign):
                    continue
                if not any(
                    isinstance(target, ast.Name) and target.id == "__tablename__"
                    for target in statement.targets
                ):
                    continue
                if isinstance(statement.value, ast.Constant):
                    table_name = statement.value.value
            if table_name in table_owners:
                class_owners[node.name] = table_owners[table_name]

    violations = []
    modules_root = BACKEND_SRC / "modules"
    for path in modules_root.rglob("*.py"):
        relative = path.relative_to(modules_root)
        if len(relative.parts) < 2:
            continue
        module_name = relative.parts[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            owner = class_owners.get(node.func.id)
            if owner is not None and owner != module_name:
                violations.append(
                    f"{path.relative_to(BACKEND_SRC)}:{node.lineno}: "
                    f"{node.func.id} is owned by {owner}"
                )
    assert violations == []
