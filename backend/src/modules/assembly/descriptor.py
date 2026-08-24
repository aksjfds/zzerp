from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="assembly",
    public_api="modules.assembly.api",
    owns=("assembly_execution_policy",),
    collaborates_with=(
        "inventory",
        "organization",
        "planning",
        "production_core",
        "quality",
        "sales",
        "standard_execution",
        "workforce",
    ),
    collaboration_apis=(
        "modules.assembly.qc_api",
    ),
)
