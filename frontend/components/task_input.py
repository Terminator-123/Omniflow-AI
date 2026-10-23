"""Workspace component matching Panel 1 of the reference mockup (Hero, Floating Orb Graphic, Prompt Card, Examples)."""
import streamlit as st
from frontend.api_client import api_client

DEFAULT_TASK = (
    "Research the benefits and limitations of AI agents. Compare their capabilities, "
    "reliability, risks, and need for human oversight. Use IBM, Google Cloud and NIST "
    "as sources and generate a concise report with source links."
)

DEFAULT_SCOPE = "IBM, Google Cloud, NIST"

EXAMPLES = [
    {
        "icon": "📄",
        "title": "Research a topic",
        "desc": "Gather information from trusted sources",
        "task": DEFAULT_TASK,
        "scope": DEFAULT_SCOPE,
    },
    {
        "icon": "📊",
        "title": "Analyse a product",
        "desc": "Compare features, pricing and reviews",
        "task": "Compare the features, enterprise pricing, developer documentation, and user feedback of Google Vertex AI Agent Builder versus Amazon Bedrock Agents.",
        "scope": "cloud.google.com, aws.amazon.com",
    },
    {
        "icon": "📝",
        "title": "Create study material",
        "desc": "Generate notes, quizzes and flashcards",
        "task": "Synthesize a comprehensive study guide on LLM alignment, RLHF techniques, constitutional AI principles, and evaluation benchmarks.",
        "scope": "anthropic.com, openai.com, arxiv.org",
    },
    {
        "icon": "🔍",
        "title": "Competitor analysis",
        "desc": "Collect insights and summarize findings",
        "task": "Analyze enterprise AI governance offerings between IBM watsonx.governance, Microsoft Azure AI Content Safety, and Google Cloud Model Armor.",
        "scope": "ibm.com, microsoft.com, cloud.google.com",
    },
    {
        "icon": "🛡️",
        "title": "AI Risk & Safety Audit",
        "desc": "Assess risk frameworks and alignment standards",
        "task": "Investigate the NIST AI Risk Management Framework (AI RMF 1.0) and ISO/IEC 42001 standards for autonomous agent safety, red-teaming, and human-in-the-loop controls.",
        "scope": "nist.gov, iso.org",
    },
    {
        "icon": "⚡",
        "title": "Agentic Architecture Survey",
        "desc": "Analyze reactive vs proactive tool execution",
        "task": "Compare ReAct, Plan-and-Solve, and LangGraph multi-agent architectures for stateful digital workflows with recoverable error bounds.",
        "scope": "arxiv.org, langchain.com",
    },
]

def render_task_input():
    """Renders the Workspace view matching Panel 1 of the reference mockup."""
    if "current_task_input" not in st.session_state:
        st.session_state["current_task_input"] = DEFAULT_TASK
    if "current_scope_input" not in st.session_state:
        st.session_state["current_scope_input"] = DEFAULT_SCOPE
    if "selected_mode" not in st.session_state:
        st.session_state["selected_mode"] = "demo"
    if "show_file_uploader" not in st.session_state:
        st.session_state["show_file_uploader"] = False
    if "show_scope_editor" not in st.session_state:
        st.session_state["show_scope_editor"] = False
    if "show_advanced" not in st.session_state:
        st.session_state["show_advanced"] = False
    if "show_all_examples" not in st.session_state:
        st.session_state["show_all_examples"] = False

    # Top Hero Split: Left text & input, Right 3D Orb Graphic
    hero_col1, hero_col2 = st.columns([1.25, 1])

    with hero_col1:
        # Tag pill and Hero headline
        st.html("""
        <div style="margin-bottom: 8px;">
            <span style="font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #4F46E5; background: #EEF2FF; padding: 4px 10px; border-radius: 9999px;">
                TURN IDEAS INTO ACTION
            </span>
        </div>
        <h1 style="font-size: 40px; font-weight: 800; color: #0F172A; margin: 0 0 10px 0; line-height: 1.15; letter-spacing: -0.025em;">
            Your personal<br/>
            <span class="gradient-text">AI execution agent</span>
        </h1>
        <p style="font-size: 14.5px; color: #64748B; margin-bottom: 20px; line-height: 1.5; max-width: 480px;">
            Plan, research, create and automate multi-step tasks on the web while keeping you in control.
        </p>
        <div style="font-size: 12px; font-weight: 600; color: #64748B; margin-bottom: 6px;">
            Describe what you want to accomplish...
        </div>
        """)

        # Prompt Input Box
        task_text = st.text_area(
            label="Task Prompt",
            value=st.session_state["current_task_input"],
            height=110,
            placeholder="Describe what you want to accomplish...",
            label_visibility="collapsed",
        )

        # Bottom Bar inside prompt card: Interactive Chips + Submit Button
        chip_col1, chip_col2, chip_col3, btn_col = st.columns([1.2, 1.2, 1.2, 1.4])
        with chip_col1:
            if st.button("📎 Attach files", key="btn_chip_attach", use_container_width=True):
                st.session_state["show_file_uploader"] = not st.session_state["show_file_uploader"]
                st.rerun()
        with chip_col2:
            if st.button("🌐 Web search ▾", key="btn_chip_scope", use_container_width=True):
                st.session_state["show_scope_editor"] = not st.session_state["show_scope_editor"]
                st.rerun()
        with chip_col3:
            if st.button("⚙️ Advanced ▾", key="btn_chip_adv", use_container_width=True):
                st.session_state["show_advanced"] = not st.session_state["show_advanced"]
                st.rerun()
        with btn_col:
            if st.button("Run agent  →", type="primary", use_container_width=True):
                if not task_text.strip():
                    st.error("Please enter a task objective.")
                    return
                with st.spinner("Generating execution plan & ingesting attachments..."):
                    try:
                        task = api_client.create_task(
                            request=task_text.strip(),
                            scope=st.session_state.get("current_scope_input", DEFAULT_SCOPE),
                            execution_mode=st.session_state.get("selected_mode", "demo"),
                            mode=st.session_state.get("selected_mode", "demo"),
                        )
                        task_id = task["id"]
                        st.session_state["active_task_id"] = task_id

                        # Ingest any attached documents
                        pending_files = st.session_state.get("pending_uploaded_files", [])
                        for uf in pending_files:
                            try:
                                api_client.upload_document(task_id, uf.name, uf.getvalue())
                            except Exception as up_err:
                                st.warning(f"Failed to ingest document '{uf.name}': {up_err}")

                        st.session_state["pending_uploaded_files"] = []
                        st.session_state["active_view"] = "plan"
                        st.session_state["current_task_input"] = task_text
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to create task plan: {exc}")

        # Interactive Attachments Panel
        if st.session_state.get("show_file_uploader"):
            with st.container():
                st.html("<div style='font-size: 12px; font-weight: 700; color: #4F46E5; margin-top: 10px;'>📎 Attach Reference Documents (PDF, TXT, MD, DOCX)</div>")
                uploaded_files = st.file_uploader(
                    "Upload reference documents",
                    type=["pdf", "txt", "md", "docx"],
                    accept_multiple_files=True,
                    label_visibility="collapsed",
                    key="task_file_uploader",
                )
                if uploaded_files:
                    st.session_state["pending_uploaded_files"] = uploaded_files
                    st.success(f"Attached {len(uploaded_files)} reference document(s). They will be parsed and grounded upon running.")

        # Interactive Target Sources / Web Search Editor
        if st.session_state.get("show_scope_editor"):
            with st.container():
                st.html("<div style='font-size: 12px; font-weight: 700; color: #4F46E5; margin-top: 10px;'>🌐 Target Domains & Search Scope</div>")
                scope_val = st.text_input(
                    "Target Scope / Whitelisted Domains",
                    value=st.session_state["current_scope_input"],
                    placeholder="e.g. IBM, Google Cloud, NIST",
                    label_visibility="collapsed",
                )
                st.session_state["current_scope_input"] = scope_val

        # Interactive Advanced Settings Panel (Mode & Google Gemini API Key)
        if st.session_state.get("show_advanced"):
            with st.container():
                st.html("<div style='font-size: 12px; font-weight: 700; color: #4F46E5; margin-top: 10px;'>⚙️ Execution Settings & Google API Key</div>")
                s_col1, s_col2 = st.columns(2)
                with s_col1:
                    mode_opts = {
                        "demo": "Certified Demonstration (Offline Fixtures)",
                        "live": "Live Web Automation (Playwright Browser)",
                        "controlled_failure": "Controlled Failure & Recovery Demo",
                    }
                    mode_val = st.selectbox(
                        "Execution Mode",
                        options=list(mode_opts.keys()),
                        format_func=lambda k: mode_opts[k],
                        index=0 if st.session_state["selected_mode"] == "demo" else (1 if st.session_state["selected_mode"] == "live" else 2),
                    )
                    st.session_state["selected_mode"] = mode_val
                with s_col2:
                    api_key_input = st.text_input(
                        "Google Gemini API Key (Optional)",
                        type="password",
                        placeholder="AIzaSy...",
                        help="Enter your Google AI Studio API key to enable live Gemini LLM reasoning. If omitted, OmniFlow uses deterministic mode.",
                    )
                    if api_key_input:
                        res = api_client.set_gemini_key(api_key_input)
                        if res.get("status") == "success":
                            st.success("Google Gemini API Key connected!")
                        else:
                            st.info("API Key saved.")

    with hero_col2:
        # Floating 3D Orb and Connected Glass Cards Graphic
        st.html("""
        <div class="hero-orb-container">
            <!-- Glowing 3D Glass Sphere -->
            <div class="hero-orb"></div>

            <!-- Floating Card 1: Plan (Top Right) -->
            <div class="floating-pill-card" style="top: 25px; right: 20px;">
                <div class="f-icon-circle" style="background: #EEF2FF; color: #4F46E5;">📋</div>
                <div>
                    <div style="font-size: 13px; font-weight: 700; color: #0F172A;">Plan</div>
                    <div style="font-size: 11px; color: #64748B;">Break down your goal</div>
                </div>
            </div>

            <!-- Floating Card 2: Execute (Mid Left) -->
            <div class="floating-pill-card" style="top: 145px; left: 10px;">
                <div class="f-icon-circle" style="background: #EFF6FF; color: #2563EB;">⚡</div>
                <div>
                    <div style="font-size: 13px; font-weight: 700; color: #0F172A;">Execute</div>
                    <div style="font-size: 11px; color: #64748B;">Live task action on the web</div>
                </div>
            </div>

            <!-- Floating Card 3: Verify (Mid Right) -->
            <div class="floating-pill-card" style="top: 190px; right: 15px;">
                <div class="f-icon-circle" style="background: #FDF4FF; color: #9333EA;">🛡️</div>
                <div>
                    <div style="font-size: 13px; font-weight: 700; color: #0F172A;">Verify</div>
                    <div style="font-size: 11px; color: #64748B;">Check results and sources</div>
                </div>
            </div>

            <!-- Floating Card 4: Deliver (Bottom Right) -->
            <div class="floating-pill-card" style="bottom: 30px; right: 65px;">
                <div class="f-icon-circle" style="background: #ECFDF5; color: #059669;">📄</div>
                <div>
                    <div style="font-size: 13px; font-weight: 700; color: #0F172A;">Deliver</div>
                    <div style="font-size: 11px; color: #64748B;">Structured report</div>
                </div>
            </div>
        </div>
        """)

    st.html("<div style='height: 24px;'></div>")

    # Bottom Section: "Try an example" + 4 Cards
    ex_hdr1, ex_hdr2 = st.columns([4, 1])
    with ex_hdr1:
        st.html("<h3 style='font-size: 18px; font-weight: 700; margin: 0 0 14px 0;'>Try an example</h3>")
    with ex_hdr2:
        view_all_label = "Hide extra ←" if st.session_state["show_all_examples"] else "View all →"
        if st.button(view_all_label, key="btn_toggle_view_all"):
            st.session_state["show_all_examples"] = not st.session_state["show_all_examples"]
            st.rerun()

    active_examples = EXAMPLES if st.session_state["show_all_examples"] else EXAMPLES[:4]

    cols = st.columns(len(active_examples))
    for i, ex in enumerate(active_examples):
        with cols[i]:
            st.html(f"""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 14px; padding: 18px; min-height: 120px; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04); margin-bottom: 8px;">
                <div style="font-size: 22px; margin-bottom: 8px;">{ex['icon']}</div>
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 4px;">{ex['title']}</div>
                <div style="font-size: 12px; color: #64748B; line-height: 1.4;">{ex['desc']}</div>
            </div>
            """)
            if st.button(f"Load: {ex['title']}", key=f"btn_ex_{i}", use_container_width=True):
                st.session_state["current_task_input"] = ex["task"]
                st.session_state["current_scope_input"] = ex["scope"]
                st.rerun()
