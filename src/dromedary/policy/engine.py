import os
import yaml
from typing import Dict, List, Any, Optional, Tuple
import logging
from pathlib import Path
from .loader import Policy, EmailPolicy, CalendarPolicy, FilePolicy

logger = logging.getLogger(__name__)

class PolicyViolationError(Exception):
    def __init__(self, message: str, violations: List[str]):
        super().__init__(message)
        self.violations = violations

class PolicyEngine:
    """
    Policy engine for evaluating tool calls against security policies.
    
    Note: When accessing capability_values for provenance checking, use both parameter names 
    and positional fallbacks (arg_0, arg_1, etc.) since the interpreter passes positional 
    arguments with generic names.
    """
    def __init__(self, policies_dir: str):
        self.policies_dir = Path(policies_dir)
        self.policies_config = {}
        self.policy_map = {}
        self._load_policies()
        self._register_policies()
    
    def _load_policies(self):
        """Load policy rules from YAML configuration file"""
        config_file = self.policies_dir
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    self.policies_config = yaml.safe_load(f)
                logger.info(f"Loaded policy rules from {config_file}")
            except Exception as e:
                logger.error(f"Failed to load policies from {config_file}: {e}")
        else:
            logger.error(f"Policy configuration file {config_file} not found")
    
    def _register_policies(self):
        """Hard-coded policy objects for each tool type"""
        # TODO: This is a temporary solution to register policy objects for each tool type.
        self.policy_map = {
            "send_email": EmailPolicy(self.policies_config.get("email_policy", {})),
            "create_calendar_event": CalendarPolicy(self.policies_config.get("calendar_policy", {})),
            "reschedule_calendar_event": CalendarPolicy(self.policies_config.get("calendar_policy", {})),
            "delete_file": FilePolicy(self.policies_config.get("file_policy", {})),
            "share_file": FilePolicy(self.policies_config.get("file_policy", {})),
            "create_file": FilePolicy(self.policies_config.get("file_policy", {})),
        }
    
    def evaluate_tool_call(self, tool_name: str, tool_args: Dict[str, Any], 
                          additional_context: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str]]:
        """
        Evaluate whether a tool call is allowed by the policies
        
        Args:
            tool_name: Name of the tool being called
            tool_args: Arguments passed to the tool
            additional_context: Additional context like file content for file operations
            
        Returns:
            Tuple of (is_allowed, list_of_violations)
        """
        violations = []
        
        try:
            if tool_name in self.policy_map:
                policy = self.policy_map[tool_name]
                violations.extend(policy.evaluate(tool_args, additional_context))
        except Exception as e:
            logger.error(f"Error evaluating policy for {tool_name}: {e}")
            violations.append(f"Policy evaluation error: {str(e)}")
        
        is_allowed = len(violations) == 0
        return is_allowed, violations
    

def create_policy_engine(policies_dir: str) -> PolicyEngine:
    return PolicyEngine(policies_dir)