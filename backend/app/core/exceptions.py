"""
Custom exception handlers for the FastAPI application.
"""

from fastapi import HTTPException


class FileValidationError(HTTPException):
    """Raised when an uploaded file fails security validation."""

    def __init__(self, detail: str = "Invalid file"):
        super().__init__(status_code=400, detail=detail)


class FileTooLargeError(HTTPException):
    """Raised when an uploaded file exceeds size limit."""

    def __init__(self, max_mb: int):
        super().__init__(
            status_code=413,
            detail=f"File exceeds maximum size of {max_mb}MB",
        )


class GraphQueryError(HTTPException):
    """Raised when a Neo4j query fails."""

    def __init__(self, detail: str = "Graph query failed"):
        super().__init__(status_code=500, detail=detail)


class AgentError(HTTPException):
    """Raised when the AI agent encounters an error."""

    def __init__(self, detail: str = "Agent processing failed"):
        super().__init__(status_code=500, detail=detail)
