简要回答

好的，我将修复这些测试失败。主要问题在于测试代码尚未适应新的“主权端口”命名（从 `output` 变更为 `output_default`），以及编译器后端在处理位置参数时与 `BleachNode` 的端口命名不匹配。

我将实施以下修复：
1.  **增强 `ParameterWiringPolicy`**: 使其能够智能地将基于索引的输入键（如 `"0"`）映射到实际的参数名（如 `"msg"`），从而解决 `test_sovereign_wiring_flow` 中的连接错误。
2.  **更新单元测试**: 修改 `test_expander.py` 和 `test_stainer.py` 以断言新的 `output_default` 端口，而不是过时的 `output`。

## [WIP] fix(compiler): 修复主权端口重构后的测试与参数映射

### 错误分析

1.  **`WiringError` (Port mismatch)**: `test_sovereign_wiring_flow` 失败是因为 `IRGenerator` 将位置参数存储为 `"0"`, `"1"` 等键，而 `BleachNode` 的端口是根据参数名（如 `"msg"`）生成的。`ParameterWiringPolicy` 之前直接使用输入键作为目标端口名，导致不匹配。
2.  **`KeyError: 'output'` / `AssertionError`**: 多个单元测试失败是因为它们仍然断言旧的 `output` 端口存在，而我们已经将其重命名为 `output_default`。

### 用户需求
修复因引入主权端口而破坏的测试，并增强编译器处理位置参数的能力。

### 评论
这次修复不仅是为了通过测试，更是为了增强编译器的健壮性。通过在布线策略层处理“位置索引到参数名”的映射，我们允许前端（IRGenerator）保持简单，同时确保物理层连接的正确性。

### 目标
1.  修改 `ParameterWiringPolicy` 以正确解析位置参数。
2.  更新 `test_expander.py` 适配新端口名。
3.  更新 `test_stainer.py` 适配新端口名。

### 基本原理
*   **参数绑定迟滞**: 逻辑层 (NodeIR) 可能使用位置索引，但物理层 (Bleacher) 必须使用具名端口。布线策略是进行这种转换的最佳位置。
*   **测试同步**: 测试必须反映代码库的当前真实状态（即主权端口是新的事实标准）。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #comp/std #scope/core #task/domain/compiler #task/object/parameter-wiring #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 增强 ParameterWiringPolicy 以支持位置参数映射

我们将修改布线策略，使其在连接 `Bleacher` 之前，先将输入键（可能是数字字符串）解析为正确的参数名。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/wiring/policies/parameter.py
~~~~~
~~~~~python.old
    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        for arg_name, source_ref in node_ir.inputs.items():
            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(source_ref)
                assert source_subgraph.stainer is not None

                # Violation Fix: Insert D_dep (Intermediate Data Node)
                d_dep_id = f"dep.{source_ref}.to.{node_ir.id}.{arg_name}"
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({arg_name})")
                ctx.wire.add_node(d_dep)

                # Source Stainer -> D_dep (Connect from output_default)
                ctx.wire.connect(source_subgraph.stainer.id, "output_default", d_dep_id, "in")

                # D_dep -> Target Bleacher
                ctx.wire.connect(d_dep_id, "out", subgraph.bleacher.id, arg_name)

            # Case B: Literal Value (Constant) - Use Probe Model
            else:
                # 1. D_const (DataNode holding the literal value)
                d_const_id = PhysicalIdGenerator.constant(node_ir.id, arg_name)
                d_const = PhysicsDataNode(
                    id=d_const_id,
                    name=f"Const({arg_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=source_ref,
                )
                ctx.wire.add_node(d_const)

                # 2. F_probe (The probe node for constants)
                f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, arg_name)
                f_probe = PhysicsFuncNode(
                    id=f_probe_id,
                    name=f"Probe({arg_name})",
                    input_ports={"value": PortDef("value", PortRole.DATA)},
                    output_ports={"out": PortDef("out", PortRole.DATA)},
                )
                ctx.wire.add_node(f_probe)

                # 3. D_probed (Intermediate data node to connect to Bleacher)
                d_probed_id = f"{f_probe_id}.out"
                d_probed = PhysicsDataNode(id=d_probed_id, name=f"Probed({arg_name})")
                ctx.wire.add_node(d_probed)

                # 4. Wiring
                # D_const -> F_probe
                ctx.wire.connect(d_const_id, "out", f_probe_id, "value")
                # F_probe -> D_probed
                ctx.wire.connect(f_probe_id, "out", d_probed_id, "in")
                # D_probed -> Target Bleacher
                ctx.wire.connect(d_probed_id, "out", subgraph.bleacher.id, arg_name)
~~~~~
~~~~~python.new
    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        for input_key, source_ref in node_ir.inputs.items():
            # Resolve the actual port name on the Bleacher.
            # NodeIR input keys might be positional indices ("0", "1") or keyword names.
            # We map indices to argument names using the TaskDef.
            if input_key.isdigit():
                idx = int(input_key)
                if idx < len(node_ir.task.args):
                    port_name = node_ir.task.args[idx].name
                else:
                    # Fallback/Error case: index out of range for defined args.
                    # We use the key as is, which will likely fail later at wiring validation if invalid.
                    port_name = input_key
            else:
                port_name = input_key

            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(source_ref)
                assert source_subgraph.stainer is not None

                # Violation Fix: Insert D_dep (Intermediate Data Node)
                # Use input_key for ID uniqueness to avoid collisions if multiple inputs map to same name (unlikely but safe)
                d_dep_id = f"dep.{source_ref}.to.{node_ir.id}.{input_key}"
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({port_name})")
                ctx.wire.add_node(d_dep)

                # Source Stainer -> D_dep (Connect from output_default)
                ctx.wire.connect(source_subgraph.stainer.id, "output_default", d_dep_id, "in")

                # D_dep -> Target Bleacher
                ctx.wire.connect(d_dep_id, "out", subgraph.bleacher.id, port_name)

            # Case B: Literal Value (Constant) - Use Probe Model
            else:
                # 1. D_const (DataNode holding the literal value)
                d_const_id = PhysicalIdGenerator.constant(node_ir.id, input_key)
                d_const = PhysicsDataNode(
                    id=d_const_id,
                    name=f"Const({port_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=source_ref,
                )
                ctx.wire.add_node(d_const)

                # 2. F_probe (The probe node for constants)
                f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, input_key)
                f_probe = PhysicsFuncNode(
                    id=f_probe_id,
                    name=f"Probe({port_name})",
                    input_ports={"value": PortDef("value", PortRole.DATA)},
                    output_ports={"out": PortDef("out", PortRole.DATA)},
                )
                ctx.wire.add_node(f_probe)

                # 3. D_probed (Intermediate data node to connect to Bleacher)
                d_probed_id = f"{f_probe_id}.out"
                d_probed = PhysicsDataNode(id=d_probed_id, name=f"Probed({port_name})")
                ctx.wire.add_node(d_probed)

                # 4. Wiring
                # D_const -> F_probe
                ctx.wire.connect(d_const_id, "out", f_probe_id, "value")
                # F_probe -> D_probed
                ctx.wire.connect(f_probe_id, "out", d_probed_id, "in")
                # D_probed -> Target Bleacher
                ctx.wire.connect(d_probed_id, "out", subgraph.bleacher.id, port_name)
~~~~~

#### Acts 2: 更新 Expander 测试

更新断言以期望 `output_default`。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_expander.py
~~~~~
~~~~~python.old
    assert stainer.input_ports["worker_result"].role == PortRole.DATA
    assert stainer.output_ports["output"].role == PortRole.DATA

    # Trace -> Stain
~~~~~
~~~~~python.new
    assert stainer.input_ports["worker_result"].role == PortRole.DATA
    assert stainer.output_ports["output_default"].role == PortRole.DATA

    # Trace -> Stain
~~~~~

#### Acts 3: 更新 Stainer 测试

更新断言以期望 `output_default`。

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
async def test_stainer_success_case():
    start_ts = 1000.0
    end_ts = 1002.5

    inputs = {
        "worker_result": Token(payload="SuccessData"),
        "trace_input": Token(payload={"start_ts": start_ts, "id": "task_A"}),
    }
    node = create_mock_stain_node({"output": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node, MagicMock())

    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload == "SuccessData"
    # Tag assertion removed
~~~~~
~~~~~python.new
async def test_stainer_success_case():
    start_ts = 1000.0
    end_ts = 1002.5

    inputs = {
        "worker_result": Token(payload="SuccessData"),
        "trace_input": Token(payload={"start_ts": start_ts, "id": "task_A"}),
    }
    node = create_mock_stain_node({"output_default": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node, MagicMock())

    assert "output_default" in outputs
    output_token = outputs["output_default"]

    assert output_token.payload == "SuccessData"
    # Tag assertion removed
~~~~~

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
async def test_stainer_error_case():
    start_ts = 2000.0
    end_ts = 2000.1
    error = ValueError("Something went wrong")

    inputs = {
        "worker_result": Token(payload=error),
        "trace_input": Token(payload={"start_ts": start_ts}),
    }
    node = create_mock_stain_node({"output": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node, MagicMock())

    assert "output" in outputs
    output_token = outputs["output"]

    assert output_token.payload is error  # Should be the same exception instance
    # Tag assertion removed
~~~~~
~~~~~python.new
async def test_stainer_error_case():
    start_ts = 2000.0
    end_ts = 2000.1
    error = ValueError("Something went wrong")

    inputs = {
        "worker_result": Token(payload=error),
        "trace_input": Token(payload={"start_ts": start_ts}),
    }
    node = create_mock_stain_node({"output_default": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node, MagicMock())

    assert "output_default" in outputs
    output_token = outputs["output_default"]

    assert output_token.payload is error  # Should be the same exception instance
    # Tag assertion removed
~~~~~

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_stainer.py
~~~~~
~~~~~python.old
async def test_stainer_handles_missing_start_ts_gracefully():
    end_ts = 3000.0
    inputs = {
        "worker_result": Token(payload="data"),
        "trace_input": Token(payload={}),  # No start_ts
    }
    node = create_mock_stain_node({"output": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node, MagicMock())

    output_token = outputs["output"]
    assert output_token.trace["duration"] == 0.0
    assert output_token.trace["end_ts"] == end_ts
~~~~~
~~~~~python.new
async def test_stainer_handles_missing_start_ts_gracefully():
    end_ts = 3000.0
    inputs = {
        "worker_result": Token(payload="data"),
        "trace_input": Token(payload={}),  # No start_ts
    }
    node = create_mock_stain_node({"output_default": PortRole.DATA})

    with patch("time.monotonic", return_value=end_ts):
        outputs = await standard_stainer(inputs, node, MagicMock())

    output_token = outputs["output_default"]
    assert output_token.trace["duration"] == 0.0
    assert output_token.trace["end_ts"] == end_ts
~~~~~

### 下一步建议
修复完成后，所有测试应能通过。这标志着“主权端口”基础设施的成功落地。
接下来，我们可以考虑验证“连续资源”的支持，或者开始着手优化 JIT (Phase 2) 的工作。但根据当前进度，确保新的布线逻辑稳固是最优先的。
