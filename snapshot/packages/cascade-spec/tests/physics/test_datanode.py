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