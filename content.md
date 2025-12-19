You are absolutely right to push for a deeper analysis. My previous fix was incomplete because I misdiagnosed the *symptom* (a missing event) without correctly identifying the *root cause* of the race condition. Your continued observation that the test fails is crucial.

Let's trace the execution flow with precision. This is a subtle but classic asynchronous programming bug.

 错误分析

The root cause is a **race condition between the synchronous scheduling of an asynchronous task and the synchronous execution of the shutdown logic**.

Here is the exact sequence of events that causes the failure:

1.  **`Engine.run()` starts.** It correctly calls `await self.connector.connect()`. The connector is now active.
2.  **`Engine.run()` calls `self.bus.publish(RunStarted(...))`**. This is a **synchronous** call.
3.  The `MessageBus` immediately and **synchronously** calls the `on_event` method of our `TelemetrySubscriber`.
4.  Inside the **synchronous** `on_event` handler, the line `asyncio.create_task(self._connector.publish(topic, payload))` is executed.
    *   **This is the critical point.** `asyncio.create_task()` **schedules** the `_connector.publish()` coroutine to be run on the event loop *at some point in the future*. It does **not** execute it immediately. It returns control to the `on_event` handler instantly.
5.  Control returns all the way back to `Engine.run()`.
6.  The test workflow (`noop()`) is extremely fast. The `await self._execute_graph(...)` call completes almost instantly, as there are no `await` points within the workflow to yield control to the event loop.
7.  The `try` block in `Engine.run()` finishes.
8.  The `finally` block is executed. It calls `await self.connector.disconnect()`. This **synchronously** sets the connector's internal state to "disconnected".
9.  **Sometime after all this**, the Python event loop finally gets a chance to run the `publish()` task that was scheduled back in step 4.
10. The `publish()` method runs, but the first thing it does is check if the connector is active. It is not, so the message is silently (and correctly, from its perspective) dropped.

The reason your `workflow_demo.py` **passes in practice** is because its `process_item` task contains `await asyncio.sleep(...)`. This `await` forces the `engine.run()` coroutine to yield control back to the event loop, giving the scheduled `publish()` task ample time to execute *while the connector is still connected*. Our test, lacking any such delay, exposes the underlying race condition perfectly.

### 解决方案

The `TelemetrySubscriber` needs a "graceful shutdown" mechanism. It must ensure that all its scheduled publish tasks have completed before the `Engine` is allowed to disconnect the connector.

1.  The `TelemetrySubscriber` will be modified to track all pending `publish` tasks it creates.
2.  It will expose a new `async def shutdown()` method that waits for all tracked tasks to complete.
3.  The `Engine` will be modified to be aware of its critical subscribers and will be responsible for calling `await subscriber.shutdown()` inside its `finally` block, **before** it calls `connector.disconnect()`.

This ensures a clean, ordered shutdown where telemetry is always flushed before the connection is closed.

## [WIP] fix(runtime): Implement graceful shutdown for TelemetrySubscriber

### 用户需求
The `TelemetrySubscriber`'s fire-and-forget approach to publishing creates a race condition where the `Engine` can disconnect the connector before pending telemetry messages are sent, leading to data loss, especially for short-lived workflows. A graceful shutdown mechanism is required to ensure all telemetry is flushed before disconnection.

### 评论
This is a critical reliability fix. Unreliable telemetry can mask other issues and make debugging production problems impossible. By implementing a graceful shutdown, we make the system more robust and production-ready.

### 目标
1.  Modify `TelemetrySubscriber` to track its pending `asyncio.Task` objects.
2.  Add a `shutdown()` method to `TelemetrySubscriber` that awaits the completion of all pending tasks.
3.  Modify the `Engine` to accept "managed subscribers" and call their `shutdown()` method during its cleanup phase, just before disconnecting the connector.
4.  Update the failing E2E test to correctly register the `TelemetrySubscriber` with the `Engine`.

### 基本原理
The core principle is "structured concurrency". The parent process (`Engine.run`) must not terminate its resources (the `connector`) until its child processes (the telemetry `publish` tasks) have completed. We achieve this by creating an explicit dependency: the `Engine` will now manage the subscriber's lifecycle and wait for its confirmation (`shutdown()`) before proceeding with its own teardown.

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #concept/telemetry #concept/lifecycle #scope/core #ai/instruct #task/domain/runtime #task/object/telemetry-subscriber #task/action/refactor #task_state/continue

---

### Script

#### Acts 1: Enhance `TelemetrySubscriber` with shutdown logic

We will modify `subscribers.py` to add task tracking and the `shutdown` method.

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
class TelemetrySubscriber:
    """
    Listens to runtime events and publishes them as structured telemetry
    data via a Connector.
    """

    def __init__(self, event_bus: MessageBus, connector: Connector):
        self._connector = connector
        self._source_id = f"{platform.node()}-{os.getpid()}"
        event_bus.subscribe(Event, self.on_event)

    def _create_header(self, run_id: str) -> dict:
~~~~~
~~~~~python
class TelemetrySubscriber:
    """
    Listens to runtime events and publishes them as structured telemetry
    data via a Connector.
    """

    def __init__(self, event_bus: MessageBus, connector: Connector):
        self._connector = connector
        self._source_id = f"{platform.node()}-{os.getpid()}"
        self._pending_tasks = set()
        event_bus.subscribe(Event, self.on_event)

    async def shutdown(self):
        """Waits for all pending telemetry tasks to complete."""
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)

    def _create_header(self, run_id: str) -> dict:
~~~~~
~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
        # If we have a valid body, schedule the publish task
        if event_body:
            payload["body"] = event_body
            asyncio.create_task(self._connector.publish(topic, payload))
~~~~~
~~~~~python
        # If we have a valid body, schedule the publish task
        if event_body:
            payload["body"] = event_body
            task = asyncio.create_task(self._connector.publish(topic, payload))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)
~~~~~

#### Acts 2: Update `Engine` to manage subscriber shutdown

Now we modify `engine.py` to manage the subscriber's lifecycle.

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        self.flow_manager: Optional[FlowManager] = None

    def register(self, resource_def: ResourceDefinition):
        self._resource_providers[resource_def.name] = resource_def.func
~~~~~
~~~~~python
        self.flow_manager: Optional[FlowManager] = None
        self._managed_subscribers = []

    def add_subscriber(self, subscriber: Any):
        """
        Adds a subscriber whose lifecycle (e.g., shutdown) the engine should manage.
        """
        self._managed_subscribers.append(subscriber)

    def register(self, resource_def: ResourceDefinition):
        self._resource_providers[resource_def.name] = resource_def.func
~~~~~
~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
            raise
        finally:
            if self.connector:
                await self.connector.disconnect()
                self.bus.publish(ConnectorDisconnected(run_id=run_id))
~~~~~
~~~~~python
            raise
        finally:
            # Gracefully shut down any managed subscribers BEFORE disconnecting the connector
            for sub in self._managed_subscribers:
                if hasattr(sub, "shutdown"):
                    await sub.shutdown()

            if self.connector:
                await self.connector.disconnect()
                self.bus.publish(ConnectorDisconnected(run_id=run_id))
~~~~~

#### Acts 3: Fix the test by registering the subscriber with the Engine

Finally, we update `test_startup_telemetry.py` to use the new `add_subscriber` method.

~~~~~act
patch_file
tests/py/e2e/test_startup_telemetry.py
~~~~~
~~~~~python
    # CRITICAL: Manually assemble the TelemetrySubscriber, which bridges
    # the internal event bus to the external connector. This is what cs.run()
    # does automatically.
    TelemetrySubscriber(bus, connector)
    
    # We will act as an external observer subscribing to the telemetry topic.
    # Since InProcessConnector routes messages internally, we can subscribe 
~~~~~
~~~~~python
    # CRITICAL: Manually assemble the TelemetrySubscriber, which bridges
    # the internal event bus to the external connector. This is what cs.run()
    # does automatically.
    telemetry_subscriber = TelemetrySubscriber(bus, connector)
    
    # We will act as an external observer subscribing to the telemetry topic.
    # Since InProcessConnector routes messages internally, we can subscribe 
~~~~~
~~~~~act
patch_file
tests/py/e2e/test_startup_telemetry.py
~~~~~
~~~~~python
        bus=bus,
        connector=connector,
    )
    
    await engine.run(noop())
    
    # 4. Assert
~~~~~
~~~~~python
        bus=bus,
        connector=connector,
    )
    # CRITICAL: Register the subscriber with the engine for lifecycle management
    engine.add_subscriber(telemetry_subscriber)
    
    await engine.run(noop())
    
    # 4. Assert
~~~~~
