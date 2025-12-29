## [WIP] refactor: rename 'id' to 'structural_id' or 'constraint_id' and enforce deterministic hashing

### 错误分析
1.  **非确定性 ID**: 测试失败中的 `op-t-...` 格式 ID 证明了编译器在某种情况下使用了内存地址（`id()`）生成 Op ID，这违反了架构的确定性原则。虽然当前 XML 显示的代码似乎正确，但必须通过重写来消除任何潜在的非确定性逻辑。
2.  **命名公理违规**: 字段名 `id` 过于通用且遮蔽了 Python 内置函数，容易导致混淆。必须将其重命名为更具体的名称，如 `structural_id`（用于 Op）和 `constraint_id`（用于 GlobalConstraint）。
3.  **Schema 违规**: `IdentityService` 生成的指纹键缺少一段，必须修正为 4 段式。

### 用户需求
*   **绝对**禁止使用 `id` 作为字段名或变量名（除非指代 Python 内置函数）。
*   **必须**使用长哈希（SHA256 Hex）作为标识符。
*   修复非确定性 ID 生成问题。
*   严格管理符号。

### 目标
1.  重构 `Op` 类，将 `id` 重命名为 `structural_id`。
2.  重构 `GlobalConstraint` 类，将 `id` 重命名为 `constraint_id`。
3.  重写 `Compiler` (builder.py)，确保生成的 `structural_id` 严格基于 `IdentityService` 的 SHA256 计算，绝不回退到对象 ID。
4.  修正 `IdentityService` 的指纹键名。
5.  更新所有相关引用的代码。

### 标签
#intent/refine #flow/ready #priority/critical #comp/compiler #comp/runtime #scope/core #task/domain/compiler #task/object/identity #task/action/rename

---

### Script

#### Acts 1: 重构 GlobalConstraint (id -> constraint_id)

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/constraint.py
~~~~~
~~~~~old
@dataclass
class GlobalConstraint:
    id: str
    scope: str  # e.g., "global", "project:quipu", "task:openai_request"
    type: str  # "concurrency", "rate_limit", "pause"
~~~~~
~~~~~new
@dataclass
class GlobalConstraint:
    constraint_id: str
    scope: str  # e.g., "global", "project:quipu", "task:openai_request"
    type: str  # "concurrency", "rate_limit", "pause"
~~~~~

#### Acts 2: 重构 Op (id -> structural_id)

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/ir/ops.py
~~~~~
~~~~~old
@dataclass(kw_only=True)
class Op:
    """
    Base class for Level 1 IR Operations.
    Ops are the executable instructions for the Engine.
    They must be strict, fully resolved, and immutable.
    """
    # The structural hash/fingerprint of this operation.
    # Serves as the primary key for caching and identification.
    id: str

    # Data dependencies: Map[ArgName, UpstreamOpID]
~~~~~
~~~~~new
@dataclass(kw_only=True)
class Op:
    """
    Base class for Level 1 IR Operations.
    Ops are the executable instructions for the Engine.
    They must be strict, fully resolved, and immutable.
    """
    # The structural hash/fingerprint of this operation.
    # Serves as the primary key for caching and identification.
    structural_id: str

    # Data dependencies: Map[ArgName, UpstreamOpID]
~~~~~

#### Acts 3: 修正 IdentityService 并重命名 id 变量

~~~~~act
write_file
packages/cascade-foundation/src/cascade/foundation/identity/service.py
~~~~~
~~~~~python
import hashlib
import json
from typing import Any
from cascade.foundation.definitions.base import Definition
from cascade.foundation.definitions.model import TaskDef
from cascade.foundation.identity.fingerprint import Fingerprint

class IdentityService:
    def compute_fingerprint(self, definition: Definition) -> Fingerprint:
        if isinstance(definition, TaskDef):
            return self._compute_task_fingerprint(definition)
        raise NotImplementedError(f"Cannot fingerprint {type(definition)}")

    def _compute_task_fingerprint(self, task_def: TaskDef) -> Fingerprint:
        # 1. Code Identity (Simplistic: module + qualname)
        # In a real impl, this would hash the bytecode or source AST.
        code_id = f"{task_def.func.__module__}:{task_def.func.__qualname__}"
        code_hash = hashlib.sha256(code_id.encode("utf-8")).hexdigest()
        
        # 2. Config Identity (Name, Policies)
        # We assume policies are JSON-serializable dicts or None
        config_data = {
            "name": task_def.name,
            "retry": task_def.retry_policy,
            "cache": task_def.cache_policy
        }
        config_str = json.dumps(config_data, sort_keys=True)
        config_hash = hashlib.sha256(config_str.encode("utf-8")).hexdigest()
        
        # 3. Structure Identity (Bindings)
        # This is computed by the Compiler.
        
        fp = Fingerprint()
        fp["baseline_code_signature_hash"] = code_hash
        # FIX: Conforming to 4-segment naming axiom
        fp["baseline_task_config_hash"] = config_hash
        return fp

    @staticmethod
    def compute_op_id(fingerprint: Fingerprint, input_hash: str) -> str:
        """
        Combines the Definition's static fingerprint with the resolved inputs' hash
        to form the final Execution Op ID.
        """
        # Mix code, config, and inputs
        seed = fingerprint["baseline_code_signature_hash"] + \
               fingerprint["baseline_task_config_hash"] + \
               input_hash
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()
~~~~~

#### Acts 4: 重写 Compiler (Builder) 以使用 structural_id 并强制确定性

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/builder.py
~~~~~
~~~~~python
from typing import Dict, Any, List, Optional
import hashlib
import json

from cascade.foundation.definitions.base import Definition
from cascade.foundation.definitions.model import TaskDef, ServiceDef
from cascade.foundation.ir.ops import Op, ComputeOp, ConstantOp
from cascade.foundation.identity.service import IdentityService

class ExecutionGraph:
    def __init__(self):
        self.ops: Dict[str, Op] = {}
        self.root_op_id: Optional[str] = None

    def add_op(self, op: Op):
        self.ops[op.structural_id] = op


class Compiler:
    def __init__(self):
        self.graph = ExecutionGraph()
        self.identity_service = IdentityService()
        # Memoization: Definition Object ID -> Op Structural ID
        # We use id() here ONLY for object identity within a single compile pass
        # (to handle DAG diamonds), but the VALUES stored are deterministic hashes.
        self._memo: Dict[int, str] = {}

    def compile(self, target_def: Definition) -> ExecutionGraph:
        """
        Main entry point. Compiles a Definition into an ExecutionGraph.
        """
        root_id = self._lower(target_def)
        self.graph.root_op_id = root_id
        return self.graph

    def _lower(self, definition: Definition) -> str:
        """
        Recursively lowers a Definition into an Op, returning the Op structural_id.
        """
        obj_id = id(definition)
        
        if obj_id in self._memo:
            return self._memo[obj_id]

        op_structural_id = None

        if isinstance(definition, TaskDef):
            op_structural_id = self._lower_task(definition)
        # elif isinstance(definition, ServiceDef):
        #     op_structural_id = self._lower_service(definition)
        else:
            raise NotImplementedError(f"Cannot compile definition type: {type(definition)}")

        self._memo[obj_id] = op_structural_id
        return op_structural_id

    def _lower_task(self, task_def: TaskDef) -> str:
        # 1. Resolve Inputs and calculate Input Hash
        inputs = {}
        input_hash_parts = []
        
        # Sort keys for deterministic hashing
        for arg_name in sorted(task_def.bindings.keys()):
            arg_val = task_def.bindings[arg_name]
            
            if isinstance(arg_val, Definition):
                # Recursively lower dependency
                upstream_op_id = self._lower(arg_val)
                inputs[arg_name] = upstream_op_id
                input_hash_parts.append(f"{arg_name}:{upstream_op_id}")
            else:
                # Literal -> ConstantOp
                # Calculate stable hash for literal
                lit_repr = repr(arg_val)
                lit_hash = hashlib.sha256(lit_repr.encode("utf-8")).hexdigest()
                # Use a specific prefix to distinguish constant ops
                const_id = f"const-{lit_hash}"
                
                if const_id not in self.graph.ops:
                    const_op = ConstantOp(structural_id=const_id, value=arg_val)
                    self.graph.add_op(const_op)
                
                inputs[arg_name] = const_id
                input_hash_parts.append(f"{arg_name}:{const_id}")

        input_hash = hashlib.sha256("|".join(input_hash_parts).encode("utf-8")).hexdigest()

        # 2. Calculate Static Fingerprint
        static_fp = self.identity_service.compute_fingerprint(task_def)
        task_def.fingerprint = static_fp # Store it back for observability

        # 3. Generate Final Op ID
        op_structural_id = IdentityService.compute_op_id(static_fp, input_hash)
        
        op = ComputeOp(
            structural_id=op_structural_id,
            inputs=inputs,
            callable_ref=f"{task_def.func.__module__}.{task_def.func.__qualname__}",
            config={
                "retry": task_def.retry_policy,
                "cache": task_def.cache_policy
            }
        )
        self.graph.add_op(op)
        return op_structural_id
~~~~~

#### Acts 5: 更新 CLI Controller 使用 constraint_id

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~old
        # Create a deterministic ID for idempotency (Last-Write-Wins)
        constraint_id = f"pause-{scope}"
        expires_at = time.time() + ttl if ttl else None

        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at,
~~~~~
~~~~~new
        # Create a deterministic ID for idempotency (Last-Write-Wins)
        constraint_id = f"pause-{scope}"
        expires_at = time.time() + ttl if ttl else None

        constraint = GlobalConstraint(
            constraint_id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at,
~~~~~
~~~~~old
        if concurrency is not None:
            constraint_id = f"concurrency-{scope}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="concurrency",
                params={"limit": concurrency},
                expires_at=expires_at,
            )
~~~~~
~~~~~new
        if concurrency is not None:
            constraint_id = f"concurrency-{scope}"
            constraint = GlobalConstraint(
                constraint_id=constraint_id,
                scope=scope,
                type="concurrency",
                params={"limit": concurrency},
                expires_at=expires_at,
            )
~~~~~
~~~~~old
        if rate is not None:
            constraint_id = f"ratelimit-{scope}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="rate_limit",
                params={"rate": rate},
                expires_at=expires_at,
            )
~~~~~
~~~~~new
        if rate is not None:
            constraint_id = f"ratelimit-{scope}"
            constraint = GlobalConstraint(
                constraint_id=constraint_id,
                scope=scope,
                type="rate_limit",
                params={"rate": rate},
                expires_at=expires_at,
            )
~~~~~

#### Acts 6: 更新 CLI Observer 使用 constraint_id

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~old
                # Filter out any malformed or non-constraint messages
                if "scope" in payload and "type" in payload:
                    constraints.append(GlobalConstraint(**payload))
            except TypeError:
                pass  # Ignore malformed payloads
~~~~~
~~~~~new
                # Filter out any malformed or non-constraint messages
                if "scope" in payload and "type" in payload:
                    # Rename 'id' to 'constraint_id' if legacy payload
                    if "id" in payload and "constraint_id" not in payload:
                        payload["constraint_id"] = payload.pop("id")
                    constraints.append(GlobalConstraint(**payload))
            except TypeError:
                pass  # Ignore malformed payloads
~~~~~
~~~~~old
        for row in rows:
            try:
                constraints.append(
                    GlobalConstraint(
                        id=row["id"],
                        scope=row["scope"],
                        type=row["type"],
                        params=json.loads(row["params"]),
                        expires_at=row.get("expires_at"),
                    )
                )
~~~~~
~~~~~new
        for row in rows:
            try:
                constraints.append(
                    GlobalConstraint(
                        constraint_id=row["id"],
                        scope=row["scope"],
                        type=row["type"],
                        params=json.loads(row["params"]),
                        expires_at=row.get("expires_at"),
                    )
                )
~~~~~

#### Acts 7: 更新 Connector 数据库 Schema (id -> constraint_id)

这里我们需要更新表结构。简单起见，我们直接更新创建语句和插入逻辑。

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~old
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS constraints (
                    id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    type TEXT NOT NULL,
                    params TEXT NOT NULL,
                    expires_at REAL,
                    updated_at REAL NOT NULL
                )
                """
            )
~~~~~
~~~~~new
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS constraints (
                    constraint_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    type TEXT NOT NULL,
                    params TEXT NOT NULL,
                    expires_at REAL,
                    updated_at REAL NOT NULL
                )
                """
            )
~~~~~
~~~~~old
                else:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO constraints (id, scope, type, params, expires_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            payload["id"],
                            payload["scope"],
                            payload["type"],
                            json.dumps(payload["params"]),
                            payload.get("expires_at"),
                            time.time(),
                        ),
                    )
                conn.commit()
~~~~~
~~~~~new
                else:
                    # Handle legacy payload key if necessary
                    c_id = payload.get("constraint_id", payload.get("id"))
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO constraints (constraint_id, scope, type, params, expires_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c_id,
                            payload["scope"],
                            payload["type"],
                            json.dumps(payload["params"]),
                            payload.get("expires_at"),
                            time.time(),
                        ),
                    )
                conn.commit()
~~~~~
~~~~~old
            if not last or last["updated_at"] < current["updated_at"]:
                payload = {
                    "id": current["id"],
                    "scope": current["scope"],
                    "type": current["type"],
                    "params": json.loads(current["params"]),
                    "expires_at": current["expires_at"],
                }
                await callback(self._scope_to_topic(current["scope"]), payload)
~~~~~
~~~~~new
            if not last or last["updated_at"] < current["updated_at"]:
                payload = {
                    "constraint_id": current["constraint_id"],
                    "scope": current["scope"],
                    "type": current["type"],
                    "params": json.loads(current["params"]),
                    "expires_at": current["expires_at"],
                }
                await callback(self._scope_to_topic(current["scope"]), payload)
~~~~~
~~~~~old
        rows = await asyncio.to_thread(_blocking_fetch_all)
        current_constraints: Dict[str, Dict] = {dict(r)["id"]: dict(r) for r in rows}

        for cid, current in current_constraints.items():
~~~~~
~~~~~new
        rows = await asyncio.to_thread(_blocking_fetch_all)
        current_constraints: Dict[str, Dict] = {dict(r)["constraint_id"]: dict(r) for r in rows}

        for cid, current in current_constraints.items():
~~~~~

#### Acts 8: 更新 Engine 的 ConstraintManager

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~old
        conflicting_ids = [
            cid
            for cid, c in self._constraints.items()
            if c.scope == constraint.scope
            and c.type == constraint.type
            and cid != constraint.id
        ]
        for cid in conflicting_ids:
            self._remove_constraint_by_id(cid)

        # 2. Add/Update the new constraint
        self._constraints[constraint.id] = constraint
~~~~~
~~~~~new
        conflicting_ids = [
            cid
            for cid, c in self._constraints.items()
            if c.scope == constraint.scope
            and c.type == constraint.type
            and cid != constraint.constraint_id
        ]
        for cid in conflicting_ids:
            self._remove_constraint_by_id(cid)

        # 2. Add/Update the new constraint
        self._constraints[constraint.constraint_id] = constraint
~~~~~

#### Acts 9: 更新 Engine.py 的 Payload 处理

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~old
            else:
                # Basic validation, could be improved with a schema library
                constraint = GlobalConstraint(
                    id=payload["id"],
                    scope=payload["scope"],
                    type=payload["type"],
                    params=payload["params"],
                    expires_at=payload.get("expires_at"),
                )
                self.constraint_manager.update_constraint(constraint)
~~~~~
~~~~~new
            else:
                # Basic validation, could be improved with a schema library
                c_id = payload.get("constraint_id", payload.get("id"))
                constraint = GlobalConstraint(
                    constraint_id=c_id,
                    scope=payload["scope"],
                    type=payload["type"],
                    params=payload["params"],
                    expires_at=payload.get("expires_at"),
                )
                self.constraint_manager.update_constraint(constraint)
~~~~~

#### Acts 10: 更新测试文件引用

~~~~~act
patch_file
packages/cascade-compiler/tests/test_builder.py
~~~~~
~~~~~old
    # 3. Assert Graph Structure
    assert graph.root_op_id is not None
    root_op = graph.ops[graph.root_op_id]
    
    assert isinstance(root_op, ComputeOp)
~~~~~
~~~~~new
    # 3. Assert Graph Structure
    assert graph.root_op_id is not None
    root_op = graph.ops[graph.root_op_id]
    
    assert isinstance(root_op, ComputeOp)
~~~~~
~~~~~old
    # 4. Assert Argument Resolution (Literal -> ConstantOp)
    assert "x" in root_op.inputs
    const_op_id = root_op.inputs["x"]
    const_op = graph.ops[const_op_id]
    
    assert isinstance(const_op, ConstantOp)
~~~~~
~~~~~new
    # 4. Assert Argument Resolution (Literal -> ConstantOp)
    assert "x" in root_op.inputs
    const_op_id = root_op.inputs["x"]
    const_op = graph.ops[const_op_id]
    
    assert isinstance(const_op, ConstantOp)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/test_dependency_linking.py
~~~~~
~~~~~old
    # 2. Check Dependency Link
    # root_op.inputs["y"] should be the ID of Task A's op
    op_a_id = root_op.inputs["y"]
    assert op_a_id in graph.ops
    op_a = graph.ops[op_a_id]
~~~~~
~~~~~new
    # 2. Check Dependency Link
    # root_op.inputs["y"] should be the ID of Task A's op
    op_a_id = root_op.inputs["y"]
    assert op_a_id in graph.ops
    op_a = graph.ops[op_a_id]
~~~~~
~~~~~old
    # 3. Check Task A's input
    # op_a.inputs["x"] should be a ConstantOp
    const_id = op_a.inputs["x"]
    assert graph.ops[const_id].value == 10
~~~~~
~~~~~new
    # 3. Check Task A's input
    # op_a.inputs["x"] should be a ConstantOp
    const_id = op_a.inputs["x"]
    assert graph.ops[const_id].value == 10
~~~~~
