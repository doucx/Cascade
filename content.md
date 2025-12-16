很好的观察。这个测试失败揭示了我们在测试设计上的一个细微差别：试图在一个非容器类型（如 `int`）上继续进行路径查找会引发 `TypeError`，这在逻辑上是正确的，但与测试预期的 `KeyError` 不符。

我将修复这个测试，使其针对真正的“键缺失”场景，并补充一个专门针对“类型错误”场景的测试，以确保两种边界情况都被正确覆盖。

## [WIP] fix(tests): 修正配置查找测试中的异常断言不匹配

### 错误分析
在 `test_lookup_missing_key_raises_error` 中，测试数据是 `{"a": 1}`，查找路径是 `"a.nonexistent"`。
1.  第一步 `"a"` 解析为 `1` (int)。
2.  第二步试图在 `1` 上查找 `"nonexistent"`。由于 `int` 不是容器，代码正确地抛出了 `TypeError`。
3.  测试使用 `pytest.raises(KeyError)`，导致捕获失败。

### 用户需求
修复测试失败，确保测试用例准确反映代码行为。

### 评论
区分 `KeyError`（在容器中找不到键）和 `TypeError`（试图在非容器中查找）对于调试配置问题非常重要。测试套件应该明确区分并验证这就两种行为。

### 目标
1.  修改 `test_lookup_missing_key_raises_error`，使其查找路径为 `"b"`（在根字典中不存在），从而正确触发并断言 `KeyError`。
2.  添加一个新的测试 `test_lookup_invalid_path_raises_type_error`，使用原先的逻辑（在 int 上查找）来明确验证 `TypeError` 的行为。

### 基本原理
通过分离这两个测试用例，我们不仅修复了 CI 失败，还提高了测试的精确度和覆盖率。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/tests #task/object/config-tests #task/action/fix-assertion #task/state/continue

---

### Script

#### Acts 1: 修正并增强配置查找测试

修改 `tests/providers/test_config.py`，修正错误的测试用例并添加新的类型错误测试。

~~~~~act
patch_file
tests/providers/test_config.py
~~~~~
~~~~~
@pytest.mark.asyncio
async def test_lookup_missing_key_raises_error():
    """Tests that a missing key raises a KeyError."""
    
    @cs.task
    def provide_dict():
        return {"a": 1}
        
    source = provide_dict()
    missing_value = cs.lookup(source=source, key="a.nonexistent")
    
    engine = cs.Engine()
    with pytest.raises(KeyError):
        await engine.run(missing_value)
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_lookup_missing_key_raises_error():
    """Tests that a missing key raises a KeyError."""
    
    @cs.task
    def provide_dict():
        return {"a": 1}
        
    source = provide_dict()
    # "b" does not exist in the root dict, should raise KeyError
    missing_value = cs.lookup(source=source, key="b")
    
    engine = cs.Engine()
    with pytest.raises(KeyError):
        await engine.run(missing_value)

@pytest.mark.asyncio
async def test_lookup_invalid_path_raises_type_error():
    """Tests that lookup on a non-container value raises TypeError."""

    @cs.task
    def provide_dict():
        return {"a": 1}

    source = provide_dict()
    # "a" resolves to 1 (int), which is not a container. 
    # Attempting to look up "nonexistent" on it should raise TypeError.
    invalid_lookup = cs.lookup(source=source, key="a.nonexistent")

    engine = cs.Engine()
    with pytest.raises(TypeError, match="Cannot access segment"):
        await engine.run(invalid_lookup)
~~~~~

### 下一步建议
现在测试应该可以通过了。由于我们不仅修复了测试，还完成了整个“配置加载重构”任务（包括代码实现、文档更新和测试修复），我建议接下来执行 Git 提交，将所有这些变更作为一个完整的原子提交记录下来。
