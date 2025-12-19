## [WIP] fix(runtime): 调整 Engine 启动顺序以修复遥测丢失与竞态条件

### 用户需求
修复 Engine 启动时的时序缺陷：
1.  **遥测丢失**: `RunStarted` 事件在 MQTT 连接建立前触发，导致其被丢弃。
2.  **控制面竞态**: Engine 在完全同步外部约束（如 `pause`）之前就开始执行任务。

### 评论
该修复实施了“先连接，后运行”的策略。通过将 `connector.connect()` 和 `connector.subscribe()` 的调用提前到 `RunStarted` 事件发布和任何任务调度之前，我们确保了：
1.  遥测通道在第一条消息产生前是畅通的。
2.  初始的系统状态（包括保留的 MQTT 约束消息）在执行任何工作前已完全同步。

### 目标
修改 `cascade-runtime/src/cascade/runtime/engine.py` 中的 `run` 方法，重排初始化逻辑。

### 基本原理
当前的实现是“乐观执行”，即先宣布开始（`RunStarted`），再尝试连接基础设施。这在分布式环境中是脆弱的。新的顺序强制执行“基础设施优先”原则，消除了启动时的不确定性窗口。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/lifecycle #scope/core #ai/instruct #task/domain/runtime #task/object/engine-startup #task/action/reorder #task/state/continue

---

### Script

#### Acts 1: 重构 `Engine.run` 方法

我们将 `connector` 的连接和订阅逻辑提升到方法的顶部，置于 `RunStarted` 事件发布之前。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()

        # Robustly determine target name
        if hasattr(target, "task"):
            target_name = getattr(target.task, "name", "unknown")
        elif hasattr(target, "factory"):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"
        else:
            target_name = "unknown"

        self.bus.publish(
            RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
        )

        state_backend = self.state_backend_cls(run_id=run_id)

        try:
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                # Subscribe to constraint updates
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            with ExitStack() as stack:
~~~~~
~~~~~python
    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()

        # Robustly determine target name
        if hasattr(target, "task"):
            target_name = getattr(target.task, "name", "unknown")
        elif hasattr(target, "factory"):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"
        else:
            target_name = "unknown"

        # Initialize State Backend first (no side effects)
        state_backend = self.state_backend_cls(run_id=run_id)

        try:
            # 1. Establish Infrastructure Connection FIRST
            # This ensures we are ready to transmit telemetry and receive constraints
            # BEFORE we announce the run starting or execute any logic.
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                # Subscribe to constraint updates immediately.
                # This gives the connector a chance to receive retained messages (like global pause)
                # before we enter the execution loop.
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            # 2. Publish Lifecycle Event
            # Now that the connector is active, this event will be successfully transmitted.
            self.bus.publish(
                RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
            )

            with ExitStack() as stack:
~~~~~

### 下一步建议
我们已经应用了针对启动竞态条件的修复。根据测试驱动开发（TDD）流程，现在应当重新运行我们编写的失败测试用例：
1.  `test_startup_telemetry_no_race_condition`
2.  `test_startup_pause_is_respected` (如果已添加)

如果这些测试通过，我们将继续执行路线图的 **步骤 4: [红灯] 为运行时控制延迟编写一个失败的测试**，验证 `Engine` 是否能在长运行阶段中及时响应新的约束。
