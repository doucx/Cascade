import asyncio
from collections import deque, defaultdict
from typing import Deque, Set, List, Dict, Any, Optional, Callable
from cascade.spec.physics import FuncNode, EmitterNode, Token
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel
from cascade.vm.protocols import ResourceManager
from cascade.spec.topology import ChannelKind


class Reactor:
    def __init__(
        self, executor: Any, resource_manager: Optional[ResourceManager] = None
    ):
        self.executor = executor
        self.resource_manager = resource_manager
        self._event_queue: Deque[ReactorEvent] = deque()

        # External world interfaces
        self._sinks: Dict[str, Callable] = {}

        # Topology Indexes
        self._nodes: Set[Any] = set()
        self._channels_by_source: Dict[str, List[Channel]] = defaultdict(list)
        self._downstream_map: Dict[str, List[FuncNode]] = defaultdict(list)

        # State Sets
        self._dirty_func_nodes: Set[FuncNode] = set()
        self._pending_on_resource: Set[FuncNode] = set()

        # Run Control
        self._is_running = False
        self._activity_signal = asyncio.Event()

    def register_sink(self, sink_id: str, callback: Callable):
        """Registers an external sink (callback) for EmitterNodes."""
        self._sinks[sink_id] = callback

    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)

        if isinstance(node, FuncNode):
            for port in node.inputs.values():
                if port.source:
                    self._downstream_map[port.source.name].append(node)

            for port_name, port in node.outputs.items():
                if port.target:
                    existing = any(
                        c.output_name == port_name and c.match("default")
                        for c in self._channels_by_source.get(node.name, [])
                    )
                    if not existing:
                        default_channel = Channel(
                            source=node,
                            target=port.target,
                            output_name=port_name,
                            tag_filter="default",
                        )
                        self.register_channel(default_channel)

    def register_channel(self, channel: Channel):
        self._channels_by_source[channel.source.name].append(channel)
        self.register_node(channel.source)
        self.register_node(channel.target)

    def push_event(self, event: ReactorEvent):
        """Pushes an event to the queue and wakes up the run loop if it's waiting."""
        self._event_queue.append(event)
        self._activity_signal.set()

    def _has_pending_work(self) -> bool:
        """Checks if there's any immediate work to be done."""
        return bool(
            self._event_queue or self._dirty_func_nodes or self._pending_on_resource
        )

    async def run(self):
        """Continuously runs the reactor loop until stop() is called."""
        self._is_running = True
        while self._is_running:
            await self.step()

            # If step() resulted in more immediate work, loop again without waiting.
            if self._has_pending_work():
                continue

            # If no more work, wait for a new event to arrive.
            await self._activity_signal.wait()
            self._activity_signal.clear()

    def stop(self):
        """Stops the reactor's run loop gracefully."""
        self._is_running = False
        self._activity_signal.set()

    async def step(self):
        """
        Advance the reactor by one atomic "tick".

        A tick is a full reaction to the current state, processing all immediately
        available events and firing all ready nodes until no more immediate work
        can be done. It does not wait for long-running tasks to complete.
        """
        while True:
            progress_made = False

            # 1. Process all pending events
            if self._event_queue:
                while self._event_queue:
                    event = self._event_queue.popleft()
                    await self._handle_event(event)
                progress_made = True

            # 2. Evaluate Candidates
            # Candidates are newly dirty nodes + any previously pending nodes
            # We include pending nodes because an event (e.g. resource release) might have unblocked them.
            candidates = self._dirty_func_nodes.union(self._pending_on_resource)

            # Reset sets for this iteration.
            # Nodes that fail to fire will be added back to _pending_on_resource.
            self._dirty_func_nodes.clear()
            self._pending_on_resource.clear()

            if not candidates:
                if not progress_made:
                    # Stable state reached: No events processed, no candidates to check.
                    break
                else:
                    # Events were processed, loop again to check if they triggered anything new
                    continue

            fire_tasks = []

            for node in candidates:
                if not node.is_ready():
                    continue

                # Resource Check (Potential Barrier)
                can_fire = True
                if self.resource_manager and node.resource_requirements:
                    if self.resource_manager.can_acquire(node.resource_requirements):
                        await self.resource_manager.acquire(node.resource_requirements)
                    else:
                        can_fire = False
                        # Resource barrier not met, keep it pending.
                        self._pending_on_resource.add(node)

                if can_fire:
                    fire_tasks.append(self._fire(node))

            if fire_tasks:
                # Await submission to ensure deterministic behavior (e.g. for testing mocks).
                # This does NOT wait for the task itself to finish, just for the submission to the executor.
                await asyncio.gather(*fire_tasks)
                progress_made = True

            # Termination Condition:
            # If we processed candidates but fired nothing (all blocked), and processed no events,
            # we are in a resource-constrained block or stable state. Stop stepping to avoid busy loop.
            if not progress_made:
                break

    async def _handle_event(self, event: ReactorEvent):
        if isinstance(event, TokenGenerated):
            self._handle_token_generated(event)
        elif isinstance(event, ExecutionFinished):
            await self._handle_execution_finished(event)

    def _handle_token_generated(self, event: TokenGenerated):
        # 1. Update State (Physics: Inject Energy)
        event.node.put(event.token)

        # 2. Mark downstream FuncNodes as dirty (Potential might have increased)
        downstream = self._downstream_map.get(event.node.name, [])
        for f_node in downstream:
            self._dirty_func_nodes.add(f_node)

    async def _handle_execution_finished(self, event: ExecutionFinished):
        # 1. Release Resources
        if self.resource_manager and event.node.resource_requirements:
            await self.resource_manager.release(event.node.resource_requirements)
            # Optimization hint: Releasing resources might wake up pending nodes.
            # In Phase 4.2, we might explicitly trigger a wake-up here.
            # For now, the next step() call will re-evaluate _pending_on_resource.

        # 2. Routing Logic
        channels = self._channels_by_source.get(event.node.name, [])

        for output_name, token in event.outputs.items():
            # Find matching channels for this output port
            for channel in channels:
                if channel.output_name == output_name and channel.match(token.tag):
                    # Route: Generate a TokenGenerated event for the target DataNode
                    if channel.kind == ChannelKind.SIGNAL:
                        # For signal channels, create a new, payload-less token
                        signal_token = Token(
                            payload=None, tag=token.tag, metadata=token.metadata
                        )
                        self.push_event(
                            TokenGenerated(node=channel.target, token=signal_token)
                        )
                    else:
                        # For data channels, pass the original token
                        self.push_event(
                            TokenGenerated(node=channel.target, token=token)
                        )

    async def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()

        # 2. Handle Intrinsic Nodes (not submitted to executor)
        if isinstance(node, EmitterNode):
            sink = self._sinks.get(node.sink_id)
            if sink:
                # Emitter assumes a single input token for simplicity
                # We find the first token from the consumed inputs
                input_token = next(iter(inputs.values()), None)
                if input_token:
                    sink(input_token.payload)

            # CRITICAL: After emitting, fire a completion event to trigger downstream
            # nodes (like a chained terminator). We use the default 'result' output
            # as a signal port.
            signal_token = Token(payload=True, tag="default")
            self.push_event(
                ExecutionFinished(node=node, outputs={"result": signal_token})
            )
            return

        # 3. Submit to Executor
        await self.executor.submit(node, inputs)
