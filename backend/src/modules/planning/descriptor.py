from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="planning",
    public_api="modules.planning.api",
    owns=("pmc_part_progress_read_model", "production_reporting"),
    collaborates_with=(
        "assembly",
        "engineering",
        "organization",
        "production_core",
        "quality",
        "sales",
        "standard_execution",
    ),
)
