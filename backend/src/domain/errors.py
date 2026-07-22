class DomainViolation(Exception):
    """A client-correctable domain validation error.

    Exception instances must remain mutable because Python and context managers
    assign ``__traceback__`` while propagating an error through transaction
    rollback. A frozen dataclass turns an ordinary validation failure into a
    secondary ``FrozenInstanceError`` and therefore an HTTP 500 response.
    """

    def __init__(
        self,
        code: str,
        message: str,
        path: str | None = None,
        element_id: str | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.element_id = element_id
        self.status_code = status_code
