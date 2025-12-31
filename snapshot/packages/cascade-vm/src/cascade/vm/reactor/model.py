from dataclasses import dataclass
from cascade.spec.physics import FuncNode, DataNode


@dataclass
class Channel:
    """
    Represents a directed connection from a FuncNode output port to a DataNode.
    Includes routing logic (tag filtering).
    """
    source: FuncNode
    target: DataNode
    output_name: str
    tag_filter: str = "default"

    def match(self, tag: str) -> bool:
        """
        Check if the token tag matches this channel's filter.
        """
        return self.tag_filter == tag