import asyncio
from collections import deque, defaultdict
from typing import Deque, Set, List, Dict, Any

from cascade.spec.physics import DataNode, FuncNode
from .events import ReactorEvent, TokenGenerated, ExecutionFinished
from .model import Channel


class Reactor:
    def __init__(self, executor: Any):
        self.executor = executor
        self._event_queue: Deque[ReactorEvent] = deque()
        
        # Topology Indexes
        self._nodes: Set[Any] = set() # Track all known nodes
        self._channels_by_source: Dict[str, List[Channel]] = defaultdict(list)
        
        # Optimization: Map DataNode -> List[FuncNode] (Reverse dependency)
        # Used to quickly find which FuncNodes to check when a DataNode updates.
        self._downstream_map: Dict[str, List[FuncNode]] = defaultdict(list)
        
        # Dirty set for potential evaluation
        self._dirty_func_nodes: Set[FuncNode] = set()

    def register_node(self, node: Any):
        if node in self._nodes:
            return
        self._nodes.add(node)
        
        # Build reverse index for FuncNodes
        if isinstance(node, FuncNode):
            for port in node.inputs.values():
                if port.source:
                    self._downstream_map[port.source.name].append(node)

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
        3. Firing ready nodes.
        """
        # 1. Process Event Loop
        # We drain the queue completely to handle propagation chains within one step.
        while self._event_queue:
            event = self._event_queue.popleft()
            self._handle_event(event)

        # 2. Fire Ready Nodes
        # Iterate over a snapshot of dirty nodes
        ready_nodes = []
        for node in list(self._dirty_func_nodes):
            if node.is_ready():
                ready_nodes.append(node)
        
        self._dirty_func_nodes.clear()

        for node in ready_nodes:
            self._fire(node)

    def _handle_event(self, event: ReactorEvent):
        if isinstance(event, TokenGenerated):
            self._handle_token_generated(event)
        elif isinstance(event, ExecutionFinished):
            self._handle_execution_finished(event)

    def _handle_token_generated(self, event: TokenGenerated):
        # 1. Update State (Physics: Inject Energy)
        event.node.put(event.token)
        
        # 2. Mark downstream FuncNodes as dirty (Potential might have increased)
        downstream = self._downstream_map.get(event.node.name, [])
        for f_node in downstream:
            self._dirty_func_nodes.add(f_node)

    def _handle_execution_finished(self, event: ExecutionFinished):
        # Routing Logic
        channels = self._channels_by_source.get(event.node.name, [])
        
        for output_name, token in event.outputs.items():
            # Find matching channels for this output port
            for channel in channels:
                if channel.output_name == output_name and channel.match(token.tag):
                    # Route: Generate a TokenGenerated event for the target DataNode
                    # This queues the event for processing in the same step loop
                    self.push_event(TokenGenerated(node=channel.target, token=token))

    def _fire(self, node: FuncNode):
        # 1. Atomically consume inputs (Physics: Consume Energy)
        inputs = node.consume_inputs()
        
        # 2. Submit to Executor
        # Note: Executor is responsible for running the code and eventually
        # pushing an ExecutionFinished event back to the reactor.
        # For AsyncMock in tests, this call is synchronous.
        self.executor.submit(node, inputs)