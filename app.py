import streamlit as st
from ui import question, chat

st.set_page_config(page_title="PQ Agent Demo", menu_items={})
st.title("Parliamentary QA Agent")

LAMBDA_URL = st.secrets["LAMBDA_URL"]
SHARED_SECRET = st.secrets.get("SHARED_SECRET", "")
INTERFACE_TYPE = st.secrets.get("INTERFACE_TYPE", "CHAT")

# Render the appropriate interface based on INTERFACE_TYPE
if INTERFACE_TYPE == "QUESTION":
    question.render(LAMBDA_URL, SHARED_SECRET)
elif INTERFACE_TYPE == "CHAT":
    chat.render(LAMBDA_URL, SHARED_SECRET)
else:
    st.error(f"Unknown INTERFACE_TYPE: {INTERFACE_TYPE}")
