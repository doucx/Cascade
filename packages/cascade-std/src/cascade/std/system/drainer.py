from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.spec.components import DrainerSpec
from cascade.spec.physics.binding import implements


@implements(DrainerSpec)
def drain_signal(io: DrainerSpec.IO, node: PhysicsNode, resources: Any) -> None:
    control_token = SystemControlToken(command=ControlCommand.DRAIN)
    io.out = Token(payload=control_token)
