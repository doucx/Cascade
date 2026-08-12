from pathlib import Path

from stitcher.refactor.migration import MigrationSpec, Move, MoveDir


def upgrade(spec: MigrationSpec):
    # 基础路径定义
    base = Path("packages/cascade-runtime/src/cascade").absolute()
    runtime_base = base / "runtime"
    adapters_base = base / "adapters"

    # ==========================================
    # 1. IO Layer (From cascade.adapters)
    # ==========================================
    # 将原来的 adapters 移入 runtime.io
    spec.add(MoveDir(adapters_base / "executors", runtime_base / "io/executors"))
    spec.add(MoveDir(adapters_base / "cache", runtime_base / "io/cache"))
    spec.add(MoveDir(adapters_base / "state", runtime_base / "io/state"))
    spec.add(MoveDir(adapters_base / "caching", runtime_base / "io/caching"))

    # ==========================================
    # 2. Kernel Layer
    # ==========================================
    # Solvers 属于核心调度内核
    spec.add(MoveDir(adapters_base / "solvers", runtime_base / "kernel/solvers"))

    # ==========================================
    # 3. Host Layer
    # ==========================================
    # Engine 类是运行时的实例
    spec.add(Move(runtime_base / "engine.py", runtime_base / "host/instance.py"))

    # ==========================================
    # 4. Services Layer
    # ==========================================
    # Constraints 服务
    spec.add(
        MoveDir(runtime_base / "constraints", runtime_base / "services/constraints")
    )

    # Observability 服务 (EventBus, Events, Logs)
    spec.add(
        Move(
            runtime_base / "event_bus.py",
            runtime_base / "services/observability/bus.py",
        )
    )
    spec.add(
        Move(
            runtime_base / "events.py",
            runtime_base / "services/observability/events.py",
        )
    )
    spec.add(
        Move(
            runtime_base / "subscribers.py",
            runtime_base / "services/observability/subscribers.py",
        )
    )

    # Resource 服务
    spec.add(
        Move(
            runtime_base / "resource_manager.py",
            runtime_base / "services/resources/manager.py",
        )
    )
    spec.add(
        Move(
            runtime_base / "resource_container.py",
            runtime_base / "services/resources/container.py",
        )
    )

    # ==========================================
    # 5. Legacy Layer (V2 Logic)
    # ==========================================
    # 这些组件未来会被 VM 取代，暂时归档到 legacy
    spec.add(MoveDir(runtime_base / "strategies", runtime_base / "legacy/strategies"))
    spec.add(Move(runtime_base / "processor.py", runtime_base / "legacy/processor.py"))
    spec.add(Move(runtime_base / "flow.py", runtime_base / "legacy/flow.py"))
    spec.add(Move(runtime_base / "resolvers.py", runtime_base / "legacy/resolvers.py"))

    # ==========================================
    # 6. Commons
    # ==========================================
    spec.add(Move(runtime_base / "exceptions.py", runtime_base / "errors.py"))
