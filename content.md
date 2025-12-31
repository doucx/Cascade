好的，我们正处于 TDD 流程的 RED -> GREEN 阶段。测试已经写好并指出了我们 Spec 中的缺失，现在我们来补全它。

## [WIP] feat(spec): Implement Jump and JumpIfFalse control flow instructions

### 用户需求
在 `packages/cascade-spec/src/cascade/spec/blueprint.py` 中实现 `Jump` 和 `JumpIfFalse` 数据类，以使 `test_blueprint_control_flow.py` 测试通过。

### 评论
这是为新架构添加 `run_if` 等条件执行能力的关键第一步。通过在指令集（Blueprint）层面定义控制流，我们为 Compiler 和 VM 之间建立了清晰的契约，使得上层逻辑可以被编译成底层的跳转指令。

### 目标
1.  在 `blueprint.py` 中添加 `Jump` 和 `JumpIfFalse` 两个 `dataclass`。
2.  确保这两个类都继承自 `Instruction` 基类。
3.  让 `cascade-spec` 的测试套件恢复 GREEN 状态。

### 基本原理
我们遵循“先定义数据，再实现逻辑”的原则。通过先在 Spec 包中定义好指令的结构，我们为后续的 Compiler 后端和 VM 执行器的工作提供了一个稳定的、类型安全的目标。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #concept/vm #task/domain/core #task/object/control-flow #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在 `blueprint.py` 中定义控制流指令

我们将 `Jump` 和 `JumpIfFalse` 添加到指令集中。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/blueprint.py
~~~~~
~~~~~python.old
@dataclass
class Call(Instruction):
    func: Any
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None


@dataclass
class TailCall:
~~~~~
~~~~~python.new
@dataclass
class Call(Instruction):
    func: Any
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None


@dataclass
class Jump(Instruction):
    """Unconditionally jumps execution by a relative offset."""

    offset: int


@dataclass
class JumpIfFalse(Instruction):
    """Jumps execution by a relative offset if the condition register is False."""

    condition: Register
    offset: int


@dataclass
class TailCall:
~~~~~

### 下一步建议
现在 Spec 已经完备，测试应该会通过（GREEN）。下一步是让 VM “理解”这些新指令。

我建议编写一个新的 VM 单元测试 `packages/cascade-vm/tests/unit/test_vm_control_flow.py`，该测试将手动构造一个包含 `Jump` 和 `JumpIfFalse` 指令的 Blueprint，并断言 VM 的指令指针（Program Counter）是否正确跳转。这将驱动我们修改 VM 的主执行循环。
