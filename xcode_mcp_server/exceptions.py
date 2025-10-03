#!/usr/bin/env python3
"""Custom exceptions for Xcode MCP Server"""


class XCodeMCPError(Exception):
    """Base exception class for Xcode MCP Server errors"""
    def __init__(self, message, code=None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class AccessDeniedError(XCodeMCPError):
    """Raised when access to a path is denied"""
    pass


class InvalidParameterError(XCodeMCPError):
    """Raised when an invalid parameter is provided"""
    pass
