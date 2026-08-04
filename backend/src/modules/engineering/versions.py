from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from database import SessionLocal
from domain.engineering_products import validate_expected_revision
from domain.models import BomItemCommand
from domain.time import utc_now
from modules.engineering.persistence import ProductVersion
from modules.engineering.command_support import command_result, product_versions
from modules.engineering.editability import ensure_product_version_editable
from modules.engineering.repository import EngineeringProductRepository
from modules.engineering.support import (
    empty_process_flow,
    raise_integrity_error,
    raise_stale_data_error,
)
from modules.engineering.flow_mapping import synchronize_part_metadata
from modules.errors import DomainError, product_not_found
from modules.standard_execution.pricing_api import copy_product_version_prices
from schemas.engineering import ProcessFlowPayload


def create_product_version(
    product_id: int,
    expected_revision: int,
    source_version: int | None = None,
) -> dict:
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
            next_version = max(available_versions | {product.version}) + 1
            product.versions.append(ProductVersion(version=next_version))
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
            copied_by_part_no = {item.part_no: item for item in copied_items}
            id_map = {
                source.id: copied_by_part_no[source.part_no].id
                for source in source_items
            }
            source_flow = next(
                (
                    item.flow_json
                    for item in product.process_flows
                    if item.product_version == copy_from_version
                ),
                empty_process_flow(),
            )
            copied_flow = deepcopy(source_flow)
            for node in copied_flow.get("nodes", []):
                if node.get("type") == "part":
                    source_bom_id = node.get("bom_item_id")
                    if source_bom_id not in id_map:
                        raise DomainError(
                            "source_flow_bom_invalid",
                            "源版本流程中的配件节点未引用有效 BOM 行，请先修复源版本流程",
                            element_id=node.get("id"),
                        )
                    node["bom_item_id"] = id_map[source_bom_id]
            copied_flow = synchronize_part_metadata(
                ProcessFlowPayload.model_validate(copied_flow),
                {
                    item.id: (item.part_name, item.part_no)
                    for item in copied_items
                },
                product.factory_code,
            ).model_dump(exclude_none=True)
            repository.set_process_flow(product, next_version, copied_flow)
            copy_product_version_prices(
                session,
                product_id=product.id,
                source_version=copy_from_version,
                target_version=next_version,
            )
            product.version = next_version
            product.revision += 1
            product.updated_at = utc_now()
            return command_result(repository, product)
    except IntegrityError as exc:
        raise_integrity_error(exc)


def delete_product_version(
    product_id: int,
    product_version: int,
    expected_revision: int,
) -> dict | None:
    try:
        with SessionLocal.begin() as session:
            repository = EngineeringProductRepository(session)
            product = repository.get(product_id)
            if product is None:
                raise product_not_found()
            session.refresh(product, with_for_update=True)
            validate_expected_revision(product.revision, expected_revision)
            versions = sorted(product_versions(product))
            if product_version not in versions:
                raise product_not_found()
            ensure_product_version_editable(session, product.id, product_version)
            if len(versions) == 1:
                repository.delete(product)
                return None

            for item in list(product.bom_items):
                if item.product_version == product_version:
                    product.bom_items.remove(item)
            for item in list(product.process_flows):
                if item.product_version == product_version:
                    product.process_flows.remove(item)
            for item in list(product.versions):
                if item.version == product_version:
                    product.versions.remove(item)
            product.version = max(version for version in versions if version != product_version)
            product.revision += 1
            product.updated_at = utc_now()
            return command_result(repository, product)
    except IntegrityError as exc:
        raise DomainError(
            "product_version_in_use",
            "当前产品版本已被订单或生产数据引用，不能删除",
            status_code=409,
        ) from exc
    except StaleDataError as exc:
        raise_stale_data_error(exc)
