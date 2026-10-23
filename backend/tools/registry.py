"""Strict tool registry with allowlist enforcement and parameter validation."""
from typing import Dict, Any, Callable
from urllib.parse import urlparse
from backend.core.exceptions import PolicyViolationError
from backend.core.logging_config import logger

ALLOWED_TOOLS = {
    "web_search",
    "browser_page_extractor",
    "evidence_synthesizer",
    "report_generator",
    "result_verifier",
}

def validate_tool_call(tool_name: str, tool_input: Dict[str, Any]) -> None:
    """Enforces strict tool allowlist and parameter bounds to prevent unauthorized actions."""
    if tool_name not in ALLOWED_TOOLS:
        logger.error(f"Policy violation: Attempted unauthorized tool execution: {tool_name}")
        raise PolicyViolationError(f"Tool '{tool_name}' is not in the permitted allowlist.")

    # Validate URL inputs if present
    if "url" in tool_input:
        url = tool_input["url"]
        if not isinstance(url, str):
            raise PolicyViolationError("Tool parameter 'url' must be a valid string.")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise PolicyViolationError(f"Disallowed URL scheme: '{parsed.scheme}'. Only http and https are permitted.")
        hostname = parsed.hostname or parsed.netloc.split(":")[0]
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"):
            raise PolicyViolationError("Access to internal or local loopback addresses is prohibited.")

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable):
        if name not in ALLOWED_TOOLS:
            raise PolicyViolationError(f"Cannot register '{name}'; not in ALLOWED_TOOLS allowlist.")
        self._tools[name] = func

    def get(self, name: str) -> Callable:
        if name not in self._tools:
            raise PolicyViolationError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def is_allowed(self, name: str) -> bool:
        return name in ALLOWED_TOOLS

registry = ToolRegistry()
