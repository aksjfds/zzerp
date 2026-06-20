from pydantic import BaseModel, Field


class CreateProductPayload(BaseModel):
    zz_code: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    process: list[str] = Field(min_length=1)
    quantity: int = Field(gt=0)


class CreateTaskPayload(BaseModel):
    zz_code: str = Field(min_length=1)
    product: str = Field(min_length=1)
    worker: str = Field(min_length=1)
    department: str = Field(min_length=1)
    procedure: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    note: str | None = None
