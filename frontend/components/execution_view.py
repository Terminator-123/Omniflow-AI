"""Live Execution component dynamically visualizing real agent steps, streaming events, and tool telemetry."""
import time
from datetime import datetime
import streamlit as st
from frontend.api_client import api_client

def render_execution_view():
    """Renders the Live Execution screen matching Panel 3 of the mockup with 100% genuine execution data."""
    task_id = st.session_state.get("active_task_id")
    if not task_id:
        st.warning("No active execution found. Please submit a task in the Workspace.")
        if st.button("← Return to Workspace"):
            st.session_state["active_view"] = "workspace"
            st.rerun()
        return

    try:
        task = api_client.get_task(task_id)
        events = api_client.get_events(task_id)
        evidence_list = api_client.get_evidence(task_id)
        sources_list = api_client.get_sources(task_id)
    except Exception as exc:
        st.error(f"Error communicating with backend: {exc}")
        return

    task_status = task["status"]
    steps = task.get("steps", [])

    # Top Header & Controls Row
    top_col1, top_col2 = st.columns([3, 1.2])
    with top_col1:
        st.html(f"""
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
            <h1 style="font-size: 26px; font-weight: 800; color: #0F172A; margin: 0;">Live Execution</h1>
            <span class="status-badge badge-{task_status}">● {task_status.replace('_', ' ').title()}</span>
        </div>
        <p style="font-size: 14px; color: #64748B; margin: 0 0 16px 0;">
            OmniFlow is actively executing your research goal. Telemetry and state transitions are streamed below.
        </p>
        """)

    with top_col2:
        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        with btn_c2:
            if st.button("⏹ Stop", type="primary", use_container_width=True):
                api_client.cancel_task(task_id)
                st.warning("Execution halt requested.")
                st.rerun()

    # If completed, show primary direct button to view report
    if task_status == "completed":
        st.success(f"✨ Task finalized. Synthesized {len(sources_list)} sources and {len(evidence_list)} evidence records.")
        if st.button("View Final Report & Deliverables →", type="primary"):
            st.session_state["active_view"] = "results"
            st.rerun()

    st.html("<div style='height: 8px;'></div>")

    # Calculate real progress
    total_steps = len(steps)
    completed_steps = sum(1 for s in steps if s.get("status") == "completed")
    progress_pct = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
    active_step = next((s for s in steps if s.get("status") in ("running", "retrying")), None)

    # 2-Column Execution Grid: Left Steps, Right Live Activity & Tool Details
    col_steps, col_activity = st.columns([1.6, 1.2])

    with col_steps:
        for s in steps:
            order = s["step_order"]
            status = s["status"]
            title = s["title"]
            summary = s.get("output_summary") or s.get("description")
            retries = s.get("retry_count", 0)

            if status == "completed":
                st.html(f"""
                <div class="timeline-step completed">
                    <div class="step-circle" style="background: #10B981; color: #FFFFFF;">✓</div>
                    <div style="flex-grow: 1;">
                        <div style="display: flex; justify-content: space-between; align-items: baseline;">
                            <span style="font-size: 14px; font-weight: 700; color: #0F172A;">{title}</span>
                            <span style="font-size: 12px; font-weight: 600; color: #059669;">Completed</span>
                        </div>
                        <div style="font-size: 12.5px; color: #64748B; margin-top: 2px;">{summary}</div>
                    </div>
                </div>
                """)
            elif status in ("running", "retrying"):
                active_label = f"Retrying #{retries}" if status == "retrying" else "Running ~ active"
                tool_in = s.get("tool_input", {})
                target_url = tool_in.get("url") or (sources_list[-1]["url"] if sources_list else "")
                
                st.html(f"""
                <div class="timeline-step running" style="flex-direction: column;">
                    <div style="display: flex; align-items: center; gap: 14px; width: 100%;">
                        <div class="step-circle" style="background: #4F46E5; color: #FFFFFF; box-shadow: 0 0 12px rgba(79, 70, 229, 0.4);">⚡</div>
                        <div style="flex-grow: 1;">
                            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                                <span style="font-size: 15px; font-weight: 700; color: #0F172A;">{title}</span>
                                <span style="font-size: 12px; font-weight: 700; color: #4F46E5;">{active_label}</span>
                            </div>
                            <div style="font-size: 12.5px; color: #64748B; margin-top: 2px;">{summary}</div>
                        </div>
                    </div>
                """)
                if target_url:
                    st.html(f"""
                    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 12px; margin-top: 12px; width: 100%;">
                        <div style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase; margin-bottom: 4px;">Target Resource</div>
                        <div style="font-size: 12px; font-family: monospace; color: #1E293B; word-break: break-all;">{target_url}</div>
                    </div>
                    """)
                st.html("</div>")
            else:
                # Pending step
                st.html(f"""
                <div class="timeline-step">
                    <div class="step-circle" style="background: #F1F5F9; color: #94A3B8;">{order}</div>
                    <div style="flex-grow: 1;">
                        <div style="display: flex; justify-content: space-between; align-items: baseline;">
                            <span style="font-size: 14px; font-weight: 600; color: #64748B;">{title}</span>
                            <span style="font-size: 12px; color: #94A3B8;">Pending</span>
                        </div>
                        <div style="font-size: 12px; color: #94A3B8; margin-top: 2px;">{summary}</div>
                    </div>
                </div>
                """)

    with col_activity:
        # Build live activity entries from real database execution events
        activity_rows = []
        if events:
            for ev in events[-7:]:
                t_raw = ev.get("timestamp", "")
                t_str = t_raw[11:19] if len(t_raw) >= 19 else "Just now"
                msg = ev.get("message", "Processing operation")
                level = ev.get("level", "INFO")
                dot_color = "#10B981" if level == "SUCCESS" else ("#F59E0B" if level == "WARNING" else ("#EF4444" if level == "ERROR" else "#6366F1"))
                activity_rows.append(f"""
                <div style="display: flex; gap: 10px; align-items: baseline; margin-bottom: 8px;">
                    <span style="color: #94A3B8; font-family: monospace; font-size: 11px;">{t_str}</span>
                    <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: {dot_color}; flex-shrink: 0;"></span>
                    <span style="color: #0F172A; font-size: 12.5px;">{msg}</span>
                </div>
                """)
        else:
            activity_rows = [
                '<div style="font-size: 12px; color: #94A3B8;">Initializing agent execution pipeline...</div>'
            ]

        entries_html = "".join(activity_rows)

        st.html(f"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 20px; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04); margin-bottom: 16px;">
            <div style="font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 14px;">Live Activity Stream</div>
            <div style="font-size: 12.5px; line-height: 1.5; color: #334155; max-height: 220px; overflow-y: auto;">
                {entries_html}
            </div>
        </div>
        """)

        # Real Tool & Workflow Progress Telemetry
        active_tool = active_step.get("tool_name", "None") if active_step else "Workflow complete"
        target_display = "Completed" if not active_step else (active_step.get("tool_input", {}).get("url") or active_step.get("title"))
        active_retries = active_step.get("retry_count", 0) if active_step else 0

        st.html(f"""
        <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 20px; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);">
            <div style="font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 12px;">Active Step Telemetry</div>

            <div style="font-size: 12px; color: #64748B; margin-bottom: 4px; display: flex; justify-content: space-between;">
                <span>Workflow Progress</span>
                <span style="font-weight: 700; color: #0F172A;">{completed_steps}/{total_steps} ({progress_pct}%)</span>
            </div>
            <div style="width: 100%; height: 6px; background: #E2E8F0; border-radius: 9999px; overflow: hidden; margin-bottom: 16px;">
                <div style="width: {progress_pct}%; height: 100%; background: #4F46E5; border-radius: 9999px;"></div>
            </div>

            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 8px;">
                <span style="color: #64748B;">Active Tool</span>
                <span style="font-family: monospace; color: #4338CA; font-weight: 600;">{active_tool}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 8px;">
                <span style="color: #64748B;">Current Step Status</span>
                <span style="font-weight: 600; color: #059669;">{task_status.capitalize()}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 8px;">
                <span style="color: #64748B;">Sources Harvested</span>
                <span style="font-weight: 600; color: #0F172A;">{len(sources_list)}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 12px;">
                <span style="color: #64748B;">Active Step Retries</span>
                <span style="font-weight: 600; color: #0F172A;">{active_retries} / 2</span>
            </div>
        </div>
        """)

    # Auto-polling loop when actively executing
    if task_status in ("running", "retrying"):
        time.sleep(1.2)
        st.rerun()
