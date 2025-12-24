这是一个非常精准的战略分析。

**Heavy 模式的性能黑洞**在于：虽然我们跳过了图构建，但图中的 **20 个 `noop` 节点** 依然需要在每一轮迭代中被执行。而在当前的实现中，即使是这些极其简单的节点，`ArgumentResolver` 依然会回落到“慢速路径”，执行昂贵的 `inspect.Signature.bind_partial` 来检查是否存在 `Inject`——尽管 `has_complex_inputs=False` 已经保证了不存在这种情况。

此外，关于 `RedisStateBackend` 的报错，是因为我在上一轮重构中过于激进地移除了 `hasattr` 检查，而 `RedisStateBackend` 确实尚未实现 `clear` 方法。

我们将分两步解决这些问题。

## [WIP] fix: Restore Redis backend & Optimize ArgumentResolver for heavy graphs

### 用户需求
1.  修复 `RedisStateBackend` 缺失 `clear` 方法导致的测试失败。
2.  彻底消除 `ArgumentResolver` 在处理带有依赖的简单节点时的反射开销，以恢复 `Heavy` 模式下的 TCO 性能。

### 评论
我们正在补上最后一块性能拼图。通过让“带有依赖的简单节点”也走“零摩擦路径”，我们将消除 `noop` 链带来的巨大开销。同时，修复 `RedisStateBackend` 确保了代码库的稳定性。

### 目标
1.  **修复 `RedisStateBackend`**: 在 `packages/cascade-engine/src/cascade/adapters/state/redis.py` 中实现 `async def clear(self)`（暂时可以是 no-op，或者是清空当前 run 的 key，视 TCO 语义而定。鉴于 TCO 只是覆盖旧状态，no-op 或简单的日志记录足够防止崩溃）。
2.  **优化 `ArgumentResolver`**:
    *   重构 `resolve` 方法。
    *   即使存在 `incoming_edges`，只要 `!has_complex_inputs`，就**直接**将边缘数据填充到 `args/kwargs` 中，并**立即返回**，绝对禁止掉入下方的 `bind_partial` 逻辑。

### 基本原理
`GraphBuilder` 已经由我们在上一步中增强，能够准确计算 `has_complex_inputs`。如果该标志为 `False`，即意味着没有 `Inject`，没有特殊参数。此时，参数解析仅仅是“字面量绑定 + 上游结果注入”的简单合并，是一个纯粹的字典操作，复杂度应为 O(E) 而非 O(Reflect)。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/optimization #scope/core #ai/instruct #task/domain/core #task/object/performance-bottleneck #task/action/optimization #task/state/continue

---

### Script

#### Acts 1: 修复 `RedisStateBackend`

添加缺失的方法以满足协议并修复测试。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/state/redis.py
~~~~~
~~~~~python
    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        data = await asyncio.to_thread(self._client.hget, self._skipped_key, node_id)
        if data:
            return data.decode("utf-8")
        return None
~~~~~
~~~~~python
    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        data = await asyncio.to_thread(self._client.hget, self._skipped_key, node_id)
        if data:
            return data.decode("utf-8")
        return None

    async def clear(self) -> None:
        """
        Clears the state for the current run.
        For Redis, since TCO reuses the same run_id and overwrites keys,
        explicit clearing might be expensive (SCAN+DEL).
        For now, we treat this as a no-op to satisfy the protocol,
        relying on key overwrite semantics.
        """
        pass
~~~~~

#### Acts 2: 终极优化 `ArgumentResolver`

我们将“零摩擦路径”扩展到包含依赖的情况。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
            if not incoming_edges:
                # ABSOLUTE FASTEST PATH: Literals/Overrides only, no edges.
                # Just return them. Note: we don't convert to list here to save time,
                # as executors can handle positional-args-as-dict if they are careful,
                # but to maintain protocol, we'll do a quick conversion.
                f_args = []
                f_kwargs = {}
                for k, v in bindings.items():
                    if k.isdigit():
                        idx = int(k)
                        while len(f_args) <= idx: f_args.append(None)
                        f_args[idx] = v
                    else:
                        f_kwargs[k] = v
                return f_args, f_kwargs

        args = []
~~~~~
~~~~~python
            if not incoming_edges:
                # ABSOLUTE FASTEST PATH: Literals/Overrides only, no edges.
                f_args = []
                f_kwargs = {}
                for k, v in bindings.items():
                    if k.isdigit():
                        idx = int(k)
                        while len(f_args) <= idx: f_args.append(None)
                        f_args[idx] = v
                    else:
                        f_kwargs[k] = v
                return f_args, f_kwargs
            
            # FAST PATH WITH EDGES: Simple node, but has upstream data.
            # We merge literals and edges without reflection.
            f_args = []
            # 1. Fill from bindings
            for k, v in bindings.items():
                if k.isdigit():
                    idx = int(k)
                    while len(f_args) <= idx: f_args.append(None)
                    f_args[idx] = v
                else:
                    # Note: We use a temp dict for kwargs to avoid modifying bindings if cached
                    # But bindings is already a copy from node if input_overrides was present,
                    # or node.input_bindings directly. To be safe, we create a new dict.
                    pass
            
            f_kwargs = {k: v for k, v in bindings.items() if not k.isdigit()}

            # 2. Fill from edges
            for edge in incoming_edges:
                val = await self._resolve_dependency(
                    edge, node.structural_id, state_backend, graph, instance_map
                )
                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
                    while len(f_args) <= idx: f_args.append(None)
                    f_args[idx] = val
                else:
                    f_kwargs[edge.arg_name] = val
            
            return f_args, f_kwargs

        args = []
~~~~~

### 下一步建议

现在 `ArgumentResolver` 对所有简单节点（无论是否有依赖）都实现了零反射处理。

请再次运行压测：
`python observatory/benchmarks/tco_performance.py`

**预期结果**：
1.  **Explicit Jump Loop (Simple)**: 应该保持在 **50k+ TPS** 的高位。
2.  **Heavy Explicit Loop**: 这是见证奇迹的时刻。由于 20 个 `noop` 节点的执行现在也绕过了反射和资源锁，`Heavy` 模式的性能应该大幅回升，Penalty 应该从 1600% 下降到 **100-200%** 左右（仅剩必要的 `await` 开销）。

这将证明我们的架构不仅对“空循环”有效，对“实际负载循环”同样具备极高的效率。
