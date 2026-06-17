from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.src.models.record import Record
from backend.src.types.workorder import CreateWorkOrderPayload

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

@app.get("/")
def root():
    return {"message": "zzerp backend running"}

@app.get("/query_workorders")
def query_workorders():
    return {"data": Record.get_work_orders()}

@app.post("/create_workorder")
def create_workorder(payload: CreateWorkOrderPayload):
    try:
        records = Record.create_from_work_order(
            item=payload.item.strip(),
            quantity=payload.quantity,
            procedures=[procedure.value for procedure in payload.procedures],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not records:
        raise HTTPException(status_code=400, detail="创建工单失败")

    return {
        "message": "zzerp create workorder",
        "data": {
            "id": records[0].order_id,
            "item": records[0].item,
            "quantity": records[0].inbound,
            "createdAt": records[0].created_at.date().isoformat(),
            "steps": [
                {
                    "name": record.repository,
                    "inbound": record.inbound,
                    "outbound": record.outbound,
                }
                for record in records
            ],
        },
    }
