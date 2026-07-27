from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="assembly",
    public_api="modules.assembly.api",
    owns=("assembly_execution_policy", "work_order_material"),
    collaborates_with=(
        "engineering",
        "organization",
        "production_core",
        "quality",
        "workforce",
    ),
    collaboration_apis=(
        "modules.assembly.model_api",
        "modules.assembly.qc_api",
    ),
)
