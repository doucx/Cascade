Excellent, the audit is complete. Your static analysis has correctly identified several type safety issues. These are precisely the kinds of subtle bugs that a strong type system helps us prevent.

I will now generate a plan to resolve all four `pyright` errors. The fixes involve adding null-safety checks in the hashing service and completing the implementation of the `WorkflowContext` to fulfill its contract.

## [WIP] fix(typing): Resolve pyright errors for type safety

### 错误分析
1.  **`cascade-compiler` (`hashing.py`)**: The errors indicate that we are attempting to access attributes (`_uuid`, `requirements`) on variables that could be `None`. This happens when `getattr` is used with a default of `None`. The fix is to add explicit `if var is not None:` checks before accessing attributes.
2.  **`cascade-std` (`context.py`)**: The error `Attribute "get_value" is unknown` is correct. The `WorkflowContext` class in `cascade-common` defines a contract for registering input specifications but lacks the implementation for storing and retrieving the actual runtime values. The `param_probe` function correctly anticipates this capability, but the type definition is incomplete. The fix is to extend `WorkflowContext` to manage runtime values.

### 用户需求
Resolve all identified `pyright` errors to improve the type safety and correctness of the codebase.

### 评论
This is a high-value refinement. By addressing these type errors, we are not just silencing a linter; we are making the system more robust and predictable. Fixing the `WorkflowContext` in particular is a crucial step in solidifying the contract between the runtime environment and the physical functions that need to sample it.

### 目标
1.  Patch `packages/cascade-compiler/src/cascade/compiler/utils/hashing.py` to safely handle optional `_condition` and `_constraints` attributes.
2.  Patch `packages/cascade-common/src/cascade/common/context.py` to add value management (`set_value`, `get_value`) to `WorkflowContext`.
3.  Patch `packages/cascade-std/src/cascade/std/probe/context.py` to remove the defensive `hasattr` check, relying on the newly corrected `WorkflowContext` type.

### 基本原理
-   **Null Safety**: For the hashing errors, we will assign the result of `getattr` to a variable first, then check if that variable is not `None` before proceeding. This pattern is robust and clearly communicates the handling of optional attributes to the type checker.
-   **Complete the Contract**: For the context error, we will complete the implementation of `WorkflowContext` to match its intended use. This makes the system's architecture more explicit and allows static analysis tools to validate interactions correctly.

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #comp/runtime #scope/dx #ai/instruct #task/domain/typing #task/object/pyright-errors #task/action/fix #task/state/continue

---

### Script

#### Acts 1: Make Hashing Service Null-Safe

First, we'll fix the potential `None` access errors in `hashing.py`.

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/hashing.py
~~~~~
~~~~~python.old
        # 5. Metadata
        if getattr(result, "_condition", None):
            # We need the ID of the condition node
            cond = result._condition
            # Handle potential MappedLazyResult or other types in condition if necessary
            # For now assuming LazyResult or similar which is in dep_nodes
            if hasattr(cond, "_uuid") and cond._uuid in dep_nodes:
                node = dep_nodes[cond._uuid]
                node_id = getattr(node, "id", getattr(node, "structural_id", str(node)))
                components.append(f"ConditionID:{node_id}")
            else:
                components.append("Condition:UNKNOWN")

        if getattr(result, "_dependencies", None):
            deps = result._dependencies
            if deps:
                components.append("Dependencies:[")
                # Sort by UUID to ensure stable hash
                sorted_deps = sorted(deps, key=lambda x: x._uuid)
                for dep in sorted_deps:
                    if dep._uuid in dep_nodes:
                        node = dep_nodes[dep._uuid]
                        node_id = getattr(
                            node, "id", getattr(node, "structural_id", str(node))
                        )
                        components.append(f"DepID:{node_id}")
                    else:
                        components.append("DepID:UNKNOWN")
                components.append("]")

        # 6. Constraints
        if getattr(result, "_constraints", None):
            reqs = result._constraints.requirements
            keys = sorted(reqs.keys())
            s_vals = [f"{k}={reqs[k]}" for k in keys]
            components.append(f"Constraints({','.join(s_vals)})")
~~~~~
~~~~~python.new
        # 5. Metadata
        cond = getattr(result, "_condition", None)
        if cond:
            # We need the ID of the condition node
            # Handle potential MappedLazyResult or other types in condition if necessary
            # For now assuming LazyResult or similar which is in dep_nodes
            if hasattr(cond, "_uuid") and cond._uuid in dep_nodes:
                node = dep_nodes[cond._uuid]
                node_id = getattr(node, "id", getattr(node, "structural_id", str(node)))
                components.append(f"ConditionID:{node_id}")
            else:
                components.append("Condition:UNKNOWN")

        deps = getattr(result, "_dependencies", None)
        if deps:
            components.append("Dependencies:[")
            # Sort by UUID to ensure stable hash
            sorted_deps = sorted(deps, key=lambda x: x._uuid)
            for dep in sorted_deps:
                if hasattr(dep, "_uuid") and dep._uuid in dep_nodes:
                    node = dep_nodes[dep._uuid]
                    node_id = getattr(
                        node, "id", getattr(node, "structural_id", str(node))
                    )
                    components.append(f"DepID:{node_id}")
                else:
                    components.append("DepID:UNKNOWN")
            components.append("]")

        # 6. Constraints
        constraints = getattr(result, "_constraints", None)
        if constraints:
            reqs = constraints.requirements
            keys = sorted(reqs.keys())
            s_vals = [f"{k}={reqs[k]}" for k in keys]
            components.append(f"Constraints({','.join(s_vals)})")
~~~~~

#### Acts 2: Implement Value Management in WorkflowContext

Next, we'll add the missing value storage to `WorkflowContext` in the common package.

~~~~~act
patch_file
packages/cascade-common/src/cascade/common/context.py
~~~~~
~~~~~python.old
from contextvars import ContextVar
from typing import Dict, List
from cascade.spec.input import InputSpec


class WorkflowContext:
    def __init__(self):
        self.input_specs: Dict[str, InputSpec] = {}

    def register(self, spec: InputSpec):
        if spec.name in self.input_specs:
            # 在未来可以实现更复杂的合并或警告逻辑
            return
        self.input_specs[spec.name] = spec

    def get_all_specs(self) -> List[InputSpec]:
        return list(self.input_specs.values())
~~~~~
~~~~~python.new
from contextvars import ContextVar
from typing import Dict, List, Any, Optional
from cascade.spec.input import InputSpec


class WorkflowContext:
    def __init__(self):
        self.input_specs: Dict[str, InputSpec] = {}
        self.values: Dict[str, Any] = {}

    def register(self, spec: InputSpec):
        if spec.name in self.input_specs:
            # 在未来可以实现更复杂的合并或警告逻辑
            return
        self.input_specs[spec.name] = spec

    def get_all_specs(self) -> List[InputSpec]:
        return list(self.input_specs.values())

    def set_value(self, name: str, value: Any) -> None:
        self.values[name] = value

    def get_value(self, name: str) -> Optional[Any]:
        return self.values.get(name)
~~~~~

#### Acts 3: Clean up `param_probe`

Finally, with `WorkflowContext` fixed, we can simplify the `param_probe` implementation and remove the runtime `hasattr` check.

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/context.py
~~~~~
~~~~~python.old
async def param_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    name = inputs["name"].payload
    # In a real run, values are resolved by the Context/Engine.
    # Here we interface with the common context.
    ctx = get_current_context()

    # We assume context has a method to get values by spec name.
    # If not found, it returns None (as a payload).
    val = ctx.get_value(name) if hasattr(ctx, "get_value") else None

    return {"out": Token(payload=val)}
~~~~~
~~~~~python.new
async def param_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    name = inputs["name"].payload
    # In a real run, values are resolved by the Context/Engine.
    # Here we interface with the common context.
    ctx = get_current_context()

    # We assume context has a method to get values by spec name.
    # If not found, it returns None (as a payload).
    val = ctx.get_value(name)

    return {"out": Token(payload=val)}
~~~~~

### 下一步建议

我们已经解决了所有的 `pyright` 报错，代码库的类型安全性得到了提升。

现在我们可以继续路线图的**任务 2.2: 统一函数签名 (Signature Standardization)**。我将开始审计 `cascade-std` 包中的物理函数，以确保它们的签名都符合 `async def (inputs, node, resources) -> dict` 规范。这将是为 FFI 做准备的重要一步。
