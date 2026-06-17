from sqlalchemy import String, Integer, BigInteger, TIMESTAMP, func, text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import List, Optional
from typing_extensions import Self
from backend.src.database import Base, SessionLocal


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item: Mapped[str] = mapped_column(String(100), nullable=False)
    repository: Mapped[str] = mapped_column(String(50), nullable=False)
    worker: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inbound: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outbound: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __init__(self, order_id: int, item: str, repository: str, worker: str | None = None,
                 inbound: int = 0, outbound: int = 0):
        self.order_id = order_id
        self.item = item
        self.repository = repository
        self.worker = worker
        self.inbound = inbound
        self.outbound = outbound

    def __str__(self):
        return f"Record(id={self.id}, order_id={self.order_id}, item={self.item}, repository={self.repository})"

    # ====================== 批量创建（适配前端） ======================
    @classmethod
    def create_from_work_order(cls, 
                               item: str, 
                               procedures: List[str], 
                               quantity: int,
                               order_id: int | None = None,
                               worker: str | None = None) -> List[Self]:
        if not procedures:
            raise ValueError("至少需要一道工序")

        created_records = []

        with SessionLocal() as session:
            if order_id is None:
                max_order_id = session.query(func.max(cls.order_id)).scalar() or 0
                order_id = max_order_id + 1

            for index, repository in enumerate(procedures):
                inbound = quantity if index == 0 else 0
                
                record = cls(
                    order_id=order_id, # type: ignore
                    item=item,
                    repository=repository,
                    worker=worker,
                    inbound=inbound,
                    outbound=0
                )
                session.add(record)
                created_records.append(record)

            session.commit()
            
            # 刷新所有记录，获取 id 和 created_at
            for record in created_records:
                session.refresh(record)

        return created_records

    @classmethod
    def get_work_orders(cls) -> list[dict]:
        """按 order_id + item 聚合 records，返回前端工单视图需要的数据。"""
        with SessionLocal() as session:
            records = (
                session.query(cls)
                .order_by(cls.order_id.desc(), cls.id.asc())
                .all()
            )

            work_orders: dict[tuple[int, str], dict] = {}

            for record in records:
                key = (record.order_id, record.item)
                work_order = work_orders.setdefault(
                    key,
                    {
                        "id": record.order_id,
                        "item": record.item,
                        "quantity": 0,
                        "createdAt": record.created_at.date().isoformat(),
                        "steps": [],
                    },
                )

                work_order["quantity"] = max(work_order["quantity"], record.inbound)
                work_order["steps"].append(
                    {
                        "name": record.repository,
                        "inbound": record.inbound,
                        "outbound": record.outbound,
                    }
                )

            return list(work_orders.values())
    
    # ====================== 查询 ======================
    @classmethod
    def get_by_id(cls, record_id: int) -> Optional[Self]:
        """根据ID查询"""
        with SessionLocal() as session:
            return session.query(cls).filter(cls.id == record_id).first()

    @classmethod
    def get_by_order_id(cls, order_id: int) -> List[Self]:
        """根据 order_id 查询"""
        with SessionLocal() as session:
            return session.query(cls).filter(cls.order_id == order_id).all()

    @classmethod
    def get_all(cls) -> List[Self]:
        """查询所有"""
        with SessionLocal() as session:
            return session.query(cls).all()

    @classmethod
    def get_by_repository(cls, repository: str) -> List[Self]:
        """按仓库查询"""
        with SessionLocal() as session:
            return session.query(cls).filter(cls.repository == repository).all()

    # ====================== 修改 ======================
    @classmethod
    def update(cls, record_id: int, **kwargs) -> Optional[Self]:
        """更新记录"""
        with SessionLocal() as session:
            record = cls.get_by_id(record_id)   # 注意：这里会再开一个session，下面优化
            if not record:
                return None

            for key, value in kwargs.items():
                if hasattr(record, key):
                    setattr(record, key, value)

            session.commit()
            session.refresh(record)
            return record

    def update_self(self, **kwargs) -> Self:
        """实例方法更新"""
        with SessionLocal() as session:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            session.add(self)          # 确保对象被关联
            session.commit()
            session.refresh(self)
            return self
