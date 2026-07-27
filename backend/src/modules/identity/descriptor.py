from modules.contracts import ModuleDescriptor


MODULE = ModuleDescriptor(
    name="identity",
    public_api="modules.identity.api",
    owns=("user", "user_session", "authentication", "authorization"),
    collaboration_apis=("modules.identity.model_api",),
)
