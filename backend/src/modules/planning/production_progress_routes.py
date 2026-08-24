from __future__ import annotations

"""Production-progress route and organization mapping."""

def _node_department_code(node, workshops, departments):
    if node.get("type") in {"process", "assembly"}:
        workshop = workshops.get(node.get("workshop_id"))
        department = departments.get(workshop.department_id) if workshop else None
        return department.department_code if department else None
    return {
        "qc": "qc",
        "shipping": "finished",
    }.get(node.get("type"))

def _node_workshop_name(node, workshops):
    workshop = workshops.get(node.get("workshop_id"))
    if workshop:
        return workshop.workshop_name
    if node.get("type") == "assembly":
        return str(node.get("label") or "装配")
    return None
