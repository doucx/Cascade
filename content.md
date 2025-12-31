简要回答：
好的，我们现在进入第一阶段，一次性创建所有物理层定义的测试文件，将测试套件置于 RED 状态。

## [WIP] test(spec): 创建物理层测试套件 (TDD RED Phase)

### 用户需求
用户要求根据重构计划的第一阶段 (Phase 1)，创建 `Token`, `DataNode`, `FuncNode` 及其交互逻辑的测试用例。这标志着 TDD 流程的开始，预期这些测试在实现代码编写前会因 `ImportError` 或断言失败而无法通过。

### 评论
这是一个教科书式的 TDD 开局。我们将定义核心实体的预期行为和接口契约。
1.  `test_datanode.py` 将定义数据的存储、状态转换（空态/激发态）和容量策略。
2.  `test_funcnode.py` 将定义计算节点的连接（端口）、激活条件（势垒检查）和激发行为（消耗/生产）。

### 目标
创建两个测试文件：
1.  `packages/cascade-spec/tests/physics/test_datanode.py`
2.  `packages/cascade-spec/tests/physics/test_funcnode.py`

### 基本原理
通过先写测试，我们明确了物理层的 API 设计：
-   `Token` 是不可变的值对象。
-   `DataNode` 是有状态的容器，负责持有 Token。
-   `FuncNode` 是无状态的转换器，通过 `Port` 连接 `DataNode`。
-   `is_ready()` 方法体现了“势能”的概念（输入就绪 = 数据势能满足）。

### 标签
#intent/tooling #flow/draft #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/physics-layer #task/action/test-creation #task/state/begin #task/status/active

---

### Script

#### Acts 1: 创建物理层测试目录

确保测试目录存在。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-spec/tests/physics
~~~~~

#### Acts 2: 创建 `DataNode` 与 `Token` 测试

定义 Token 的结构和 DataNode 的状态机行为（Put/Take/Peek）。

~~~~~act
write_file
packages/cascade-spec/tests/physics/test_datanode.py
~~~~~
~~~~~python
import pytest
from cascade.spec.physics import Token, DataNode, AccessPolicy

def test_token_structure():
    """验证 Token 是一个包含 payload, tag 和 metadata 的数据结构"""
    token = Token(payload="data", tag="default", metadata={"ts": 123})
    assert token.payload == "data"
    assert token.tag == "default"
    assert token.metadata == {"ts": 123}

def test_datanode_state_transition():
    """验证 DataNode 在 Empty 和 Excited 状态之间的转换"""
    node = DataNode(name="d1")
    
    # 初始状态为空 (Ground State)
    assert node.is_empty()
    assert not node.is_excited()
    assert node.peek() is None

    # 注入令牌 -> 激发态 (Excited State)
    token = Token(payload=42)
    node.put(token)
    
    assert not node.is_empty()
    assert node.is_excited()
    assert node.peek() == token

    # 取出令牌 -> 回归空态
    taken = node.take()
    assert taken == token
    assert node.is_empty()
    assert not node.is_excited()

def test_datanode_capacity_policy_reject():
    """验证 REJECT 策略下，向满节点写入会抛出异常"""
    node = DataNode(name="d2", capacity=1, policy=AccessPolicy.REJECT)
    t1 = Token(1)
    t2 = Token(2)
    
    node.put(t1)
    
    # 再次写入应该失败
    with pytest.raises(BufferError):
        node.put(t2)
        
    # 状态应保持不变
    assert node.peek() == t1

def test_datanode_capacity_policy_overwrite():
    """验证 OVERWRITE 策略下，向满节点写入会覆盖旧值"""
    node = DataNode(name="d3", capacity=1, policy=AccessPolicy.OVERWRITE)
    t1 = Token(1)
    t2 = Token(2)
    
    node.put(t1)
    node.put(t2) # 不应抛出异常
    
    # 应该是新值
    assert node.peek() == t2
~~~~~

#### Acts 3: 创建 `FuncNode` 测试

定义 FuncNode 的端口连接、激活势垒检查和模拟激发过程。

~~~~~act
write_file
packages/cascade-spec/tests/physics/test_funcnode.py
~~~~~
~~~~~python
import pytest
from cascade.spec.physics import FuncNode, DataNode, Token, Port

def test_funcnode_wiring():
    """验证 FuncNode 可以正确注册输入和输出端口"""
    f_node = FuncNode(name="f1")
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")
    
    # 连接数据节点
    f_node.add_input(Port(name="arg1", source=d_in))
    f_node.add_output(Port(name="res", target=d_out))
    
    assert len(f_node.inputs) == 1
    assert len(f_node.outputs) == 1
    assert f_node.inputs["arg1"].source == d_in
    assert f_node.outputs["res"].target == d_out

def test_funcnode_activation_logic():
    """验证 FuncNode 的势能检查逻辑 (is_ready)"""
    f_node = FuncNode(name="f2")
    d_in = DataNode(name="in")
    f_node.add_input(Port(name="arg1", source=d_in))
    
    # Case 1: 输入为空 -> 势能不足 -> 未就绪
    assert d_in.is_empty()
    assert not f_node.is_ready()
    
    # Case 2: 输入激发 -> 势能满足 -> 就绪
    d_in.put(Token(10))
    assert d_in.is_excited()
    assert f_node.is_ready()

def test_funcnode_firing_dynamics():
    """验证激发过程：消耗输入，产生输出"""
    f_node = FuncNode(name="f3")
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")
    
    f_node.add_input(Port(name="arg1", source=d_in))
    f_node.add_output(Port(name="result", target=d_out))
    
    # 设置初始状态
    d_in.put(Token(10))
    
    # 1. 消耗输入 (模拟 Reactor 的原子操作)
    consumed_inputs = f_node.consume_inputs()
    
    # 验证输入被消耗
    assert consumed_inputs["arg1"].payload == 10
    assert d_in.is_empty() # 输入节点应回归空态
    
    # 2. 产生输出 (模拟执行完成后的回调)
    output_token = Token(payload=consumed_inputs["arg1"].payload * 2)
    f_node.produce_outputs({"result": output_token})
    
    # 验证输出被推送
    assert d_out.is_excited()
    assert d_out.peek().payload == 20
~~~~~

### 下一步建议
执行此计划后，测试套件将处于 **RED** 状态（因为 `cascade.spec.physics` 模块尚不存在）。
下一步将是实现 `packages/cascade-spec/src/cascade/spec/physics.py` 来定义这些类，使测试变绿。
