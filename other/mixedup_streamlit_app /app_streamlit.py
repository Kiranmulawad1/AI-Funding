# app_streamlit.py
import os
import re
import html
import hashlib
import fitz  # PyMuPDF
import streamlit as st

from config import (
    OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENV, FUNDING_CSV_PATH,
    get_openai_client, OPENAI_SUMMARY_MODEL
)
from rag_core import (
    load_full_df, query_funding_data, hybrid_boost,
    llm_select_top, llm_enrich_picks, backfill_records   # <-- backfill
)
from utils import (
    fmt, two_sentences, short_text, program_name, steps_from_dataset,
    deadline_with_badge, present
)
from docx_builder import build_application_docx

# ---------- Page & ENV checks ----------
st.set_page_config(page_title="Smart Funding Chatbot", layout="centered")

required = {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "PINECONE_API_KEY": PINECONE_API_KEY,
    "PINECONE_ENV": PINECONE_ENV,
}
if missing := [k for k, v in required.items() if not v]:
    st.error(f"Missing environment variables: {', '.join(missing)}")
    st.stop()

# OpenAI client (for PDF summary only; RAG calls use rag_core's client)
client = get_openai_client()

# ---------- Cache ----------
@st.cache_data(show_spinner=False)
def _cached_full_df():
    return load_full_df(str(FUNDING_CSV_PATH))

df_full = _cached_full_df()

# ---------- Session ----------
def _ensure_state():
    defaults = {
        "chat_history": [],
        "draft_blobs": {},
        "generated_query": "",
        "seed_ready": False,
        "pdf_hash": None,
        "pdf_processed": False,
        "last_query": None,
        "last_matches": None,
        "last_chosen_ids": None,
        "last_reasons": None,
        "last_enrich": None,
        "detail_id": None,
        "__reset_requested__": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_ensure_state()

# ---------- Reset handling ----------
def _request_reset():
    st.session_state["__reset_requested__"] = True
st.sidebar.button("🔄 Reset conversation", on_click=_request_reset)

if st.session_state.pop("__reset_requested__", False):
    st.session_state.clear()
    _ensure_state()
    st.rerun()

# ---------- Sidebar: PDF upload w/ hash guard ----------
st.sidebar.subheader("📄 Upload Company Profile (Optional)")
uploaded_pdf = st.sidebar.file_uploader("Upload PDF", type=["pdf"])

def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
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
        model=OPENAI_SUMMARY_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

if uploaded_pdf:
    pdf_bytes = uploaded_pdf.getvalue()
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    if st.session_state.get("pdf_hash") != pdf_hash:
        st.session_state["pdf_hash"] = pdf_hash
        raw_text = _extract_text_from_pdf_bytes(pdf_bytes)
        st.session_state["generated_query"] = _summarize_text_with_gpt(raw_text)
        st.session_state["seed_ready"] = True
        st.session_state["pdf_processed"] = True
else:
    st.session_state["pdf_hash"] = None
    st.session_state["pdf_processed"] = False
    st.session_state["generated_query"] = ""
    st.session_state["seed_ready"] = False

if st.session_state.get("pdf_processed"):
    st.sidebar.success("✅ Profile processed. Using it to search.")

# ---------- Follow-up targeting ----------
ORDINALS = {
    "first":1,"1st":1,"one":1,"second":2,"2nd":2,"two":2,
    "third":3,"3rd":3,"three":3,"fourth":4,"4th":4,"four":4,
    "fifth":5,"5th":5,"five":5
}

def find_followup_target(query_text: str, chosen_ids: list[int], matches: list[dict]):
    if not chosen_ids or not matches:
        return None, None
    q = (query_text or "").lower()

    # 1) ordinal
    for word, num in ORDINALS.items():
        if re.search(rf"\b{word}\b", q) and 1 <= num <= len(chosen_ids):
            orig_id = chosen_ids[num-1]
            return orig_id, matches[orig_id - 1]

    # 2) fuzzy by program name
    def norm(x): 
        return re.sub(r"\s+", " ", str(x or "").lower()).strip()
    for cid in chosen_ids:
        m = matches[cid - 1]
        name = norm(program_name(m))
        tokens = [t for t in re.findall(r"\w+", name) if len(t) > 3]
        if tokens and any(t in q for t in tokens):
            return cid, m

    # 3) generic "tell me more"
    if re.search(r"(tell me more|details|more info|expand|elaborate)", q):
        cid = chosen_ids[0]
        return cid, matches[cid - 1]
    return None, None

# ---------- Field-only follow-ups ----------
FIELD_KEYS = {
    "contact": ["contact", "email", "e-mail", "mail", "phone", "telephone", "number"],
    "url": ["url", "link", "website", "web page", "official page", "site"],
    "deadline": ["deadline", "due date", "closing date"],
    "amount": ["amount", "grant", "funding", "budget", "max"],
    "eligibility": ["eligibility", "eligible", "who can apply"],
    "procedure": ["procedure", "apply", "application", "how to apply", "process"],
    "location": ["location", "region", "state", "country", "where"],
    "source": ["source", "publisher"],
}

def extract_requested_fields(q: str) -> list[str]:
    ql = (q or "").lower()
    want = []
    for k, synonyms in FIELD_KEYS.items():
        if any(s in ql for s in synonyms):
            want.append(k)
    if want == ["contact"] and "url" not in want:
        want.append("url")
    seen, out = set(), []
    for f in want:
        if f not in seen:
            out.append(f); seen.add(f)
    return out

def render_compact_fields(program: dict, fields: list[str], heading_prefix: str = "") -> str:
    lines = []
    title = program_name(program)
    src = present(program.get("source"))
    title_line = f"**{heading_prefix + title if heading_prefix else title} ({src})**" if src else f"**{heading_prefix + title if heading_prefix else title}**"
    lines.append(title_line)

    def val(key):
        if key == "url":
            v = present(program.get("url")) or "Not specified"
            if v != "Not specified":
                return f"[Official page]({v})"
            return v
        return present(program.get(key)) or "Not specified"

    for f in fields:
        pretty = f.capitalize()
        lines.append(f"- **{pretty}:** {val(f)}")

    md = "\n".join(lines)
    with st.chat_message("assistant"):
        st.markdown(md)
    return md

# --- helper: clean and shorten the "Why it fits" text ---
# --- helper: clean and shorten the "Why it fits" text ---
def _clean_reason(reason, title):
    """Remove program title/empty quotes and boilerplate, then cap to 2 sentences."""
    if not reason:
        return None
    r = str(reason)

    # Remove the program title (quoted or unquoted)
    quotes = "'\"‘’“”"
    patt_title = re.escape(title)
    r = re.sub(rf"[{quotes}]*\s*{patt_title}\s*[{quotes}]*", "", r, flags=re.I)

    # Remove leading: The program '' is / The program is / It is
    r = re.sub(r"^\s*the\s+program\s*(?:[\"'‘’“”]{0,2})\s*is\s+", "", r, flags=re.I)
    r = re.sub(r"^\s*the\s+program\s+is\s+", "", r, flags=re.I)
    r = re.sub(r"^\s*it\s+is\s+", "", r, flags=re.I)

    # Collapse leftover repeated quotes and tidy punctuation/spacing
    r = re.sub(r"[\"'‘’“”]{2,}", "", r)
    r = re.sub(r"\s+", " ", r).strip(" :,-“”‘’'\"")

    # Cap to 2 sentences (no mid-sentence cut, so no ellipsis)
    return two_sentences(r)

# ---------- Rendering (ctx-suffixed keys) ----------
def render_program_bubbles_html(chosen_pairs, reasons_map, query, enrich_map=None, ctx="list"):
    def _dedupe_and_supplement_steps(base_steps, program):
        """Keep one 'visit' step max; add solid generic steps until we have 3."""
        def norm(s): return re.sub(r'[\s\W]+', ' ', (s or "").lower()).strip()
        out, seen = [], set()
        have_visit = False
        for s in base_steps:
            if not s: 
                continue
            n = norm(s)
            is_visit = "visit" in n and ("page" in n or "official" in n or "website" in n or "site" in n)
            if is_visit:
                if have_visit:
                    continue
                have_visit = True
            if n not in seen:
                out.append(s); seen.add(n)

        # Top up with dataset-based strong generics (already dedupes + includes deadline)
        if len(out) < 3:
            supplement = steps_from_dataset(program)
            for s in supplement:
                n = norm(s)
                if n not in seen:
                    out.append(s); seen.add(n)
                if len(out) >= 3:
                    break
        return out[:3]

    for rank, (orig_id, m) in enumerate(chosen_pairs, start=1):
        with st.chat_message("assistant"):
            name   = program_name(m)
            source = present(m.get("source"))
            title  = f"{name} ({source})" if source else name

            # Why it fits: clean out program title, then 2 sentences (no ellipsis)
            reason_raw = (reasons_map or {}).get(orig_id, "")
            reason = _clean_reason(reason_raw, name)

            # Description: prefer LLM brief, else dataset; 2 sentences (no ellipsis)
            brief = (enrich_map or {}).get(orig_id, {}).get("brief", "") if enrich_map else ""
            desc  = two_sentences(brief) or two_sentences(m.get("description"))

            parts = []
            parts.append(f"<strong>{rank}. {html.escape(title)}</strong><br><br>")
            if reason:
                parts.append(f"<strong>Why it fits:</strong> {html.escape(reason)}<br><br>")
            if desc:
                parts.append(f"<strong>Description:</strong> {html.escape(desc)}<br>")

            # Only show real fields (no Source here — it's in the title)
            for label, key in [
                ("Domain","domain"),
                ("Eligibility","eligibility"),
                ("Amount","amount"),
                ("Location","location"),
                ("Contact","contact"),
            ]:
                v_raw = present(m.get(key))
                if not v_raw:
                    continue
                # Keep these brief but not mid-sentence: 2 sentences max, no char cap
                if key in ("eligibility", "amount", "domain"):
                    v = two_sentences(v_raw) or v_raw
                else:
                    v = v_raw
                parts.append(f"<strong>{label}:</strong> {html.escape(v)}<br>")


            dl_txt = deadline_with_badge(m)
            if dl_txt and dl_txt.lower() != "not specified":
                parts.append(f"<strong>Deadline:</strong> {html.escape(dl_txt)}<br>")

            st.markdown("<div>" + "\n".join(parts) + "</div>", unsafe_allow_html=True)

            # Build steps from LLM enrich + official page; then dedupe/supplement
            steps = (enrich_map or {}).get(orig_id, {}).get("next_steps", []) if enrich_map else []
            url = present(m.get("url"))
            if url:
                url_step = f'Visit the <a href="{html.escape(url)}" target="_blank">official page</a>'
                steps = [url_step] + steps  # we’ll dedupe if LLM had a similar one
            steps = _dedupe_and_supplement_steps(steps, m)

            st.markdown("**Next Steps:**", unsafe_allow_html=True)
            for s in steps:
                st.markdown(f"- {s}", unsafe_allow_html=True)

            # Unique keys per context + item + rank
            gen_key = f"{ctx}-gen-{orig_id}-{rank}"
            dl_key  = f"{ctx}-dl-{orig_id}-{rank}"
            if st.button("📝 Generate Draft", key=gen_key):
                try:
                    qtext = (st.session_state.get("last_query") or "")
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

def build_chosen_pairs(chosen_ids, matches):
    return [(cid, matches[cid - 1]) for cid in (chosen_ids or []) if 1 <= cid <= len(matches)]

def run_full_pipeline(user_query: str):
    base = query_funding_data(user_query, location="", top_k=8, need_eur=0, dom_pref="")
    matches = hybrid_boost(base, df_full, user_query, need_eur=0, dom_pref="", user_loc="", want=8)
    # Backfill missing fields from CSV (URL/name match)
    matches = backfill_records(matches, df_full)

    wanted = 3
    chosen_ids, reasons = llm_select_top(user_query, matches, wanted=wanted)
    enrich_map = llm_enrich_picks(chosen_ids, matches)

    # Persist
    st.session_state.last_query = user_query
    st.session_state.last_matches = matches
    st.session_state.last_chosen_ids = chosen_ids
    st.session_state.last_reasons = reasons
    st.session_state.last_enrich = enrich_map

    return build_chosen_pairs(chosen_ids, matches), reasons, enrich_map

def render_detail(target_id: int, program: dict, user_query: str):
    chosen_pairs = [(target_id, program)]
    reasons = st.session_state.last_reasons or {}
    enrich_map = st.session_state.last_enrich or {}
    render_program_bubbles_html(chosen_pairs, reasons, user_query, enrich_map=enrich_map, ctx=f"detail-{target_id}")
    if st.button("⬅ Back to results", key=f"detail-{target_id}-back"):
        st.session_state.detail_id = None

def render_current_view(just_ran_pipeline: bool):
    last_matches = st.session_state.get("last_matches")
    last_ids     = st.session_state.get("last_chosen_ids")
    if last_matches and last_ids:
        pairs   = build_chosen_pairs(last_ids, last_matches)
        reasons = st.session_state.get("last_reasons") or {}
        enrich  = st.session_state.get("last_enrich") or {}
        ctx     = "results" if just_ran_pipeline else "cache"
        render_program_bubbles_html(pairs, reasons, st.session_state.get("last_query",""), enrich_map=enrich, ctx=ctx)

    did = st.session_state.get("detail_id")
    if did and last_matches and 1 <= did <= len(last_matches):
        prog = last_matches[did - 1]
        render_detail(did, prog, st.session_state.get("last_query",""))

# ---------- Show prior transcript ----------
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------- Input (one-time seed from PDF summary) ----------
seed = st.session_state.get("generated_query", "")
query = st.chat_input("Describe your company or ask a follow-up…")

if not query and st.session_state.get("seed_ready") and seed:
    query = seed
    st.session_state["seed_ready"] = False
    st.session_state["generated_query"] = ""  # consume

just_ran_pipeline = False
deferred_compact = None  # (program, fields) – print after list/detail to stay at bottom

if query:
    same_as_last = (query == (st.session_state.get("last_query") or ""))

    if not same_as_last:
        with st.chat_message("user"):
            st.markdown(query)
        st.session_state.chat_history.append({"role": "user", "content": query})
        st.session_state.chat_history = st.session_state.chat_history[-50:]

    if st.session_state.last_matches and st.session_state.last_chosen_ids:
        orig_id, prog = find_followup_target(query, st.session_state.last_chosen_ids, st.session_state.last_matches)
        if orig_id and prog:
            fields = extract_requested_fields(query)
            if fields:
                deferred_compact = (prog, fields)
                st.session_state.detail_id = None  # compact reply only
            else:
                st.session_state.detail_id = orig_id
        else:
            with st.spinner("Finding and ranking programs…"):
                run_full_pipeline(query)
            st.session_state.detail_id = None
            just_ran_pipeline = True
    else:
        with st.spinner("Finding and ranking programs…"):
            run_full_pipeline(query)
        st.session_state.detail_id = None
        just_ran_pipeline = True

# ---- Render list + (optional) detail ----
render_current_view(just_ran_pipeline)

# ---- Deferred compact reply prints LAST (bottom of chat) ----
if deferred_compact:
    prog, fields = deferred_compact
    md = render_compact_fields(prog, fields)
    st.session_state.chat_history.append({"role": "assistant", "content": md})
