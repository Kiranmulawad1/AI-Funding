# app_streamlit.py
import html
import fitz  # PyMuPDF
import streamlit as st

from config import OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENV, FUNDING_CSV_PATH
from rag_core import (
    load_full_df, get_index, query_funding_data, hybrid_boost,
    llm_select_top, llm_enrich_picks
)
from utils import fmt, two_sentences, program_name, steps_from_dataset, deadline_with_badge
from docx_builder import build_application_docx
from openai import OpenAI

# ---- Page & ENV checks ----
st.set_page_config(page_title="Smart Funding Chatbot", layout="centered")

required = {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "PINECONE_API_KEY": PINECONE_API_KEY,
    "PINECONE_ENV": PINECONE_ENV,
}
if missing := [k for k, v in required.items() if not v]:
    st.error(f"Missing environment variables: {', '.join(missing)}")
    st.stop()

# ---- Clients for app-only tasks (like PDF summary) ----
client = OpenAI(api_key=OPENAI_API_KEY)

# ---- Cache wrappers (so rag_core stays framework-agnostic) ----
@st.cache_resource(show_spinner=False)
def _cached_index():
    return get_index()

@st.cache_data(show_spinner=False)
def _cached_full_df():
    return load_full_df(FUNDING_CSV_PATH)

df_full = _cached_full_df()

# ---- Session ----
def _ensure_state():
    defaults = {
        "chat_history": [],
        "draft_blobs": {},
        "generated_query": "",
        "last_query": None,
        "last_matches": None,     # list[dict]
        "last_chosen_ids": None,  # list[int] (1-based ids within last_matches)
        "last_reasons": None,     # {id: why}
        "last_enrich": None,      # {id: {"brief":..., "next_steps":[...]}}
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def _reset_session():
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    _ensure_state()
    st.rerun()

_ensure_state()

# ---- Sidebar: PDF upload + Reset ----
st.sidebar.subheader("📄 Upload Company Profile (Optional)")
uploaded_pdf = st.sidebar.file_uploader("Upload PDF", type=["pdf"])

def _extract_text_from_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    return "\n".join(page.get_text() for page in doc).strip()

def _summarize_text_with_gpt(raw_text: str) -> str:
    prompt = f"""
Summarize this company profile into 2–3 lines for public funding discovery in Germany.
Focus on domain, goals, and funding need.

---
{raw_text[:6000]}
---
"""
    res = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

if uploaded_pdf:
    raw_text = _extract_text_from_pdf(uploaded_pdf)
    st.session_state.generated_query = _summarize_text_with_gpt(raw_text)
    st.sidebar.success("✅ Profile processed. Using it to search.")

st.sidebar.button("🔄 Reset conversation", on_click=_reset_session)

# ---- Follow-up targeting ----
ORDINALS = {"first":1,"1st":1,"one":1,"second":2,"2nd":2,"two":2,"third":3,"3rd":3,"three":3,"fourth":4,"4th":4,"four":4,"fifth":5,"5th":5,"five":5}

def find_followup_target(query_text: str, chosen_ids: list[int], matches: list[dict]):
    if not chosen_ids or not matches:
        return None, None
    import re
    q = (query_text or "").lower()
    for word, num in ORDINALS.items():
        if re.search(rf"\b{word}\b", q):
            if 1 <= num <= len(chosen_ids):
                orig_id = chosen_ids[num-1]
                return orig_id, matches[orig_id - 1]
    def norm(x): 
        return re.sub(r"\s+", " ", str(x or "").lower()).strip()
    for cid in chosen_ids:
        m = matches[cid - 1]
        name = norm(program_name(m))
        tokens = [t for t in re.findall(r"\w+", name) if len(t) > 3]
        if tokens and any(t in q for t in tokens):
            return cid, m
    if re.search(r"(tell me more|details|more info|expand|elaborate)", q):
        cid = chosen_ids[0]
        return cid, matches[cid - 1]
    return None, None

# ---- Rendering ----
def render_program_bubbles_html(chosen_pairs, reasons_map, query, enrich_map=None):
    for rank, (orig_id, m) in enumerate(chosen_pairs, start=1):
        with st.chat_message("assistant"):
            name     = program_name(m)
            reason   = (reasons_map or {}).get(orig_id, "")
            brief    = (enrich_map or {}).get(orig_id, {}).get("brief", "").strip() if enrich_map else ""
            desc     = brief or two_sentences(fmt(m.get("description")))
            domain   = fmt(m.get("domain"), "Not specified")
            elig     = two_sentences(fmt(m.get("eligibility")))
            amount   = fmt(m.get("amount"))
            deadline = deadline_with_badge(m)
            loc_txt  = fmt(m.get("location"))
            contact  = fmt(m.get("contact"))
            src      = fmt(m.get("source"), "N/A")

            html_block = f"""
<div>
  <strong>{rank}. {html.escape(name)}</strong><br><br>
  {f"<strong>Why it fits:</strong> {html.escape(reason)}<br><br>" if reason else ""}
  <strong>Description:</strong> {html.escape(desc)}<br>
  <strong>Domain:</strong> {html.escape(domain)}<br>
  <strong>Eligibility:</strong> {html.escape(elig)}<br>
  <strong>Amount:</strong> {html.escape(amount)}<br>
  <strong>Deadline:</strong> {html.escape(deadline)}<br>
  <strong>Location:</strong> {html.escape(loc_txt)}<br>
  <strong>Contact:</strong> {html.escape(contact)}<br>
  <strong>Source:</strong> {html.escape(src)}<br>
</div>
"""
            st.markdown(html_block, unsafe_allow_html=True)

            # Steps (ensure official link present if available)
            steps = (enrich_map or {}).get(orig_id, {}).get("next_steps", []) if enrich_map else []
            url = (m.get("url") or "").strip()
            if url:
                url_step = f'Visit the <a href="{html.escape(url)}" target="_blank">official page</a>'
                if not any("official page" in str(s).lower() for s in steps):
                    steps = [url_step] + steps
            if not steps:
                steps = steps_from_dataset(m)

            st.markdown("**Next Steps:**", unsafe_allow_html=True)
            for s in steps[:3]:
                st.markdown(f"- {s}", unsafe_allow_html=True)

            gen_key = f"gen-{orig_id}"
            dl_key  = f"dl-{orig_id}"
            if st.button("📝 Generate Draft", key=gen_key):
                try:
                    qtext = query or st.session_state.get("last_query") or ""
                    buf = build_application_docx(m, qtext)
                    st.session_state.draft_blobs[orig_id] = buf.getvalue()
                    st.success("Draft ready ↓")
                except Exception as e:
                    st.error(f"Couldn't generate the DOCX: {e}")

            if orig_id in st.session_state.draft_blobs:
                st.download_button(
                    label="⬇️ Download .docx",
                    data=st.session_state.draft_blobs[orig_id],
                    file_name=f"application_{rank}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=dl_key
                )

# ---- Pipeline runner ----
def build_chosen_pairs(chosen_ids, matches):
    return [(cid, matches[cid - 1]) for cid in (chosen_ids or []) if 1 <= cid <= len(matches)]

def run_full_pipeline(user_query: str):
    base = query_funding_data(user_query, location="", top_k=8, need_eur=0, dom_pref="")
    matches = hybrid_boost(base, df_full, user_query, need_eur=0, dom_pref="", user_loc="", want=8)
    wanted = 3
    chosen_ids, reasons = llm_select_top(user_query, matches, wanted=wanted)
    enrich_map = llm_enrich_picks(chosen_ids, matches)
    st.session_state.last_query = user_query
    st.session_state.last_matches = matches
    st.session_state.last_chosen_ids = chosen_ids
    st.session_state.last_reasons = reasons
    st.session_state.last_enrich = enrich_map
    return build_chosen_pairs(chosen_ids, matches), reasons, enrich_map

def render_detail_for_followup(target_id: int, program: dict, user_query: str):
    chosen_pairs = [(target_id, program)]
    reasons = st.session_state.last_reasons or {}
    enrich_map = st.session_state.last_enrich or {}
    render_program_bubbles_html(chosen_pairs, reasons, user_query, enrich_map=enrich_map)

# ---- Transcript ----
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---- Input ----
# Take the generated query once, then remove it so it can't autofire again
seed = st.session_state.pop("generated_query", "")

# Normal user input
query = st.chat_input("Describe your company or ask a follow-up…")

# If user didn’t type anything this run, use the one-time seed
if not query and seed:
    query = seed


if query:
    with st.chat_message("user"):
        st.markdown(query)
    st.session_state.chat_history.append({"role": "user", "content": query})

    if st.session_state.last_matches and st.session_state.last_chosen_ids:
        orig_id, prog = find_followup_target(query, st.session_state.last_chosen_ids, st.session_state.last_matches)
        if orig_id and prog:
            with st.spinner("Pulling details…"):
                render_detail_for_followup(orig_id, prog, st.session_state.last_query or query)
        else:
            with st.spinner("Finding and ranking programs…"):
                pairs, reasons, enrich = run_full_pipeline(query)
                render_program_bubbles_html(pairs, reasons, query, enrich_map=enrich)
    else:
        with st.spinner("Finding and ranking programs…"):
            pairs, reasons, enrich = run_full_pipeline(query)
            render_program_bubbles_html(pairs, reasons, query, enrich_map=enrich)
