from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


@dataclass
class Token:
    """
    The atomic carrier of information in the network.
    """
    payload: Any
    tag: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)


class AccessPolicy(Enum):
    """
    Defines behavior when writing to a full DataNode.
    """
    REJECT = auto()     # Raise an error (Blocking/Safety)
    OVERWRITE = auto()  # Overwrite old data (Register/Streaming)


class DataNode:
    """
    Stateful container for Tokens. Represents the 'Noun' in the physics model.
    """
    def __init__(
        self, 
        name: str, 
        capacity: int = 1, 
        policy: AccessPolicy = AccessPolicy.OVERWRITE
    ):
        self.name = name
        self.capacity = capacity
        self.policy = policy
        self._buffer: List[Token] = []

    def is_empty(self) -> bool:
        return len(self._buffer) == 0

    def is_excited(self) -> bool:
        return len(self._buffer) > 0

    def peek(self) -> Optional[Token]:
        if not self._buffer:
            return None
        return self._buffer[0]

    def put(self, token: Token) -> None:
        """
        Inject a token into the node. 
        Respects capacity and access policy.
        """
        if len(self._buffer) >= self.capacity:
            if self.policy == AccessPolicy.REJECT:
                raise BufferError(f"DataNode '{self.name}' is full (capacity={self.capacity})")
            elif self.policy == AccessPolicy.OVERWRITE:
                # Make room by dropping oldest elements
                while len(self._buffer) >= self.capacity:
                    self._buffer.pop(0)
        
        self._buffer.append(token)

    def take(self) -> Optional[Token]:
        """
        Consume and return the oldest token.
        """
        if not self._buffer:
            return None
        return self._buffer.pop(0)


from cascade.spec.topology import ChannelKind


@dataclass
class Port:
    """
    Connection point on a FuncNode, representing a dependency.
    """
    name: str
    kind: ChannelKind = ChannelKind.DATA
    source: Optional[DataNode] = None
    target: Optional[DataNode] = None


class FuncNode:
    """
    Stateless transformer. Represents the 'Verb' in the physics model.
    """
    def __init__(
        self, 
        name: str, 
        resource_requirements: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.resource_requirements = resource_requirements or {}
        self.inputs: Dict[str, Port] = {}
        self.outputs: Dict[str, Port] = {}

    def add_input(self, port: Port):
        self.inputs[port.name] = port

    def add_output(self, port: Port):
        self.outputs[port.name] = port

    def is_ready(self) -> bool:
        """
        Dual-Barrier Potential Check:
        Returns True if and only if ALL connected input ports have an excited source DataNode.
        """
        print(f"\n[is_ready CHECK for {self.name}]")
        if not self.inputs:
            print(" -> No inputs, node is ready.")
            return True  # A node with no inputs is always ready.

        all_ready = True
        for port in self.inputs.values():
            is_excited = port.source and port.source.is_excited()
            print(f" -> Port '{port.name}' ({port.kind.name}) source excited: {is_excited}")
            if not is_excited:
                all_ready = False
        
        print(f" -> Final is_ready result: {all_ready}")
        return all_ready

    def consume_inputs(self) -> Dict[str, Token]:
        """
        Atomically consumes tokens from all input sources, but only returns
        payloads from DATA channels.
        """
        result = {}
        for name, port in self.inputs.items():
            if port.source:
                token = port.source.take()
                # Only add to the result if it's a DATA port and a token was present
                if token and port.kind == ChannelKind.DATA:
                    result[name] = token
        return result

    def produce_outputs(self, tokens: Dict[str, Token]):
        """
        Push result tokens to output targets.
        """
        for name, token in tokens.items():
            if name in self.outputs:
                port = self.outputs[name]
                if port.target:
                    port.target.put(token)


class TerminatorNode(FuncNode):
    """
    Runtime representation of a termination point.
    When fired, it signals the Reactor to stop.
    """
    pass


class EmitterNode(FuncNode):
    """
    Runtime representation of an emission point.
    When fired, it pushes the payload of its input token to a registered Sink.
    """
    def __init__(
        self, 
        name: str, 
        sink_id: str,
        resource_requirements: Optional[Dict[str, Any]] = None
    ):
        super().__init__(name, resource_requirements)
        self.sink_id = sink_id
