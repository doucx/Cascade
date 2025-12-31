import asyncio
from collections import deque, defaultdict
from typing import Deque, Set, List, Dict, Any, Optional
from cascade.spec.physics import DataNode, FuncNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel
from cascade.vm.protocols import ResourceManager


class Reactor:
    def __init__(self, executor: Any, resource_manager: Optional[ResourceManager] = None):
        self.executor = executor
        self.resource_manager = resource_manager
        self._event_queue: Deque[ReactorEvent] = deque()
        
        # Topology Indexes
        self._nodes: Set[Any] = set() # Track all known nodes
        self._channels_by_source: Dict[str, List[Channel]] = defaultdict(list)
        
        # Optimization: Map DataNode -> List[FuncNode] (Reverse dependency)
        # Used to quickly find which FuncNodes to check when a DataNode updates.
        self._downstream_map: Dict[str, List[FuncNode]] = defaultdict(list)
        
        # Dirty set for potential evaluation
        self._dirty_func_nodes: Set[FuncNode] = set()
        
        # Pending set for nodes blocked by resources (Phase 4.2 foundation)
        self._pending_on_resource: Set[FuncNode] = set()

    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)
        
        # Build reverse index for FuncNodes and Auto-discover Channels
        if isinstance(node, FuncNode):
            # 1. Reverse dependency map (DataNode -> Downstream FuncNodes)
            for port in node.inputs.values():
                if port.source:
                    self._downstream_map[port.source.name].append(node)
            
            # 2. Auto-discover Output Channels (Physics -> Routing)
            # If a port is connected to a DataNode physically, implies a default channel.
            for port_name, port in node.outputs.items():
                if port.target:
                    # Check if a channel already exists for this path to avoid duplicates
                    # or overriding explicit custom channels.
                    existing = any(
                        c.output_name == port_name and c.match("default")
                        for c in self._channels_by_source.get(node.name, [])
                    )
                    if not existing:
                        # Create implicit default channel
                        default_channel = Channel(
                            source=node,
                            target=port.target,
                            output_name=port_name,
                            tag_filter="default"
                        )
                        self.register_channel(default_channel)

    def register_channel(self, channel: Channel):
        self._channels_by_source[channel.source.name].append(channel)
        # Ensure nodes are registered
        self.register_node(channel.source)
        self.register_node(channel.target)

    def push_event(self, event: ReactorEvent):
        self._event_queue.append(event)

    async def step(self):
        """
        Advance the reactor by one "tick".
        A tick consists of:
        1. Processing all pending events (State Updates & Routing).
           - This includes cascading events generated during processing.
        2. Evaluating potentials of affected (dirty) nodes.
        3. Firing ready nodes (if resources allow).
        """
        # 1. Process Event Loop
        while self._event_queue:
            event = self._event_queue.popleft()
            await self._handle_event(event)

        # 2. Evaluate Potentials
        # We process both new dirty nodes AND nodes previously pending on resources
        candidates = self._dirty_func_nodes.union(self._pending_on_resource)
        
        # Reset sets for this tick
        self._dirty_func_nodes.clear()
        self._pending_on_resource.clear()

        fire_tasks = []
        
        for node in candidates:
            if not node.is_ready():
                continue
                
            # Resource Check (Potential Barrier)
            if self.resource_manager and node.resource_requirements:
                if self.resource_manager.can_acquire(node.resource_requirements):
                    # Immediate acquisition to prevent over-commitment in this loop
                    # Note: can_acquire is synchronous, but acquire is async.
                    # Since we verified with can_acquire, acquire should not block significantly
                    # unless another process stole resources (unlikely in this single-threaded loop).
                    await self.resource_manager.acquire(node.resource_requirements)
                    fire_tasks.append(self._fire(node))
                else:
                    # Resource barrier not met, keep pending
                    self._pending_on_resource.add(node)
            else:
                # No resource constraints
                fire_tasks.append(self._fire(node))

        if fire_tasks:
            # Concurrently execute all fired nodes
            await asyncio.gather(*fire_tasks)

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
                    self.push_event(TokenGenerated(node=channel.target, token=token))

    async def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Submit to Executor
        await self.executor.submit(node, inputs)
