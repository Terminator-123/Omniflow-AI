"""Custom exceptions for OmniFlow AI."""

class OmniFlowException(Exception):
    """Base exception for OmniFlow AI."""
    pass

class TaskNotFoundError(OmniFlowException):
    """Raised when a requested task does not exist."""
    pass

class InvalidTaskStateError(OmniFlowException):
    """Raised when an operation is invalid for current task state."""
    pass

class ToolExecutionError(OmniFlowException):
    """Raised when an agent tool fails during execution."""
    def __init__(self, message: str, tool_name: str, recoverable: bool = True):
        super().__init__(message)
        self.tool_name = tool_name
        self.recoverable = recoverable

class PolicyViolationError(OmniFlowException):
    """Raised when a disallowed tool or action is attempted."""
    pass

class VerificationError(OmniFlowException):
    """Raised when step or report verification fails."""
    pass

class LLMServiceError(OmniFlowException):
    """Raised when Gemini or the fallback LLM encounter an unrecoverable issue."""
    pass
