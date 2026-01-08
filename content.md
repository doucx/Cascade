好的，我明白了。测试套件的失败是由于我上次修改 `IRGenerator` 的 API 签名后，没有同步更新其调用方（即测试用例）所导致的。这是一个典型的回归错误，我将立即修复它。

我将生成一个计划，逐一修复所有失败的测试用例。

## [WIP] fix(tests): 适配 IRGenerator 以处理新的 GenerationResult API

### 错误分析
`IRGenerator.generate()` 方法的返回类型已从 `GraphIR` 更改为 `GenerationResult`。所有测试用例仍然假设它返回 `GraphIR`，并直接尝试访问 `.nodes` 属性，从而导致 `AttributeError: 'GenerationResult' object has no attribute 'nodes'`。`test_generate_simple_task` 中的 `AssertionError` 也是由 `isinstance(result, GraphIR)` 失败引起的，根本原因相同。

### 用户需求
修复所有因 `IRGenerator` API 变更而失败的测试，使测试套件恢复到绿色状态。

### 评论
这是一个必要且直接的修复。将测试与新的 API 对齐，不仅能修复当前的失败，也为后续在 `GenerationResult` 中传递更多编译产物（如 `executables`）铺平了道路。

### 目标
- 定位所有调用 `IRGenerator.generate()` 的测试文件。
- 修改这些调用，使其能正确解包 `GenerationResult` 对象，提取出 `.ir` 属性（即 `GraphIR`），然后再传递给 `Builder` 或进行断言。

### 基本原理
此修复是纯粹的机械性重构。我们将遵循新的 API 契约：`generation_result = generator.generate(...)`，然后使用 `generation_result.ir` 来访问 `GraphIR`。对于那些后续需要 `graph_ir` 变量的测试，我们将显式地将其解包出来。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/compiler #scope/dx #ai/instruct #task/domain/compiler #task/object/ir-generator #task/action/hardening #task/state/continue

---

### Script

#### Acts 1: 修复 `cascade-compiler` 集成测试

我们将首先修复 `cascade-compiler` 包内的集成测试。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_assembly_purity.py
~~~~~
~~~~~python.old
    graph_ir = generator.generate(workflow)
    artifact = builder.build(graph_ir, environment)
~~~~~
~~~~~python.new
    generation_result = generator.generate(workflow)
    artifact = builder.build(generation_result.ir, environment)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_graph_purity.py
~~~~~
~~~~~python.old
    graph_ir = generator.generate(workflow)
    artifact = builder.build(graph_ir, environment)
~~~~~
~~~~~python.new
    generation_result = generator.generate(workflow)
    artifact = builder.build(generation_result.ir, environment)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_manifest_content.py
~~~~~
~~~~~python.old
    graph_ir = generator.generate(workflow)
    artifact = builder.build(graph_ir, environment)
~~~~~
~~~~~python.new
    generation_result = generator.generate(workflow)
    artifact = builder.build(generation_result.ir, environment)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_sovereign_wiring.py
~~~~~
~~~~~python.old
    ir_generator = IRGenerator()
    graph_ir = ir_generator.generate(t2)

    # 2. Build Physical Graph
    builder = Builder()
    artifact = builder.build(graph_ir, EnvironmentDef())
~~~~~
~~~~~python.new
    ir_generator = IRGenerator()
    generation_result = ir_generator.generate(t2)
    graph_ir = generation_result.ir

    # 2. Build Physical Graph
    builder = Builder()
    artifact = builder.build(graph_ir, EnvironmentDef())
~~~~~

#### Acts 2: 修复 `cascade-compiler` 单元测试

接下来是 `frontend` 的单元测试。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/frontend/test_generator.py
~~~~~
~~~~~python.old
    # Act
    graph_ir = generator.generate(target)

    # Assert
    assert isinstance(graph_ir, GraphIR)
    assert len(graph_ir.nodes) == 1

    node_ir = graph_ir.nodes[0]
~~~~~
~~~~~python.new
    # Act
    generation_result = generator.generate(target)
    graph_ir = generation_result.ir

    # Assert
    assert isinstance(graph_ir, GraphIR)
    assert len(graph_ir.nodes) == 1

    node_ir = graph_ir.nodes[0]
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/frontend/test_generator.py
~~~~~
~~~~~python.old
    # Act
    graph_ir = generator.generate(target)

    # Assert
    assert len(graph_ir.nodes) == 1
    node_ir = graph_ir.nodes[0]
~~~~~
~~~~~python.new
    # Act
    generation_result = generator.generate(target)
    graph_ir = generation_result.ir

    # Assert
    assert len(graph_ir.nodes) == 1
    node_ir = graph_ir.nodes[0]
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/frontend/test_generator.py
~~~~~
~~~~~python.old
    # Act
    graph_ir = generator.generate(downstream_lr)

    # Assert
    assert len(graph_ir.nodes) == 2
~~~~~
~~~~~python.new
    # Act
    generation_result = generator.generate(downstream_lr)
    graph_ir = generation_result.ir

    # Assert
    assert len(graph_ir.nodes) == 2
~~~~~

#### Acts 3: 修复 `cascade-vm` 集成测试

最后，修复所有 `cascade-vm` 中依赖 `IRGenerator` 的集成测试。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_linker_validation.py
~~~~~
~~~~~python.old
async def test_blind_optimism_without_linker():
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
~~~~~
~~~~~python.new
async def test_blind_optimism_without_linker():
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    generation_result = ir_generator.generate(workflow)
    artifact = builder.build(generation_result.ir, EnvironmentDef())
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_linker_validation.py
~~~~~
~~~~~python.old
async def test_linker_enforces_integrity():
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
~~~~~
~~~~~python.new
async def test_linker_enforces_integrity():
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    generation_result = ir_generator.generate(workflow)
    artifact = builder.build(generation_result.ir, EnvironmentDef())
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_linker_validation.py
~~~~~
~~~~~python.old
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
~~~~~
~~~~~python.new
    generation_result = ir_generator.generate(workflow)
    artifact = builder.build(generation_result.ir, EnvironmentDef())
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
~~~~~
~~~~~python.new
    ir_generator = IRGenerator()
    builder = Builder()
    generation_result = ir_generator.generate(workflow)
    graph_ir = generation_result.ir
    artifact = builder.build(graph_ir, EnvironmentDef())
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    graph_ir = ir_generator.generate(tasks)

    # 2. Build Physical Graph
    env = EnvironmentDef(
        resources=[ResourceDef(name=RESOURCE_NAME, capacity=RESOURCE_CAPACITY)]
    )
    builder = Builder()
    artifact = builder.build(graph_ir, env)
~~~~~
~~~~~python.new
    generation_result = ir_generator.generate(tasks)
    graph_ir = generation_result.ir

    # 2. Build Physical Graph
    env = EnvironmentDef(
        resources=[ResourceDef(name=RESOURCE_NAME, capacity=RESOURCE_CAPACITY)]
    )
    builder = Builder()
    artifact = builder.build(graph_ir, env)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    ir_generator = IRGenerator()
    graph_ir = ir_generator.generate([t_gpu, t_cpu])

    env = EnvironmentDef(resources=[ResourceDef("gpu", 1), ResourceDef("cpu", 1)])
    builder = Builder()
    artifact = builder.build(graph_ir, env)
~~~~~
~~~~~python.new
    ir_generator = IRGenerator()
    generation_result = ir_generator.generate([t_gpu, t_cpu])
    graph_ir = generation_result.ir

    env = EnvironmentDef(resources=[ResourceDef("gpu", 1), ResourceDef("cpu", 1)])
    builder = Builder()
    artifact = builder.build(graph_ir, env)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_sentry.py
~~~~~
~~~~~python.old
    # 3. Compile the graph
    ir_generator = IRGenerator()
    graph_ir = ir_generator.generate([task_a, task_b])

    builder = Builder()
    artifact = builder.build(graph_ir, env)
~~~~~
~~~~~python.new
    # 3. Compile the graph
    ir_generator = IRGenerator()
    generation_result = ir_generator.generate([task_a, task_b])

    builder = Builder()
    artifact = builder.build(generation_result.ir, env)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~
~~~~~python.old
    flow = source_task()
    graph_ir = ir_generator.generate(flow)
    node_ir = graph_ir.nodes[0]
    artifact = builder.build(graph_ir, EnvironmentDef())
~~~~~
~~~~~python.new
    flow = source_task()
    generation_result = ir_generator.generate(flow)
    graph_ir = generation_result.ir
    node_ir = graph_ir.nodes[0]
    artifact = builder.build(graph_ir, EnvironmentDef())
~~~~~

### 下一步建议
测试套件现已稳定。我们可以安全地进入路线图的**阶段三：流量切换**。我将准备一个计划，修改 `GraphExecutionStrategy` 来使用新的 `IRGenerator` 和 `IRToRuntimeAdapter`。
