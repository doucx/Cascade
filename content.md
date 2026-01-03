## [WIP] debug(vm): 深度追踪 Reactor 调度与执行

### 用户需求
增强调试能力，在 `Reactor` 的 `_execute_task` 方法和测试的 `adapter` 中添加详细日志，以追踪哪些任务被实际调度了，以及它们的执行状态。

### 评论
面对“物理逻辑成立但观测结果矛盾”的困境，我们必须深入到执行引擎的微观层面。通过记录每一次任务调度的尝试和结果，我们将揭示 `setup_task` 到底经历了什么——是被忽略了、被调度但未执行、还是执行了但无声无息。

### 目标
1.  修改 `packages/cascade-vm/src/cascade/vm/reactor.py`，在 `_execute_task` 开始时打印日志。
2.  修改 `test_e2e_vm_run.py`，在 adapter 中打印更多上下文信息（如 Node ID）。

### 标签
#intent/tooling #flow/ready #priority/high #comp/vm #comp/tests #task/domain/testing #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 在 Reactor 中增加执行日志

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    async def _execute_task(
        self, node: PhysicsFuncNode, input_data: Dict[str, Token]
    ) -> None:
        try:
            # 1. Execution
            func = self.function_map.get(node.id)
~~~~~
~~~~~python.new
    async def _execute_task(
        self, node: PhysicsFuncNode, input_data: Dict[str, Token]
    ) -> None:
        try:
            print(f"[Reactor] Executing {node.id} ({node.name})")
            # 1. Execution
            func = self.function_map.get(node.id)
~~~~~

#### Acts 2: 在测试 Adapter 中增加日志

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_e2e_vm_run.py
~~~~~
~~~~~python.old
    # Helper to adapt user functions to Physics Protocol
    def create_worker_adapter(user_func):
        async def adapter(inputs: Dict[str, Token], node):
            # Unpack kwargs from the worker_input token
            kwargs = inputs["worker_input"].payload
            print(f"DEBUG: Executing {user_func.__name__} with {kwargs}")
            
            # Call user function
~~~~~
~~~~~python.new
    # Helper to adapt user functions to Physics Protocol
    def create_worker_adapter(user_func):
        async def adapter(inputs: Dict[str, Token], node):
            # Unpack kwargs from the worker_input token
            kwargs = inputs["worker_input"].payload
            print(f"DEBUG: Adapter invoked for {node.id} -> {user_func.__name__} with {kwargs}")

            # Call user function
~~~~~

### 下一步建议
再次运行测试。这次的日志将告诉我们 `setup_task.worker` 是否曾经被 `Reactor` 触碰过。
