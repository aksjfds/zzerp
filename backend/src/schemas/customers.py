from pydantic import BaseModel, ConfigDict


class CustomerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    customer_name: str
    created_at: str
    updated_at: str


class CustomerListEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[CustomerResponse]
