from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from database import SessionLocal
from domain.engineering_products import validate_bom_identity, validate_expected_revision
from domain.time import utc_now
from modules.engineering.command_support import command_result, ensure_version_exists
from modules.engineering.editability import (
    ensure_base_info_editable,
    ensure_product_version_editable,
)
from modules.engineering.flow_mapping import synchronize_part_metadata
from modules.engineering.persistence import Product, ProductVersion
from modules.engineering.repository import EngineeringProductRepository
from modules.engineering.support import (
    bom_commands,
    empty_process_flow,
    raise_integrity_error,
    raise_stale_data_error,
    validated_flow,
)
from schemas.engineering import (
    BomItemPayload,
    CreateProductPayload,
    ProcessFlowPayload,
    UpdateProductPayload,
)
from modules.errors import DomainError, product_not_found
from modules.organization.read_api import (
    get_department_ids_by_codes,
    get_procedure_routes,
)
from modules.sales.customer_api import resolve_customer


def _ensure_procedures_exist(session, flow: ProcessFlowPayload) -> None:
    procedure_ids = {
        node.procedure_id for node in flow.nodes if node.type == "process"
    }
    if not procedure_ids:
        return
    existing_ids = set(get_procedure_routes(session, procedure_ids))
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
    procedures = get_procedure_routes(session, procedure_ids)
    department_ids = get_department_ids_by_codes(
        session,
        {"assembly", "finished", "qc"},
    )
    required_department_codes = {
        code
        for code, node_type in (
            ("assembly", "assembly"),
            ("finished", "shipping"),
            ("qc", "qc"),
        )
        if any(node.type == node_type for node in flow.nodes)
    }
    missing_department_codes = required_department_codes - set(department_ids)
    if missing_department_codes:
        missing_code = sorted(missing_department_codes)[0]
        missing_type = {
            "assembly": "assembly",
            "finished": "shipping",
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
            return procedure.department_id if procedure else None
        if node.type == "assembly":
            return department_ids.get("assembly")
        if node.type == "shipping":
            return department_ids.get("finished")
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
            customer = resolve_customer(
                session,
                payload.customer_id,
                payload.customer_name,
                allow_create=True,
            )
            product = Product(
                customer_id=customer.id,
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
            customer = resolve_customer(
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
            if product.factory_code != payload.factory_code:
                for flow_record in product.process_flows:
                    version_bom = {
                        item.id: (item.part_name, item.part_no)
                        for item in product.bom_items
                        if item.product_version == flow_record.product_version
                    }
                    synchronized = synchronize_part_metadata(
                        ProcessFlowPayload.model_validate(flow_record.flow_json),
                        version_bom,
                        payload.factory_code,
                    )
                    repository.set_process_flow(
                        product,
                        flow_record.product_version,
                        synchronized.model_dump(exclude_none=True),
                    )
            product.customer_id = customer.id
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
                    product.factory_code,
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
                product.factory_code,
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
