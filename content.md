[简要回答]
好的，我们将启动 Phase 1，在 `cascade-spec` 中正式定义 `EventIR` 及其相关枚举，作为全息投影协议的法律基础。

## [WIP] feat(spec): 定义 EventIR 全息投影协议规范

### 用户需求
根据 [Cascade 3.0 实施路线图 (Phase 1)](docs/实施路线图：Cascade%203.0%20全息投影协议%20(Event%20IR).md)，需要在 `cascade-spec` 包中定义通用的遥测数据结构 `EventIR`，以及标准化的事件类型 `EventType` 和状态枚举 `EventState`，以解耦物理层与逻辑层的可观测性依赖。

### 评论
这是 Cascade 3.0 可观测性架构的基石。通过引入一个扁平的、可序列化的中间表示 (IR)，我们允许物理 VM 发射纯净的遥测数据，而无需了解 Engine 的复杂对象模型。这直接对齐了 CNCF CloudEvents 和 OpenTelemetry 的设计哲学，为未来的分布式追踪和跨语言支持打下基础。

### 目标
1.  创建 `packages/cascade-spec/src/cascade/spec/observability.py`。
2.  定义 `EventIR` TypedDict 结构，包含元数据、上下文、物理锚点和数据负载。
3.  定义 `EventType` 和 `EventState` 枚举。
4.  在 `__init__.py` 中导出新类型。
5.  添加单元测试验证规范定义的正确性。

### 基本原理
-   **结构选择**: 使用 `TypedDict` 而非 `dataclass`，以确保“零成本抽象”和天然的 JSON 序列化能力，符合物理层的高性能要求。
-   **命名规范**: 采用极简的字段名 (`v`, `t`, `ts`, `ctx`, `phy`, `data`) 以减小传输开销，同时保持语义清晰。
-   **兼容性**: 使用 `StrEnum` (Python 3.11+) 提供更好的字符串互操作性。

### 标签
#intent/architect #intent/build #flow/ready #priority/high #comp/interfaces #concept/history #scope/core #ai/instruct #task/domain/observability #task/object/event-ir #task/action/define #task/state/begin

---

### Script

#### Acts 1: 定义 EventIR 规范

创建 `observability.py` 文件，定义协议的核心数据结构。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/observability.py
~~~~~
~~~~~python
from enum import StrEnum
from typing import TypedDict, Dict, Any, Optional


class EventType(StrEnum):
    """
    Standard taxonomy for Cascade telemetry events.
    Aligned with OpenTelemetry semantic conventions where possible.
    """
    LIFECYCLE = "task.lifecycle"
    RESOURCE = "resource.usage"
    DATA = "data.flow"
    ERROR = "system.error"
    CUSTOM = "custom.event"


class EventState(StrEnum):
    """
    Standard lifecycle states for tasks and workflows.
    """
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class PhysicalAnchor(TypedDict):
    """
    Physical location metadata identifying where the event originated in the topology.
    """
    nid: str  # Node ID (The physical node hash)


class EventContext(TypedDict, total=False):
    """
    Logical context injected by the environment.
    This metadata is orthogonal to the physical topology.
    """
    rid: str  # Run ID
    pid: str  # Project ID
    uid: str  # User/Org ID


class EventIR(TypedDict):
    """
    The Intermediate Representation of an Observability Event.
    Designed to be a flat, JSON-serializable dictionary (The 'Hologram').
    
    Structure:
    - Header: Protocol metadata (v, t, ts)
    - Context (ctx): Logical environment info
    - Physics (phy): Physical topology info
    - Data (data): The actual payload
    """
    v: str            # Protocol Version: "1.0"
    t: str            # Event Type (EventType)
    ts: float         # Unix Timestamp (when it happened physically)
    
    ctx: EventContext
    phy: PhysicalAnchor
    
    data: Dict[str, Any]
~~~~~

#### Acts 2: 导出规范

将新定义的类型从 `cascade.spec` 包根目录导出，以便其他模块使用。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
from .assembly import Assembly, SymbolTable

__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Token",
    "PhysicsNode",
    "PhysicsDataNode",
    "PhysicsFuncNode",
    "BleachNode",
    "WorkerNode",
    "StainNode",
    "ObservabilityNode",
    "Channel",
    "BipartiteGraph",
    "ResourceSlot",
    "EnvironmentDef",
    "ResourceDef",
    "PortRole",
    "PortDef",
    "Assembly",
    "SymbolTable",
]
~~~~~
~~~~~python.new
from .assembly import Assembly, SymbolTable
from .observability import (
    EventIR,
    EventType,
    EventState,
    PhysicalAnchor,
    EventContext,
)

__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Token",
    "PhysicsNode",
    "PhysicsDataNode",
    "PhysicsFuncNode",
    "BleachNode",
    "WorkerNode",
    "StainNode",
    "ObservabilityNode",
    "Channel",
    "BipartiteGraph",
    "ResourceSlot",
    "EnvironmentDef",
    "ResourceDef",
    "PortRole",
    "PortDef",
    "Assembly",
    "SymbolTable",
    "EventIR",
    "EventType",
    "EventState",
    "PhysicalAnchor",
    "EventContext",
]
~~~~~

#### Acts 3: 创建测试

添加单元测试以验证 `EventIR` 的结构约束和枚举行为。

~~~~~act
write_file
packages/cascade-spec/tests/unit/test_observability.py
~~~~~
~~~~~python
import time
import pytest
from cascade.spec import (
    EventIR,
    EventType,
    EventState,
    PhysicalAnchor,
    EventContext,
)


def test_event_type_enums():
    assert EventType.LIFECYCLE == "task.lifecycle"
    assert EventType.ERROR == "system.error"
    # Verify StrEnum behavior
    assert "task.lifecycle" == EventType.LIFECYCLE


def test_event_state_enums():
    assert EventState.RUNNING == "running"
    assert EventState.FAILED == "failed"


def test_event_ir_structure():
    # Verify we can instantiate a valid EventIR structure
    now = time.time()
    
    ctx: EventContext = {"rid": "run-123", "pid": "proj-abc"}
    phy: PhysicalAnchor = {"nid": "node-hash-xyz"}
    
    event: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now,
        "ctx": ctx,
        "phy": phy,
        "data": {
            "state": EventState.RUNNING,
            "inputs": {"a": 1}
        }
    }
    
    assert event["v"] == "1.0"
    assert event["t"] == "task.lifecycle"
    assert event["ctx"]["rid"] == "run-123"
    assert event["phy"]["nid"] == "node-hash-xyz"
    assert event["data"]["state"] == "running"
~~~~~

### 下一步建议

完成“立法”阶段后，我们需要进入 **Phase 2: 翻译机制 (The Translation Layer)**。

接下来的计划应该聚焦于：
1.  在 `cascade-engine` 中，修改 `Event` 类以支持 `from_ir` 静态工厂方法。
2.  更新 `EventBus` 以支持 `publish_ir`，从而实现 Engine 对双语（对象与 IR）的支持。
