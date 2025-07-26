"""Xcode MCP Server - Model Context Protocol server for Xcode integration"""

def main():
    """Entry point for the xcode-mcp-server command"""
    import sys
    from . import __main__
    
    # Initialize allowed folders
    __main__.ALLOWED_FOLDERS = __main__.get_allowed_folders()
    
    # Debug info
    print(f"Allowed folders: {__main__.ALLOWED_FOLDERS}", file=sys.stderr)
    
    # Run the server
    __main__.mcp.run()

__version__ = "1.0.0"
__all__ = ["main"]