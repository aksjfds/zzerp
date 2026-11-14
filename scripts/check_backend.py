"""Read-only package, public-port and SQL/ORM consistency checks; no app imports."""

from __future__ import annotations

import ast
from pathlib import Path

from .check_source import tree
from .check_sql import schema_checks

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend" / "src"
PACKAGE = SOURCE / "zzerp"
MODULES = PACKAGE / "modules"
LEGACY_ROOTS = {
    "application",
    "auth_dependencies",
    "authorization",
    "config",
    "database",
    "domain",
    "modules",
    "routers",
    "schemas",
}


def module_path(name: str) -> Path | None:
    path = SOURCE.joinpath(*name.split("."))
    if path.with_suffix(".py").is_file():
        return path.with_suffix(".py")
    if (path / "__init__.py").is_file():
        return path / "__init__.py"
    return None


def import_base(node: ast.ImportFrom, path: Path) -> str:
    base = node.module or ""
    if node.level:
        package = path.parent.relative_to(SOURCE).parts
        if node.level > len(package):
            raise ValueError(f"{path}: relative import outside backend/src")
        base = ".".join((*package[: len(package) - node.level + 1], base)).rstrip(".")
    return base


def imports(node: ast.AST, path: Path) -> set[str]:
    if isinstance(node, ast.Import):
        return {item.name for item in node.names}
    if not isinstance(node, ast.ImportFrom):
        return set()
    base = import_base(node, path)
    return {
        f"{base}.{item.name}" if module_path(f"{base}.{item.name}") else base for item in node.names
    }


def bound_names(syntax: ast.Module) -> set[str]:
    names = set()
    for node in syntax.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(item.asname or item.name.split(".")[0] for item in node.names)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.TypeAlias)):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target if isinstance(node, ast.AnnAssign) else node.name]
            )
            names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def imported_name_errors(node: ast.ImportFrom, path: Path) -> list[str]:
    base = import_base(node, path)
    target = module_path(base)
    if not base.startswith("zzerp") or target is None:
        return []
    names = bound_names(tree(target))
    return [
        f"unknown import {base}.{item.name}"
        for item in node.names
        if item.name not in names and not module_path(f"{base}.{item.name}")
    ]


def port_error(path: Path, imported: str) -> str | None:
    if not imported.startswith("zzerp.modules."):
        return None
    parts = imported.split(".")
    source = path.relative_to(PACKAGE).parts
    if source[:1] == ("modules",) and len(source) > 2 and source[1] == parts[2]:
        return None
    if len(parts) != 4 or parts[3] not in {"api", "contracts"}:
        return f"cross-module access bypasses api/contracts: {imported}"
    return None


def public_export_checks(path: Path, syntax: ast.Module) -> list[str]:
    if path.name != "api.py" or path.parent.parent != MODULES:
        return []
    exports = next(
        (
            node.value
            for node in syntax.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
            )
        ),
        None,
    )
    if exports is None:
        return [f"{path.relative_to(ROOT)}: public port needs explicit __all__"]
    return [
        f"{path.relative_to(ROOT)}: undefined public export {name}"
        for name in set(ast.literal_eval(exports)) - bound_names(syntax)
    ]


def dependency_checks() -> list[str]:
    errors = []
    for path in sorted(PACKAGE.rglob("*.py")):
        syntax = tree(path)
        for node in ast.walk(syntax):
            prefix = f"{path.relative_to(ROOT)}:{getattr(node, 'lineno', 1)}: "
            if isinstance(node, ast.ImportFrom):
                errors.extend(prefix + error for error in imported_name_errors(node, path))
            for imported in imports(node, path):
                if imported.split(".")[0] in LEGACY_ROOTS:
                    errors.append(prefix + f"legacy unqualified import: {imported}")
                if imported.startswith("zzerp") and module_path(imported) is None:
                    errors.append(prefix + f"missing package module: {imported}")
                if error := port_error(path, imported):
                    errors.append(prefix + error)
        errors.extend(public_export_checks(path, syntax))
    return errors


def structure_checks() -> list[str]:
    errors = []
    for path in SOURCE.rglob("*.py"):
        if not path.is_relative_to(PACKAGE):
            errors.append(f"source outside native package: {path.relative_to(ROOT)}")
    for path in (
        ROOT / "main.py",
        PACKAGE / "services",
        PACKAGE / "repositories",
        PACKAGE / "models",
    ):
        if path.exists():
            errors.append(f"obsolete entry point or layer: {path.relative_to(ROOT)}")
    forbidden = {"SessionLocal", "create_engine", "sessionmaker", "get_settings", "load_settings"}
    for path in MODULES.rglob("*.py"):
        syntax = tree(path)
        for node in ast.walk(syntax):
            if isinstance(node, ast.Name) and node.id in forbidden:
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: module owns app resource {node.id}"
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"commit", "rollback"}
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: transaction boundary belongs to Database.command"
                )
        if path.name in {"descriptor.py", "registry.py"}:
            errors.append(f"duplicate module metadata: {path.relative_to(ROOT)}")
    return errors


def syntax_checks() -> list[str]:
    errors = []
    for path in sorted([*SOURCE.rglob("*.py"), *(ROOT / "scripts").glob("*.py")]):
        try:
            tree(path)
        except SyntaxError as exc:
            errors.append(f"{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
    return errors


def main() -> int:
    try:
        errors = syntax_checks()
        if not errors:
            errors += dependency_checks() + structure_checks() + schema_checks()
    except (OSError, SyntaxError, ValueError, KeyError) as exc:
        errors = [f"check infrastructure: {type(exc).__name__}: {exc}"]
    if errors:
        for error in sorted(set(errors)):
            print(f"ERROR: {error}")
        print(f"Architecture check failed with {len(set(errors))} issue(s)")
        return 1
    print("Package, public ports and SQL/ORM consistency passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
