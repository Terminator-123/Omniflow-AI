"""HTTP Client for communicating between Streamlit frontend and FastAPI backend."""
import httpx
from typing import Dict, Any, List, Optional
from backend.config import settings
from backend.core.logging_config import logger

class OmniFlowAPIClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.API_BASE_URL).rstrip("/")

    def set_gemini_key(self, api_key: str) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(
                    f"{self.base_url}/api/config/gemini_key",
                    json={"api_key": api_key},
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return {"status": "failed", "gemini_configured": False}

    def health_check(self) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self.base_url}/api/health")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return {"status": "offline", "gemini_configured": False, "playwright_available": False}

    def create_task(
        self,
        request: str,
        scope: Optional[str] = None,
        execution_mode: str = "demo",
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        chosen_mode = mode or execution_mode or "demo"
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.base_url}/api/tasks",
                json={
                    "original_request": request,
                    "scope": scope,
                    "execution_mode": chosen_mode,
                },
            )
            resp.raise_for_status()
            return resp.json()

    def get_task(self, task_id: str) -> Dict[str, Any]:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{self.base_url}/api/tasks/{task_id}")
            resp.raise_for_status()
            return resp.json()

    def list_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{self.base_url}/api/tasks?limit={limit}")
            if resp.status_code == 200:
                return resp.json()
            return []

    def approve_task(self, task_id: str, decision: str = "approved", comments: Optional[str] = None) -> Dict[str, Any]:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(
                f"{self.base_url}/api/tasks/{task_id}/approve",
                json={"decision": decision, "comments": comments},
            )
            resp.raise_for_status()
            return resp.json()

    def start_task(self, task_id: str) -> Dict[str, Any]:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(f"{self.base_url}/api/tasks/{task_id}/start")
            resp.raise_for_status()
            return resp.json()

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(f"{self.base_url}/api/tasks/{task_id}/cancel")
            resp.raise_for_status()
            return resp.json()

    def get_events(self, task_id: str) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{self.base_url}/api/tasks/{task_id}/events")
            if resp.status_code == 200:
                return resp.json()
            return []

    def get_evidence(self, task_id: str) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{self.base_url}/api/tasks/{task_id}/evidence")
            if resp.status_code == 200:
                return resp.json()
            return []

    def get_sources(self, task_id: str) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(f"{self.base_url}/api/tasks/{task_id}/sources")
            if resp.status_code == 200:
                return resp.json()
            return []

    def get_report(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(f"{self.base_url}/api/tasks/{task_id}/report")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return None

    def upload_document(self, task_id: str, filename: str, file_bytes: bytes) -> Dict[str, Any]:
        """Uploads and ingests a reference document to ground research."""
        files = {"file": (filename, file_bytes, "application/octet-stream")}
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{self.base_url}/api/tasks/{task_id}/documents", files=files)
            resp.raise_for_status()
            return resp.json()

    def get_productivity(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves empirical productivity evaluation metrics for a task."""
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(f"{self.base_url}/api/tasks/{task_id}/productivity")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return None

api_client = OmniFlowAPIClient()
