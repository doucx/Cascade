简要回答：
测试结果异常。`DirectChannel` 遭遇了严重的超时问题，且吞吐量反而低于 `LocalBus`。
分析显示：`!! Timeout !! Received 80000/4000000`。
这意味着 `DirectChannel` 的消费者几乎没有工作（80,000 条消息恰好等于 800 个通道 * 100 容量，即所有消息都堆积在 Queue 中，消费者没有取出）。

**根源分析**：
这是一个典型的 **事件循环饿死 (Event Loop Starvation)** 问题。
在 `benchmark_direct_channel` 中，Producers 是紧密循环 (`for _ in range(NUM_ITERATIONS): for neighbor...`)。因为 `DirectChannel.send` 使用的是 `put_nowait`（非阻塞同步调用），整个 Producer 循环在 `asyncio` 看来是一个同步块（或者极少让出控制权）。
结果是，Producer 霸占了 CPU，填满了所有 Queue，直到它们抛出 `QueueFull`（我们在代码中 `pass` 掉了这个异常），而 Consumer 的 `await channel.recv()` 协程从未获得执行机会去清空 Queue。

相比之下，`LocalBus.publish` 内部虽然也是 `put_nowait`，但其内部的锁机制或其他 `await` 点可能隐式地提供了让步机会，或者其开销本身导致了自然的节奏变慢。

**修正方案**：
1.  **主动让步**：在 Producer 的 `send` 循环中，或者在 `DirectChannel.send` 内部，必须加入 `await asyncio.sleep(0)` 来强制让出控制权，模拟真实世界中 Agent 的计算间隔。
2.  **容量控制**：基准测试不应忽略 `QueueFull`。如果满了，Producer 应该等待 (`await put()`) 而不是丢弃，这才是公平的吞吐量测试。

摘要头：
## [WIP] fix: 修复 DirectChannel 基准测试中的事件循环饿死问题

### 标签
#intent/fix #flow/ready #priority/high
#comp/observatory #concept/async #scope/core
#ai/instruct
#task/domain/networking
#task/object/direct-channel
#task/action/bug-fix
#task/state/continue

### 用户需求
1.  **修复基准测试逻辑**：修正 `benchmark_direct_channel` 中的饿死现象，确保消费者有机会处理消息。
2.  **实现公平对比**：将 `DirectChannel.send` 改为标准的 `await queue.put()` 以处理背压，或者在 Producer 中添加 `await asyncio.sleep(0)`。考虑到我们要测试吞吐量极限，使用 `await queue.put()` 是更符合“无损传输”要求的做法。
3.  **重新校准参数**：400万条消息对于单线程 Python 还是有点重，如果加上 `await` 切换开销，时间会变长。我们将 `NUM_ITERATIONS` 调整为 1000 以获得更快的反馈。

### 评论
这个失败是非常有价值的“反面教材”。它揭示了在 Python `asyncio` 中，"Direct" 并不总是意味着快。如果没有 IO 等待（`await`），单一的协程可以轻易阻塞整个世界。为了公平对比，我们必须让 `DirectChannel` 表现得像一个真正的异步通道，即处理背压。

### 目标
*   修改 `direct_channel.py`，将 `put_nowait` 改为 `await put`。
*   修改 `proto_direct_connect.py`，减少迭代次数，确保测试能在合理时间内完成。

### 基本原理
*   **背压 (Backpressure)**：当消费者处理不过来时，生产者必须减速。`await queue.put()` 天然实现了这一点。这不仅解决了饿死问题，也使得吞吐量测试更加真实——它测量的是系统在背压平衡下的最大处理能力。

---

### Script

#### Acts 1: 修正 `DirectChannel` 为异步阻塞模式

~~~~~act
patch_file
observatory/protoplasm/networking/direct_channel.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
    async def send(self, payload: Any):
        """
        Directly puts a message into the channel. Zero-copy.
        """
        # 1. Core Logic: Direct Delivery
        # We use await put() to handle backpressure and ensure fair scheduling.
        # This prevents the producer from starving the consumer loop.
        await self._inbox.put(payload)

        # 2. Telemetry Probe (The "Leak")
~~~~~

#### Acts 2: 调整基准测试参数与逻辑

减少迭代次数，修正预期行为。

~~~~~act
patch_file
observatory/protoplasm/networking/proto_direct_connect.py
~~~~~
~~~~~python
# --- Configuration ---
NUM_ITERATIONS = 5000  # How many messages each producer sends
NUM_PRODUCERS = 100
NUM_CONSUMERS_PER_PRODUCER = 8 # Simulating Moore neighborhood (8 neighbors)

async def benchmark_local_bus():
~~~~~
~~~~~python
# --- Configuration ---
NUM_ITERATIONS = 1000  # Reduced for quicker feedback loop
NUM_PRODUCERS = 100
NUM_CONSUMERS_PER_PRODUCER = 8 # Simulating Moore neighborhood (8 neighbors)

async def benchmark_local_bus():
~~~~~

### 下一步建议
再次运行 `python -m observatory.protoplasm.networking.proto_direct_connect`。

这一次，`DirectChannel` 应该能正确跑完，并显示出比 `LocalBus` 更高的吞吐量，因为它省去了 Topic 匹配、列表查找和锁的开销，仅保留了最纯粹的 `Queue` 操作和协程切换成本。
