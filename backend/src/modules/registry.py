from modules.assembly.descriptor import MODULE as ASSEMBLY
from modules.engineering.descriptor import MODULE as ENGINEERING
from modules.identity.descriptor import MODULE as IDENTITY
from modules.inventory.descriptor import MODULE as INVENTORY
from modules.organization.descriptor import MODULE as ORGANIZATION
from modules.planning.descriptor import MODULE as PLANNING
from modules.production_core.descriptor import MODULE as PRODUCTION_CORE
from modules.purchasing.descriptor import MODULE as PURCHASING
from modules.quality.descriptor import MODULE as QUALITY
from modules.sales.descriptor import MODULE as SALES
from modules.standard_execution.descriptor import MODULE as STANDARD_EXECUTION
from modules.workforce.descriptor import MODULE as WORKFORCE


MODULES = {
    module.name: module
    for module in (
        IDENTITY,
        INVENTORY,
        ORGANIZATION,
        ENGINEERING,
        SALES,
        PRODUCTION_CORE,
        STANDARD_EXECUTION,
        PURCHASING,
        ASSEMBLY,
        QUALITY,
        WORKFORCE,
        PLANNING,
    )
}


def module_descriptor(name: str):
    try:
        return MODULES[name]
    except KeyError as exc:
        raise LookupError(f"Unknown business module: {name}") from exc


def module_manifests() -> list[dict]:
    return [
        {
            "name": module.name,
            "api_version": module.api_version,
            "public_api": module.public_api,
            "collaboration_apis": list(module.collaboration_apis),
            "owns": list(module.owns),
            "collaborates_with": list(module.collaborates_with),
        }
        for module in MODULES.values()
    ]
