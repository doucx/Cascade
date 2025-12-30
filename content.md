## [WIP] feat(compiler): 实现 Optimizer 逻辑

### 摘要头
## [WIP] feat(compiler): 实现 Optimizer 逻辑

### 用户需求
实现 `cascade-compiler` 包中的 `Optimizer` 类，使其通过 "Phase 2" 定义的 RED 状态测试。具体要求是实现一个能够处理 `GraphIR` 的拓扑排序算法，并正确处理循环依赖异常。

### 评论
这是编译器管线中的 "优化/调度" 阶段。我们将使用 Kahn 算法来实现拓扑排序。这与旧版引擎中的 `NativeSolver` 逻辑类似，但这次是针对纯数据结构 `GraphIR` 进行操作，完全解耦了运行时状态。根据测试用例的契约，`ExecutionPlan` 在此阶段被定义为节点 ID 的列表的列表（`List[List[str]]`）。

### 目标
1.  创建 `packages/cascade-compiler/src/cascade/compiler/optimizer.py`。
2.  实现 `Kahn's Algorithm` 以生成分阶段的执行计划。
3.  更新 `packages/cascade-compiler/src/cascade/compiler/__init__.py` 导出 `Optimizer` 和 `ExecutionPlan`。
4.  更新 `packages/cascade-compiler/tests/test_optimizer.py`，移除 `xfail` 标记，验证 GREEN 状态。

### 基本原理
我们选择在 `optimizer.py` 中重新实现拓扑排序逻辑，而不是复用 `cascade-engine` 中的代码，这符合 "焦土政策" 中彻底解耦和重写的目标。该实现是一个纯函数变换：`GraphIR -> ExecutionPlan`。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #concept/optimizer #scope/core #ai/instruct #task/domain/refactor #task/object/compiler-optimizer #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 实现 Optimizer 类

创建 `optimizer.py` 并实现拓扑排序算法。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/optimizer.py
~~~~~
~~~~~python
from typing import List, Dict, Set
from collections import deque, defaultdict

from cascade.spec.ir.models import GraphIR
from cascade.compiler.exceptions import CycleDetectedError

# ExecutionPlan is defined as a list of stages, where each stage is a list of Node IDs
ExecutionPlan = List[List[str]]


class Optimizer:
    """
    Compiler Optimizer: Transforms a GraphIR into a scheduled ExecutionPlan.
    """

    @staticmethod
    def optimize(graph: GraphIR) -> ExecutionPlan:
        """
        Performs topological sort on the GraphIR to produce an execution schedule.
        
        Args:
            graph: The Intermediate Representation of the compute graph.
            
        Returns:
            A list of stages, where each stage contains a list of Node IDs that 
            can be executed in parallel.
            
        Raises:
            CycleDetectedError: If the graph contains a dependency cycle.
        """
        # 1. Initialize data structures
        # Adjacency list: source_id -> list of target_ids
        adj: Dict[str, List[str]] = defaultdict(list)
        # In-degree: node_id -> count
        in_degree: Dict[str, int] = {node.id: 0 for node in graph.nodes}
        
        # 2. Build graph topology from IR edges
        for edge in graph.edges:
            # Check if nodes exist (sanity check, though IR should be valid)
            if edge.source_id not in in_degree or edge.target_id not in in_degree:
                continue
                
            adj[edge.source_id].append(edge.target_id)
            in_degree[edge.target_id] += 1
            
        # 3. Kahn's Algorithm
        # Initial queue: nodes with in-degree 0
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        
        plan: ExecutionPlan = []
        processed_count = 0
        total_nodes = len(graph.nodes)
        
        while queue:
            # Snapshot current queue as the current stage
            # All nodes in this stage depend only on nodes from previous stages
            current_stage_ids = list(queue)
            
            # Sort for deterministic output (crucial for testing and reproducibility)
            current_stage_ids.sort()
            
            plan.append(current_stage_ids)
            processed_count += len(current_stage_ids)
            
            # Clear queue for the next iteration (we process stage by stage)
            queue.clear()
            
            # Process neighbors
            for node_id in current_stage_ids:
                for neighbor_id in adj[node_id]:
                    in_degree[neighbor_id] -= 1
                    if in_degree[neighbor_id] == 0:
                        queue.append(neighbor_id)
                        
        # 4. Cycle Detection
        if processed_count != total_nodes:
            raise CycleDetectedError(
                f"Cycle detected in dependency graph. Processed {processed_count}/{total_nodes} nodes."
            )
            
        return plan
~~~~~

#### Acts 2: 导出 Optimizer

更新包的 `__init__.py`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/__init__.py
~~~~~
~~~~~python.old
from .frontend import Frontend
from .exceptions import CompilerError, CycleDetectedError

__all__ = ["Frontend", "CompilerError", "CycleDetectedError"]
~~~~~
~~~~~python.new
from .frontend import Frontend
from .optimizer import Optimizer, ExecutionPlan
from .exceptions import CompilerError, CycleDetectedError

__all__ = [
    "Frontend",
    "Optimizer",
    "ExecutionPlan",
    "CompilerError",
    "CycleDetectedError",
]
~~~~~

#### Acts 3: 更新测试用例 (GREEN)

移除 `xfail` 标记，并清理 import 语句，正式启用测试。

~~~~~act
patch_file
packages/cascade-compiler/tests/test_optimizer.py
~~~~~
~~~~~python.old
# NOTE: The Optimizer and its specific exception are not yet implemented.
# We expect an ImportError, which will cause the tests to fail (RED state).
try:
    from cascade.compiler.optimizer import Optimizer, ExecutionPlan
    from cascade.compiler.exceptions import CycleDetectedError
except ImportError:
    # Define a placeholder for type hinting if the import fails
    ExecutionPlan = List[List[str]]
~~~~~
~~~~~python.new
from cascade.compiler.optimizer import Optimizer, ExecutionPlan
from cascade.compiler.exceptions import CycleDetectedError
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/test_optimizer.py
~~~~~
~~~~~python.old
@pytest.mark.xfail(reason="Optimizer not implemented", raises=(ImportError, NameError))
def test_optimizer_detects_cycle():
~~~~~
~~~~~python.new
def test_optimizer_detects_cycle():
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/test_optimizer.py
~~~~~
~~~~~python.old
@pytest.mark.xfail(reason="Optimizer not implemented", raises=(ImportError, NameError))
def test_optimizer_schedules_diamond_graph():
~~~~~
~~~~~python.new
def test_optimizer_schedules_diamond_graph():
~~~~~
