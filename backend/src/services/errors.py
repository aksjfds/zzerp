class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        path: str | None = None,
        element_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.path = path
        self.element_id = element_id


def product_not_found() -> DomainError:
    return DomainError("product_not_found", "产品不存在", status_code=404)
