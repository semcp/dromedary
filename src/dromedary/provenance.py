from typing import Any, Dict, List, Union, Iterable
from .capability import CapabilityValue, Capability, Source, SourceType


class ProvenanceManager:
    """Centralizes all creation and management of CapabilityValue objects."""
    
    def literal(self, value: Any) -> CapabilityValue:
        """Creates a CapabilityValue from a user-defined literal."""
        source = Source(type=SourceType.USER, identifier="literal")
        return self._create_capability_value(value, sources=[source])
    
    def from_tool(self, value: Any, tool_name: str) -> CapabilityValue:
        """Creates a CapabilityValue from a tool's output."""
        source = Source(type=SourceType.TOOL, identifier=tool_name)
        return self._create_capability_value(value, sources=[source])
    
    def from_system(self, value: Any, identifier: str = "dromedary") -> CapabilityValue:
        """Creates a CapabilityValue from a system source."""
        source = Source(type=SourceType.SYSTEM, identifier=identifier)
        return self._create_capability_value(value, sources=[source])
    
    def from_computation(self, value: Any, dependencies: Union[List[CapabilityValue], Dict[int, CapabilityValue]]) -> CapabilityValue:
        """Creates a CapabilityValue from a system computation (e.g., bin op, attribute access)."""
        if isinstance(dependencies, list):
            dependencies_dict = {}
            for dep in dependencies:
                if isinstance(dep, CapabilityValue):
                    dependencies_dict[id(dep)] = dep
            dependencies = dependencies_dict
        
        merged_deps, merged_sources = self._merge_dependencies_and_sources(dependencies)
        
        # Add a system source to show a computation happened
        system_source = Source(type=SourceType.SYSTEM, identifier="dromedary")
        system_key = (system_source.type, system_source.identifier)
        
        sources_dict = {}
        for source in merged_sources:
            source_key = (source.type, source.identifier)
            sources_dict[source_key] = source
        
        sources_dict[system_key] = system_source
        sources = list(sources_dict.values())
        
        return self._create_capability_value(value, sources=sources, dependencies=merged_deps)
    
    def merge_capabilities(self, *cap_values: CapabilityValue) -> CapabilityValue:
        """Merge multiple CapabilityValues into one with combined provenance."""
        if not cap_values:
            return self.from_system(None)
        
        # Take the first value as the primary value
        primary_value = cap_values[0].value if cap_values else None
        
        all_dependencies = {}
        all_sources_dict = {}
        
        for val in cap_values:
            if isinstance(val, CapabilityValue):
                all_dependencies[id(val)] = val
                all_dependencies.update(val.dependencies)
                for source in val.capability.sources:
                    source_key = (source.type, source.identifier)
                    if source_key not in all_sources_dict:
                        all_sources_dict[source_key] = source
        
        all_sources = list(all_sources_dict.values())
        return self._create_capability_value(primary_value, all_sources, all_dependencies)
    
    def unwrap(self, obj: Any) -> Any:
        """Central place to unwrap values."""
        if isinstance(obj, CapabilityValue):
            return obj.value
        return obj
    
    def _merge_dependencies_and_sources(self, dependencies: Dict[int, CapabilityValue]) -> tuple[Dict[int, CapabilityValue], List[Source]]:
        """Merge dependencies and sources from multiple CapabilityValues"""
        all_dependencies = dependencies.copy()
        all_sources_dict = {}
        
        for val in dependencies.values():
            if isinstance(val, CapabilityValue):
                all_dependencies.update(val.dependencies)
                for source in val.capability.sources:
                    source_key = (source.type, source.identifier)
                    if source_key not in all_sources_dict:
                        all_sources_dict[source_key] = source
        
        all_sources = list(all_sources_dict.values())
        return all_dependencies, all_sources
    
    def _create_capability_value(self, value: Any, sources: List[Source] = None, dependencies: Dict[int, CapabilityValue] = None) -> CapabilityValue:
        """Helper to create a CapabilityValue with proper sources and dependencies"""
        if sources is None:
            sources = []
        if dependencies is None:
            dependencies = {}
            
        capability = Capability()
        capability.sources = sources
        
        cap_value = CapabilityValue()
        cap_value.value = value
        cap_value.capability = capability
        cap_value.dependencies = dependencies
        return cap_value 