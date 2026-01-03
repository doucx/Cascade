好的，我们来创建一个可执行的示例脚本，以验证 `GraphDumper` 的可用性。

我将把这个脚本放在项目根目录下的新 `examples/` 目录中。它会构建一个简单的两任务工作流，并通过新创建的 `GraphDumper` 将其生成的物理图以 DOT 格式打印到标准输出。

## [WIP] feat(compiler): 添加示例脚本以演示 GraphDumper

### 用户需求
创建一个位于 `./examples` 目录下的脚本，该脚本使用 `GraphDumper` 来构建并可视化一个简单的物理图，从而验证 Dumper 的功能并提供一个即用型调试工具。

### 评论
这个脚本是“白盒验证”策略的关键第一步。它提供了一个快速、直观的方式来审查编译器的输出，极大地提高了调试物理层问题的效率。

### 目标
1.  创建 `examples/` 目录。
2.  在该目录中创建一个 `dump_graph.py` 脚本。
3.  脚本将定义一个简单的工作流（一个任务依赖另一个）。
4.  脚本将调用 `IRGenerator` 和 `Builder` 来生成物理图。
5.  脚本将使用 `GraphDumper` 将物理图转换为 DOT 字符串并打印到 `stdout`。

### 基本原理
通过创建一个独立的、可执行的示例，我们不仅能测试 `GraphDumper`，还能为项目贡献一个持久的、可用于未来调试的实用工具。这遵循了“吃自己的狗粮”原则，用我们自己构建的工具来改进开发流程。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/compiler #scope/dx #task/domain/compiler #task/object/graph-dumper #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 `examples` 目录

首先，我们确保 `examples` 目录存在。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p examples
~~~~~

#### Acts 2: 创建可视化脚本

现在，我们编写 `dump_graph.py` 脚本。它包含了从定义工作流到打印 DOT 字符串的完整流程。

~~~~~act
write_file
examples/dump_graph.py
~~~~~
~~~~~python
import sys
from pathlib import Path

# This is a common pattern for running scripts in a monorepo project root.
# It ensures that the 'src' directories of our packages are on the Python path.
# NOTE: This assumes you run the script from the project's root directory.
# An alternative is to do an editable install of the workspace (`uv pip install -e .`).
workspace_root = Path(__file__).parent.parent
sys.path.append(str(workspace_root / "packages/cascade-spec/src"))
sys.path.append(str(workspace_root / "packages/cascade-compiler/src"))
sys.path.append(str(workspace_root / "packages/cascade-std/src"))


from cascade.spec.task import task
from cascade.spec.environment import EnvironmentDef
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.compiler.utils import GraphDumper


# --- 1. Define a simple workflow ---
@task
def task_a(x: int):
    """A simple source task."""
    return x * 2


@task
def task_b(a_val: int, y: int):
    """A task that depends on another."""
    return a_val + y


def main():
    """
    Builds a simple physical graph and dumps its DOT representation to stdout.
    """
    print("--- Cascade Physical Graph Dumper ---", file=sys.stderr)

    # --- 2. Create the logical flow ---
    result_a = task_a(10)
    result_b = task_b(result_a, 5).with_constraints(gpu=1)

    # --- 3. Instantiate Compiler components ---
    ir_generator = IRGenerator()
    builder = Builder()
    dumper = GraphDumper()

    # --- 4. Run the compilation pipeline ---
    print("Generating IR...", file=sys.stderr)
    graph_ir = ir_generator.generate(result_b)

    # Define a simple environment for the builder
    environment = EnvironmentDef(resources=[{"name": "gpu", "capacity": 2}])

    print("Building physical graph...", file=sys.stderr)
    physical_graph = builder.build(graph_ir, environment)

    print("Dumping graph to DOT format...", file=sys.stderr)
    dot_string = dumper.to_dot(physical_graph)

    # --- 5. Print the DOT string to stdout ---
    print("\n" + dot_string)

    print("\n--- To generate an image, run: ---", file=sys.stderr)
    print(
        "python examples/dump_graph.py | dot -Tpng -o physical_graph.png",
        file=sys.stderr,
    )
    print("-----------------------------------", file=sys.stderr)


if __name__ == "__main__":
    main()
~~~~~

### 下一步建议
你现在可以从项目根目录运行以下命令来生成并查看物理图：

```bash
python examples/dump_graph.py | dot -Tpng -o physical_graph.png && xdg-open physical_graph.png
```

这将生成一个名为 `physical_graph.png` 的图像文件并打开它。

下一步，我们应该仔细检查这张图，特别是资源请求（`Req`）、授予（`Gnt`）和释放（`Rel`）的闭环连线，看看是否能发现导致我们最初问题的拓扑缺陷。
