import asyncio
from cascade.connectors.local import LocalBusConnector

async def main():
    print("--- Debug 01: Raw Bus Test ---")
    
    # 1. Setup
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()
    print("[1] Connector connected.")

    # 2. Define a subscriber
    received = asyncio.Event()
    
    async def on_message(topic, payload):
        print(f"[3] Received message on {topic}: {payload}")
        received.set()

    # 3. Subscribe
    await connector.subscribe("test/topic", on_message)
    print("[2] Subscribed.")

    # 4. Publish (Simulate a firefly flash)
    print("[4] Publishing...")
    await connector.publish("test/topic", {"msg": "hello"})

    # 5. Wait for receipt
    try:
        await asyncio.wait_for(received.wait(), timeout=2.0)
        print("[5] SUCCESS: Message received.")
    except asyncio.TimeoutError:
        print("[5] FAILURE: Timed out waiting for message.")
    
    await connector.disconnect()

if __name__ == "__main__":
    asyncio.run(main())