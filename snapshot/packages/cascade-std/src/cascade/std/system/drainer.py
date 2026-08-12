from typing import Any

from cascade.spec.components import DrainerSpec
from cascade.spec.physical.nodes import PhysicsNode, Token
from cascade.spec.physics.binding import implements
from cascade.spec.runtime.system import ControlCommand, SystemControlToken


@implements(DrainerSpec)
def drain_signal(io: DrainerSpec.IO, node: PhysicsNode, resources: Any) -> None:
    control_token = SystemControlToken(command=ControlCommand.DRAIN)
    io.out = Token(payload=control_token)
