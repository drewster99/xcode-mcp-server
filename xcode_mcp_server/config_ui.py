#!/usr/bin/env python3
import os
import sys
import subprocess
from typing import Optional, List
import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from xcode_mcp_server.config_manager import ConfigManager, ConfigLevel
from xcode_mcp_server import __version__


console = Console()


def run_configuration_ui():
    """Main entry point for the configuration UI"""
    config = ConfigManager()

    # Ensure root config exists
    root_config = config.get_or_create_root_config()

    # Start with root config level
    current_level = root_config

    console.print(f"\n[bold cyan]Xcode MCP Server Configuration[/bold cyan]")
    console.print(f"Version: {__version__}\n")

    while True:
        choice = show_main_menu(current_level)

        if choice == "Change config level":
            new_level = select_config_level(config, current_level)
            if new_level:
                current_level = new_level
        elif choice == "Enable/disable tools":
            manage_tools(config, current_level)
        elif choice == "Configure notifications":
            manage_notifications(config, current_level)
        elif choice == "Set parameter overrides":
            manage_parameter_overrides(config, current_level)
        elif choice == "View configuration":
            view_configuration(config, current_level)
        elif choice == "Done":
            console.print("\n[green]Configuration saved. Exiting.[/green]\n")
            break


def show_main_menu(current_level: ConfigLevel) -> str:
    """Show the main menu"""
    level_display = f"{current_level.name}" if current_level.type == "root" else f"{current_level.name} ({current_level.type})"

    choices = [
        f"Change config level [{level_display}]",
        "View configuration",
        "Enable/disable tools",
        "Configure notifications",
        "Set parameter overrides",
        "Done"
    ]

    return questionary.select(
        "Select an option:",
        choices=choices
    ).ask()


def select_config_level(config: ConfigManager, current_level: ConfigLevel) -> Optional[ConfigLevel]:
    """Select a config level to edit"""
    all_levels = config.list_all_config_levels()

    choices = []
    level_map = {}

    # Add existing levels
    for level in all_levels:
        if level.type == "root":
            display = "root (user home directory)"
        else:
            display = f"{level.name} ({level.type}: {level.path})"

        choices.append(display)
        level_map[display] = level

    choices.append("Add new configuration...")
    choices.append("Cancel")

    choice = questionary.select(
        f"Currently editing: [{current_level.name}]",
        choices=choices
    ).ask()

    if choice == "Cancel" or choice is None:
        return None
    elif choice == "Add new configuration...":
        return add_new_config_level(config)
    else:
        return level_map.get(choice)


def add_new_config_level(config: ConfigManager) -> Optional[ConfigLevel]:
    """Add a new configuration level via folder picker"""
    console.print("\n[yellow]Opening folder picker...[/yellow]")

    # Use AppleScript to show folder picker
    script = '''
    set chosenFolder to choose folder with prompt "Select a folder for configuration:"
    return POSIX path of chosenFolder
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            check=True
        )
        folder_path = result.stdout.strip()

        if folder_path:
            # Remove trailing slash if present
            folder_path = folder_path.rstrip('/')

            # Auto-detect type
            if folder_path.endswith('.xcodeproj') or folder_path.endswith('.xcworkspace'):
                config_type = 'project'
            else:
                config_type = 'path'

            # Confirm with user
            name = os.path.basename(folder_path)
            confirm = questionary.confirm(
                f"Create {config_type} configuration for '{name}'?"
            ).ask()

            if confirm:
                new_level = config.create_config_for_path(folder_path)
                console.print(f"\n[green]Created {config_type} configuration: {name}[/green]\n")
                return new_level

    except subprocess.CalledProcessError:
        console.print("\n[red]Folder selection cancelled[/red]\n")

    return None


def view_configuration(config: ConfigManager, current_level: ConfigLevel):
    """View the current configuration with merged values"""
    console.print()

    # Get effective config for current level's path
    project_path = current_level.path if current_level.type == "project" else None
    all_configs = config.get_effective_config(project_path)

    # Show disabled tools
    table = Table(title="Disabled Tools", show_header=True, header_style="bold magenta")
    table.add_column("Tool Name", style="cyan")
    table.add_column("Disabled At", style="yellow")

    disabled_tools = set()
    for level_name in ["root", "cwd", "project"]:
        if level_name in all_configs:
            level = all_configs[level_name]
            for tool in level.data.get("disabled_tools", []):
                disabled_tools.add((tool, f"[{level_name}]"))

    if disabled_tools:
        for tool, source in sorted(disabled_tools):
            table.add_row(tool, source)
        console.print(table)
    else:
        console.print("[green]No disabled tools[/green]")

    console.print()

    # Show parameter overrides
    table = Table(title="Parameter Overrides", show_header=True, header_style="bold magenta")
    table.add_column("Tool", style="cyan")
    table.add_column("Parameter", style="magenta")
    table.add_column("Value", style="green")
    table.add_column("Source", style="yellow")

    overrides = []
    for level_name in ["root", "cwd", "project"]:
        if level_name in all_configs:
            level = all_configs[level_name]
            for tool_name, params in level.data.get("parameter_overrides", {}).items():
                for param_name, value in params.items():
                    overrides.append((tool_name, param_name, str(value), f"[{level_name}]"))

    if overrides:
        for tool, param, value, source in sorted(overrides):
            table.add_row(tool, param, value, source)
        console.print(table)
    else:
        console.print("[green]No parameter overrides[/green]")

    console.print()

    # Show notification settings
    notifications_enabled = config.should_show_notification("__any__", project_path)
    console.print(f"Global notifications: [{'green' if notifications_enabled else 'red'}]{'Enabled' if notifications_enabled else 'Disabled'}[/]")

    console.print()
    input("Press Enter to continue...")


def manage_tools(config: ConfigManager, current_level: ConfigLevel):
    """Manage tool enable/disable"""
    while True:
        choice = questionary.select(
            f"Tool Management [{current_level.name}]",
            choices=[
                "View tool status",
                "Disable tools",
                "Enable tools",
                "Back to main menu"
            ]
        ).ask()

        if choice == "View tool status":
            view_tool_status(config, current_level)
        elif choice == "Disable tools":
            disable_tools(config, current_level)
        elif choice == "Enable tools":
            enable_tools(config, current_level)
        elif choice == "Back to main menu":
            break


def view_tool_status(config: ConfigManager, current_level: ConfigLevel):
    """View enabled/disabled status of all tools"""
    all_tools = config.list_available_tools()

    if not all_tools:
        console.print("\n[yellow]No tools registered yet. Tools are registered when the server starts.[/yellow]\n")
        input("Press Enter to continue...")
        return

    project_path = current_level.path if current_level.type == "project" else None

    enabled = []
    disabled = []

    for tool in all_tools:
        if config.is_tool_enabled(tool, project_path):
            enabled.append(tool)
        else:
            # Find where it's disabled
            all_configs = config.get_effective_config(project_path)
            source = "unknown"
            for level_name in ["project", "cwd", "root"]:
                if level_name in all_configs:
                    if tool in all_configs[level_name].data.get("disabled_tools", []):
                        source = level_name
                        break
            disabled.append(f"{tool} [{source}]")

    console.print()
    if enabled:
        console.print(f"[green]Enabled tools ({len(enabled)}):[/green]")
        for tool in sorted(enabled):
            console.print(f"  • {tool}")

    console.print()
    if disabled:
        console.print(f"[red]Disabled tools ({len(disabled)}):[/red]")
        for tool in sorted(disabled):
            console.print(f"  • {tool}")

    if not enabled and not disabled:
        console.print("[yellow]No tools found[/yellow]")

    console.print()
    input("Press Enter to continue...")


def disable_tools(config: ConfigManager, current_level: ConfigLevel):
    """Disable one or more tools"""
    all_tools = config.list_available_tools()

    if not all_tools:
        console.print("\n[yellow]No tools available to disable[/yellow]\n")
        input("Press Enter to continue...")
        return

    project_path = current_level.path if current_level.type == "project" else None

    # Filter to only enabled tools
    enabled_tools = [t for t in all_tools if config.is_tool_enabled(t, project_path)]

    if not enabled_tools:
        console.print("\n[yellow]All tools are already disabled[/yellow]\n")
        input("Press Enter to continue...")
        return

    selected = questionary.checkbox(
        f"Select tools to disable at [{current_level.name}]:",
        choices=sorted(enabled_tools)
    ).ask()

    if selected:
        for tool in selected:
            config.disable_tool(tool, current_level)

        console.print(f"\n[green]Disabled {len(selected)} tool(s) at [{current_level.name}][/green]\n")


def enable_tools(config: ConfigManager, current_level: ConfigLevel):
    """Enable one or more tools"""
    # Get tools disabled at current level
    disabled_at_level = current_level.data.get("disabled_tools", [])

    if not disabled_at_level:
        console.print(f"\n[yellow]No tools are disabled at [{current_level.name}][/yellow]\n")
        input("Press Enter to continue...")
        return

    selected = questionary.checkbox(
        f"Select tools to enable at [{current_level.name}]:",
        choices=sorted(disabled_at_level)
    ).ask()

    if selected:
        for tool in selected:
            config.enable_tool(tool, current_level)

        console.print(f"\n[green]Enabled {len(selected)} tool(s) at [{current_level.name}][/green]\n")


def manage_notifications(config: ConfigManager, current_level: ConfigLevel):
    """Manage notification settings"""
    while True:
        choice = questionary.select(
            f"Notification Settings [{current_level.name}]",
            choices=[
                "Toggle global notifications",
                "Disable notifications for specific tools",
                "Enable notifications for specific tools",
                "Back to main menu"
            ]
        ).ask()

        if choice == "Toggle global notifications":
            toggle_global_notifications(config, current_level)
        elif choice == "Disable notifications for specific tools":
            disable_notifications_for_tools(config, current_level)
        elif choice == "Enable notifications for specific tools":
            enable_notifications_for_tools(config, current_level)
        elif choice == "Back to main menu":
            break


def toggle_global_notifications(config: ConfigManager, current_level: ConfigLevel):
    """Toggle global notifications on/off"""
    current = current_level.data.get("notifications", {}).get("enabled", True)
    new_state = not current

    config.set_notifications_enabled(new_state, current_level)

    state_str = "enabled" if new_state else "disabled"
    console.print(f"\n[green]Global notifications {state_str} at [{current_level.name}][/green]\n")


def disable_notifications_for_tools(config: ConfigManager, current_level: ConfigLevel):
    """Disable notifications for specific tools"""
    all_tools = config.list_available_tools()

    if not all_tools:
        console.print("\n[yellow]No tools available[/yellow]\n")
        input("Press Enter to continue...")
        return

    selected = questionary.checkbox(
        f"Select tools to disable notifications for at [{current_level.name}]:",
        choices=sorted(all_tools)
    ).ask()

    if selected:
        for tool in selected:
            config.disable_notification_for_tool(tool, current_level)

        console.print(f"\n[green]Disabled notifications for {len(selected)} tool(s) at [{current_level.name}][/green]\n")


def enable_notifications_for_tools(config: ConfigManager, current_level: ConfigLevel):
    """Enable notifications for specific tools"""
    disabled = current_level.data.get("notifications", {}).get("disabled_for_tools", [])

    if not disabled:
        console.print(f"\n[yellow]No tools have notifications disabled at [{current_level.name}][/yellow]\n")
        input("Press Enter to continue...")
        return

    selected = questionary.checkbox(
        f"Select tools to enable notifications for at [{current_level.name}]:",
        choices=sorted(disabled)
    ).ask()

    if selected:
        for tool in selected:
            config.enable_notification_for_tool(tool, current_level)

        console.print(f"\n[green]Enabled notifications for {len(selected)} tool(s) at [{current_level.name}][/green]\n")


def manage_parameter_overrides(config: ConfigManager, current_level: ConfigLevel):
    """Manage parameter overrides"""
    while True:
        choice = questionary.select(
            f"Parameter Overrides [{current_level.name}]",
            choices=[
                "Add/modify override",
                "Remove override",
                "Back to main menu"
            ]
        ).ask()

        if choice == "Add/modify override":
            add_parameter_override(config, current_level)
        elif choice == "Remove override":
            remove_parameter_override(config, current_level)
        elif choice == "Back to main menu":
            break


def add_parameter_override(config: ConfigManager, current_level: ConfigLevel):
    """Add or modify a parameter override"""
    all_tools = config.list_available_tools()

    if not all_tools:
        console.print("\n[yellow]No tools available. Run the server first to register tools.[/yellow]\n")
        input("Press Enter to continue...")
        return

    # Select tool
    tool_name = questionary.select(
        "Select tool:",
        choices=sorted(all_tools)
    ).ask()

    if not tool_name:
        return

    # Get parameters for this tool
    params = config.get_tool_parameters(tool_name)

    if not params:
        console.print(f"\n[yellow]No parameters found for {tool_name}[/yellow]\n")
        input("Press Enter to continue...")
        return

    # Select parameter
    param_name = questionary.select(
        f"Select parameter for {tool_name}:",
        choices=sorted(params.keys())
    ).ask()

    if not param_name:
        return

    # Get parameter type
    param_type = params[param_name]

    # Ask for value
    console.print(f"\n[cyan]Parameter type: {param_type}[/cyan]")
    value_str = questionary.text(
        f"Enter value for {param_name}:"
    ).ask()

    if value_str is None:
        return

    # Convert value based on type
    try:
        if 'bool' in str(param_type).lower():
            value = value_str.lower() in ('true', 'yes', '1')
        elif 'int' in str(param_type).lower():
            value = int(value_str)
        elif 'float' in str(param_type).lower():
            value = float(value_str)
        elif 'list' in str(param_type).lower():
            # Simple list parsing - comma separated
            value = [v.strip() for v in value_str.split(',')]
        else:
            value = value_str

        # Validate
        if config.validate_parameter_type(tool_name, param_name, value):
            config.set_parameter_override(tool_name, param_name, value, current_level)
            console.print(f"\n[green]Set {tool_name}.{param_name} = {value} at [{current_level.name}][/green]\n")
        else:
            console.print(f"\n[red]Invalid type for {param_name}. Expected {param_type}[/red]\n")

    except ValueError as e:
        console.print(f"\n[red]Invalid value: {e}[/red]\n")


def remove_parameter_override(config: ConfigManager, current_level: ConfigLevel):
    """Remove a parameter override"""
    overrides = current_level.data.get("parameter_overrides", {})

    if not overrides:
        console.print(f"\n[yellow]No parameter overrides at [{current_level.name}][/yellow]\n")
        input("Press Enter to continue...")
        return

    # Build list of overrides
    choices = []
    override_map = {}

    for tool_name, params in overrides.items():
        for param_name, value in params.items():
            display = f"{tool_name}.{param_name} = {value}"
            choices.append(display)
            override_map[display] = (tool_name, param_name)

    if not choices:
        console.print(f"\n[yellow]No parameter overrides at [{current_level.name}][/yellow]\n")
        input("Press Enter to continue...")
        return

    selected = questionary.select(
        f"Select override to remove from [{current_level.name}]:",
        choices=sorted(choices)
    ).ask()

    if selected:
        tool_name, param_name = override_map[selected]
        config.remove_parameter_override(tool_name, param_name, current_level)
        console.print(f"\n[green]Removed {tool_name}.{param_name} from [{current_level.name}][/green]\n")


if __name__ == "__main__":
    run_configuration_ui()
