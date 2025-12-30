You've correctly identified the `NameError`. My apologies, that's a classic import error on my part.

The traceback is crystal clear. While I defined the new `ParamNode`, `TaskNode`, and `MapNode` classes in `packages/cascade-graph/src/cascade/graph/model.py`, I completely forgot to import them into `packages/cascade-graph/src/cascade/graph/build.py` where they are being used.

I will fix this immediately by adding the necessary imports.

## [WIP] fix: Fix NameError by importing Node subclasses in GraphBuilder

### 用户需求
The previous plan failed with a `NameError` because the new `Node` subclasses (`TaskNode`, `MapNode`, `ParamNode`) were used in `GraphBuilder` without being imported.

### 评论
This is a straightforward but critical fix. Resolving this import error is necessary to make the new polymorphic `Node` architecture functional and allow the tests to proceed.

### 目标
1.  Add the required import statement to `packages/cascade-graph/src/cascade/graph/build.py`.

### 基本原理
The `GraphBuilder` needs access to the class definitions of the nodes it is responsible for creating. Adding the import statement makes these definitions available within the module's scope, resolving the `NameError`.

### 标签
#intent/fix #flow/ready #priority/critical 
#comp/graph #concept/graph-model #scope/core
#ai/instruct
#task/domain/core
#task/object/node-hierarchy
#task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: Import Node subclasses into GraphBuilder

I will add `TaskNode`, `MapNode`, and `ParamNode` to the import line from `cascade.graph.model`.

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
from typing import Dict, Any, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~
~~~~~python.new
from typing import Dict, Any, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType, TaskNode, MapNode, ParamNode
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~

### 下一步建议
With this import error corrected, the `GraphBuilder` should now be able to correctly instantiate the new `Node` subclasses.

I recommend we re-run the tests. If they pass, we can proceed with a final `pyright` check to confirm that the original `lisp.py` type error has also been resolved.
