分析显示，`examples/dump_physical_graph.py` 中的报错是由于脚本使用了过时的 `NodeIR` 初始化参数（`id` 应为 `current_node_instance_hash`）以及未正确处理 `Builder.build` 返回的 `CompilationArtifact` 对象导致的。此外，`Fingerprint` 的初始化也需要调整为使用 `from_dict` 类方法。

我将生成一个计划来修复此示例脚本。

## [WIP] fix: 修复 dump_physical_graph.py 中的 API 调用错误

### 用户需求
修复 `examples/dump_physical_graph.py` 运行时报出的 `TypeError`，使其能够正确生成物理图谱的 DOT 输出。

### 评论
示例脚本作为开发者了解系统的第一入口，其正确性至关重要。随着 `cascade-spec` 和 `cascade-compiler` 的重构，底层 IR 的字段名和编译器返回值的结构发生了变化，脚本需要相应更新以保持同步。

### 目标
1. 修正 `NodeIR` 的初始化参数名。
2. 修正 `Fingerprint` 的初始化方式。
3. 修正对 `Builder.build` 返回值的解包逻辑，提取 `artifact.assembly.graph`。
4. 使用 `ArgumentKind` 枚举代替字符串。

### 基本原理
按照 `packages/cascade-spec/src/cascade/spec/ir/graph.py` 和 `packages/cascade-compiler/src/cascade/compiler/backend/builder.py` 中定义的最新协议更新调用代码。

### 标签
#intent/fix #flow/ready #priority/high #comp/docs #concept/parser #scope/dx #ai/instruct #task/domain/testing #task/object/examples #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修复 `examples/dump_physical_graph.py` 中的 API 调用

我们将更新导入语句，并修正任务定义、节点创建及编译器调用的逻辑。

~~~~~act
patch_file
examples/dump_physical_graph.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import GraphIR, NodeIR, TaskDef, ArgumentDef
from cascade.spec.ir.fingerprint import Fingerprint
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import GraphIR, NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.ir.fingerprint import Fingerprint
~~~~~

~~~~~act
patch_file
examples/dump_physical_graph.py
~~~~~
~~~~~python.old
    # 1. Define a dummy task definition
    # We use a static fingerprint for reproducibility
    fp = Fingerprint({"canonical_code_structure_hash": "abc12345"})
    task_def = TaskDef(
        name="gpu_task",
        args=[ArgumentDef("x", "POSITIONAL_OR_KEYWORD")],
        fingerprint=fp,
    )

    # 2. Create two nodes that both require 1 GPU
    node_1 = NodeIR(
        id="node_1",
        name="TrainingJob_A",
        task=task_def,
        inputs={"x": 10},
        constraints={"gpu": 1},
    )
    node_2 = NodeIR(
        id="node_2",
        name="TrainingJob_B",
        task=task_def,
        inputs={"x": 20},
        constraints={"gpu": 1},
    )
~~~~~
~~~~~python.new
    # 1. Define a dummy task definition
    # We use a static fingerprint for reproducibility
    fp = Fingerprint.from_dict({"canonical_code_structure_hash": "abc12345"})
    task_def = TaskDef(
        name="gpu_task",
        args=[ArgumentDef("x", ArgumentKind.POSITIONAL_OR_KEYWORD)],
        fingerprint=fp,
    )

    # 2. Create two nodes that both require 1 GPU
    node_1 = NodeIR(
        current_node_instance_hash="node_1",
        name="TrainingJob_A",
        task=task_def,
        inputs={"x": 10},
        constraints={"gpu": 1},
    )
    node_2 = NodeIR(
        current_node_instance_hash="node_2",
        name="TrainingJob_B",
        task=task_def,
        inputs={"x": 20},
        constraints={"gpu": 1},
    )
~~~~~

~~~~~act
patch_file
examples/dump_physical_graph.py
~~~~~
~~~~~python.old
    print("# Compiling to Physical Bipartite Graph...", file=sys.stderr)
    builder = Builder()
    physical_graph = builder.build(graph_ir, environment=env)

    node_count = len(physical_graph.nodes)
~~~~~
~~~~~python.new
    print("# Compiling to Physical Bipartite Graph...", file=sys.stderr)
    builder = Builder()
    artifact = builder.build(graph_ir, environment=env)
    physical_graph = artifact.assembly.graph

    node_count = len(physical_graph.nodes)
~~~~~

### 下一步建议
修复后，你可以再次运行 `python examples/dump_physical_graph.py > graph.dot`。如果本地安装了 Graphviz，可以使用 `dot -Tpng graph.dot -o graph.png` 查看生成的资源竞争拓扑图。
