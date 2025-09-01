# rag_core.py
import os
import re
import json
import pandas as pd
import numpy as np
from dateutil import parser
from openai import OpenAI
from pinecone import Pinecone
from utils import present, program_name as _program_name

from config import (
    OPENAI_API_KEY, PINECONE_API_KEY, PINECONE_ENV,
    INDEX_NAME, NAMESPACE,
    OPENAI_SELECT_MODEL, OPENAI_ENRICH_MODEL,
    get_openai_client, FUNDING_CSV_PATH,
)
from utils import present, program_name as _program_name

# ---- clients / index ----
_client = get_openai_client()
_pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
_index = _pc.Index(INDEX_NAME)

# ---- data loader ----
def load_full_df(path: str = None) -> pd.DataFrame:
    path = path or str(FUNDING_CSV_PATH)
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()

# ---- embeddings ----
_EMBED_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

def get_embedding(text: str):
    return _client.embeddings.create(input=[text], model=_EMBED_MODEL).data[0].embedding

# ---- date parsing ----
def safe_parse_deadline(deadline_str):
    try:
        if pd.isna(deadline_str) or str(deadline_str).strip() == "":
            return None
        return parser.parse(str(deadline_str), dayfirst=True, fuzzy=True)
    except Exception:
        return None

# ---- scoring ----
def compute_relevance_score(row, query, funding_need=0, target_domain="", user_location=""):
    def _get(k, d=None): 
        try:
            return row.get(k, d)
        except AttributeError:
            return row[k] if k in row else d

    score = 0.0
    if target_domain and target_domain.lower() in str(_get("domain","")).lower():
        score += 0.4
    try:
        nums = re.findall(r"\d+", str(_get("amount","0")))
        amount_val = int(nums[-1]) if nums else 0
        if funding_need and amount_val >= funding_need:
            score += 0.3
    except Exception:
        pass
    dd = _get("deadline_date")
    if isinstance(dd, pd.Timestamp) and pd.notnull(dd) and dd >= pd.Timestamp.now(tz="UTC"):
        score += 0.2
    tokens = re.findall(r"\w+", (query or "").lower())
    if any(tok in str(_get("description","")).lower() for tok in tokens):
        score += 0.1
    if user_location and user_location.lower() in str(_get("location","")).lower():
        score += 0.1
    return round(score * 100)

# ---- keyword boost ----
def _normalize_text(x): 
    return str(x or "").lower()

def keyword_candidates(df, query, dom_pref="", top_n=50):
    if df.empty or not query:
        return pd.DataFrame()
    fields = ["name","title","program","call","description","domain","eligibility","location"]
    toks = set(re.findall(r"\w+", (query or "").lower()))
    dom_tok = set(re.findall(r"\w+", (dom_pref or "").lower())) if dom_pref else set()

    def score_row(r):
        hay = " ".join(_normalize_text(r.get(f, "")) for f in fields)
        score = sum(tok in hay for tok in toks)
        if dom_tok and any(d in hay for d in dom_tok):
            score += 2
        return score

    df2 = df.copy()
    df2["kw_score"] = df2.apply(score_row, axis=1)
    df2 = df2[df2["kw_score"] > 0].sort_values("kw_score", ascending=False).head(top_n)
    return df2

def _key_from_item(item):
    return (item.get("url") or "").strip() or _normalize_text(item.get("name") or item.get("title"))

def hybrid_boost(semantic_matches, df_full, query, need_eur=0, dom_pref="", user_loc="", want=8):
    seen = set(_key_from_item(m) for m in semantic_matches)
    kw = keyword_candidates(df_full, query, dom_pref=dom_pref, top_n=50)
    now_ts = pd.Timestamp.now(tz="UTC")

    additions = []
    for _, r in kw.iterrows():
        item = r.to_dict()
        k = _key_from_item(item)
        if k in seen:
            continue
        deadline_val = item.get("deadline")
        item["deadline_date"] = pd.to_datetime(safe_parse_deadline(deadline_val), errors="coerce", utc=True)
        if pd.notnull(item["deadline_date"]):
            days = int((item["deadline_date"] - now_ts).days)
            if days < 0:
                continue
            item["days_left"] = days
        item["relevance_score"] = compute_relevance_score(
            item, query, funding_need=need_eur, target_domain=dom_pref, user_location=user_loc
        )
        additions.append(item)

    merged = semantic_matches + additions
    merged = sorted(merged, key=lambda x: x.get("relevance_score", 0), reverse=True)[:want]
    return merged

# ---- retrieval ----
def query_funding_data(query, location="", top_k=8, need_eur=0, dom_pref=""):
    emb = get_embedding(query)
    res = _index.query(vector=emb, top_k=top_k, include_metadata=True, namespace=NAMESPACE)
    matches = [m["metadata"] for m in res.get("matches", [])]
    if not matches: 
        return []

    df = pd.DataFrame(matches)
    if "deadline" in df.columns:
        df["deadline"] = df["deadline"].replace(["", "deadline information not found"], np.nan)
        df["deadline_date"] = pd.to_datetime(df["deadline"].apply(safe_parse_deadline), errors="coerce", utc=True)
        now_ts = pd.Timestamp.now(tz="UTC")
        df["days_left"] = (df["deadline_date"] - now_ts).dt.days
        df = df[(df["days_left"].isna()) | (df["days_left"] >= 0)]
        if df.empty: 
            return []

    df["relevance_score"] = df.apply(
        lambda r: compute_relevance_score(r, query, funding_need=need_eur, target_domain=dom_pref, user_location=location),
        axis=1,
    )
    df = df.sort_values("relevance_score", ascending=False).head(top_k)
    return df.to_dict(orient="records")

# ---- LLM: selection & enrichment ----
def build_llm_selection_payload(query, matches, wanted=3):
    items = []
    for i, m in enumerate(matches, 1):
        items.append({
            "id": i,
            "name": m.get("name",""),
            "title": m.get("title",""),
            "domain": m.get("domain",""),
            "description": (m.get("description","") or "")[:800],
            "eligibility": (m.get("eligibility","") or "")[:400],
            "amount": m.get("amount",""),
            "deadline": m.get("deadline",""),
            "location": m.get("location",""),
            "source": m.get("source",""),
            "url": m.get("url",""),
        })
    return {
      "query": query,
      "programs": items,
      "instruction": (
        f"Pick up to {wanted} unique programs by id. DO NOT select duplicates "
        "(same name/source/url). Prefer programs whose text explicitly mentions the user's domain(s), "
        "region, or a funding amount that matches/exceeds the user's need. "
        "For each pick, give a 1–2 sentence reason with exact surface cues "
        "(e.g., 'mentions robotics', 'Rhineland-Palatinate', 'grant up to €500k'). "
        "Return JSON: {\"picks\":[{\"id\":<int>,\"why\":\"...\"}]}. Use only provided programs."
      )
    }

def llm_select_top(user_query, matches, wanted=3):
    try:
        payload = build_llm_selection_payload(user_query, matches, wanted=wanted)
        res = _client.chat.completions.create(
            model=OPENAI_SELECT_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a precise funding advisor. Use only the provided programs. Do not invent anything."},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
            ],
        )
        data = json.loads(res.choices[0].message.content)
        picks = data.get("picks", [])
        ids, reasons = [], {}
        for p in picks:
            try:
                pid = int(p.get("id"))
                if 1 <= pid <= len(matches):
                    ids.append(pid)
                    why = p.get("why")
                    if present(why):
                        reasons[pid] = str(why)[:300]
            except Exception:
                continue
        ids = ids[:wanted] or list(range(1, min(wanted, len(matches)) + 1))
        return ids, reasons
    except Exception:
        ids = list(range(1, min(wanted, len(matches)) + 1))
        return ids, {}

def llm_enrich_picks(chosen_ids, matches):
    items = []
    for cid in chosen_ids:
        m = matches[cid - 1]
        items.append({
            "id": cid,
            "name": m.get("name", ""),
            "title": m.get("title", ""),
            "description": (m.get("description", "") or "")[:1200],
            "eligibility": (m.get("eligibility", "") or "")[:600],
            "procedure": (m.get("procedure", "") or "")[:600],
            "source": m.get("source", ""),
            "url": m.get("url", ""),
            "location": m.get("location", ""),
            "domain": m.get("domain", ""),
            "deadline": m.get("deadline", ""),
        })

    user_payload = {
        "instruction": (
            "For each program, write a concise brief in 1–2 short sentences "
            "(prefer two sentences when possible) summarizing WHAT the program funds and its goal. "
            "Do NOT include eligibility or domain details in the brief; those are separate fields. "
            "Use ONLY the provided text; do not invent facts.\n\n"
            "Then propose up to 3 concrete NEXT STEPS. "
            "Anchor them in 'procedure' and/or 'eligibility' if present. "
            "If those fields are missing, use generic but practical actions like "
            "'Draft a short project outline', 'Prepare budget & timeline', "
            "'Contact the program office to confirm fit'. "
            "Each step must be ≤ 12 words. "
            "Do NOT include any 'visit website/page' steps (the UI adds that). "
            "Do NOT invent URLs or contacts.\n\n"
            "Return JSON: {\"items\":[{\"id\":<int>,\"brief\":\"..\",\"next_steps\":[\"..\",\"..\",\"..\"]}]}. "
            "If description is missing, set brief to 'Not specified'."
        ),
        "programs": items
    }

    try:
        res = _client.chat.completions.create(
            model=OPENAI_ENRICH_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Compress and structure text precisely. Use ONLY provided fields; do not invent facts."},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
            ],
            max_tokens=700,
        )
        data = json.loads(res.choices[0].message.content)
        out = {}
        for it in data.get("items", []):
            cid = it.get("id")
            if isinstance(cid, int) and cid in chosen_ids:
                brief = str(it.get("brief", "")).strip()
                steps = [str(s).strip() for s in (it.get("next_steps") or []) if str(s).strip()]
                out[cid] = {"brief": brief[:600], "next_steps": steps[:3]}
        return out
    except Exception:
        return {cid: {"brief": "", "next_steps": []} for cid in chosen_ids}

FALLBACK_FIELDS = [
    "description","eligibility","procedure","contact",
    "amount","deadline","location","source","domain",
    "name","title","program","call","url"
]

def _norm_url(u: str) -> str:
    try:
        return str(u or "").strip().rstrip("/").lower()
    except Exception:
        return ""

def _norm_name(d: dict) -> str:
    try:
        return _program_name(d).strip().lower()
    except Exception:
        return ""

def _index_full_df(df_full: pd.DataFrame):
    if df_full.empty:
        return None, None

    df = df_full.copy()

    # --- Normalize URL column safely (Series.str.* not plain .strip()) ---
    if "url" in df.columns:
        url_series = df["url"].astype(str)
    else:
        # create an empty string Series if url column is missing
        url_series = pd.Series([""] * len(df), index=df.index, dtype="string")

    df["__url_norm"] = (
        url_series
        .fillna("")
        .str.strip()
        .str.rstrip("/")
        .str.lower()
    )

    # --- Build a fused name column for fallback name-based matching ---
    candidates = ["name", "title", "program", "call", "call_title", "funding_title", "display_name"]

    def fuse(row):
        for c in candidates:
            v = row.get(c)
            if present(v):
                return str(v).strip().lower()
        return ""

    df["__name_norm"] = df.apply(fuse, axis=1)

    return df, {"url": "__url_norm", "name": "__name_norm"}

def _match_row(item: dict, df_indexed):
    df, cols = df_indexed
    if df is None:
        return None
    u = _norm_url(item.get("url"))
    if u:
        hit = df[df[cols["url"]] == u]
        if not hit.empty:
            return hit.iloc[0].to_dict()
    n = _norm_name(item)
    if n:
        hit = df[df[cols["name"]] == n]
        if not hit.empty:
            return hit.iloc[0].to_dict()
    return None

def _backfill_item(item: dict, row: dict) -> dict:
    if not row:
        return item
    for key in FALLBACK_FIELDS:
        if present(item.get(key)) is None:
            val = row.get(key)
            if present(val):
                item[key] = val
    return item

def backfill_records(records: list[dict], df_full: pd.DataFrame) -> list[dict]:
    """Fill missing fields per match from CSV via URL or normalized program name."""
    if not records or df_full.empty:
        return records
    df_indexed = _index_full_df(df_full)
    out = []
    for r in records:
        row = _match_row(r, df_indexed)
        out.append(_backfill_item(r, row))
    return out