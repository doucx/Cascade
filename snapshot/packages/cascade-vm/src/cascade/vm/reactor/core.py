import asyncio
from collections import deque, defaultdict
from typing import Deque, Set, List, Dict, Any, Optional

from cascade.spec.physics import DataNode, FuncNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel


class Reactor:
    def __init__(self, executor: Any, resource_manager: Optional[Any] = None):
        self.executor = executor
        self.resource_manager = resource_manager
        self._event_queue: Deque[ReactorEvent] = deque()
        
        # Topology Indexes
        self._nodes: Set[Any] = set()
        self._channels_by_source: Dict[str, List[Channel]] = defaultdict(list)
        self._downstream_map: Dict[str, List[FuncNode]] = defaultdict(list)
        
        # State Sets
        self._dirty_func_nodes: Set[FuncNode] = set()
        self._pending_on_resource: Set[FuncNode] = set()
        self._in_flight_reqs: Dict[FuncNode, Dict[str, Any]] = {}

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
                            tag_filter="default"
                        )
                        self.register_channel(default_channel)

    def register_channel(self, channel: Channel):
        self._channels_by_source[channel.source.name].append(channel)
        self.register_node(channel.source)
        self.register_node(channel.target)

    def push_event(self, event: ReactorEvent):
        self._event_queue.append(event)

    async def step(self):
        # 1. Process Event Loop
        while self._event_queue:
            event = self._event_queue.popleft()
            await self._handle_event(event)

        # 2. Evaluate Potentials
        # Move pending nodes back to dirty set for re-evaluation (Wake-up)
        self._dirty_func_nodes.update(self._pending_on_resource)
        self._pending_on_resource.clear()

        ready_to_fire = []
        still_dirty = set()

        for node in self._dirty_func_nodes:
            if not node.is_ready():
                still_dirty.add(node)
                continue

            # Resource Check
            requirements = getattr(node, 'resource_requirements', {})
            if self.resource_manager and not self.resource_manager.can_acquire(requirements):
                self._pending_on_resource.add(node)
            else:
                ready_to_fire.append((node, requirements))
        
        self._dirty_func_nodes = still_dirty
        
        # 3. Fire Ready Nodes
        if ready_to_fire:
            fire_tasks = [self._fire(node, reqs) for node, reqs in ready_to_fire]
            await asyncio.gather(*fire_tasks)

    async def _handle_event(self, event: ReactorEvent):
        if isinstance(event, TokenGenerated):
            self._handle_token_generated(event)
        elif isinstance(event, ExecutionFinished):
            await self._handle_execution_finished(event)

    def _handle_token_generated(self, event: TokenGenerated):
        event.node.put(event.token)
        downstream = self._downstream_map.get(event.node.name, [])
        for f_node in downstream:
            self._dirty_func_nodes.add(f_node)

    async def _handle_execution_finished(self, event: ExecutionFinished):
        # 1. Release Resources, which implicitly triggers wake-up on next step
        if self.resource_manager and event.node in self._in_flight_reqs:
            requirements = self._in_flight_reqs.pop(event.node)
            await self.resource_manager.release(requirements)

        # 2. Routing Logic
        channels = self._channels_by_source.get(event.node.name, [])
        for output_name, token in event.outputs.items():
            for channel in channels:
                if channel.output_name == output_name and channel.match(token.tag):
                    self.push_event(TokenGenerated(node=channel.target, token=token))

    async def _fire(self, node: FuncNode, requirements: Dict[str, Any]):
        # 1. Acquire Resources
        if self.resource_manager and requirements:
            await self.resource_manager.acquire(requirements)
            self._in_flight_reqs[node] = requirements

        # 2. Atomically consume inputs
        inputs = node.consume_inputs()
        
        # 3. Submit to Executor
        await self.executor.submit(node, inputs)