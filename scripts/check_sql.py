"""Compare literal SQL/ORM declarations without importing the app or connecting to a database."""

import ast
import re
from pathlib import Path

from .check_source import call_name, keyword, string, tree

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "backend" / "src" / "zzerp" / "modules"
SQL_TOKEN = re.compile(r"'(?:''|[^'])*'|[A-Za-z_][A-Za-z_0-9]*|->>|->|>=|<=|<>|!=|\S")


def normalize(expression: str) -> str:
    return "".join(
        token if token.startswith("'") else token.lower() for token in SQL_TOKEN.findall(expression)
    )


def parenthesized(value: str, start: int = 0) -> tuple[str, str]:
    opening = value.index("(", start)
    depth = 0
    for match in re.finditer(r"'(?:''|[^'])*'|[()]", value[opening:]):
        token = match.group()
        depth += token == "("
        depth -= token == ")"
        if depth == 0:
            end = opening + match.start()
            return value[opening + 1 : end], value[end + 1 :].strip()
    raise ValueError("unclosed SQL parentheses")


def split_items(value: str) -> list[str]:
    items, start, depth = [], 0, 0
    for match in re.finditer(r"'(?:''|[^'])*'|[(),]", value):
        token = match.group()
        depth += token == "("
        depth -= token == ")"
        if token == "," and depth == 0:
            items.append(value[start : match.start()].strip())
            start = match.end()
    return items + [value[start:].strip()]


def literal_keyword(call: ast.Call, name: str, default=None):
    node = keyword(call, name)
    return ast.literal_eval(node) if node is not None else default


def constraint_options(call: ast.Call) -> tuple:
    return (
        literal_keyword(call, "ondelete", "NO ACTION"),
        literal_keyword(call, "deferrable", False),
        literal_keyword(call, "initially", "IMMEDIATE"),
    )


def orm_constraint(call: ast.Call, column: str | None = None) -> tuple:
    kind = call_name(call)
    if kind == "CheckConstraint":
        return ("check", normalize(ast.literal_eval(call.args[0])))
    if kind == "UniqueConstraint":
        return (
            "unique",
            tuple(ast.literal_eval(arg) for arg in call.args),
            *constraint_options(call)[1:],
        )
    if kind == "ForeignKey":
        columns, targets = (column,), (ast.literal_eval(call.args[0]),)
    else:
        columns, targets = (tuple(ast.literal_eval(arg)) for arg in call.args)
    return ("foreign", columns, targets, *constraint_options(call))


def orm_index(call: ast.Call) -> tuple:
    expressions = [
        string(arg) if not isinstance(arg, ast.Call) else string(arg.args[0])
        for arg in call.args[1:]
    ]
    if any(value is None for value in expressions):
        raise ValueError("indexes must use literal columns or text expressions")
    ops = literal_keyword(call, "postgresql_ops", {})
    return (
        tuple(
            normalize(value + (" " + ops[value] if value in ops else "")) for value in expressions
        ),
        literal_keyword(call, "postgresql_using", "btree"),
        tuple(literal_keyword(call, "postgresql_include", [])),
        normalize(
            string(keyword(call, "postgresql_where").args[0])
            if keyword(call, "postgresql_where") is not None
            else ""
        ),
    )


def orm_declarations(cls: ast.ClassDef) -> tuple[dict, dict]:
    constraints, indexes = {}, {}
    kinds = {"CheckConstraint", "UniqueConstraint", "ForeignKeyConstraint", "ForeignKey", "Index"}
    for statement in cls.body:
        column = statement.target.id if isinstance(statement, ast.AnnAssign) else None
        for call in ast.walk(statement):
            if not isinstance(call, ast.Call) or call_name(call) not in kinds:
                continue
            if call_name(call) == "Index":
                indexes[string(call.args[0])] = orm_index(call)
            else:
                name = string(keyword(call, "name"))
                if not name:
                    raise ValueError(f"{cls.name}: constraint needs an explicit name")
                constraints[name] = orm_constraint(call, column)
    return constraints, indexes


def orm_schema() -> dict:
    result = {}
    for path in sorted(MODULES.glob("*/persistence.py")):
        for cls in (node for node in tree(path).body if isinstance(node, ast.ClassDef)):
            table = next(
                (
                    string(node.value)
                    for node in cls.body
                    if isinstance(node, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "__tablename__" for t in node.targets
                    )
                ),
                None,
            )
            if table is None:
                continue
            constraints, indexes = orm_declarations(cls)
            result[table] = {
                "owner": path.parent.name,
                "columns": {
                    node.target.id
                    for node in cls.body
                    if isinstance(node, ast.AnnAssign)
                    and isinstance(node.value, ast.Call)
                    and call_name(node.value) == "mapped_column"
                },
                "constraints": constraints,
                "indexes": indexes,
            }
    return result


def sql_flags(value: str) -> tuple:
    action = re.search(
        r"ON DELETE\s+(NO ACTION|CASCADE|RESTRICT|SET NULL|SET DEFAULT)", value, re.I
    )
    deferred = bool(re.search(r"\bDEFERRABLE\b", value, re.I)) and not re.search(
        r"NOT\s+DEFERRABLE", value, re.I
    )
    initially = re.search(r"INITIALLY\s+(DEFERRED|IMMEDIATE)", value, re.I)
    return (
        action.group(1).upper() if action else "NO ACTION",
        bool(deferred),
        initially.group(1).upper() if initially else "IMMEDIATE",
    )


def sql_constraint(value: str) -> tuple[str, tuple]:
    match = re.match(r"CONSTRAINT\s+(\w+)\s+(CHECK|UNIQUE|FOREIGN KEY)\s*", value, re.I)
    if not match:
        raise ValueError(f"unrecognized named constraint: {value}")
    name, kind = match.groups()
    body, tail = parenthesized(value, match.end())
    if kind.upper() == "CHECK":
        return name, ("check", normalize(body))
    columns = tuple(split_items(body))
    if kind.upper() == "UNIQUE":
        return name, ("unique", columns, *sql_flags(tail)[1:])
    target = re.match(r"REFERENCES\s+(\w+)\s*\(", tail, re.I)
    if target is None:
        raise ValueError(f"{name}: foreign key target missing")
    referenced, options = parenthesized(tail)
    targets = tuple(f"{target.group(1)}.{col}" for col in split_items(referenced))
    return name, ("foreign", columns, targets, *sql_flags(options))


def sql_indexes(sql: str) -> dict:
    result = {}
    for match in re.finditer(
        r"CREATE INDEX\s+(\w+)\s+ON\s+(\w+)\s*(?:USING\s+(\w+)\s*)?\(", sql, re.I
    ):
        name, table, method = match.groups()
        body, tail = parenthesized(sql, match.end() - 1)
        tail = tail.split(";", 1)[0].strip()
        include = ()
        if tail.upper().startswith("INCLUDE"):
            included, tail = parenthesized(tail)
            include = tuple(split_items(included))
        where = re.sub(r"^WHERE\s+", "", tail, flags=re.I)
        result[name] = (
            table,
            (
                tuple(normalize(item) for item in split_items(body)),
                (method or "btree").lower(),
                include,
                normalize(where),
            ),
        )
    return result


def sql_schema(sql: str) -> dict:
    result = {}
    for match in re.finditer(r"CREATE TABLE\s+(\w+)\s*\(", sql, re.I):
        body, _ = parenthesized(sql, match.end() - 1)
        columns, constraints = set(), {}
        for item in split_items(body):
            if item.upper().startswith("CONSTRAINT"):
                name, signature = sql_constraint(item)
                constraints[name] = signature
            elif item.upper().startswith("PRIMARY KEY"):
                continue
            else:
                if re.search(r"\bREFERENCES\b|\bFOREIGN KEY\b", item, re.I):
                    raise ValueError(f"{match.group(1)}: foreign key needs a table-level name")
                columns.add(item.split()[0])
        result[match.group(1)] = {"columns": columns, "constraints": constraints}
    for match in re.finditer(r"ALTER TABLE\s+(\w+)\s+ADD\s+(CONSTRAINT\s+.*?);", sql, re.I | re.S):
        name, signature = sql_constraint(match.group(2))
        result[match.group(1)]["constraints"][name] = signature
    return result


def declaration_errors(label: str, sql: dict, orm: dict) -> list[str]:
    errors = [
        f"{label}: declaration missing on one side: {name}" for name in sql.keys() ^ orm.keys()
    ]
    errors.extend(
        f"{label}: definition mismatch: {name}"
        for name in sql.keys() & orm.keys()
        if sql[name] != orm[name]
    )
    return errors


def function_errors(sql: str) -> list[str]:
    functions = set(re.findall(r"CREATE FUNCTION\s+(\w+)", sql, re.I))
    valid = set(
        re.findall(
            r"CREATE FUNCTION\s+(\w+)\(\)\s+RETURNS TRIGGER\s+LANGUAGE plpgsql\s+"
            r"SET search_path = pg_catalog, public\s+AS \$function\$.*?\$function\$;",
            sql,
            re.I | re.S,
        )
    )
    return [f"SQL function delimiter or search_path invalid: {name}" for name in functions - valid]


def schema_checks() -> list[str]:
    source = (ROOT / "zzerp.sql").read_text(encoding="utf-8")
    sql = re.sub(r"--[^\n]*", "", source)
    orm, tables = orm_schema(), sql_schema(sql)
    assignment = next(
        node
        for node in tree(MODULES / "ownership.py").body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "TABLE_OWNERS" for t in node.targets)
    )
    owners = ast.literal_eval(assignment.value)
    errors = function_errors(sql)
    errors += [f"ownership/ORM table mismatch: {name}" for name in owners.keys() ^ orm.keys()]
    errors += [f"SQL/ORM table mismatch: {name}" for name in tables.keys() ^ orm.keys()]
    for name in tables.keys() & orm.keys():
        if owners.get(name) != orm[name]["owner"]:
            errors.append(f"table owner mismatch: {name}")
        if tables[name]["columns"] != orm[name]["columns"]:
            errors.append(f"column mismatch: {name}")
        errors += declaration_errors(
            f"constraints/{name}", tables[name]["constraints"], orm[name]["constraints"]
        )
    indexes = {
        name: (table, definition)
        for table, data in orm.items()
        for name, definition in data["indexes"].items()
    }
    return errors + declaration_errors("indexes", sql_indexes(sql), indexes)
