from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Set


class SourceType(Enum):
    USER = "user"
    TOOL = "tool"
    SYSTEM = "system"

@dataclass
class Source:
    type: SourceType
    identifier: Optional[str] = None
    inner_source: Optional["Source"] = None

@dataclass
class Capability:
    """ tracks access control and data provenance """
    sources: List[Source] = field(default_factory=list)

    def merge_with(self, other: 'Capability') -> 'Capability':
        merged_sources = self.sources + other.sources
        return Capability(sources=merged_sources)

@dataclass
class CapabilityValue:
    """ wraps a value with its capability """
    value: Any = None
    capability: Capability = field(default_factory=Capability)
    dependencies: Set['CapabilityValue'] = field(default_factory=set)

    def __repr__(self):
        return f"CapabilityValue({self.value}, sources={[s.type.value for s in self.capability.sources]})"
    
    def __hash__(self):
        return id(self)
    
    def __eq__(self, other):
        if not isinstance(other, CapabilityValue):
            return False
        return id(self) == id(other)