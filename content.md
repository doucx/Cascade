You are absolutely right. The test failed, and the traceback clearly shows that the `result_emitter` node was not found in the compiled graph. My apologies.

The error `AssertionError: Result emitter node was not injected` on the line `assert result_emitter is not None` indicates that when the test inspected the `topology.func_nodes`, none of the `PhysicsFuncNode` objects had a `sink_id` attribute equal to `"main_output"`.

My previous implementation in `backend.py` correctly attempted to instantiate `PhysicsFuncNode` with the `sink_id` keyword argument. The test failure, despite this, points to a fundamental mismatch: the `PhysicsFuncNode` data class itself must be missing the `sink_id` field. The roadmap item "unify emitter definition in topology" implies this change was necessary, and it appears I proceeded without ensuring the underlying data structure was updated first.

Additionally, as I reviewed the test code I wrote, I noticed a latent bug: I used `ChannelKind` without importing it, which would have caused the next test run to fail with a `NameError`.

I will now correct both issues.

1.  **Update `cascade.spec.topology.PhysicsFuncNode`**: I will patch the `PhysicsFuncNode` class to include the `sink_id: Optional[str]` field. This will make the data structure consistent with the `Backend`'s logic.
2.  **Fix Test Imports**: I will patch `test_backend_topology.py` to import `ChannelKind`, resolving the latent bug.

This two-part fix will align the specification, implementation, and verification, allowing the test to pass correctly.

## [WIP] fix(compiler): Add sink_id to spec and fix test imports

### 用户需求
The previously written test failed because the `result_emitter` node could not be found, indicating a problem with the `sink_id` property. The test code also had a missing import. Both issues need to be fixed.

### 错误分析
The core error is that `PhysicsFuncNode` was being instantiated with a `sink_id` that it didn't have as a defined field, causing the value to be discarded and the test assertion to fail. A secondary error was a missing `ChannelKind` import in the test file.

### 评论
This is a classic TDD cycle: the test revealed a flaw not just in the implementation but in the underlying data specification. By fixing the `spec` and the test simultaneously, we ensure the compiler's components have a solid, consistent contract to work against.

### 目标
1.  Add the `sink_id: Optional[str]` field to the `PhysicsFuncNode` dataclass in `cascade.spec.topology.py`.
2.  Add the `ChannelKind` import to `test_backend_topology.py`.
3.  Ensure the previously written test now passes, confirming the lifecycle injection logic is correct.

### 基本原理
I will apply two precise `patch_file` operations. The first will add the missing field to the `PhysicsFuncNode` dataclass. The second will add the missing import to the top of the test file. These targeted changes will resolve the `AssertionError` and the latent `NameError`.

### 标签
#intent/fix #flow/ready #priority/critical
#comp/compiler #comp/spec #comp/tests
#scope/core
#ai/instruct
#task/domain/compiler #task/object/backend #task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: Add `sink_id` field to `PhysicsFuncNode`

First, I will correct the data class definition in `topology.py`.

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/topology.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """

    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """

    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)
~~~~~

#### Acts 2: Fix missing import in `test_backend_topology.py`

Next, I will add the `ChannelKind` import to the test file to prevent the subsequent `NameError`.

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_topology.py
~~~~~
~~~~~python.old
import pytest
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, TaskDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.topology import BipartiteGraph, ChannelDef

from cascade.compiler.backend import Backend
~~~~~
~~~~~python.new
import pytest
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, TaskDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.topology import BipartiteGraph, ChannelDef, ChannelKind

from cascade.compiler.backend import Backend
~~~~~
