class PhysicalIdGenerator:
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
        # Legacy: Keeping it for D_res if needed, but we are moving to brokers
        return f"canonical.resource.{resource_name}"

    @staticmethod
    def global_broker_req(resource_name: str) -> str:
        return f"canonical.resource.broker.req.{resource_name}"

    @staticmethod
    def global_broker_rel(resource_name: str) -> str:
        return f"canonical.resource.broker.rel.{resource_name}"

    @staticmethod
    def global_ledger(resource_name: str) -> str:
        return f"canonical.resource.ledger.{resource_name}"

    @staticmethod
    def requestor(target_node_id: str, resource_name: str) -> str:
        return f"req.{target_node_id}.{resource_name}"

    @staticmethod
    def probe_const(target_node_id: str, arg_name: str) -> str:
        return f"probe.const.{target_node_id}.{arg_name}"

    @staticmethod
    def constant(target_node_id: str, arg_name: str) -> str:
        # The DataNode holding the constant value
        return f"const.{target_node_id}.{arg_name}"

    @staticmethod
    def observability_bus() -> str:
        return "global.observability.bus"

    @staticmethod
    def observability_observer() -> str:
        return "global.observability.observer"
