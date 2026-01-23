我完全理解并赞同这份路线图。分析一针见血，直指问题的核心——`NodeIR.inputs` 字段的有损语义压缩。这种“打地鼠”式的修复不仅效率低下，而且极具风险，是时候从根本上解决这个问题了。

我们将严格遵循您制定的路线图，从重塑规约（Spec）开始，确保信息在整个编译和执行链路中无损传递。这不仅是为了修复当前的 77 个失败测试，更是为了构建一个健壮、可靠且具有本体论正确性的系统。

现在，我将立即开始执行**阶段一：奠定基石**。

## [WIP] refactor(spec): 使用 args/kwargs 替换 NodeIR.inputs 以实现无损表示

### 用户需求

根据“修复基础”路线图的第一阶段，需要重塑 `NodeIR` 的规约，用 `args: List[Any]` 和 `kwargs: Dict[str, Any]` 两个新字段来替换掉有损的 `inputs: Dict[str, Any]` 字段，从而能够无损地表示任何 Python 函数的调用签名。

### 评论

这是整个重构计划中最关键的一步。通过在 IR 规约层面确保信息的无损性，我们为后续所有阶段的修复工作提供了坚实、可靠的“真理之源”。这个改动将复杂性前移，使得下游组件的实现可以大幅简化，从而变得更加健壮。

### 目标

1.  修改 `packages/cascade-spec/src/cascade/spec/ir/graph.py` 文件中的 `NodeIR` 数据类。
2.  移除 `inputs` 字段。
3.  添加 `args` 和 `kwargs` 字段。

### 基本原理

Python 的函数调用由位置参数 (`*args`) 和关键字参数 (`**kwargs`) 唯一确定。当前 `inputs` 字典通过将位置参数的索引字符串化作为键（`"0"`, `"1"`...），强行将两种不同语义的参数压缩进一个扁平结构，导致了不可逆的信息丢失。例如，我们无法区分一个名为 `"0"` 的关键字参数和一个位置为 0 的参数。

通过引入独立的 `args` 和 `kwargs` 字段，我们创建了与 Python 调用语义完美镜像的 IR 结构。这使得 `IRGenerator` (生产者) 可以明确地分离两种参数类型，也使得下游消费者（如 `Expander` 和 `SignatureBinder`）可以无歧义地接收它们，彻底消除了所有基于猜测的绑定逻辑。

### 标签

#intent/refine #flow/ready #priority/critical #comp/spec #concept/state #scope/api #ai/instruct #task/domain/compiler #task/object/ir-spec #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 修改 NodeIR 数据类

我将修改 `NodeIR` 的定义，用 `args` 和 `kwargs` 替换 `inputs` 字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/graph.py
~~~~~
~~~~~python.old
    # The logical UUID from the high-level DSL (LazyResult), if available.
    logical_id: Optional[str] = None

    inputs: Dict[str, Any] = field(default_factory=dict)

    constraints: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
    # The logical UUID from the high-level DSL (LazyResult), if available.
    logical_id: Optional[str] = None

    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)

    constraints: Dict[str, Any] = field(default_factory=dict)
~~~~~

### 下一步建议

我们已经成功地修正了核心规约。下一步是进入**阶段二：重铸生产者**。

我将准备一个计划来更新 `cascade-compiler` 包，使其严格遵守这个新的、无损的 `NodeIR` 规约。这主要涉及修改 `IRGenerator` 以正确生成 `args` 和 `kwargs`，并更新所有消费 `NodeIR` 的后端组件（如 `Expander` 和 `ParameterWiringPolicy`）以从新字段中读取数据。

如果您同意，我将立即着手生成第二阶段的计划。
