我们开始实现 `CSPSolver`。这将分为两个步骤：首先是配置环境和依赖，然后是核心算法的实现。

## [WIP] feat(solver): Introduce CSPSolver foundation and dependency

### 用户需求
引入基于约束满足问题 (CSP) 的高级求解器 `CSPSolver`，以支持资源感知的任务调度。首先需要配置项目依赖，并搭建求解器的基础架构。

### 评论
`CSPSolver` 是 `Cascade` 迈向高级调度能力的第一步。通过引入 `python-constraint` 库，我们可以利用现成的 CSP 算法来处理复杂的依赖和资源约束，而无需从头编写复杂的调度算法。

### 目标
1.  在 `pyproject.toml` 的 `optional-dependencies` 中添加 `csp_solver` 组，包含 `python-constraint`。
2.  创建 `src/cascade/adapters/solvers/csp.py`，定义 `CSPSolver` 类结构和基本的初始化逻辑。
3.  创建测试文件 `tests/adapters/solvers/test_csp.py`，验证依赖是否能正确加载。

### 基本原理
我们将 `python-constraint` 作为一个可选依赖，保持核心库的轻量化。只有需要高级调度的用户才需要安装它。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #concept/scheduling #scope/core
#ai/instruct
#task/domain/scheduling #task/object/csp-solver #task/action/implementation
#task/state/begin

---

### Script

#### Acts 1: 添加项目依赖

修改 `pyproject.toml`，添加 `csp_solver` 依赖组。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
config = ["PyYAML"]

# 新增一个 'all' 组，方便一键安装所有可选依赖
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer[all]",
  "PyYAML",
]
~~~~~
~~~~~toml
config = ["PyYAML"]
csp_solver = ["python-constraint"]

# 新增一个 'all' 组，方便一键安装所有可选依赖
all = [
  "jinja2",
  "aiohttp",
  "sqlalchemy",
  "typer[all]",
  "PyYAML",
  "python-constraint",
]
~~~~~

#### Acts 2: 创建 CSPSolver 基础结构

创建 `src/cascade/adapters/solvers/csp.py`。我们先实现基本的类结构和依赖检查。

~~~~~act
write_file
src/cascade/adapters/solvers/csp.py
~~~~~
~~~~~python
from typing import Dict, List, Any, Optional
from cascade.graph.model import Graph, Node
from cascade.runtime.protocols import ExecutionPlan

try:
    import constraint
except ImportError:
    constraint = None


class CSPSolver:
    """
    A solver that uses Constraint Satisfaction Problem (CSP) techniques to produce
    a resource-aware execution plan.
    
    It ensures that:
    1. Dependencies are respected (Downstream tasks run in later stages than upstream).
    2. System resource limits are not exceeded in any single stage.
    """

    def __init__(self, system_resources: Dict[str, float]):
        """
        Args:
            system_resources: A dictionary defining the total available capacity 
                              for each resource (e.g., {"gpu": 2, "memory_gb": 32}).
        """
        if constraint is None:
            raise ImportError(
                "The 'python-constraint' library is required to use the CSPSolver. "
                "Please install it with: pip install cascade-py[csp_solver]"
            )
        self.system_resources = system_resources

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # Placeholder for the actual CSP logic
        # For now, we will raise NotImplementedError to indicate it's WIP
        raise NotImplementedError("CSP resolution logic is coming in the next step.")
~~~~~

#### Acts 3: 创建基础测试

创建 `tests/adapters/solvers/test_csp.py`，验证导入逻辑。

~~~~~act
write_file
tests/adapters/solvers/test_csp.py
~~~~~
~~~~~python
import pytest
from cascade.adapters.solvers.csp import CSPSolver

# Skip tests if python-constraint is not installed
pytest.importorskip("constraint")


def test_csp_solver_init():
    """Test that CSPSolver can be initialized with resources."""
    solver = CSPSolver(system_resources={"cpu": 4, "ram": 16})
    assert solver.system_resources == {"cpu": 4, "ram": 16}


def test_csp_solver_missing_dependency(monkeypatch):
    """Test that meaningful error is raised if dependency is missing."""
    import cascade.adapters.solvers.csp as csp_module
    
    # Simulate missing dependency by setting constraint to None
    monkeypatch.setattr(csp_module, "constraint", None)
    
    with pytest.raises(ImportError, match="python-constraint"):
        CSPSolver(system_resources={})
~~~~~

### 下一步建议
基础结构已就绪。下一步是实现 `resolve` 方法的核心逻辑：
1.  将 `Graph` 转换为 CSP 问题变量（每个 Node 分配一个 Stage 索引）。
2.  添加依赖约束（`parent_stage < child_stage`）。
3.  添加资源约束（每个 Stage 的资源总和 <= 系统资源）。
4.  求解并将结果转换为 `ExecutionPlan`。

这将是一个较大的逻辑实现，我将作为一个单独的步骤进行。
