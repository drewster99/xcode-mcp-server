"""MCP tools for Xcode integration - imports all tools to register them"""

# Import all tool modules to trigger @mcp.tool() decoration
from . import version
from . import get_xcode_projects
from . import get_directory_tree
from . import get_directory_listing
from . import get_project_schemes
from . import build_project
from . import run_project_with_user_interaction
from . import run_project_until_terminated
from . import run_project_unmonitored
from . import get_build_errors
from . import clean_project
from . import stop_project
from . import get_runtime_output
from . import list_booted_simulators
from . import take_xcode_screenshot
from . import take_simulator_screenshot
from . import list_running_mac_apps
from . import list_mac_app_windows
from . import take_window_screenshot
from . import take_app_screenshot
from . import list_project_tests
from . import run_project_tests
from . import get_latest_test_results
from . import debug_list_notification_history
