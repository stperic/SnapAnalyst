"""
SnapAnalyst Custom Exceptions
"""


class SnapAnalystError(Exception):
    """Base exception for all SnapAnalyst errors"""

    pass


class DatabaseError(SnapAnalystError):
    """Database-related errors"""

    pass


class ETLError(SnapAnalystError):
    """ETL processing errors"""

    pass


class ValidationError(SnapAnalystError):
    """Data validation errors"""

    pass


class DataFileNotFoundError(SnapAnalystError):
    """File not found errors"""

    pass


class ConfigurationError(SnapAnalystError):
    """Configuration errors"""

    pass


class LoadJobError(SnapAnalystError):
    """Data loading job errors"""

    pass
