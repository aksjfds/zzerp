from dataclasses import dataclass


@dataclass(frozen=True)
class DomainViolation(Exception):
    code: str
    message: str
    path: str | None = None
    element_id: str | None = None
    status_code: int = 400
