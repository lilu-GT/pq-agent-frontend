import uuid
import requests
import streamlit as st
import time
import threading


def render(LAMBDA_URL: str, SHARED_SECRET: str):
    """Render the chat interface"""
    
    # Initialize chat history in session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "chat_run_id" not in st.session_state:
        st.session_state.chat_run_id = str(uuid.uuid4())
    
    # Initialize settings in session state
    if "show_timing" not in st.session_state:
        st.session_state.show_timing = True
    if "show_steps" not in st.session_state:
        st.session_state.show_steps = True
    if "show_run_id" not in st.session_state:
        st.session_state.show_run_id = True
    
    # Settings menu in top left
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        with st.popover("⚙️ Settings"):
            st.write("**Display Options**")
            st.session_state.show_timing = st.checkbox(
                "Show timing details", 
                value=st.session_state.show_timing
            )
            st.session_state.show_steps = st.checkbox(
                "Show observability steps", 
                value=st.session_state.show_steps
            )
            st.session_state.show_run_id = st.checkbox(
                "Show run IDs", 
                value=st.session_state.show_run_id
            )
    
    with col2:
        st.write(f"**Session ID:** `{st.session_state.chat_run_id}`")
    
    with col3:
        if st.button("New Session"):
            st.session_state.messages = []
            st.session_state.chat_run_id = str(uuid.uuid4())
            st.rerun()
    
    st.markdown("---")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Show metadata if available
            if message["role"] == "assistant" and "metadata" in message:
                metadata = message["metadata"]
                
                if st.session_state.show_run_id and "run_id" in metadata:
                    st.caption(f"run_id: `{metadata['run_id']}`")
                
                # Show timing summary if available
                if st.session_state.show_timing and "timing_summary" in metadata:
                    timing = metadata["timing_summary"]
                    with st.expander("Timing details", expanded=False):
                        st.write(f"🧠 Planner LLM: **{timing.get('planner_llm_ms', 0)/1000} s**")
                        st.write(f"✍️ Synthesis LLM: **{timing.get('synthesis_llm_ms', 0)/1000} s**")
                        
                        tools = timing.get("tools_ms", {})
                        if tools:
                            st.write("🔎 Tools:")
                            for name, ms in tools.items():
                                st.write(f"   • {name}: **{ms/1000} s**")
                        
                        st.write("---")
                        st.write(f"⏱️ **Total: {timing.get('total_ms', 0)/1000} s**")
                
                # Show steps if available
                if st.session_state.show_steps and "steps_for_observability" in metadata:
                    with st.expander("Steps / Observability", expanded=False):
                        st.text(metadata["steps_for_observability"])
    
    # Chat input
    if prompt := st.chat_input("Ask a question about Parliamentary matters..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Display assistant response with loading
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            status_placeholder = st.empty()
            
            # Show loading status
            with status_placeholder.status("Agent is thinking...", expanded=False) as status:
                def invoke_agent(q: str, rid: str):
                    headers = {"Content-Type": "application/json"}
                    if SHARED_SECRET:
                        headers["x-shared-secret"] = SHARED_SECRET
                    
                    payload = {"query": q}
                    if rid:
                        payload["run_id"] = rid
                    
                    r = requests.post(LAMBDA_URL, headers=headers, json=payload, timeout=180, verify=False)
                    return r.status_code, r.headers.get("content-type", ""), r.text
                
                def _invoke_worker(result_holder: dict, query: str, run_id: str):
                    try:
                        code, content_type, text = invoke_agent(query, run_id)
                        result_holder["ok"] = True
                        result_holder["text"] = text
                    except Exception as e:
                        result_holder["ok"] = False
                        result_holder["error"] = f"{type(e).__name__}: {e}"
                
                holder = {}
                run_id = str(uuid.uuid4())
                
                t = threading.Thread(
                    target=_invoke_worker,
                    args=(holder, prompt, run_id),
                    daemon=True,
                )
                t.start()
                
                # Wait for completion
                while t.is_alive():
                    time.sleep(0.3)
                
                status.update(label="Completed", state="complete")
            
            status_placeholder.empty()
            
            # Process response
            if not holder.get("ok"):
                error_msg = f"Error: {holder.get('error', 'unknown error')}"
                message_placeholder.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": error_msg
                })
            else:
                try:
                    data = requests.models.complexjson.loads(holder.get("text", ""))
                except Exception:
                    data = {"raw": holder.get("text", "")}
                
                if "error" in data:
                    error_msg = f"Error: {data['error']}"
                    message_placeholder.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
                else:
                    # Get final answer
                    final_answer = data.get("final_answer", holder.get("text", "No response"))
                    message_placeholder.markdown(final_answer)
                    
                    # Store message with metadata
                    message_data = {
                        "role": "assistant",
                        "content": final_answer,
                        "metadata": {
                            "run_id": data.get("run_id"),
                        }
                    }
                    
                    # Add timing and steps if available
                    if "timing_summary" in data:
                        message_data["metadata"]["timing_summary"] = data["timing_summary"]
                    
                    if "steps_for_observability" in data:
                        message_data["metadata"]["steps_for_observability"] = data["steps_for_observability"]
                    
                    st.session_state.messages.append(message_data)
                    
                    # Display metadata
                    if st.session_state.show_run_id and data.get("run_id"):
                        st.caption(f"run_id: `{data.get('run_id')}`")
                    
                    # Show timing
                    if st.session_state.show_timing and "timing_summary" in data:
                        timing = data["timing_summary"]
                        with st.expander("Timing details", expanded=False):
                            st.write(f"🧠 Planner LLM: **{timing.get('planner_llm_ms', 0)/1000} s**")
                            st.write(f"✍️ Synthesis LLM: **{timing.get('synthesis_llm_ms', 0)/1000} s**")
                            
                            tools = timing.get("tools_ms", {})
                            if tools:
                                st.write("🔎 Tools:")
                                for name, ms in tools.items():
                                    st.write(f"   • {name}: **{ms/1000} s**")
                            
                            st.write("---")
                            st.write(f"⏱️ **Total: {timing.get('total_ms', 0)/1000} s**")
                    
                    # Show steps
                    if st.session_state.show_steps and "steps_for_observability" in data:
                        with st.expander("Steps / Observability", expanded=False):
                            st.text(data["steps_for_observability"])
