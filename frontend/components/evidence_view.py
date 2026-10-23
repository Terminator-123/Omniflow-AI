"""Evidence Explorer component dynamically visualizing genuine captured sources, evidence trails, and claim audits."""
import streamlit as st
from frontend.api_client import api_client

DEMO_FALLBACK_SOURCES = [
    {
        "title": "[Demo Fixture] What are AI agents? | IBM",
        "domain": "ibm.com",
        "url": "https://www.ibm.com/think/topics/ai-agents",
        "access_status": "demo_fixture",
        "http_status_code": 200,
        "extracted_chars": 4200,
        "accessed_at": "Demo Catalog",
        "raw_content_preview": "AI agents are autonomous software entities powered by foundational models that perceive their environment, reason, plan multi-step workflows, and take actions using tools.",
    },
    {
        "title": "[Demo Fixture] AI agents on Google Cloud",
        "domain": "cloud.google.com",
        "url": "https://cloud.google.com/discover/what-are-ai-agents",
        "access_status": "demo_fixture",
        "http_status_code": 200,
        "extracted_chars": 3850,
        "accessed_at": "Demo Catalog",
        "raw_content_preview": "Google Cloud defines AI agents as autonomous systems combining large language models with external tools, reasoning engines, and runtime memory to execute complex business tasks.",
    },
    {
        "title": "[Demo Fixture] NIST AI Risk Management Framework",
        "domain": "nist.gov",
        "url": "https://www.nist.gov/itl/ai-risk-management-framework",
        "access_status": "demo_fixture",
        "http_status_code": 200,
        "extracted_chars": 5100,
        "accessed_at": "Demo Catalog",
        "raw_content_preview": "The NIST AI RMF offers voluntary guidance to improve the ability to incorporate trustworthiness considerations into the design, development, use, and evaluation of AI products.",
    },
]

def render_evidence_view():
    """Renders the Evidence Explorer master-detail split screen with honest evidence attribution."""
    task_id = st.session_state.get("active_task_id")
    if not task_id:
        st.warning("No active task selected. Please define a task in the Workspace.")
        return

    try:
        evidence_list = api_client.get_evidence(task_id)
        sources_list = api_client.get_sources(task_id)
        task_info = api_client.get_task(task_id)
    except Exception as exc:
        st.error(f"Error loading evidence trail: {exc}")
        return

    is_demo_task = (task_info.get("execution_mode") == "demo") if task_info else False

    # Top Header & Search Bar
    top_c1, top_c2 = st.columns([2.5, 1.5])
    with top_c1:
        st.html("""
        <div>
            <h1 style="font-size: 26px; font-weight: 800; color: #0F172A; margin: 0 0 4px 0;">Evidence Explorer</h1>
            <p style="font-size: 14px; color: #64748B; margin: 0 0 16px 0;">
                All collected sources, extracted content and how they support the findings.
            </p>
        </div>
        """)

    with top_c2:
        search_query = st.text_input("Search sources...", placeholder="Filter by domain or keyword...", label_visibility="collapsed")

    # Determine Active Sources
    if sources_list:
        active_sources = sources_list
        is_demo_mode = False
    elif is_demo_task:
        active_sources = DEMO_FALLBACK_SOURCES
        is_demo_mode = True
        st.info("ℹ️ **Demo Mode:** Displaying certified demonstration fixtures. Run an agent in Live mode for real web discovery.")
    else:
        st.info("ℹ️ No sources have been captured for this task yet. Please start or approve task execution to collect evidence.")
        return

    # Filter sources if search query is provided
    if search_query and search_query.strip():
        q_lower = search_query.strip().lower()
        active_sources = [
            s for s in active_sources
            if q_lower in s.get("title", "").lower()
            or q_lower in s.get("domain", "").lower()
            or q_lower in s.get("url", "").lower()
        ]

    if not active_sources:
        st.warning(f"No sources match search filter: '{search_query}'")
        return

    # Master-Detail Layout
    col_master, col_detail = st.columns([1.3, 2.2])

    # Left Column: Source Cards
    with col_master:
        st.html(f"<div style='font-size: 12px; font-weight: 700; color: #64748B; text-transform: uppercase; margin-bottom: 10px;'>Collected Sources ({len(active_sources)})</div>")
        
        if "selected_source_idx" not in st.session_state:
            st.session_state["selected_source_idx"] = 0

        # Bound check
        if st.session_state["selected_source_idx"] >= len(active_sources):
            st.session_state["selected_source_idx"] = 0

        for idx, src in enumerate(active_sources):
            is_active = (st.session_state["selected_source_idx"] == idx)
            active_border = "border: 2px solid #6366F1;" if is_active else "border: 1px solid #E2E8F0;"
            active_bg = "background: #F8FAFC;" if is_active else "background: #FFFFFF;"
            acc_date = str(src.get("accessed_at", "Recently"))[:16]
            dom_text = src.get("domain", "web")
            status_text = src.get("access_status", "success")

            status_color = "#059669" if status_text in ("success", "recovered", "user_provided") else "#D97706"
            status_bg = "#ECFDF5" if status_text in ("success", "recovered", "user_provided") else "#FEF3C7"

            st.html(f"""
            <div style="{active_bg} {active_border} border-radius: 12px; padding: 12px 16px; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);">
                <div style="font-size: 13.5px; font-weight: 700; color: #0F172A; margin-bottom: 4px;">{src.get('title', 'Untitled')}</div>
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11.5px; color: #64748B;">
                    <span>{dom_text}</span>
                    <span style="background: {status_bg}; color: {status_color}; font-weight: 600; padding: 2px 6px; border-radius: 9999px;">{status_text}</span>
                </div>
            </div>
            """)
            if st.button(f"Select: {src.get('title', '')[:24]}...", key=f"src_select_{idx}", use_container_width=True):
                st.session_state["selected_source_idx"] = idx
                st.rerun()

    # Right Column: Detail Card Pane
    with col_detail:
        cur_idx = min(st.session_state.get("selected_source_idx", 0), len(active_sources) - 1)
        sel_src = active_sources[cur_idx]
        sel_domain = sel_src.get("domain", "")
        sel_url = sel_src.get("url", "#")

        # Find evidence items associated with this source
        linked_evidences = [
            e for e in evidence_list
            if (e.get("source_url") and e.get("source_url") == sel_url)
            or (sel_domain and sel_domain in str(e.get("source_url", "")))
        ]

        tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Extracted Content", "Relevance & Claims", "Metadata"])

        with tab1:
            preview_content = sel_src.get("raw_content_preview") or "No textual preview available."
            preview_summary = preview_content[:300].strip() + ("..." if len(preview_content) > 300 else "")

            st.html(f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 22px; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                    <div>
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <h2 style="font-size: 20px; font-weight: 800; color: #0F172A; margin: 0;">{sel_src.get('title')}</h2>
                        </div>
                        <div style="font-size: 12.5px; color: #4F46E5; margin-top: 4px;">
                            <a href="{sel_url}" target="_blank" style="color: #4F46E5; text-decoration: none; font-weight: 600;">{sel_url} ↗</a>
                        </div>
                    </div>
                    <div style="background: #EEF2FF; color: #4338CA; font-weight: 800; font-size: 13px; padding: 6px 12px; border-radius: 8px;">
                        {sel_domain.upper()[:12]}
                    </div>
                </div>

                <hr style="margin: 14px 0 18px 0; border: none; border-top: 1px solid #F1F5F9;" />

                <div style="font-size: 13.5px; font-weight: 700; color: #0F172A; margin-bottom: 6px;">Source Excerpt Summary</div>
                <p style="font-size: 13px; color: #475569; line-height: 1.55; margin-bottom: 16px;">
                    {preview_summary}
                </p>

                <div style="font-size: 13.5px; font-weight: 700; color: #0F172A; margin-bottom: 8px;">Extracted Evidence Findings ({len(linked_evidences)})</div>
            """)

            if linked_evidences:
                for ev in linked_evidences:
                    st.html(f"""
                    <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 12px 14px; margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                            <span style="font-family: monospace; font-size: 12px; font-weight: 700; color: #4338CA; background: #EEF2FF; padding: 2px 6px; border-radius: 4px;">{ev.get('stable_id')}</span>
                            <span style="font-size: 11px; font-weight: 600; color: #059669; background: #ECFDF5; padding: 2px 6px; border-radius: 9999px;">{ev.get('verification_status')}</span>
                        </div>
                        <div style="font-size: 12.5px; font-weight: 600; color: #1E293B; margin-bottom: 4px;">{ev.get('research_question')}</div>
                        <div style="font-size: 12px; color: #64748B; font-style: italic;">&ldquo;{ev.get('excerpt')}&rdquo;</div>
                    </div>
                    """)
            else:
                st.html("""
                <div style="font-size: 12.5px; color: #64748B; padding: 8px 0;">
                    No discrete claim-level evidence items linked to this source yet.
                </div>
                """)

            st.html("</div>")

        with tab2:
            st.html(f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 22px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div style="font-size: 14px; font-weight: 700; color: #0F172A;">Extracted Content Stream</div>
                    <span style="font-size: 12px; color: #64748B; background: #F1F5F9; padding: 2px 8px; border-radius: 4px;">{sel_src.get('extracted_chars', 0):,} chars</span>
                </div>
                <div style="font-family: monospace; font-size: 12px; background: #F8FAFC; padding: 14px; border-radius: 10px; border: 1px solid #E2E8F0; max-height: 340px; overflow-y: auto; color: #334155; line-height: 1.6; white-space: pre-wrap;">
{sel_src.get('raw_content_preview') or 'No raw content extracted.'}
                </div>
            </div>
            """)

        with tab3:
            st.html("""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 22px;">
                <div style="font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 8px;">Claim Verification & Target Relevance</div>
            """)

            if linked_evidences:
                for ev in linked_evidences:
                    st.html(f"""
                    <div style="border-bottom: 1px solid #F1F5F9; padding-bottom: 12px; margin-bottom: 12px;">
                        <div style="font-size: 13px; font-weight: 700; color: #0F172A;">
                            <code>{ev.get('stable_id')}</code> — {ev.get('finding')}
                        </div>
                        <div style="font-size: 12px; color: #475569; margin-top: 4px;">
                            • <b>Status:</b> <code>{ev.get('verification_status')}</code><br/>
                            • <b>Grounding:</b> Verbatim source passage extracted and mapped.<br/>
                            • <b>Relevance:</b> Anchored to research objective.
                        </div>
                    </div>
                    """)
            else:
                st.html("""
                <div style="font-size: 13px; color: #64748B; padding: 8px 0;">
                    • <b>Relevance Metric:</b> Not measured (no discrete claims attached to this candidate source)<br/>
                    • <b>Status:</b> Candidate source indexed.
                </div>
                """)

            st.html("</div>")

        with tab4:
            st.html(f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 22px;">
                <div style="font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 12px;">Source Provenance & Metadata</div>
                <div style="font-size: 13px; color: #475569; line-height: 1.8;">
                    • <b>Domain:</b> <code>{sel_domain}</code><br/>
                    • <b>Canonical URL:</b> <a href="{sel_url}" target="_blank" style="color: #4F46E5;">{sel_url}</a><br/>
                    • <b>HTTP Status:</b> <code>{sel_src.get('http_status_code', 200)}</code><br/>
                    • <b>Access Status:</b> <code>{sel_src.get('access_status', 'success')}</code><br/>
                    • <b>Characters Extracted:</b> {sel_src.get('extracted_chars', 0):,}<br/>
                    • <b>Accessed At:</b> {sel_src.get('accessed_at', 'Recorded in database')}<br/>
                </div>
            </div>
            """)
