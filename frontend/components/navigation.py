"""Top navigation and status bar for OmniFlow AI."""
import streamlit as st
from frontend.api_client import api_client

def render_navigation():
    """Renders the top application status bar matching the modern mockup."""
    health = api_client.health_check()
    is_online = (health.get("status") == "healthy")
    has_gemini = health.get("gemini_configured", False)

    col1, col2 = st.columns([3, 2])
    with col1:
        # Subtle contextual breadcrumb based on active view
        view_names = {
            "workspace": "Workspace",
            "plan": "Execution Plan",
            "execution": "Live Execution",
            "evidence": "Evidence Explorer",
            "results": "Final Report",
            "history": "Task History",
        }
        current_view_name = view_names.get(st.session_state.get("active_view", "workspace"), "Workspace")
        st.markdown(
            f"""
            <div style="font-size: 13px; color: #64748B; padding-top: 4px;">
                OmniFlow AI <span style="color: #CBD5E1; margin: 0 6px;">/</span> <span style="font-weight: 600; color: #0F172A;">{current_view_name}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        status_color = "#059669" if is_online else "#DC2626"
        status_bg = "#ECFDF5" if is_online else "#FEF2F2"
        status_text = "FastAPI 200 OK" if is_online else "Backend Offline"
        
        gemini_text = "Gemini 2.5 Active" if has_gemini else "Deterministic Mode"
        gemini_bg = "#EEF2FF" if has_gemini else "#F8FAFC"
        gemini_color = "#4F46E5" if has_gemini else "#64748B"

        st.markdown(
            f"""
            <div style="display: flex; justify-content: flex-end; gap: 8px; align-items: center;">
                <span style="font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 9999px; background: {status_bg}; color: {status_color};">
                    ● {status_text}
                </span>
                <span style="font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 9999px; background: {gemini_bg}; color: {gemini_color}; border: 1px solid #E2E8F0;">
                    ⚡ {gemini_text}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<hr style='margin: 10px 0 20px 0; border: none; border-top: 1px solid #E2E8F0;' />", unsafe_allow_html=True)
