好的，我理解了。这个测试本身就是一种审计工具，用于强制执行架构原则，并且它应该位于测试目录中。

我将创建一个新的测试文件，它会构建一个具有代表性的计算图，然后尝试使用 `pickle` 对其进行序列化。如果图中存在任何不可序列化的 Python 对象（如函数闭包），测试将会失败，从而为我们提供一个强大的架构守护。

## [WIP] test(compiler): 添加图纯度测试以确保可序列化性

### 用户需求
根据路线图“任务 2.1”，创建一个工具测试，用于审计和验证由 `Builder` 生成的 `BipartiteGraph` 是纯粹的、可序列化的数据结构。

### 评论
这是一个至关重要的健全性检查。通过在测试套件中强制执行图的可序列化性，我们可以从根本上杜绝“环境走私”（例如通过 `functools.partial` 注入运行时对象）等反模式。这确保了我们编译出的图是可移植、可缓存的，为未来的 Rust VM 集成奠定了坚实的基础。

### 目标
1.  在 `packages/cascade-compiler/tests/integration/` 目录下创建一个新的测试文件 `test_graph_purity.py`。
2.  在该文件中，定义一个测试，该测试构建一个包含典型特征（任务依赖、常量参数）的 `BipartiteGraph`。
3.  断言该图对象可以被 `pickle` 模块成功序列化，没有任何错误。

### 基本原理
`pickle` 是 Python 的标准序列化库，它无法处理许多复杂的运行时对象，如闭包、套接字或线程锁。因此，`pickle.dumps()` 操作能否成功，是检验一个对象是否为“纯数据”的有效试金石。将此检查集成到我们的 CI 流程中，可以确保图的纯粹性原则不会被未来的代码修改无意中破坏。

### 标签
#intent/tooling #flow/ready #priority/high #comp/compiler #comp/tests #scope/dx #ai/instruct #task/domain/vm #task/object/graph-purity #task/action/testing #task/state/continue

---

### Script

#### Acts 1: 创建图纯度审计测试

我们将创建 `test_graph_purity.py` 文件。此测试将作为守护，确保所有由编译器生成的图都是可序列化的纯数据结构。

~~~~~act
write_file
packages/cascade-compiler/tests/integration/test_graph_purity.py
~~~~~
~~~~~python
import pickle
import pytest

from cascade.spec.task import task
from cascade.spec.environment import EnvironmentDef
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder


@task
def add(a: int, b: int) -> int:
    return a + b


@task
def square(n: int) -> int:
    return n * n


def test_graph_is_serializable_and_pure():
    """
    This test acts as an architectural guardrail. It ensures that the BipartiteGraph
    produced by the compiler is a pure, serializable data structure, free from
    any runtime objects like closures or un-pickleable state.
    """
    # 1. Define a representative workflow
    workflow = square(add(1, 2))

    # 2. Compile the workflow into a physical graph
    generator = IRGenerator()
    builder = Builder()
    environment = EnvironmentDef(resources=[])

    graph_ir = generator.generate(workflow)
    physical_graph = builder.build(graph_ir, environment)

    # 3. The Purity Test: Attempt to serialize the graph
    try:
        serialized_graph = pickle.dumps(physical_graph)
        # Optional: check that it can be deserialized correctly
        deserialized_graph = pickle.loads(serialized_graph)
    except Exception as e:
        pytest.fail(
            "Graph purity test failed. The BipartiteGraph is not serializable. "
            f"This likely means a runtime object (like a function closure) has been "
            f"leaked into the graph structure. Error: {e}"
        )

    # 4. Verify basic integrity after deserialization
    assert len(physical_graph.nodes) == len(deserialized_graph.nodes)
    assert len(physical_graph.channels) == len(deserialized_graph.channels)
    assert "const.t_1.0" in deserialized_graph.nodes
    assert deserialized_graph.nodes["const.t_1.0"].initial_payload == 1
~~~~~

### 下一步建议

我们已经成功建立了一个架构守护测试来保证图的纯粹性。

根据路线图，下一步是**任务 2.2: 统一函数签名 (Signature Standardization)**。我们将审计 `cascade-std` 和测试用例中的所有 Worker 函数，确保它们的签名严格统一为 `async def (inputs, node, resources) -> dict`。这将为 Rust FFI 桥接提供一个稳定、单一的适配目标。
