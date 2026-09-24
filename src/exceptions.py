"""Custom exception classes for the application"""


class NL2SQLException(Exception):
    """Base exception for NL2SQL application"""
    pass


class SQLGenerationError(NL2SQLException):
    """Raised when SQL generation fails"""
    pass


class DatabaseError(NL2SQLException):
    """Raised when database operation fails"""
    pass


class ClarificationNeeded(NL2SQLException):
    """Raised when question needs clarification"""
    pass


class ConfigurationError(NL2SQLException):
    """Raised when configuration is invalid"""
    pass


class LLMError(NL2SQLException):
    """Raised when LLM call fails"""
    pass

class SQLSafetyBlockedError(NL2SQLException):
    """Raised when SQL is rejected by safety rules (unsafe statement type,
    disallowed table, or stacked/multiple statements)."""
    pass
