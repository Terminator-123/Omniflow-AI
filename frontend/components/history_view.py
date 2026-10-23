"""Task History component visualizing real execution history from SQLite database."""
import streamlit as st
from frontend.api_client import api_client

def render_history_view():
    """Renders the Task History screen matching Panel 6 with genuine SQLite persistence."""
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.html("""
        <div>
            <h1 style="font-size: 26px; font-weight: 800; color: #0F172A; margin: 0 0 4px 0;">Task History</h1>
            <p style="font-size: 14px; color: #64748B; margin: 0 0 16px 0;">
                All completed, active, and past autonomous workflow runs stored in the local database.
            </p>
        </div>
        """)
    with top_col2:
        if st.button("＋ New Task", type="primary", use_container_width=True):
            st.session_state["active_view"] = "workspace"
            st.session_state["active_task_id"] = None
            st.rerun()

    try:
        tasks = api_client.list_tasks(limit=50)
    except Exception as exc:
        st.error(f"Failed to query task history: {exc}")
        return

    if not tasks:
        st.info("ℹ️ No task runs recorded in database yet. Head over to the Workspace to launch your first research workflow.")
        if st.button("Go to Workspace →"):
            st.session_state["active_view"] = "workspace"
            st.rerun()
        return

    # Table Header Row
    h1, h2, h3, h4, h5 = st.columns([3.2, 1.4, 1.2, 2, 1.2])
    with h1: st.html("<div style='font-size: 12px; font-weight: 700; color: #64748B;'>Task Objective</div>")
    with h2: st.html("<div style='font-size: 12px; font-weight: 700; color: #64748B;'>Status</div>")
    with h3: st.html("<div style='font-size: 12px; font-weight: 700; color: #64748B;'>Sources</div>")
    with h4: st.html("<div style='font-size: 12px; font-weight: 700; color: #64748B;'>Date Created</div>")
    with h5: st.html("<div style='font-size: 12px; font-weight: 700; color: #64748B;'>Actions</div>")

    st.html("<hr style='margin: 8px 0 14px 0; border: none; border-top: 1px solid #E2E8F0;' />")

    # Render Task Rows
    for t in tasks:
        c1, c2, c3, c4, c5 = st.columns([3.2, 1.4, 1.2, 2, 1.2])
        
        with c1:
            title_text = t.get('title') or t.get('original_request', 'Untitled Task')[:50]
            st.html(f"<div style='font-size: 13.5px; font-weight: 700; color: #0F172A;'>{title_text}</div>")
        with c2:
            status = t.get('status', 'planned')
            st.html(f"<span class='status-badge badge-{status}'>● {status.replace('_', ' ').title()}</span>")
        with c3:
            st.html(f"<div style='font-size: 13px; color: #64748B;'>{t.get('sources_count', 0)} sources</div>")
        with c4:
            date_raw = str(t.get('created_at', ''))[:16].replace('T', ' ')
            st.html(f"<div style='font-size: 12.5px; color: #64748B;'>{date_raw}</div>")
        with c5:
            btn_label = "View Report" if t["status"] == "completed" else "Open"
            if st.button(btn_label, key=f"view_hist_{t['id']}", use_container_width=True):
                st.session_state["active_task_id"] = t["id"]
                if t["status"] == "completed":
                    st.session_state["active_view"] = "results"
                elif t["status"] in ("running", "retrying"):
                    st.session_state["active_view"] = "execution"
                else:
                    st.session_state["active_view"] = "plan"
                st.rerun()

        st.html("<hr style='margin: 8px 0 10px 0; border: none; border-top: 1px solid #F1F5F9;' />")
