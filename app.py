"""OmniFlow AI — Autonomous Task Execution Agent
Streamlit Main Application Entrypoint (Faithful to Reference Mockup)
"""
import os
import sys
from pathlib import Path
import streamlit as st

# Add project root to Python sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from frontend.components.task_input import render_task_input
from frontend.components.plan_view import render_plan_view
from frontend.components.execution_view import render_execution_view
from frontend.components.evidence_view import render_evidence_view
from frontend.components.report_view import render_report_view
from frontend.components.history_view import render_history_view
from frontend.api_client import api_client

# Streamlit Page Setup
st.set_page_config(
    page_title="OmniFlow AI — Autonomous Task Execution Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load and inject custom CSS
css_path = BASE_DIR / "frontend" / "styles.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.html(f"<style>{f.read()}</style>")

# Auto-expand sidebar script (ensures sidebar is always expanded even if browser previously collapsed it)
st.html("""
<script>
(function forceExpandSidebar() {
    function tryExpand() {
        try {
            const doc = (window.parent && window.parent.document) ? window.parent.document : document;
            const btn = doc.querySelector('[data-testid="collapsedControl"] button') || doc.querySelector('[data-testid="collapsedControl"]');
            if (btn) {
                btn.click();
            }
        } catch (e) {}
    }
    tryExpand();
    window.addEventListener('DOMContentLoaded', tryExpand);
    window.addEventListener('load', tryExpand);
    setInterval(tryExpand, 300);
})();
</script>
""")

# Session state initialization
if "active_view" not in st.session_state:
    st.session_state["active_view"] = "workspace"
if "active_task_id" not in st.session_state or st.session_state["active_task_id"] is None:
    try:
        recent_tasks = api_client.list_tasks(limit=10)
        if recent_tasks:
            completed_tasks = [t for t in recent_tasks if t.get("status") == "completed"]
            if completed_tasks:
                st.session_state["active_task_id"] = completed_tasks[0]["id"]
            else:
                st.session_state["active_task_id"] = recent_tasks[0]["id"]
    except Exception:
        pass

# Sidebar Content (Dark Slate Theme #0B132B matching reference mockup)
with st.sidebar:
    # Logo Brand Header (glowing purple/blue ring icon + OmniFlow AI)
    st.html("""
    <div style="display: flex; align-items: center; gap: 12px; padding: 6px 0 24px 0;">
        <div style="width: 32px; height: 32px; border-radius: 50%; background: linear-gradient(135deg, #6366F1, #8B5CF6); display: flex; align-items: center; justify-content: center; box-shadow: 0 0 16px rgba(99, 102, 241, 0.6); flex-shrink: 0;">
            <div style="width: 14px; height: 14px; border-radius: 50%; background: #0B132B;"></div>
        </div>
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 20px; font-weight: 800; color: #FFFFFF; letter-spacing: -0.02em;">
            OmniFlow <span style="color: #818CF8;">AI</span>
        </div>
    </div>
    """)

    # Navigation items
    views = [
        ("workspace", "⊞  Workspace"),
        ("plan", "📋  Execution Plan"),
        ("execution", "⚡  Live Execution"),
        ("evidence", "🔍  Evidence Explorer"),
        ("results", "📄  Final Report"),
        ("history", "🕒  Task History"),
    ]

    for view_key, view_label in views:
        is_selected = (st.session_state["active_view"] == view_key)
        btn_type = "primary" if is_selected else "secondary"
        if st.button(view_label, key=f"nav_{view_key}", type=btn_type, use_container_width=True):
            st.session_state["active_view"] = view_key
            st.rerun()

    st.html("<div style='height: 48px;'></div>")

    # Dynamic Task Quota Meter (calculated from real SQLite database history)
    try:
        all_tasks_list = api_client.list_tasks(limit=100)
        total_tasks_count = len(all_tasks_list)
    except Exception:
        total_tasks_count = 1
    max_quota = 50
    used_tasks = min(total_tasks_count, max_quota)
    quota_pct = int((used_tasks / max_quota) * 100)

    st.html(f"""
    <div style="background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 12px 14px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 600; color: #E2E8F0; margin-bottom: 6px;">
            <span style="color: #E2E8F0;">Free Plan</span>
            <span style="color: #94A3B8;">{used_tasks}/{max_quota} tasks/month</span>
        </div>
        <div style="width: 100%; height: 6px; background: rgba(255, 255, 255, 0.1); border-radius: 9999px; overflow: hidden;">
            <div style="width: {quota_pct}%; height: 100%; background: linear-gradient(90deg, #6366F1, #8B5CF6); border-radius: 9999px;"></div>
        </div>
    </div>
    """)

    # User Profile Pill (matching "ST Shivansh" in mockup)
    st.html("""
    <div style="display: flex; align-items: center; gap: 10px; padding: 4px 0;">
        <div style="width: 32px; height: 32px; border-radius: 50%; background: #3B82F6; color: #FFFFFF; font-weight: 700; font-size: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
            ST
        </div>
        <div>
            <div style="font-size: 13px; font-weight: 700; color: #F1F5F9;">Shivansh</div>
            <div style="font-size: 11px; color: #64748B;">Workspace Owner</div>
        </div>
    </div>
    """)

# Main Screen Router
current_view = st.session_state["active_view"]

if current_view == "workspace":
    render_task_input()
elif current_view == "plan":
    render_plan_view()
elif current_view == "execution":
    render_execution_view()
elif current_view == "evidence":
    render_evidence_view()
elif current_view == "results":
    render_report_view()
elif current_view == "history":
    render_history_view()
