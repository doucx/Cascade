from typing import Dict, ClassVar
from .core import PortDef, PortDirection


class PhysicsSpecMeta(type):
    input_ports: Dict[str, PortDef]
    output_ports: Dict[str, PortDef]

    def __new__(mcs, name, bases, namespace):
        # 1. Create the class
        cls = super().__new__(mcs, name, bases, namespace)

        input_ports: Dict[str, PortDef] = {}
        output_ports: Dict[str, PortDef] = {}

        # 2. Inherit ports from base classes (if any)
        # We traverse bases in reverse order so that later bases (and the class itself) override earlier ones.
        for base in reversed(bases):
            if hasattr(base, "input_ports"):
                input_ports.update(base.input_ports)
            if hasattr(base, "output_ports"):
                output_ports.update(base.output_ports)

        # 3. Collect ports from the current class definition
        for key, value in namespace.items():
            if isinstance(value, PortDef):
                # The key in the dict is the attribute name (e.g. 'ledger_in').
                # The value.name is the actual string name of the port (e.g. "ledger_in").
                # Usually they are the same, but the dict allows access by attribute name.
                if value.direction == PortDirection.INPUT:
                    input_ports[key] = value
                else:
                    output_ports[key] = value

        # 4. Register the collected ports
        cls.input_ports = input_ports
        cls.output_ports = output_ports

        return cls


class PhysicsSpec(metaclass=PhysicsSpecMeta):
    input_ports: ClassVar[Dict[str, PortDef]]
    output_ports: ClassVar[Dict[str, PortDef]]
