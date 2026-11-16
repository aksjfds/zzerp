from copy import deepcopy

from database import SessionLocal
from domain.engineering_products import validate_expected_revision
from domain.models import BomItemCommand
from domain.time import utc_now
from schemas.engineering import ProcessFlowPayload
from sqlalchemy.exc import IntegrityError

from modules.engineering.command_support import command_result, product_versions
from modules.engineering.persistence import ProductVersion
from modules.engineering.repository import EngineeringProductRepository
from modules.engineering.routing import synchronize_routes, validate_nodes
from modules.engineering.support import empty_process_flow, raise_integrity_error
from modules.errors import DomainError, product_not_found


def create_product_version(
    product_id: int,
    expected_revision: int,
    version_value: str,
    source_version: int | None = None,
) -> dict:
    value = version_value.strip()
    if not value or len(value) > 100:
        raise DomainError("appearance_version_value_invalid", "外观版本值须为1–100个字符", path="version_value")
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)

            available_versions = product_versions(product)
            copy_from_version = source_version or product.version
            if copy_from_version not in available_versions:
                raise product_not_found()
            next_version = max(item.version for item in product.versions) + 1
            product.versions.append(ProductVersion(version=next_version, value=value))
            repository.flush()
            source_items = [
                item
                for item in product.bom_items
                if item.product_version == copy_from_version
            ]
            copied_items = repository.replace_bom(
                product,
                next_version,
                [
                    BomItemCommand(
                        id=None,
                        part_name=item.part_name,
                        part_no=item.part_no,
                        pcs=item.pcs,
                        remark=item.remark,
                    )
                    for item in source_items
                ],
            )
            repository.flush()
            source_flow = next(
                (
                    item.flow_json
                    for item in product.process_flows
                    if item.product_version == copy_from_version
                ),
                empty_process_flow(),
            )
            copied_flow = ProcessFlowPayload.model_validate(deepcopy(source_flow))
            copied_by_number = {item.part_no: item.id for item in copied_items}
            bom_id_map = {item.id: copied_by_number[item.part_no] for item in source_items}
            for node in copied_flow.nodes:
                if node.type == "part":
                    node.bom_item_id = bom_id_map[node.bom_item_id]
            copied_flow = validate_nodes(session, product.id, next_version, copied_flow)
            copied_flow = copied_flow.model_dump(exclude_none=True)
            repository.set_process_flow(product, next_version, copied_flow)
            product.version = next_version
            synchronize_routes(session, product.id, ProcessFlowPayload.model_validate(copied_flow))
            product.revision += 1
            product.updated_at = utc_now()
            return command_result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)
