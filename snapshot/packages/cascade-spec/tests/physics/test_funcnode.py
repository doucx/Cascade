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
    assert d_in.is_empty()  # 输入节点应回归空态

    # 2. 产生输出 (模拟执行完成后的回调)
    output_token = Token(payload=consumed_inputs["arg1"].payload * 2)
    f_node.produce_outputs({"result": output_token})

    # 验证输出被推送
    assert d_out.is_excited()
    assert d_out.peek().payload == 20
