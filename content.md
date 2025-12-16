You are absolutely right to point out the failure. My apologies. The error log provides a clear diagnosis.

The problem stems from defining the test tasks (`get_route`, `consumer`, etc.) *inside* the `test_serialize_router` function. When Python's `inspect` module gets the `__qualname__` for these nested functions, it includes `<locals>`, which our `_load_func_from_path` deserializer cannot resolve. Functions must be defined at the module's top level to be reliably located and imported.

I will now generate a plan to fix this by moving the task definitions to the top level of the test module.

## [WIP] fix(tests): Correct serialization test by moving tasks to top level

### 错误分析
The test `test_serialize_router` fails during the deserialization phase. The root cause is that the test-specific tasks (`get_route`, `task_a`, `consumer`, etc.) were defined as nested functions inside `test_serialize_router`.

1.  **Serialization**: The `_get_func_path` function correctly captures the qualified name of a nested function, which looks like `test_serialize_router.<locals>.consumer`.
2.  **Deserialization**: The `_load_func_from_path` function tries to resolve this path by splitting it at the dots and using `getattr`. However, `<locals>` is not a real attribute that can be accessed via `getattr`. It's a special marker for a function's local scope.
3.  **Result**: This leads to an `AttributeError`, which is caught and re-raised as the `ValueError` we see in the test output.

### 用户需求
Fix the failing test `test_serialize_router` to ensure the new `Router` serialization logic can be correctly validated.

### 评论
This is a common limitation when dealing with Python's serialization and dynamic import mechanisms. The fix is straightforward and aligns with best practices: any function intended to be serialized and restored by its path must be discoverable from the module's top-level scope.

### 目标
1.  Modify `tests/graph/test_serialize.py`.
2.  Move the task definitions used in `test_serialize_router` out of the function body and place them at the module's top level.
3.  Ensure the test logic within `test_serialize_router` remains the same, but now references the top-level tasks.

### 基本原理
By making the tasks (`get_route`, `task_a`, `task_b`, `consumer`) top-level objects within the `test_serialize.py` module, their `__qualname__` will be simple and resolvable (e.g., `'get_route'`). This allows the `_load_func_from_path` function to successfully find and load them using `importlib` and `getattr`, thus fixing the test failure.

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/serialization #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Refactor the test file

We will replace the entire `test_serialize_router` function with a new block of code that first defines the necessary tasks at the top level, and then defines the test function which uses them.

~~~~~act
patch_file
tests/graph/test_serialize.py
~~~~~
~~~~~python
def test_serialize_router():
    """Test full round-trip serialization of a Router."""
    
    @cs.task
    def get_route():
        return "a"
        
    @cs.task
    def task_a():
        return "A"
        
    @cs.task
    def task_b():
        return "B"
        
    @cs.task
    def consumer(val):
        return val
        
    # Construct a router
    selector = get_route()
    route_a = task_a()
    route_b = task_b()
    
    router = cs.Router(
        selector=selector,
        routes={"a": route_a, "b": route_b}
    )
    
    # Consumer depends on the router
    target = consumer(router)
    
    # Build and Serialize
    graph = build_graph(target)
    json_str = to_json(graph)
    
    # Deserialize
    restored_graph = from_json(json_str)
    
    # Verify
    # Find the edge from selector to consumer (which carries the Router metadata)
    # The selector node name is "get_route"
    # The consumer node name is "consumer"
    
    selector_node = next(n for n in restored_graph.nodes if n.name == "get_route")
    consumer_node = next(n for n in restored_graph.nodes if n.name == "consumer")
    
    # The edge between them should have the router attached
    edge = next(e for e in restored_graph.edges if e.source == selector_node and e.target == consumer_node)
    
    assert edge.router is not None
    # Check that the stub has the correct UUIDs
    assert edge.router.selector._uuid == selector._uuid
    assert edge.router.routes["a"]._uuid == route_a._uuid
    assert edge.router.routes["b"]._uuid == route_b._uuid
~~~~~
~~~~~python
# --- Router Test Tasks ---
@cs.task
def get_route():
    return "a"

@cs.task
def task_a():
    return "A"

@cs.task
def task_b():
    return "B"

@cs.task
def consumer(val):
    return val


def test_serialize_router():
    """Test full round-trip serialization of a Router."""

    # Construct a router using top-level tasks
    selector = get_route()
    route_a = task_a()
    route_b = task_b()

    router = cs.Router(
        selector=selector,
        routes={"a": route_a, "b": route_b}
    )

    # Consumer depends on the router
    target = consumer(router)

    # Build and Serialize
    graph = build_graph(target)
    json_str = to_json(graph)

    # Deserialize
    restored_graph = from_json(json_str)

    # Verify
    # Find the edge from selector to consumer (which carries the Router metadata)
    selector_node = next(n for n in restored_graph.nodes if n.name == "get_route")
    consumer_node = next(n for n in restored_graph.nodes if n.name == "consumer")

    # The edge between them should have the router attached
    edge = next(e for e in restored_graph.edges if e.source == selector_node and e.target == consumer_node)

    assert edge.router is not None
    # Check that the stub has the correct UUIDs
    assert edge.router.selector._uuid == selector._uuid
    assert edge.router.routes["a"]._uuid == route_a._uuid
    assert edge.router.routes["b"]._uuid == route_b._uuid
~~~~~
