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