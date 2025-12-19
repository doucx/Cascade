import pytest
import asyncio
from cascade.connectors.local import LocalBusConnector

# 显式声明模块内所有测试及 Fixture 均运行于 asyncio 环境
pytestmark = pytest.mark.asyncio

@pytest.fixture(autouse=True)
async def cleanup_bus():
    """每个测试运行前强制清理全局总线。"""
    await LocalBusConnector.reset_bus()
    yield

@pytest.mark.asyncio
async def test_local_bus_broadcast():
    """测试基本的消息广播功能。"""
    c1 = LocalBusConnector()
    c2 = LocalBusConnector()
    
    received = []
    async def cb(topic, payload):
        received.append(payload)

    await c1.connect()
    await c2.connect()
    
    await c1.subscribe("news/tech", cb)
    await c2.publish("news/tech", {"msg": "hello"})
    
    await asyncio.sleep(0.01)
    assert received == [{"msg": "hello"}]
    
    await c1.disconnect()
    await c2.disconnect()

@pytest.mark.asyncio
async def test_retained_messages_sync():
    """
    验证保留消息的核心特性：
    后订阅的实例必须能立即收到之前发布的保留消息。
    """
    publisher = LocalBusConnector()
    subscriber = LocalBusConnector()
    
    await publisher.connect()
    await subscriber.connect()
    
    # 1. 先发布保留消息
    await publisher.publish("config/global", {"timeout": 30}, retain=True)
    
    # 2. 后订阅
    received = []
    async def cb(topic, payload):
        received.append(payload)
    
    # subscribe 应该在返回前执行回调（针对保留消息）
    await subscriber.subscribe("config/global", cb)
    
    assert received == [{"timeout": 30}], "Subscriber should receive retained message immediately"

@pytest.mark.asyncio
async def test_wildcard_matching():
    """测试多级通配符匹配。"""
    connector = LocalBusConnector()
    await connector.connect()
    
    received = []
    async def cb(topic, payload):
        received.append(topic)

    await connector.subscribe("sensors/#", cb)
    
    await connector.publish("sensors/temp/room1", {"v": 20})
    await connector.publish("sensors/humidity", {"v": 60})
    await connector.publish("lights/kitchen", {"v": "on"}) # 不匹配
    
    await asyncio.sleep(0.01)
    assert "sensors/temp/room1" in received
    assert "sensors/humidity" in received
    assert "lights/kitchen" not in received

@pytest.mark.asyncio
async def test_clear_retained_message():
    """测试清理保留消息（发布空负载）。"""
    bus = LocalBusConnector()
    await bus.connect()
    
    await bus.publish("test/topic", "stay", retain=True)
    await bus.publish("test/topic", "", retain=True) # 清理
    
    received = []
    async def cb(t, p): received.append(p)
    
    await bus.subscribe("test/topic", cb)
    assert len(received) == 0