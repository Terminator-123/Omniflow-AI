"""Execution Plan component matching Panel 2 of the reference mockup."""
import streamlit as st
from frontend.api_client import api_client

def render_plan_view():
    """Renders the Execution Plan screen matching Panel 2 of the mockup."""
    task_id = st.session_state.get("active_task_id")
    if not task_id:
        st.warning("No active task selected. Please define a task in the Workspace.")
        if st.button("← Return to Workspace"):
            st.session_state["active_view"] = "workspace"
            st.rerun()
        return

    try:
        task = api_client.get_task(task_id)
    except Exception as exc:
        st.error(f"Could not load task plan: {exc}")
        return

    # Top Bar: Back button, Title, Action Buttons
    top_col1, top_col2, top_col3 = st.columns([1, 4, 2])
    with top_col1:
        if st.button("← Back", use_container_width=True):
            st.session_state["active_view"] = "workspace"
            st.rerun()

    with top_col2:
        req_preview = task.get("original_request", "")[:80] + ("..." if len(task.get("original_request", "")) > 80 else "")
        st.html(f"<div style='font-size: 13px; color: #64748B; padding-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;'><b>Target:</b> {req_preview}</div>")

    with top_col3:
        act_c1, act_c2 = st.columns(2)
        with act_c1:
            if st.button("Edit task", use_container_width=True):
                st.session_state["current_task_input"] = task["original_request"]
                st.session_state["active_view"] = "workspace"
                st.rerun()
        with act_c2:
            if st.button("Run task →", type="primary", use_container_width=True):
                with st.spinner("Approving plan and launching autonomous agent..."):
                    try:
                        api_client.approve_task(task_id, decision="approved")
                        api_client.start_task(task_id)
                        st.session_state["active_view"] = "execution"
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to start task: {exc}")

    st.html("<div style='height: 8px;'></div>")

    # Title & Subhead
    steps = task.get("steps", [])
    st.html(f"""
    <div>
        <h1 style="font-size: 26px; font-weight: 800; color: #0F172A; margin: 0 0 4px 0;">Execution Plan</h1>
        <p style="font-size: 14px; color: #64748B; margin: 0 0 20px 0;">
            OmniFlow has created a plan with {len(steps)} steps based on your goal. Review and approve to start.
        </p>
    </div>
    """)

    # Main 2-Column Split: Left Steps, Right Task Overview & Safety
    left_col, right_col = st.columns([2.2, 1])

    with left_col:
        badge_map = {
            "web_search": ("Web Search API", "tool-search", "~15s"),
            "browser_page_extractor": ("Playwright", "tool-browser", "~1m"),
            "evidence_synthesizer": ("Gemini LLM", "tool-gemini", "~15s"),
            "report_generator": ("Gemini LLM", "tool-gemini", "~20s"),
            "result_verifier": ("Verification", "tool-verify", "~10s"),
        }

        for s in steps:
            order = s["step_order"]
            tool_name = s["tool_name"]
            tool_label, tool_cls, est_time = badge_map.get(tool_name, (tool_name, "tool-gemini", "~15s"))
            desc = s["description"]

            st.html(f"""
            <div class="timeline-step">
                <div class="step-circle">{order}</div>
                <div style="flex-grow: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                        <span style="font-size: 15px; font-weight: 700; color: #0F172A;">{s['title']}</span>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <span class="tool-pill {tool_cls}">{tool_label}</span>
                            <span style="font-size: 12px; color: #94A3B8;">{est_time}</span>
                        </div>
                    </div>
                    <div style="font-size: 13px; color: #64748B; line-height: 1.45;">
                        {desc}
                    </div>
                </div>
            </div>
            """)

    with right_col:
        # Task Overview Card
        st.html("""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 20px; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04); margin-bottom: 16px;">
            <div style="font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 14px;">Task overview</div>
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 10px;">
                <span style="color: #64748B;">Type</span>
                <span style="font-weight: 600; color: #0F172A;">Web research</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 10px;">
                <span style="color: #64748B;">Estimated time</span>
                <span style="font-weight: 600; color: #0F172A;">2-3 minutes</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 10px;">
                <span style="color: #64748B;">Expected sources</span>
                <span style="font-weight: 600; color: #0F172A;">3-5 sources</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 12px;">
                <span style="color: #64748B;">Output</span>
                <span style="font-weight: 600; color: #0F172A;">Markdown + PDF</span>
            </div>
            <div style="font-size: 12px; color: #64748B; border-top: 1px solid #F1F5F9; padding-top: 10px;">
                <b>Tools to be used:</b> Playwright, Google Gemini, Web Search
            </div>
        </div>
        <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 16px; padding: 18px; margin-bottom: 16px;">
            <div style="display: flex; gap: 10px; align-items: flex-start;">
                <div style="font-size: 18px;">🛡️</div>
                <div>
                    <div style="font-size: 13px; font-weight: 700; color: #92400E; margin-bottom: 4px;">Safety & control</div>
                    <div style="font-size: 12px; color: #B45309; line-height: 1.45;">
                        Read-only actions only. No sensitive data will be accessed without your approval.
                    </div>
                </div>
            </div>
        </div>
        """)

        st.toggle("Require approval for web actions", value=True)
