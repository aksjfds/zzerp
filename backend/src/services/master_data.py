from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.catalog import CustomerSurfaceTreatment
from models.organization import Department, Workshop


def normalize_required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name}不能为空")
    return normalized


class MasterDataService:
    @staticmethod
    def list_departments() -> list[Department]:
        with SessionLocal() as session:
            return session.query(Department).order_by(Department.id.asc()).all()

    @staticmethod
    def list_workshops(department_id: int | None = None) -> list[Workshop]:
        with SessionLocal() as session:
            query = session.query(Workshop)
            if department_id is not None:
                query = query.filter(Workshop.department_id == department_id)
            return query.order_by(
                Workshop.department_id.asc(),
                Workshop.workshop_name.asc(),
            ).all()

    @staticmethod
    def create_workshop(
        department_id: int,
        workshop_code: str,
        workshop_name: str,
    ) -> Workshop:
        with SessionLocal() as session:
            department = session.get(Department, department_id)
            if department is None or not department.active:
                raise ValueError("部门不存在或已停用")
            if department.department_type != "production":
                raise ValueError("只有生产部门可以建立车间")

            workshop = Workshop(
                department_id=department_id,
                workshop_code=normalize_required(workshop_code, "车间编码"),
                workshop_name=normalize_required(workshop_name, "车间名称"),
                active=True,
            )
            session.add(workshop)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("同一部门下车间编码或名称不能重复") from exc
            session.refresh(workshop)
            return workshop

    @staticmethod
    def update_workshop(
        workshop_id: int,
        workshop_name: str | None,
        active: bool | None,
    ) -> Workshop:
        with SessionLocal() as session:
            workshop = session.get(Workshop, workshop_id)
            if workshop is None:
                raise ValueError("车间不存在")
            if workshop_name is not None:
                workshop.workshop_name = normalize_required(workshop_name, "车间名称")
            if active is not None:
                workshop.active = active
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("同一部门下车间名称不能重复") from exc
            session.refresh(workshop)
            return workshop

    @staticmethod
    def list_surface_treatments(
        customer_name: str | None = None,
    ) -> list[CustomerSurfaceTreatment]:
        with SessionLocal() as session:
            query = session.query(CustomerSurfaceTreatment)
            if customer_name and customer_name.strip():
                query = query.filter(
                    CustomerSurfaceTreatment.customer_name == customer_name.strip(),
                )
            return query.order_by(
                CustomerSurfaceTreatment.customer_name.asc(),
                CustomerSurfaceTreatment.treatment_name.asc(),
            ).all()

    @staticmethod
    def create_surface_treatment(
        customer_name: str,
        treatment_name: str,
    ) -> CustomerSurfaceTreatment:
        treatment = CustomerSurfaceTreatment(
            customer_name=normalize_required(customer_name, "客户名称"),
            treatment_name=normalize_required(treatment_name, "表面处理名称"),
            active=True,
        )
        with SessionLocal() as session:
            session.add(treatment)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("该客户已存在同名表面处理") from exc
            session.refresh(treatment)
            return treatment

    @staticmethod
    def update_surface_treatment(
        treatment_id: int,
        treatment_name: str | None,
        active: bool | None,
    ) -> CustomerSurfaceTreatment:
        with SessionLocal() as session:
            treatment = session.get(CustomerSurfaceTreatment, treatment_id)
            if treatment is None:
                raise ValueError("表面处理不存在")
            if treatment_name is not None:
                treatment.treatment_name = normalize_required(
                    treatment_name,
                    "表面处理名称",
                )
            if active is not None:
                treatment.active = active
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError("该客户已存在同名表面处理") from exc
            session.refresh(treatment)
            return treatment
