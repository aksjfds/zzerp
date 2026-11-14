"""Framework-independent errors shared by business rules and HTTP adapters."""


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        path: str | None = None,
        element_id: str | None = None,
        *,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.element_id = element_id
        self.status_code = status_code
