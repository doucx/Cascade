非常抱歉，这是一个低级错误。我在重写 `build.py` 以实现 Merkle 哈希构建器时，**漏掉了文件末尾的 `build_graph` 顶级函数定义**。这导致了 `ImportError`。

我将立即把这个遗漏的函数补回去。

## [WIP] fix(graph): Add missing build_graph export

### 简要回答
在上一步重写 `GraphBuilder` 时遗漏了模块级函数 `build_graph`。

### 摘要头
## [WIP] fix(graph): Add missing build_graph export

### 用户需求
修复 `ImportError: cannot import name 'build_graph'` 错误。

### 脚本

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~old
        for k, v in result.mapping_kwargs.items():
            scan(v, k)

        return node
~~~~~
~~~~~new
        for k, v in result.mapping_kwargs.items():
            scan(v, k)

        return node


def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~

### 下一步建议
请再次运行 `python observatory/benchmarks/tco_performance.py`。这一次应该能看到我们期待已久的性能飞跃。
