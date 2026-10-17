"""Web UI for the study assistant. It only talks to the FastAPI backend over HTTP.

Run (with the API running on port 8000):
    streamlit run ui/app.py
"""

import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")


def api_status() -> dict | None:
    """Return the /health result, or None if the API can't be reached at all."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
    except requests.RequestException:
        return None
    body = response.json()
    return body if response.ok else body.get("detail", {})


st.set_page_config(page_title="Lecture Study Assistant", page_icon="📚")
st.title("📚 Lecture Study Assistant")
st.caption("Answers only from your lecture slides, with the slide numbers as sources.")


# --- Sidebar: status and upload ----------------------------------------------

with st.sidebar:
    st.header("Status")
    status = api_status()
    if status is None:
        st.error(f"API not reachable at {API_URL}. Is uvicorn running?")
    else:
        for service, state in status.items():
            st.write(f"{'✅' if state == 'ok' else '❌'} {service}")

    st.header("Upload a lecture")
    uploaded = st.file_uploader("PDF with the lecture number in its name", type="pdf")
    if uploaded is not None and st.button("Index slides"):
        with st.spinner("Reading and embedding slides..."):
            response = requests.post(
                f"{API_URL}/documents",
                files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                timeout=600,
            )
        if response.ok:
            result = response.json()
            st.success(f"Indexed {result['slides_indexed']} slides from {result['filename']}")
        else:
            st.error(f"Upload failed: {response.text}")


# --- Main area: question and answer --------------------------------------------

# A form only reruns the script when the button is pressed, not on every keystroke.
with st.form("ask"):
    question = st.text_input("Your question", placeholder="What is max pooling?")
    submitted = st.form_submit_button("Ask")

if submitted and question.strip():
    with st.spinner("Searching the slides and writing the answer..."):
        try:
            response = requests.post(f"{API_URL}/ask", json={"question": question}, timeout=300)
        except requests.RequestException as error:
            st.error(f"Could not reach the API: {error}")
            st.stop()

    if not response.ok:
        st.error(f"API error {response.status_code}: {response.text}")
        st.stop()

    result = response.json()
    st.markdown(result["answer"])

    if result["citations"]:
        st.subheader("Sources")
        for citation in result["citations"]:
            with st.expander(f"{citation['lecture']}, slide {citation['slide']}"):
                st.text(citation["text"])

    with st.expander("Retrieved slides and scores"):
        for source in result["sources"]:
            st.write(f"`{source['slide_id']}`  score {source['score']:.3f}")
