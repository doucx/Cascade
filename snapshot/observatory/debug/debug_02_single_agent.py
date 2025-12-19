import asyncio
import time
import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource
from observatory.agents.kuramoto import firefly_agent

async def main():
    print("--- Debug 02: Single Agent Test ---")
    
    # 1. Setup Environment
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # 2. Setup Monitor (Log flashes)
    async def on_flash(topic, payload):
        print(f"   >>> FLASH DETECTED! Payload: {payload}")
    await connector.subscribe("firefly/flash", on_flash)

    # 3. Setup Engine (Isolated mode)
    @resource(name="_internal_connector", scope="run")
    def shared_connector_provider():
        yield connector

    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=cs.MessageBus(),
        connector=None,
    )
    engine.register(shared_connector_provider)

    # 4. Create Agent
    # Very short period (1.0s) so we don't wait long
    print("   Creating agent with period=1.0s...")
    agent_wf = firefly_agent(
        agent_id=99,
        initial_phase=0.0,
        period=1.0, 
        nudge=0.1,
        flash_topic="firefly/flash",
        listen_topic="firefly/flash",
    )

    # 5. Run for 3 seconds
    print("   Starting Engine run...")
    task = asyncio.create_task(engine.run(agent_wf))
    
    try:
        start = time.time()
        # It should flash at least twice in 3 seconds
        await asyncio.wait_for(task, timeout=3.0) 
    except asyncio.TimeoutError:
        print("   Runtime finished (Timeout as expected for infinite loop).")
    except Exception as e:
        print(f"   ERROR: {e}")
    finally:
        await connector.disconnect()
        print(f"   Done. Elapsed: {time.time() - start:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())