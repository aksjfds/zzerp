from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.src.models.record import Record, Repository
from backend.src.types.workorder import CreateWorkOrderPayload, MoveRepositoryQuantityPayload

app = FastAPI(title="zzerp")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def normalize_optional_text(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip()
    return normalized or None

@app.get("/")
def root():
    return {"message": "zzerp backend running"}

@app.get("/query_workorders")
def query_workorders():
    return {"data": Repository.get_work_orders()}

@app.get("/query_record_logs")
def query_record_logs(order_id: int, item: str, repository: str):
    return {
        "data": Record.get_by_work_order_step(
            order_id=order_id,
            item=item,
            repository=repository,
        )
    }

@app.post("/create_workorder")
def create_workorder(payload: CreateWorkOrderPayload):
    try:
        repositories = Repository.create_from_work_order(
            item=payload.item.strip(),
            quantity=payload.quantity,
            procedures=[procedure.value for procedure in payload.procedures],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not repositories:
        raise HTTPException(status_code=400, detail="创建工单失败")

    return {
        "message": "zzerp create workorder",
        "data": {
            "id": repositories[0].order_id,
            "item": repositories[0].item,
            "quantity": sum(repository.quantity for repository in repositories),
            "steps": [
                {
                    "name": repository.repository_name,
                    "quantity": repository.quantity,
                }
                for repository in repositories
                if repository.repository_name != "out"
            ],
        },
    }

@app.post("/record_outbound")
def record_outbound(payload: MoveRepositoryQuantityPayload):
    try:
        Repository.move_to_next_repository(
            order_id=payload.order_id,
            item=payload.item.strip(),
            repository_name=payload.repository.value,
            quantity=payload.quantity,
            operator=payload.operator,
            worker=normalize_optional_text(payload.worker),
            note=normalize_optional_text(payload.note),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"message": "zzerp record outbound"}

@app.post("/record_rework")
def record_rework(payload: MoveRepositoryQuantityPayload):
    try:
        Repository.rework_to_previous_repository(
            order_id=payload.order_id,
            item=payload.item.strip(),
            repository_name=payload.repository.value,
            quantity=payload.quantity,
            operator=payload.operator,
            worker=normalize_optional_text(payload.worker),
            note=normalize_optional_text(payload.note),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"message": "zzerp record rework"}
