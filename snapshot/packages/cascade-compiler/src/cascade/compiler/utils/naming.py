class PhysicalIdGenerator:
    """
    The central authority for generating canonical IDs for physical nodes.
    Ensures consistency and adherence to naming axioms across the compiler.
    """

    @staticmethod
    def bleach_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.bleach"

    @staticmethod
    def worker_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.worker"

    @staticmethod
    def stain_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.stain"

    @staticmethod
    def worker_in_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.in"

    @staticmethod
    def worker_out_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.out"

    @staticmethod
    def trace_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.trace"

    @staticmethod
    def global_resource(resource_name: str) -> str:
        return f"canonical.resource.{resource_name}"

    @staticmethod
    def constant(target_node_id: str, arg_name: str) -> str:
        return f"const.{target_node_id}.{arg_name}"

    @staticmethod
    def observability_bus() -> str:
        return "global.observability.bus"

    @staticmethod
    def observability_observer() -> str:
        return "global.observability.observer"