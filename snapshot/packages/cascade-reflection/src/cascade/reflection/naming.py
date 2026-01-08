from cascade.spec.physical.constants import NodePrefix


class PhysicalIdGenerator:
    @staticmethod
    def bleach_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.BLEACH}"

    @staticmethod
    def worker_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.WORKER}"

    @staticmethod
    def stain_node(logical_node_id: str) -> str:
        return f"{logical_node_id}.{NodePrefix.STAIN}"

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
    def context_data(logical_node_id: str) -> str:
        return f"{logical_node_id}.data.context"

    @staticmethod
    def global_resource(resource_name: str) -> str:
        # Legacy: Keeping it for D_res if needed, but we are moving to brokers
        return f"{NodePrefix.CANONICAL}.resource.{resource_name}"

    @staticmethod
    def global_allocator(resource_name: str) -> str:
        return f"{NodePrefix.CANONICAL}.resource.allocator.{resource_name}"

    @staticmethod
    def global_reclaimer(resource_name: str) -> str:
        return f"{NodePrefix.CANONICAL}.resource.reclaimer.{resource_name}"

    @staticmethod
    def global_ledger(resource_name: str) -> str:
        return f"{NodePrefix.CANONICAL}.resource.{NodePrefix.LEDGER}.{resource_name}"

    @staticmethod
    def requestor(target_node_id: str, resource_name: str) -> str:
        return f"{NodePrefix.REQ}.{target_node_id}.{resource_name}"

    @staticmethod
    def probe_const(target_node_id: str, arg_name: str) -> str:
        return f"{NodePrefix.PROBE}.{NodePrefix.CONST}.{target_node_id}.{arg_name}"

    @staticmethod
    def constant(target_node_id: str, arg_name: str) -> str:
        # The DataNode holding the constant value
        return f"{NodePrefix.CONST}.{target_node_id}.{arg_name}"

    @staticmethod
    def observability_bus() -> str:
        return f"{NodePrefix.GLOBAL}.observability.bus"

    @staticmethod
    def observability_observer() -> str:
        return f"{NodePrefix.GLOBAL}.observability.observer"

    @staticmethod
    def pulse_source(logical_node_id: str) -> str:
        return f"{NodePrefix.PULSE}.source.{logical_node_id}"
