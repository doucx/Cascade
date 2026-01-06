## [WIP] feat(vm): 实现 PhysicsKernel

### 用户需求
在 `cascade-vm` 中实现 `PhysicsKernel`，作为 v3.1 架构中负责执行内核态任务（ICs, Standard Library）的组件。它是一个纯同步、高性能的执行单元，仅处理引用和元数据，不进行 I/O 操作。

### 评论
`PhysicsKernel` 是 v3.1 架构的“心脏”。它的设计目标是**极速**。与 `ComputeDelegate` 处理繁重的用户代码不同，Kernel 只负责推演图的状态。所有的操作（漂白、染色、路由）都必须在微秒级完成。因此，它**严禁**使用 `async`，也**严禁**进行 `store.get()` (除非是极其特殊的轻量级元数据操作，但即便如此也应避免)。

### 目标
1.  创建 `cascade.vm.kernel` 包。
2.  实现 `PhysicsKernel` 类。
3.  定义 Kernel 函数的签名规范：`(inputs: Dict[str, Ref], node: PhysicsNode, resources: Any) -> Dict[str, Ref]`。
4.  实现 `executor` 风格的接口，但要是同步的。
5.  添加单元测试。

### 基本原理
*   **同步执行**: 所有 Kernel 函数都是普通的 Python 函数，不是协程。
*   **引用传递**: 输入输出全都是 `Ref`。Kernel 不关心 `Ref` 背后是什么，只关心如何传递它。
*   **即时返回**: 调用 `kernel.execute(...)` 会立即返回结果字典，没有 `await`，没有 `Future`。
*   **资源注入**: 依然支持 `resource_registry` 的注入，用于访问 EventBus 等系统服务（EventBus 的发布操作在 Kernel 中通常是 `fire_and_forget` 或非阻塞的）。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/kernel #scope/core #ai/instruct #task/domain/vm #task/object/physics-kernel #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 创建 kernel 模块目录

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-vm/src/cascade/vm/kernel
touch packages/cascade-vm/src/cascade/vm/kernel/__init__.py
~~~~~

#### Acts 2: 实现 `PhysicsKernel`

创建 `packages/cascade-vm/src/cascade/vm/kernel/core.py`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/kernel/core.py
~~~~~
~~~~~python
import logging
from typing import Any, Callable, Dict

from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)

# Kernel function signature:
# (inputs: Dict[str, Ref], node: PhysicsFuncNode, resources: ResourceRegistry) -> Dict[str, Ref]
KernelFunc = Callable[[Dict[str, Ref], PhysicsFuncNode, ResourceRegistry], Dict[str, Ref]]


class PhysicsKernel:
    """
    The synchronous execution core for Cascade v3.1 Physics Layer.

    Responsibilities:
    1. Executes Standard Library ICs (Bleachers, Stainers, Allocators).
    2. Operates exclusively on References (Ref), never dereferencing payloads.
    3. Guarantees microseconds-level latency per operation.
    4. Purely synchronous execution model (no async/await).
    """

    def __init__(self, function_map: Dict[str, KernelFunc], resources: ResourceRegistry):
        self._function_map = function_map
        self._resources = resources

    def execute(
        self, node: PhysicsFuncNode, inputs: Dict[str, Ref]
    ) -> Dict[str, Ref]:
        """
        Execute a kernel function for the given node.

        Args:
            node: The physical function node being executed.
            inputs: A dictionary of input References mapped by port name.

        Returns:
            A dictionary of output References mapped by port name.

        Raises:
            ValueError: If no kernel function is mapped to the node.
            Exception: Any error raised by the kernel function itself.
        """
        func = self._function_map.get(node.id)
        if not func:
            raise ValueError(f"No kernel function mapped for node '{node.id}'")

        try:
            # Execute synchronously
            outputs = func(inputs, node, self._resources)
            return outputs
        except Exception as e:
            logger.exception(f"Kernel panic at node '{node.id}': {e}")
            raise e
~~~~~

#### Acts 3: 导出模块

更新 `packages/cascade-vm/src/cascade/vm/kernel/__init__.py`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/kernel/__init__.py
~~~~~
~~~~~python
from .core import PhysicsKernel, KernelFunc

__all__ = ["PhysicsKernel", "KernelFunc"]
~~~~~

#### Acts 4: 创建单元测试

创建 `packages/cascade-vm/tests/unit/test_physics_kernel.py`。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_physics_kernel.py
~~~~~
~~~~~python
import pytest
from typing import Dict, Any

from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.kernel.core import PhysicsKernel


# --- Kernel Function Mocks ---


def kernel_identity(
    inputs: Dict[str, Ref], node: PhysicsFuncNode, resources: Any
) -> Dict[str, Ref]:
    # Simple pass-through: input 'in' -> output 'out'
    return {"out": inputs["in"]}


def kernel_resource_access(
    inputs: Dict[str, Ref], node: PhysicsFuncNode, resources: ResourceRegistry
) -> Dict[str, Ref]:
    # Validates that we can access resources
    config = resources.get("config")
    # Return a synthetic Ref based on config (just for testing logic)
    return {"out": Ref(uri=f"mem://config-{config['version']}")}


def kernel_fail(
    inputs: Dict[str, Ref], node: PhysicsFuncNode, resources: Any
) -> Dict[str, Ref]:
    raise RuntimeError("Kernel Crash")


# --- Tests ---


@pytest.fixture
def resources():
    r = ResourceRegistry()
    r.register("config", {"version": "1.0"})
    return r


@pytest.fixture
def kernel(resources):
    func_map = {
        "node_ident": kernel_identity,
        "node_res": kernel_resource_access,
        "node_fail": kernel_fail,
    }
    return PhysicsKernel(func_map, resources)


def test_kernel_identity_execution(kernel):
    node = PhysicsFuncNode(id="node_ident", name="Identity")
    input_ref = Ref(uri="mem://input-123")
    
    inputs = {"in": input_ref}
    outputs = kernel.execute(node, inputs)
    
    assert outputs["out"] == input_ref


def test_kernel_resource_access(kernel):
    node = PhysicsFuncNode(id="node_res", name="ResourceUser")
    
    outputs = kernel.execute(node, {})
    
    assert outputs["out"].uri == "mem://config-1.0"


def test_kernel_missing_mapping(kernel):
    node = PhysicsFuncNode(id="node_unknown", name="Unknown")
    
    with pytest.raises(ValueError, match="No kernel function mapped"):
        kernel.execute(node, {})


def test_kernel_exception_propagation(kernel):
    node = PhysicsFuncNode(id="node_fail", name="FailNode")
    
    with pytest.raises(RuntimeError, match="Kernel Crash"):
        kernel.execute(node, {})
~~~~~

### 下一步建议
我们已经完成了 **Phase 3** 的核心组件：`LocalComputeDelegate` 和 `PhysicsKernel`。
下一步，我们需要进入 **第四阶段：标准库同步化 (Phase 4: StdLib Synchronization)**。这涉及到重写 `cascade-std` 中的核心 ICs（`Bleacher`, `Stainer` 等），使其适应新的 `Ref` 模型和同步签名。这将是连接 Kernel 与具体业务逻辑的关键一步。
