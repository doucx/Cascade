You've correctly identified a bug in my previous plan. The `UnboundLocalError` is a classic variable scope issue. The `port_name` variable from the dependency wiring loop was not available in the resource wiring loop. My apologies for that oversight.

The fix is to define the correct port name for the release wiring within its proper scope. The `Stainer`'s output port for a resource release should be symmetrically named to the `Bleacher`'s input port, which is `f"res_{res_name}"`.

I will now generate a plan to correct this error.

## [WIP] fix(compiler): Correct port name variable in resource release wiring

### 错误分析
在 `builder.py` 的资源布线逻辑中，连接 `Stainer` 到 `RelBuffer` 的代码错误地引用了一个在当前作用域中不存在的变量 `port_name`。该变量是在处理依赖关系的另一个循环中定义的，导致了 `UnboundLocalError`。

### 用户需求
修复 `builder.py` 中的 `UnboundLocalError`，确保资源释放的布线逻辑使用正确的端口名称。

### 评论
这是一个简单的作用域错误，但暴露了在复杂布线逻辑中保持变量名清晰和上下文正确的重要性。通过为释放端口专门定义一个变量 `release_port_name`，我们不仅修复了 Bug，还提高了代码的可读性。

### 目标
- 在 `builder.py` 中，为 Stainer 的资源释放连接定义并使用正确的端口名称变量。

### 基本原理
根据 `Expander` 中的定义，`Stainer` 节点上用于释放资源的输出端口被命名为 `res_{resource_name}`。修复方案需要确保 `Builder` 在连接此端口时使用这个确定的命名约定。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #concept/topology #scope/core #task/domain/core #task/object/topology #task/action/sovereignty #task/state/continue

---

### Script

#### Acts 1: 修复 `builder.py` 中的变量作用域错误

我们将修正 `wire.connect` 调用，使用正确的、在当前作用域中定义的端口名。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
                # --- C. Release Wiring ---
                # Stainer -> RelBuffer
                wire.connect(
                    subgraph.stainer.id,
                    port_name,
                    rel_buffer_id,
                    "in",
                )
~~~~~
~~~~~python.new
                # --- C. Release Wiring ---
                # Stainer -> RelBuffer
                # The stainer output port for releasing a resource is named symmetrically
                # to the bleacher input port for acquiring it.
                release_port_name = f"res_{res_name}"
                wire.connect(
                    subgraph.stainer.id,
                    release_port_name,
                    rel_buffer_id,
                    "in",
                )
~~~~~

### 下一步建议
这个修复应该已经解决了编译器构建过程中的崩溃问题。现在我们可以安全地重新运行测试套件，特别是 `test_resource_backpressure.py`，以验证整个资源请求-授予-释放的闭环在新的主权端口模型下是否按预期工作。

如果测试通过，我们就可以继续执行路线图的第二阶段了。
