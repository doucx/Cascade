Excellent catch. You've uncovered a classic Python `dataclass` inheritance issue. My apologies for generating code that led to this error.

Your analysis is perfect. The test suite failed during collection because of a fundamental rule in Python's function signatures, which `dataclasses` adhere to.

I will now generate a plan to fix this precise issue.

### 错误分析

The error `TypeError: non-default argument 'target_node_id' follows default argument 'run_id'` occurs because of the way `dataclass` constructs the `__init__` method for subclasses.

1.  **Parent Class (`Event`)**: The base `Event` class in `cascade.runtime.events` defines a field `run_id: Optional[str] = None`. This is an argument with a default value.
2.  **Child Class (`PlanAnalysisStarted`)**: Our new `PlanAnalysisStarted` class inherits from `Event` and adds a new field, `target_node_id: str`. This is a required argument *without* a default value.
3.  **The Conflict**: The `dataclass` decorator tries to generate an `__init__` method where the parent's arguments come first, followed by the child's. This results in an invalid signature equivalent to `__init__(self, ..., run_id=None, target_node_id)`. Python does not allow a required argument to follow an argument with a default value.

The same issue affects `PlanNodeInspected` and `PlanAnalysisFinished` as they also introduce new, required fields.

### 解决方案

The most elegant and non-intrusive solution is to use **keyword-only arguments**. By marking the new fields in our `ToolEvent` subclasses as keyword-only, we can create a valid `__init__` signature. The `dataclass` will generate a signature like `__init__(self, ..., run_id=None, *, target_node_id, ...)` which is perfectly valid Python. This fixes the issue locally without requiring any changes to the core `runtime` `Event` class.

## [WIP] fix(tools): Correct dataclass inheritance for tool events

### 错误分析
The initial implementation of `ToolEvent` subclasses (`PlanAnalysisStarted`, etc.) introduced required fields without default values. When inheriting from the base `Event` class, which has fields with default values (e.g., `run_id=None`), this created an invalid `__init__` method signature where a non-default argument followed a default argument, leading to a `TypeError` during class creation.

### 用户需求
Fix the `TypeError` that occurs during `pytest` collection, caused by the incorrect `dataclass` inheritance pattern in `src/cascade/tools/events.py`.

### 评论
This fix applies a more advanced feature of Python's `dataclasses` to resolve an inheritance conflict cleanly. Using keyword-only arguments allows us to enforce required fields in subclasses without modifying the parent class or violating Python's method signature rules. This maintains strong type safety and clean architectural separation.

### 目标
1.  Modify `src/cascade/tools/events.py`.
2.  For each new event class, mark the newly added required fields as keyword-only to resolve the `TypeError`.
3.  Ensure all tests can be collected and run successfully.

### 基本原理
We will introduce `from dataclasses import field` and add `_: field(kw_only=True)` to each `ToolEvent` subclass that defines new, required fields. This special field acts as a separator, instructing the `@dataclass` decorator that all subsequent fields must be specified by keyword when creating an instance. This changes the generated `__init__` signature to a valid form, resolving the error while keeping the new fields semantically required.

### 标签
#intent/fix #flow/ready #priority/critical
#comp/tools #scope/core #scope/dx
#ai/refine
#task/domain/testing #task/object/dry-run-tool #task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: Fix the dataclass definitions

We will patch the `events.py` file to introduce keyword-only fields.

~~~~~act
patch_file
src/cascade/tools/events.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Any, Dict
from ..runtime.events import Event


@dataclass(frozen=True)
class ToolEvent(Event):
    """Base class for all events emitted by developer tools."""
    pass


@dataclass(frozen=True)
class PlanAnalysisStarted(ToolEvent):
    """Fired when dry_run starts analyzing a target."""
    target_node_id: str


@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    """Fired for each node in the resolved execution plan."""
    index: int
    total_nodes: int
    node_id: str
    node_name: str
    literal_inputs: Dict[str, Any]


@dataclass(frozen=True)
class PlanAnalysisFinished(ToolEvent):
    """Fired when dry_run analysis is complete."""
    total_steps: int
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Any, Dict
from ..runtime.events import Event


@dataclass(frozen=True)
class ToolEvent(Event):
    """Base class for all events emitted by developer tools."""
    pass


@dataclass(frozen=True)
class PlanAnalysisStarted(ToolEvent):
    """Fired when dry_run starts analyzing a target."""
    _: field(kw_only=True)
    target_node_id: str


@dataclass(frozen=True)
class PlanNodeInspected(ToolEvent):
    """Fired for each node in the resolved execution plan."""
    _: field(kw_only=True)
    index: int
    total_nodes: int
    node_id: str
    node_name: str
    literal_inputs: Dict[str, Any]


@dataclass(frozen=True)
class PlanAnalysisFinished(ToolEvent):
    """Fired when dry_run analysis is complete."""
    _: field(kw_only=True)
    total_steps: int
~~~~~

#### Acts 2: Update the event instantiation in preview.py

Since the fields are now keyword-only, we must use keywords when creating the event instances in `_analyze_plan`.

~~~~~act
patch_file
src/cascade/tools/preview.py
~~~~~
~~~~~python
    bus.publish(PlanAnalysisStarted(run_id=target._uuid, target_node_id=target._uuid))

    for i, node in enumerate(plan, 1):
        bus.publish(
            PlanNodeInspected(
                run_id=target._uuid,
                index=i,
                total_nodes=total_steps,
                node_id=node.id,
                node_name=node.name,
                literal_inputs=node.literal_inputs
            )
        )

    bus.publish(PlanAnalysisFinished(run_id=target._uuid, total_steps=total_steps))
~~~~~
~~~~~python
    bus.publish(PlanAnalysisStarted(run_id=target._uuid, target_node_id=target._uuid))

    for i, node in enumerate(plan, 1):
        bus.publish(
            PlanNodeInspected(
                run_id=target._uuid,
                index=i,
                total_nodes=total_steps,
                node_id=node.id,
                node_name=node.name,
                literal_inputs=node.literal_inputs,
            )
        )

    bus.publish(PlanAnalysisFinished(run_id=target._uuid, total_steps=total_steps))
~~~~~

### 下一步建议
The changes have been applied. Now, please run the tests again. They should now collect successfully, allowing us to verify the correctness of our event-driven refactoring.
