简要回答：
收到。我们将正式启动 **原基计划 (Project Protoplasm)** 的第二阶段：神经直连 (Neural Direct Connection)。

根据文档 `CS-DOC-PRE-GENESIS-251220` 的第二章，我们的目标是证明在大规模（N=10,000）网格交互下，基于 Pub/Sub 的总线模式会遭遇物理瓶颈，并验证 **拓扑感知直连 (DirectChannel)** 方案的性能优势。

摘要头：
## [WIP] feat: 预研 DirectChannel 通信原型与基准测试

### 标签
#intent/explore #flow/ready #priority/high
#comp/observatory #concept/communication #scope/core
#ai/instruct
#task/domain/networking
#task/object/direct-channel
#task/action/implementation
#task/state/begin

### 用户需求
1.  **构建网络预研目录**：在 `observatory/protoplasm/networking/` 下建立实验场。
2.  **实现 DirectChannel**：编写一个极简的、零拷贝的通信原语，基于 `asyncio.Queue` 封装，支持“点对点”直接投递。
3.  **实现采样探针**：在 DirectChannel 中集成随机采样逻辑，验证“旁路通信”下的可观测性方案（即每 N 条消息向总线泄漏一条）。
4.  **构建基准测试 (Benchmark)**：编写 `proto_direct_connect.py`，对比 `LocalBusConnector`（基于主题匹配及分发）与 `DirectChannel`（基于直接引用）在 1 对 N 广播场景下的吞吐量和延迟差异。

### 评论
在细胞自动机模型中，邻居关系是静态的。`LocalBus` 的通用性（动态订阅、通配符匹配）在这里变成了纯粹的开销。`DirectChannel` 模拟的是生物神经突触的连接——一旦建立，信号传递就是电化学的直接流动，无需经过中央邮局。这个实验将量化这种“去中心化”带来的性能提升。

### 目标
*   建立 `observatory/protoplasm/networking` 目录。
*   完成 `direct_channel.py`：实现带采样的直连通道。
*   完成 `proto_direct_connect.py`：实现高并发基准测试脚本。

### 基本原理
*   **零拷贝 (Zero-Copy)**：`DirectChannel.send(obj)` 直接将 Python 对象引用放入接收者的 `asyncio.Queue`，不进行序列化，不经过中间路由。
*   **对照实验**：模拟“一个细胞向 8 个邻居闪烁”的场景。
    *   **Group A (Bus)**: 1 次 `publish("flash")`，Bus 内部遍历订阅列表并分发给 8 个 Queue。
    *   **Group B (Direct)**: 循环 8 次 `neighbor.channel.send(msg)`。
*   **预期结论**：在协程数量巨大时，Bus 的锁竞争 (`asyncio.Lock`) 和列表遍历将导致显著的延迟抖动，而 Direct 模式应保持线性性能。

---

### Script

#### Acts 1: 创建目录结构

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p observatory/protoplasm/networking
touch observatory/protoplasm/networking/__init__.py
~~~~~

#### Acts 2: 实现 DirectChannel (`direct_channel.py`)

这是一个包装了 `asyncio.Queue` 的轻量级类，它模拟了“突触”。关键特性是它持有一个可选的 `bus` 引用用于采样。

~~~~~act
write_file
observatory/protoplasm/networking/direct_channel.py
~~~~~
~~~~~python
import asyncio
import random
from typing import Any, Optional
from cascade.common.messaging import bus as global_bus
from cascade.interfaces.protocols import Connector

class DirectChannel:
    """
    A high-performance, point-to-point communication primitive.
    Simulates a direct synaptic connection between agents, bypassing the central event bus.
    """
    
    def __init__(
        self, 
        owner_id: str, 
        capacity: int = 100, 
        sampling_rate: float = 0.001,
        telemetry_connector: Optional[Connector] = None
    ):
        self.owner_id = owner_id
        # The inbox is a simple asyncio Queue.
        # Unbounded queues are dangerous in prod, but for this proto we want to measure pure throughput.
        # We set a high limit to avoid immediate backpressure during bursts.
        self._inbox = asyncio.Queue(maxsize=capacity)
        
        # Telemetry Sampling
        self.sampling_rate = sampling_rate
        self.telemetry_connector = telemetry_connector
        
    async def send(self, payload: Any):
        """
        Directly puts a message into the channel. Zero-copy.
        """
        # 1. Core Logic: Direct Delivery
        # put_nowait is fastest, but risks Full exception. 
        # For proto, we assume consumers are fast enough or capacity is sufficient.
        try:
            self._inbox.put_nowait(payload)
        except asyncio.QueueFull:
            # In a real system, we'd handle backpressure here.
            # For the benchmark, this counts as a "dropped packet" or saturation.
            pass

        # 2. Telemetry Probe (The "Leak")
        # Randomly sample traffic to the global bus for observability.
        if self.telemetry_connector and self.sampling_rate > 0:
            if random.random() < self.sampling_rate:
                # We fire-and-forget the telemetry to minimize impact on the critical path
                asyncio.create_task(
                    self.telemetry_connector.publish(
                        f"debug/sample/{self.owner_id}", 
                        {"payload": str(payload), "type": "sample"}
                    )
                )

    async def recv(self) -> Any:
        """
        Waits for a message.
        """
        return await self._inbox.get()
    
    def qsize(self) -> int:
        return self._inbox.qsize()
~~~~~

#### Acts 3: 实现基准测试脚本 (`proto_direct_connect.py`)

该脚本将对比两种模式的每秒操作数 (OPS)。为了模拟真实负载，我们将创建 N 个消费者和 M 个生产者。

~~~~~act
write_file
observatory/protoplasm/networking/proto_direct_connect.py
~~~~~
~~~~~python
import asyncio
import time
import random
from typing import List
from cascade.connectors.local import LocalBusConnector
from .direct_channel import DirectChannel

# --- Configuration ---
NUM_ITERATIONS = 5000  # How many messages each producer sends
NUM_PRODUCERS = 100
NUM_CONSUMERS_PER_PRODUCER = 8 # Simulating Moore neighborhood (8 neighbors)

async def benchmark_local_bus():
    """
    Scenario A: Pub/Sub via LocalBusConnector.
    1 Producer publishes to a topic.
    8 Consumers subscribe to that topic.
    """
    print(f"\n--- Benchmarking LocalBus (Producers={NUM_PRODUCERS}, Fan-out={NUM_CONSUMERS_PER_PRODUCER}) ---")
    
    connector = LocalBusConnector()
    await connector.connect()
    
    # Setup Consumers
    # Each consumer is a queue attached to a subscription
    consumer_queues = []
    
    # We use a latch (Event) to signal completion
    completion_event = asyncio.Event()
    total_messages_received = 0
    expected_messages = NUM_PRODUCERS * NUM_ITERATIONS * NUM_CONSUMERS_PER_PRODUCER
    
    async def consumer_handler(topic, payload):
        nonlocal total_messages_received
        total_messages_received += 1
        if total_messages_received >= expected_messages:
            completion_event.set()

    # Subscribe 800 consumers (100 producers * 8)
    # To mimic grid, Producer I publishes to Topic I.
    # Consumers C_I_1 to C_I_8 subscribe to Topic I.
    # This is optimizing Bus usage (exact topic match is faster than wildcard).
    
    subs = []
    for i in range(NUM_PRODUCERS):
        topic = f"cell/{i}"
        for _ in range(NUM_CONSUMERS_PER_PRODUCER):
             sub = await connector.subscribe(topic, consumer_handler)
             subs.append(sub)

    # Producers
    start_time = time.perf_counter()
    
    async def producer(idx):
        topic = f"cell/{idx}"
        payload = {"data": "ping"}
        for _ in range(NUM_ITERATIONS):
            await connector.publish(topic, payload)
    
    producers = [producer(i) for i in range(NUM_PRODUCERS)]
    
    await asyncio.gather(*producers)
    
    # Wait for consumers to drain
    try:
        await asyncio.wait_for(completion_event.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        print(f"!! Timeout !! Received {total_messages_received}/{expected_messages}")
        
    duration = time.perf_counter() - start_time
    ops = expected_messages / duration
    print(f"LocalBus Result: {duration:.4f}s | Throughput: {ops:,.0f} msgs/sec")
    
    await connector.disconnect()


async def benchmark_direct_channel():
    """
    Scenario B: DirectChannel.
    1 Producer holds references to 8 Consumer Channels.
    It loops and calls send() on each.
    """
    print(f"\n--- Benchmarking DirectChannel (Producers={NUM_PRODUCERS}, Fan-out={NUM_CONSUMERS_PER_PRODUCER}) ---")

    # Setup Consumers
    # Each consumer is just a Channel
    # We flatten the structure: channels[producer_id][neighbor_index]
    consumer_channels = []
    for i in range(NUM_PRODUCERS):
        neighbors = [DirectChannel(f"p{i}_c{j}") for j in range(NUM_CONSUMERS_PER_PRODUCER)]
        consumer_channels.append(neighbors)
        
    completion_event = asyncio.Event()
    total_messages_received = 0
    expected_messages = NUM_PRODUCERS * NUM_ITERATIONS * NUM_CONSUMERS_PER_PRODUCER

    async def consumer_loop(channel: DirectChannel):
        nonlocal total_messages_received
        while True:
            await channel.recv()
            total_messages_received += 1
            if total_messages_received >= expected_messages:
                completion_event.set()
                break

    # Start 800 consumer loops
    all_consumers = []
    for group in consumer_channels:
        for channel in group:
            all_consumers.append(asyncio.create_task(consumer_loop(channel)))

    # Producers
    start_time = time.perf_counter()

    async def producer(idx):
        payload = {"data": "ping"}
        my_neighbors = consumer_channels[idx]
        for _ in range(NUM_ITERATIONS):
            # The "Bypass": Manual iteration
            for neighbor in my_neighbors:
                await neighbor.send(payload)

    producers = [producer(i) for i in range(NUM_PRODUCERS)]
    
    await asyncio.gather(*producers)

    # Wait for consumers to drain
    try:
        await asyncio.wait_for(completion_event.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        print(f"!! Timeout !! Received {total_messages_received}/{expected_messages}")

    duration = time.perf_counter() - start_time
    ops = expected_messages / duration
    print(f"DirectChannel Result: {duration:.4f}s | Throughput: {ops:,.0f} msgs/sec")
    
    # Cleanup
    for t in all_consumers:
        t.cancel()


async def main():
    print("🚀 Starting Networking Benchmark...")
    # Warmup
    await asyncio.sleep(1)
    
    await benchmark_local_bus()
    
    await asyncio.sleep(1)
    
    await benchmark_direct_channel()

if __name__ == "__main__":
    asyncio.run(main())
~~~~~

### 下一步建议
我们已经准备好了测试脚本。下一步是执行这个基准测试，观察输出数据。

预期的结果是 `DirectChannel` 的吞吐量应显著高于 `LocalBus`（可能在 2x 到 10x 之间），因为它是纯粹的 Python 协程切换，没有锁和字典查找的开销。这个数据将为我们在“创世网格”中采用混合通信架构（拓扑直连 + 随机采样总线）提供坚实的理论依据。
