## [WIP] fix(compiler): Prevent Blueprint instruction reference sharing

### 摘要头
`# [WIP] fix(compiler): Prevent Blueprint instruction reference sharing`

### 用户需求
修复 `BlueprintBuilder` 中的一个严重 Bug：生成的 `Blueprint` 对象共享了 Builder 内部的 `instructions` 列表引用。这导致当同一个 Builder 实例被多次使用时，先前生成的 Blueprint 会被破坏（其指令被清空并替换为最新编译的指令）。

### 错误分析
在 `test_vm_mutual.py` 中，我们复用了同一个 `BlueprintBuilder` 实例来编译 `ping` 和 `pong`。
由于 `BlueprintBuilder.build` 方法在构造 `Blueprint` 对象时直接传递了 `self.instructions` 的引用：
```python
return Blueprint(instructions=self.instructions, ...)
```
而 `build` 方法在开始时会调用 `self.instructions.clear()`。
这就导致 `bp_ping` 的指令列表被清空，并填充了 `pong` 的指令。实际上，`bp_ping` 和 `bp_pong` 最终都指向了同一组指令（Pong 的逻辑）。
因此，执行 `Ping(4)` 实际上执行的是 `Pong(4)`，然后不断递归调用自己（因为 `target_blueprint_id="ping"` 指向的还是那组 Pong 指令），最终输出 "Pong Done"。

### 评论
这是一个经典的引用陷阱，特别是在构建器模式中。必须确保构建产物拥有数据的独立副本。

### 目标
在 `BlueprintBuilder.build` 返回时，创建内部列表和字典的浅拷贝。

### 基本原理
使用 `list()` 和 `dict()` 构造函数创建副本。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/parser #scope/core #ai/instruct #task/domain/runtime #task/object/compiler #task/action/bugfix #task/state/continue

---

### Script

#### Acts 1: 修复 `BlueprintBuilder` 的引用问题

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/graph/compiler.py
~~~~~
~~~~~python
        return Blueprint(
            instructions=self.instructions,
            register_count=self._register_counter,
            input_args=self._input_args_map,
            input_kwargs=self._input_kwargs_map
        )
~~~~~
~~~~~python
        return Blueprint(
            instructions=list(self.instructions),
            register_count=self._register_counter,
            input_args=list(self._input_args_map),
            input_kwargs=dict(self._input_kwargs_map)
        )
~~~~~

### 下一步建议
重新运行测试，验证修复是否有效。如果测试通过，我们可以继续进行 **第四阶段：引擎集成 (Engine Integration)**。
