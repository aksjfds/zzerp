from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from database import SessionLocal
from domain.engineering_products import validate_bom_identity, validate_expected_revision
from domain.time import utc_now
from models.engineering import Product, ProductVersion
from models.customer import Customer
from models.organization import Department, Procedure, Workshop
from repositories.engineering_products import EngineeringProductRepository
from schemas.engineering import (
    BomItemPayload,
    CreateProductPayload,
    ProcessFlowPayload,
    UpdateProductPayload,
)
from services.engineering_product_command_support import command_result, ensure_version_exists
from services.engineering_product_editability import (
    ensure_base_info_editable,
    ensure_product_version_editable,
)
from services.engineering_product_support import (
    bom_commands,
    empty_process_flow,
    raise_integrity_error,
    raise_stale_data_error,
    validated_flow,
)
from services.errors import DomainError, product_not_found
from services.process_flow_mapping import synchronize_part_metadata

def _ensure_procedures_exist(session, flow: ProcessFlowPayload) -> None:
    procedure_ids = {
        node.procedure_id for node in flow.nodes if node.type == "process"
    }
    if not procedure_ids:
        return
    existing_ids = set(
        session.scalars(select(Procedure.id).where(Procedure.id.in_(procedure_ids))).all()
    )
    if existing_ids != procedure_ids:
        invalid_node = next(
            node
            for node in flow.nodes
            if node.type == "process" and node.procedure_id not in existing_ids
        )
        raise DomainError(
            "process_procedure_invalid",
            f"工艺节点“{invalid_node.label}”引用的工艺不存在，请重新选择工艺",
            path="process_flow.nodes",
            element_id=invalid_node.id,
        )


def _validate_qc_routes(session, flow: ProcessFlowPayload) -> None:
    nodes = {node.id: node for node in flow.nodes}
    targets = {
        edge.source_node_id: nodes[edge.target_node_id]
        for edge in flow.edges
    }
    procedure_ids = {
        node.procedure_id for node in flow.nodes if node.type == "process"
    }
    procedures = {
        procedure.id: procedure
        for procedure in session.scalars(
            select(Procedure).where(Procedure.id.in_(procedure_ids))
        )
    } if procedure_ids else {}
    workshop_ids = {procedure.workshop_id for procedure in procedures.values()}
    workshops = {
        workshop.id: workshop
        for workshop in session.scalars(
            select(Workshop).where(Workshop.id.in_(workshop_ids))
        )
    } if workshop_ids else {}
    department_ids = {
        code: department_id
        for code, department_id in session.execute(
            select(Department.department_code, Department.id).where(
                Department.department_code.in_(("assembly", "warehouse", "qc"))
            )
        )
    }
    required_department_codes = {
        code
        for code, node_type in (
            ("assembly", "assembly"),
            ("warehouse", "shipping"),
            ("qc", "qc"),
        )
        if any(node.type == node_type for node in flow.nodes)
    }
    missing_department_codes = required_department_codes - set(department_ids)
    if missing_department_codes:
        missing_code = sorted(missing_department_codes)[0]
        missing_type = {
            "assembly": "assembly",
            "warehouse": "shipping",
            "qc": "qc",
        }[missing_code]
        invalid_node = next(
            (node for node in flow.nodes if node.type == missing_type),
            None,
        )
        raise DomainError(
            "flow_department_missing",
            f"流程所需部门不存在：{', '.join(sorted(missing_department_codes))}",
            path="process_flow.nodes",
            element_id=invalid_node.id if invalid_node else None,
        )

    def node_department_id(node) -> int | None:
        if node.type == "process":
            procedure = procedures.get(node.procedure_id)
            workshop = workshops.get(procedure.workshop_id) if procedure else None
            return workshop.department_id if workshop else None
        if node.type == "assembly":
            return department_ids.get("assembly")
        if node.type == "shipping":
            return department_ids.get("warehouse")
        return None

    for node in flow.nodes:
        target = targets.get(node.id)
        if node.type == "process":
            procedure = procedures.get(node.procedure_id)
            if procedure is None:
                raise DomainError(
                    "process_procedure_invalid",
                    f"工艺节点“{node.label}”引用的工艺不存在，请重新选择工艺",
                    path="process_flow.nodes",
                    element_id=node.id,
                )
            if procedure.procedure_type == "standard" and (
                target is None or target.type != "qc"
            ):
                raise DomainError(
                    "standard_process_qc_required",
                    f"工艺“{node.label}”的下一节点必须是QC，请删除原连线后连接QC节点",
                    path="process_flow.edges",
                    element_id=node.id,
                )
        if node.type not in {"process", "assembly"} or target is None:
            continue
        if target.type == "qc":
            continue
        source_department_id = node_department_id(node)
        target_department = node_department_id(target)
        if (
            source_department_id is not None
            and target_department is not None
            and source_department_id != target_department
        ):
            raise DomainError(
                "cross_department_qc_required",
                f"“{node.label}”到“{target.label}”跨部门，必须经过QC节点",
                path="process_flow.edges",
                element_id=node.id,
            )


def create_product(payload: CreateProductPayload) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            items = bom_commands(payload.bom_items)
            validate_bom_identity(items, existing_ids=set())
            customer = _resolve_product_customer(
                session,
                payload.customer_id,
                payload.customer_name,
                allow_create=True,
            )
            product = Product(
                customer=customer,
                product_name=payload.product_name,
                factory_code=payload.factory_code,
                customer_code=payload.customer_code,
            )
            product.versions.append(ProductVersion(version=1))
            repository.add(product)
            repository.flush()
            repository.replace_bom(product, product.version, items)
            repository.set_process_flow(product, product.version, empty_process_flow())
            return command_result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)


def update_product_info(product_id: int, payload: UpdateProductPayload) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, payload.expected_revision)
            customer = _resolve_product_customer(
                session,
                payload.customer_id,
                payload.customer_name,
                allow_create=True,
            )
            unchanged = (
                product.customer_id == customer.id
                and product.product_name == payload.product_name
                and product.factory_code == payload.factory_code
                and product.customer_code == payload.customer_code
            )
            if unchanged:
                return command_result(repository, product)
            ensure_base_info_editable(session, product.id)
            product.customer = customer
            product.product_name = payload.product_name
            product.factory_code = payload.factory_code
            product.customer_code = payload.customer_code
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def _resolve_product_customer(
    session,
    customer_id: int | None,
    customer_name: str | None,
    *,
    allow_create: bool,
) -> Customer:
    if customer_id is not None:
        customer = session.get(Customer, customer_id)
        if customer is None:
            raise DomainError(
                "customer_not_found",
                "所选客户不存在，请重新选择",
                path="customer_id",
            )
        return customer
    normalized_name = (customer_name or "").strip()
    if not allow_create or not normalized_name:
        raise DomainError(
            "customer_required",
            "请选择客户或输入新客户名称",
            path="customer_id",
        )
    customer = session.scalar(
        select(Customer)
        .where(Customer.customer_name == normalized_name)
        .with_for_update()
    )
    if customer is None:
        customer = Customer(customer_name=normalized_name)
        session.add(customer)
        session.flush()
    return customer


def replace_product_bom(
    product_id: int,
    expected_revision: int,
    product_version: int,
    items: list[BomItemPayload],
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            ensure_version_exists(product, product_version)
            ensure_product_version_editable(session, product.id, product_version)
            commands = bom_commands(items)
            retained_ids = validate_bom_identity(
                commands,
                {
                    item.id
                    for item in product.bom_items
                    if item.product_version == product_version
                },
            )
            current_flow = None
            process_flow_record = next(
                (
                    item
                    for item in product.process_flows
                    if item.product_version == product_version
                ),
                None,
            )
            if process_flow_record is not None:
                current_flow = ProcessFlowPayload.model_validate(
                    process_flow_record.flow_json
                )
                validated_flow(current_flow, retained_ids)
            saved_items = repository.replace_bom(product, product_version, commands)
            if current_flow is not None:
                synchronized = synchronize_part_metadata(
                    current_flow,
                    {item.id: (item.part_name, item.part_no) for item in saved_items},
                )
                repository.set_process_flow(
                    product,
                    product_version,
                    synchronized.model_dump(exclude_none=True),
                )
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product, product_version)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def update_product_process_flow(
    product_id: int,
    expected_revision: int,
    product_version: int,
    process_flow: ProcessFlowPayload,
) -> dict:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            ensure_version_exists(product, product_version)
            ensure_product_version_editable(session, product.id, product_version)
            flow = synchronize_part_metadata(
                process_flow,
                {
                    item.id: (item.part_name, item.part_no)
                    for item in product.bom_items
                    if item.product_version == product_version
                },
            )
            validated = validated_flow(
                flow,
                {
                    item.id
                    for item in product.bom_items
                    if item.product_version == product_version
                },
            )
            _ensure_procedures_exist(session, flow)
            _validate_qc_routes(session, flow)
            repository.set_process_flow(
                product,
                product_version,
                validated,
            )
            product.updated_at = utc_now()
            product.revision += 1
            return command_result(repository, product, product_version)
    except IntegrityError as exc:
        raise_integrity_error(exc)
    except StaleDataError as exc:
        raise_stale_data_error(exc)


def delete_product(product_id: int, expected_revision: int) -> None:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            repository.delete(product)
    except IntegrityError as exc:
        raise DomainError(
            "product_in_use",
            "产品已被客户订单引用，不能删除",
            status_code=409,
        ) from exc
    except StaleDataError as exc:
        raise_stale_data_error(exc)
