import uuid
import requests
import streamlit as st
import time
import threading

st.set_page_config(page_title="PQ Agent Demo")
st.title("Parliamentary QA Agent")

LAMBDA_URL = st.secrets["LAMBDA_URL"]
SHARED_SECRET = st.secrets.get("SHARED_SECRET", "")

st.text(
    "An agentic QA prototype to answer Singapore Parliamentary Questions.\n"
    "It analyses the question, plans tool usage, retrieves relevant information from multiple sources, "
    "and synthesises a draft Ministerial-style reply with source attribution."
)

DEFAULT_QUESTION = (
    "Mr Fadli Fawzi asked the Acting Minister for Transport\n"
    "(a) what factors contribute to train punctuality on shorter MRT lines such as the NEL in recent news;\n"
    "(b) how these compare with longer lines; and\n"
    "(c) whether dwell times can be reduced to shorten commutes and\n"
    "(d) if not, why not."
)

if "query" not in st.session_state:
    st.session_state["query"] = DEFAULT_QUESTION

def restore_default():
    st.session_state["query"] = DEFAULT_QUESTION
    
st.text('')
st.text('')

st.markdown("##### Please enter a Parliamentary Question")

query = st.text_area(
    "",
    height=220,
    key = "query",
)

st.button("Restore default example", on_click=restore_default)

col1, col2 = st.columns([1, 1])
with col1:
    run_id = str(uuid.uuid4())
    st.text_input("run_id", value=run_id, disabled=True)


with col2:
    show_steps = st.checkbox("Show steps_for_observability", value=True)
    show_raw = st.checkbox("Show raw response", value=False)

def invoke_agent(q: str, rid: str):
    headers = {"Content-Type": "application/json"}
    if SHARED_SECRET:
        headers["x-shared-secret"] = SHARED_SECRET

    payload = {"query": q}
    # only when run_id looks like UUID 
    if rid and len(rid) >= 33:
        payload["run_id"] = rid

    r = requests.post(LAMBDA_URL, headers=headers, json=payload, timeout=(10, 460))
    

    return r.status_code, r.headers.get("content-type", ""), r.text

STEPS = [
    "🤖 Analysing the Parliamentary Question",
    "🧠 Planning next actions (planner)",
    "🔎 Calling tools to retrieve supporting information",
    "🧩 Consolidating evidence across sources",
    "🧠 Planning next actions (planner)",
    "🔎 Calling tools to retrieve supporting information",
    "🧩 Consolidating evidence across sources",
    "🧠 Planning next actions (planner)",
    "🔎 Calling tools to retrieve supporting information",
    "🧩 Consolidating evidence across sources",
    "✍️ Writing a Ministerial-style draft reply",
]
STEP_INTERVAL_S = 5

def _invoke_worker(result_holder: dict, query: str, run_id: str):
    try:
        code, content_type, text = invoke_agent(query, run_id)
        result_holder["ok"] = True
        result_holder["text"] = text
    except Exception as e:
        result_holder["ok"] = False
        result_holder["error"] = f"{type(e).__name__}: {e}"

if st.button("Invoke", type="primary"):
    if not query.strip():
        st.warning("Please enter a Parliamentary Question.")
        st.stop()

    holder = {}
    t = threading.Thread(
        target=_invoke_worker,
        args=(holder, query, run_id),
        daemon=True,
    )
    t.start()

    with st.status("Agent is working on your question...", expanded=True) as status:
        for step in STEPS:
            status.write(step)
            time.sleep(STEP_INTERVAL_S)

            if not t.is_alive():
                break

        while t.is_alive():
            time.sleep(0.3)

        status.update(label="Completed", state="complete")

    if not holder.get("ok"):
        st.error(f"Invoke failed: {holder.get('error', 'unknown error')}")
        st.stop()

    # show results
    st.subheader("Result")

    try:
        data = requests.models.complexjson.loads(holder.get("text", ""))
    except Exception:
        data = {"raw": holder.get("text", "")}

    if "error" in data:
        st.error(data["error"])
        st.stop()

    st.write(f"**run_id:** `{data.get('run_id', 'N/A')}`")

    st.subheader("Final answer")
    st.write(data.get("final_answer", ""))
    
    if show_steps:
        with st.expander("Steps / Observability", expanded=False):
            st.text(data.get("steps_for_observability", ""))

    if "timing_summary" in data:
        timing = data.get("timing_summary", {})
        with st.expander("Timing summary", expanded=False):
            if not timing:
                st.write("No timing information available.")
            else:
                st.write(f"🧠 Planner LLM: **{timing.get('planner_llm_ms', 0)/1000} s**")
                st.write(f"✍️ Synthesis LLM: **{timing.get('synthesis_llm_ms', 0)/1000} s**")

                tools = timing.get("tools_ms", {})
                if tools:
                    st.write("🔎 Tools:")
                    for name, ms in tools.items():
                        st.write(f"   • {name}: **{ms/1000} s**")

                st.write("---")
                st.write(f"⏱️ **Total: {timing.get('total_ms', 0)/1000} s**")

    if show_raw:
        with st.expander("Raw response JSON", expanded=False):
            st.code(holder.get("text", ""), language="json")