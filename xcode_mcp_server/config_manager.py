#!/usr/bin/env python3
import os
import sys
import json
import hashlib
import inspect
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Any, Dict, List, Set
from functools import wraps
from contextvars import ContextVar

# Global context for tracking active MCP tool execution
# This allows nested functions to know which tool is running
_tool_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar('tool_context', default=None)

def get_active_tool_context() -> Optional[Dict[str, Any]]:
    """Get the current tool execution context if any"""
    return _tool_context.get()


@dataclass
class ConfigLevel:
    """Represents one configuration level"""
    type: str  # "root", "path", or "project"
    name: str
    path: str
    file_path: str  # Where this config is stored
    data: dict  # The actual config JSON


class ConfigManager:
    """
    Singleton manager for all configuration operations.
    This is the ONLY class that reads/writes config files.
    """

    _instance = None
    _config_dir = Path.home() / ".xcode-mcp-server"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._ensure_config_dir_exists()
        self._tool_registry = {}  # Will be populated by decorator
        self._initialized = True

    # === INTERNAL ===

    def _ensure_config_dir_exists(self):
        """Create ~/.xcode-mcp-server if needed"""
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def _get_config_file_path(self, level_type: str, path: str) -> Path:
        """Calculate config file path (with hashing for non-root)"""
        if level_type == "root":
            return self._config_dir / "config.json"
        else:
            # Hash the path for project/path configs
            path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
            return self._config_dir / f"{path_hash}_config.json"

    def _load_config_file(self, file_path: Path) -> Optional[dict]:
        """Load and parse a config JSON file"""
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load config from {file_path}: {e}")
            return None

    def _save_config_file(self, file_path: Path, data: dict):
        """Write config JSON file"""
        self._ensure_config_dir_exists()
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _create_empty_config(self, level_type: str, name: str, path: str) -> dict:
        """Create an empty config structure"""
        return {
            "version": "1.0",
            "config_level": {
                "type": level_type,
                "name": name,
                "path": path
            },
            "disabled_tools": [],
            "notifications": {
                "enabled": True,
                "disabled_for_tools": []
            },
            "parameter_overrides": {}
        }

    # === LOADING ===

    def get_effective_config(self, project_path: Optional[str] = None) -> Dict[str, ConfigLevel]:
        """
        Returns dict of {level_name: ConfigLevel} for all applicable levels.

        Loads configs in order:
        1. root (always)
        2. cwd (always)
        3. project (only if project_path provided)
        """
        configs = {}

        # 1. Root config
        root_path = self._get_config_file_path("root", str(Path.home()))
        root_data = self._load_config_file(root_path)
        if root_data:
            configs["root"] = ConfigLevel(
                type="root",
                name="root",
                path=str(Path.home()),
                file_path=str(root_path),
                data=root_data
            )

        # 2. CWD config
        cwd = os.getcwd()
        cwd_path = self._get_config_file_path("path", cwd)
        cwd_data = self._load_config_file(cwd_path)
        if cwd_data:
            configs["cwd"] = ConfigLevel(
                type="path",
                name=os.path.basename(cwd),
                path=cwd,
                file_path=str(cwd_path),
                data=cwd_data
            )

        # 3. Project config (if project_path provided)
        if project_path:
            # Normalize project path
            project_path = os.path.realpath(project_path)
            project_file_path = self._get_config_file_path("project", project_path)
            project_data = self._load_config_file(project_file_path)
            if project_data:
                configs["project"] = ConfigLevel(
                    type="project",
                    name=os.path.basename(project_path),
                    path=project_path,
                    file_path=str(project_file_path),
                    data=project_data
                )

        return configs

    def list_all_config_levels(self) -> List[ConfigLevel]:
        """Enumerate all existing config files"""
        levels = []

        for config_file in self._config_dir.glob("*.json"):
            data = self._load_config_file(config_file)
            if data and "config_level" in data:
                level_info = data["config_level"]
                levels.append(ConfigLevel(
                    type=level_info["type"],
                    name=level_info["name"],
                    path=level_info["path"],
                    file_path=str(config_file),
                    data=data
                ))

        return levels

    # === READING (with hierarchy) ===

    def is_tool_enabled(self, tool_name: str, project_path: Optional[str] = None) -> bool:
        """Check if tool is enabled (considering all levels)"""
        configs = self.get_effective_config(project_path)

        # Check all levels - if disabled in any, tool is disabled
        for level in configs.values():
            if tool_name in level.data.get("disabled_tools", []):
                return False

        return True

    def should_show_notification(self, tool_name: str, project_path: Optional[str] = None) -> bool:
        """Check if notification should be shown"""
        configs = self.get_effective_config(project_path)

        # Check from most specific to least specific (project -> cwd -> root)
        for level_name in ["project", "cwd", "root"]:
            if level_name in configs:
                level = configs[level_name]
                notifications = level.data.get("notifications", {})

                # Check if tool is specifically disabled for notifications
                if tool_name in notifications.get("disabled_for_tools", []):
                    return False

                # Check global notifications setting
                if "enabled" in notifications:
                    return notifications["enabled"]

        return True  # Default: show notifications

    def get_parameter_override(self, tool_name: str, param_name: str,
                               project_path: Optional[str] = None) -> Optional[Any]:
        """Get overridden parameter value (returns None if not overridden)"""
        configs = self.get_effective_config(project_path)

        # Check from most specific to least specific (project -> cwd -> root)
        for level_name in ["project", "cwd", "root"]:
            if level_name in configs:
                level = configs[level_name]
                overrides = level.data.get("parameter_overrides", {})
                if tool_name in overrides and param_name in overrides[tool_name]:
                    return overrides[tool_name][param_name]

        return None

    def apply_parameter_overrides(self, tool_name: str, params: dict,
                                  project_path: Optional[str] = None) -> dict:
        """Apply all overrides to a parameter dict, return modified dict"""
        result = params.copy()

        for param_name in result.keys():
            override = self.get_parameter_override(tool_name, param_name, project_path)
            if override is not None:
                result[param_name] = override

        return result

    # === WRITING (to specific level) ===

    def disable_tool(self, tool_name: str, config_level: ConfigLevel):
        """Add tool to disabled_tools at specific level"""
        if tool_name not in config_level.data.get("disabled_tools", []):
            config_level.data.setdefault("disabled_tools", []).append(tool_name)
            self._save_config_file(Path(config_level.file_path), config_level.data)

    def enable_tool(self, tool_name: str, config_level: ConfigLevel):
        """Remove tool from disabled_tools at specific level"""
        disabled = config_level.data.get("disabled_tools", [])
        if tool_name in disabled:
            disabled.remove(tool_name)
            self._save_config_file(Path(config_level.file_path), config_level.data)

    def set_parameter_override(self, tool_name: str, param_name: str,
                               value: Any, config_level: ConfigLevel):
        """Set parameter override at specific level"""
        config_level.data.setdefault("parameter_overrides", {})
        config_level.data["parameter_overrides"].setdefault(tool_name, {})
        config_level.data["parameter_overrides"][tool_name][param_name] = value
        self._save_config_file(Path(config_level.file_path), config_level.data)

    def remove_parameter_override(self, tool_name: str, param_name: str,
                                  config_level: ConfigLevel):
        """Remove parameter override at specific level"""
        overrides = config_level.data.get("parameter_overrides", {})
        if tool_name in overrides and param_name in overrides[tool_name]:
            del overrides[tool_name][param_name]
            # Clean up empty dicts
            if not overrides[tool_name]:
                del overrides[tool_name]
            self._save_config_file(Path(config_level.file_path), config_level.data)

    def set_notifications_enabled(self, enabled: bool, config_level: ConfigLevel):
        """Set global notifications enabled/disabled"""
        config_level.data.setdefault("notifications", {})
        config_level.data["notifications"]["enabled"] = enabled
        self._save_config_file(Path(config_level.file_path), config_level.data)

    def disable_notification_for_tool(self, tool_name: str, config_level: ConfigLevel):
        """Disable notification for specific tool"""
        config_level.data.setdefault("notifications", {})
        config_level.data["notifications"].setdefault("disabled_for_tools", [])
        if tool_name not in config_level.data["notifications"]["disabled_for_tools"]:
            config_level.data["notifications"]["disabled_for_tools"].append(tool_name)
            self._save_config_file(Path(config_level.file_path), config_level.data)

    def enable_notification_for_tool(self, tool_name: str, config_level: ConfigLevel):
        """Enable notification for specific tool"""
        disabled = config_level.data.get("notifications", {}).get("disabled_for_tools", [])
        if tool_name in disabled:
            disabled.remove(tool_name)
            self._save_config_file(Path(config_level.file_path), config_level.data)

    # === LEVEL MANAGEMENT ===

    def create_config_for_path(self, path: str) -> ConfigLevel:
        """Create new config level for a path (auto-detects project vs path type)"""
        path = os.path.realpath(path)

        # Detect type
        if path.endswith('.xcodeproj') or path.endswith('.xcworkspace'):
            config_type = 'project'
        else:
            config_type = 'path'

        name = os.path.basename(path)
        file_path = self._get_config_file_path(config_type, path)

        # Create config
        data = self._create_empty_config(config_type, name, path)
        self._save_config_file(file_path, data)

        return ConfigLevel(
            type=config_type,
            name=name,
            path=path,
            file_path=str(file_path),
            data=data
        )

    def get_or_create_root_config(self) -> ConfigLevel:
        """Get root config, creating if it doesn't exist"""
        root_path = self._get_config_file_path("root", str(Path.home()))
        data = self._load_config_file(root_path)

        if data is None:
            # Create default root config
            data = self._create_empty_config("root", "root", str(Path.home()))
            self._save_config_file(root_path, data)

        return ConfigLevel(
            type="root",
            name="root",
            path=str(Path.home()),
            file_path=str(root_path),
            data=data
        )

    def delete_config_level(self, config_level: ConfigLevel):
        """Delete a config file"""
        Path(config_level.file_path).unlink(missing_ok=True)

    # === VALIDATION ===

    def register_tool(self, tool_name: str, func):
        """Register a tool and its signature for validation"""
        self._tool_registry[tool_name] = func

    def validate_parameter_type(self, tool_name: str, param_name: str, value: Any) -> bool:
        """Validate parameter value against function signature"""
        if tool_name not in self._tool_registry:
            return True  # Can't validate, assume OK

        func = self._tool_registry[tool_name]
        sig = inspect.signature(func)

        if param_name not in sig.parameters:
            return False

        param = sig.parameters[param_name]
        if param.annotation == inspect.Parameter.empty:
            return True  # No type hint, can't validate

        # Get the actual type (handle Optional types)
        param_type = param.annotation
        if hasattr(param_type, '__origin__'):
            # Handle Optional[X] -> Union[X, None]
            if param_type.__origin__ is type(None) or str(param_type.__origin__) == 'typing.Union':
                # Get the non-None type
                args = getattr(param_type, '__args__', ())
                param_type = next((arg for arg in args if arg is not type(None)), type(None))

        return isinstance(value, param_type)

    def list_available_tools(self) -> List[str]:
        """Get list of all registered MCP tool names"""
        return sorted(self._tool_registry.keys())

    def get_tool_parameters(self, tool_name: str) -> Dict[str, type]:
        """Get parameter names and types for a tool"""
        if tool_name not in self._tool_registry:
            return {}

        func = self._tool_registry[tool_name]
        sig = inspect.signature(func)

        params = {}
        for name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                params[name] = param.annotation
            else:
                params[name] = type(None)

        return params


def apply_config(func):
    """
    Decorator that handles config checks and parameter overrides.
    Apply this to @mcp.tool() decorated functions.

    Order: @mcp.tool() then @apply_config
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        config = ConfigManager()

        # Register this tool
        config.register_tool(func.__name__, func)

        # Get function signature and bind arguments
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()

        # Extract project_path if present (for config lookup)
        project_path = bound.arguments.get('project_path')

        # Check if tool is disabled
        if not config.is_tool_enabled(func.__name__, project_path):
            from xcode_mcp_server.exceptions import XCodeMCPError
            raise XCodeMCPError(f"{func.__name__} is disabled in configuration")

        # Apply parameter overrides (track which ones for debugging)
        overridden_params = []
        for param_name in sig.parameters:
            override = config.get_parameter_override(func.__name__, param_name, project_path)
            if override is not None:
                overridden_params.append(f"{param_name}={override}")
                bound.arguments[param_name] = override

        # Check if notification should be shown
        should_notify = config.should_show_notification(func.__name__, project_path)

        # DEBUG: Show configuration info in alert
        import subprocess
        debug_lines = [
            "[apply_config DEBUG]",
            f"Function: {func.__name__}",
            f"Project: {project_path or 'None'}",
            f"Show notification: {should_notify}",
            f"Overridden params: {', '.join(overridden_params) if overridden_params else 'None'}"
        ]
        debug_msg = "\\n".join(debug_lines)

        # Print to stderr
        print(debug_msg.replace("\\n", "\n"), file=sys.stderr)

        # Show in AppleScript alert (temporary debugging)
        # try:
        #     alert_script = f'display alert "apply_config Debug" message "{debug_msg}"'
        #     # No timeout - let the user dismiss it when ready
        #     subprocess.run(['osascript', '-e', alert_script], capture_output=True)
        # except:
        #     pass  # Ignore alert errors

        # Set tool context for this execution
        context = {
            'tool_name': func.__name__,
            'project_path': project_path,
            'bound_arguments': bound.arguments
        }
        token = _tool_context.set(context)

        try:
            # Show notification if enabled (with apply_config marker)
            if should_notify:
                # Import here to avoid circular dependency
                from xcode_mcp_server.utils.applescript import show_notification
                show_notification("Drew's Xcode MCP",
                                subtitle="[apply_config]",
                                message=func.__name__)

            # Call with modified parameters
            return func(*bound.args, **bound.kwargs)
        finally:
            # Always restore previous context
            _tool_context.reset(token)

    return wrapper
