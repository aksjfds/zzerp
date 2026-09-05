"""Read-only application, architecture, and SQL/ORM consistency checks."""

from __future__ import annotations

import ast
from collections import defaultdict
import importlib
import os
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" / "src"
MODULES = BACKEND / "modules"
FRONTEND = ROOT / "frontend" / "src"
INFRASTRUCTURE = {"contracts", "errors", "ownership"}
LEGACY_BACKEND_LAYERS = {"models", "repositories", "services"}


def tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def string(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def strings(node: ast.AST | None) -> set[str]:
    if not isinstance(node, (ast.Tuple, ast.List)):
        return set()
    return {value for item in node.elts if (value := string(item))}


def call_name(node: ast.Call) -> str:
    return node.func.id if isinstance(node.func, ast.Name) else ""


def keyword(node: ast.Call, name: str) -> ast.AST | None:
    return next((item.value for item in node.keywords if item.arg == name), None)


def descriptors() -> dict[str, dict[str, str | set[str]]]:
    result = {}
    for path in sorted(MODULES.glob("*/descriptor.py")):
        call = next(
            item.value for item in tree(path).body
            if isinstance(item, (ast.Assign, ast.AnnAssign))
            and isinstance(item.value, ast.Call) and call_name(item.value) == "ModuleDescriptor"
        )
        values = {item.arg: item.value for item in call.keywords if item.arg}
        name = string(values.get("name"))
        if name != path.parent.name:
            raise ValueError(f"{path}: descriptor name mismatch")
        result[name] = {
            "public_api": string(values.get("public_api")),
            "owns": strings(values.get("owns")),
            "dependencies": strings(values.get("collaborates_with")),
            "apis": strings(values.get("collaboration_apis")),
        }
    return result


def dependency_checks(metadata: dict) -> tuple[list[str], dict[str, set[str]]]:
    errors, graph = [], defaultdict(set)
    allowed = {name: {data["public_api"], *data["apis"]} for name, data in metadata.items()}
    for path in sorted(MODULES.glob("*/*.py")):
        source = path.parent.name
        if source not in metadata:
            continue
        syntax = tree(path)
        foreign_models: set[str] = set()
        parents = {child: node for node in ast.walk(syntax) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(syntax):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            if not isinstance(parents.get(node), ast.Module):
                errors.append(f"{path.relative_to(ROOT)}:{node.lineno}: local import")
            imports = (
                [node.module]
                if isinstance(node, ast.ImportFrom)
                else [item.name for item in node.names]
            )
            for imported in filter(None, imports):
                if not imported.startswith("modules."):
                    continue
                target = imported.split(".")[1]
                if target == source or target in INFRASTRUCTURE:
                    continue
                if target not in metadata:
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: unknown module {target}"
                    )
                    continue
                graph[source].add(target)
                if target not in metadata[source]["dependencies"]:
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: "
                        f"undeclared {source} -> {target}"
                    )
                if imported.endswith(".persistence"):
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: cross-owner persistence"
                    )
                if imported not in allowed[target]:
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: undeclared API {imported}"
                    )
                if imported.endswith(".model_api") and isinstance(node, ast.ImportFrom):
                    foreign_models.update(item.asname or item.name for item in node.names)
        for node in ast.walk(syntax):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in foreign_models
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: constructs foreign model "
                    f"{node.func.id}"
                )
    return errors, graph


def router_checks(metadata: dict) -> list[str]:
    errors: list[str] = []
    public_apis = {value["public_api"] for value in metadata.values()}
    for path in sorted((BACKEND / "routers").glob("*.py")):
        for node in ast.walk(tree(path)):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for imported in filter(None, (
                [node.module]
                if isinstance(node, ast.ImportFrom)
                else [item.name for item in node.names]
            )):
                if imported == "database" or imported.endswith(".persistence"):
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: router accesses persistence"
                    )
                if imported.startswith("modules.") and imported not in public_apis:
                    errors.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: router bypasses public API "
                        f"{imported}"
                    )
    return errors


def structure_checks() -> list[str]:
    errors = []
    for name in sorted(LEGACY_BACKEND_LAYERS):
        if (BACKEND / name).exists():
            errors.append(f"legacy backend layer exists: backend/src/{name}")
    return errors


def cycle_checks(graph: dict[str, set[str]]) -> list[str]:
    errors, visited, active, reported = [], set(), [], set()
    def visit(name: str) -> None:
        if name in active:
            cycle = active[active.index(name):] + [name]
            key = frozenset(cycle)
            if key not in reported:
                reported.add(key)
                errors.append("module cycle: " + " -> ".join(cycle))
            return
        if name in visited:
            return
        active.append(name)
        for target in sorted(graph.get(name, ())):
            visit(target)
        active.pop()
        visited.add(name)
    for name in sorted(graph):
        visit(name)
    return errors


def owners() -> dict[str, str]:
    assignment = next(
        node for node in tree(MODULES / "ownership.py").body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "TABLE_OWNERS"
            for target in node.targets
        )
    )
    return ast.literal_eval(assignment.value)


def named_calls(node: ast.AST | None, kinds: set[str]) -> set[str]:
    result = set()
    for call in ast.walk(node) if node else ():
        if not isinstance(call, ast.Call) or call_name(call) not in kinds:
            continue
        value = keyword(call, "name")
        if value is None and call_name(call) == "Index" and call.args:
            value = call.args[0]
        if name := string(value):
            result.add(name)
    return result


def orm_schema() -> dict[str, dict]:
    result = {}
    for path in sorted(MODULES.glob("*/persistence.py")):
        for cls in (node for node in tree(path).body if isinstance(node, ast.ClassDef)):
            table_name, table_args, columns = None, None, set()
            for node in cls.body:
                if isinstance(node, ast.Assign):
                    names = {target.id for target in node.targets if isinstance(target, ast.Name)}
                    if "__tablename__" in names:
                        table_name = string(node.value)
                    if "__table_args__" in names:
                        table_args = node.value
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    if (
                        isinstance(node.value, ast.Call)
                        and call_name(node.value) == "mapped_column"
                    ):
                        columns.add(node.target.id)
            if table_name:
                result[table_name] = {
                    "module": path.parent.name,
                    "columns": columns,
                    "constraints": named_calls(
                        cls,
                        {
                            "CheckConstraint",
                            "ForeignKey",
                            "ForeignKeyConstraint",
                            "UniqueConstraint",
                        },
                    ),
                    "indexes": named_calls(table_args, {"Index"}),
                }
    return result


def split_items(block: str) -> list[str]:
    result, start, depth, quote = [], 0, 0, None
    for index, character in enumerate(block):
        if character in {"'", '"'} and (index == 0 or block[index - 1] != "\\"):
            quote = None if quote == character else character if quote is None else quote
        if quote is not None:
            continue
        depth += character == "("
        depth -= character == ")"
        if character == "," and depth == 0:
            result.append(block[start:index].strip())
            start = index + 1
    return result + [block[start:].strip()]


def sql_schema() -> tuple[dict[str, dict], set[str]]:
    sql = (ROOT / "zzerp.sql").read_text(encoding="utf-8")
    sql = re.sub(r"--[^\n]*", "", sql)
    result = {}
    for match in re.finditer(r"CREATE TABLE\s+([a-z_][a-z0-9_]*)\s*\(", sql, re.I):
        depth, end = 1, match.end()
        while depth:
            depth += sql[end] == "("
            depth -= sql[end] == ")"
            end += 1
        block = sql[match.end():end - 1]
        columns = set()
        for item in split_items(block):
            first = item.split(None, 1)[0].lower()
            if first not in {"constraint", "primary", "foreign", "unique", "check"}:
                columns.add(first)
        result[match.group(1)] = {
            "columns": columns,
            "constraints": set(re.findall(r"\bCONSTRAINT\s+([a-z_][a-z0-9_]*)", block, re.I)),
        }
    for alter in re.finditer(
        r"ALTER TABLE\s+([a-z_][a-z0-9_]*)\s+(.*?);",
        sql,
        re.I | re.S,
    ):
        table_name, statements = alter.groups()
        for constraint in re.findall(
            r"ADD CONSTRAINT\s+([a-z_][a-z0-9_]*)",
            statements,
            re.I,
        ):
            result[table_name]["constraints"].add(constraint)
    indexes = set(re.findall(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+([a-z_][a-z0-9_]*)", sql, re.I))
    return result, indexes


def schema_checks(metadata: dict) -> list[str]:
    errors, table_owners, orm = [], owners(), orm_schema()
    sql, sql_indexes = sql_schema()
    comparisons = (
        ("ownership/ORM", set(table_owners), set(orm)),
        ("SQL/ORM", set(sql), set(orm)),
    )
    for label, left, right in comparisons:
        for name in sorted(left ^ right):
            errors.append(f"{label} table mismatch: {name}")
    for name in sorted(set(sql) & set(orm)):
        if table_owners.get(name) != orm[name]["module"]:
            errors.append(f"owner mismatch: {name}")
        if name not in metadata[orm[name]["module"]]["owns"]:
            errors.append(f"descriptor owner missing: {orm[name]['module']}.{name}")
        for column in sorted(sql[name]["columns"] ^ orm[name]["columns"]):
            errors.append(f"column mismatch: {name}.{column}")
        for constraint in sorted(sql[name]["constraints"] ^ orm[name]["constraints"]):
            errors.append(f"constraint mismatch: {name}.{constraint}")
    orm_indexes = {value for table in orm.values() for value in table["indexes"]}
    for name in sorted(sql_indexes ^ orm_indexes):
        errors.append(f"index mismatch: {name}")
    return errors


def frontend_checks() -> list[str]:
    errors = []
    pattern = re.compile(r"(?:from\s+|import\s*\()(['\"])([^'\"]+)\1")
    paths = [*FRONTEND.rglob("*.ts"), *FRONTEND.rglob("*.vue")]
    for path in sorted(paths):
        relative = path.relative_to(FRONTEND)
        content = path.read_text(encoding="utf-8")
        for imported in (match.group(2) for match in pattern.finditer(content)):
            if imported.startswith("@/"):
                target = FRONTEND / imported[2:]
            elif imported.startswith("."):
                target = path.parent / imported
            else:
                target = None
            if target is None:
                continue
            parts = target.resolve().relative_to(FRONTEND.resolve()).parts
            if relative.parts[0] == "shared" and parts[0] == "features":
                errors.append(f"{path.relative_to(ROOT)}: shared -> feature")
            if relative.parts[0] == "features" and parts[0] == "features":
                source, destination = relative.parts[1], parts[1]
                department_composition_root = (
                    source == "departments"
                    and path.name == "index.ts"
                    and len(relative.parts) == 4
                )
                if (
                    source != destination
                    and len(parts) > 2
                    and not department_composition_root
                ):
                    errors.append(f"{path.relative_to(ROOT)}: bypasses {destination}/index.ts")
    return errors


def application_check() -> list[str]:
    os.environ.setdefault("APP_ENV", "development")
    sys.path[:0] = [str(BACKEND), str(ROOT)]
    try:
        app = importlib.import_module("main").app
    except Exception as exc:
        return [f"application import: {type(exc).__name__}: {exc}"]
    print(f"Application import: {app.title!r}, {len(app.routes)} routes")
    return []


def main() -> int:
    errors = []
    try:
        metadata = descriptors()
        dependency_errors, graph = dependency_checks(metadata)
        errors += dependency_errors + cycle_checks(graph)
        errors += router_checks(metadata) + structure_checks()
        errors += schema_checks(metadata) + frontend_checks() + application_check()
    except (OSError, SyntaxError, ValueError, KeyError) as exc:
        errors.append(f"check infrastructure: {type(exc).__name__}: {exc}")
    if errors:
        for error in sorted(set(errors)):
            print(f"ERROR: {error}")
        print(f"Architecture check failed with {len(set(errors))} issue(s)")
        return 1
    print("Architecture check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
