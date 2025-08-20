# rag_core.py
import re
import json
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple

from config import get_openai_client, get_pinecone_client, INDEX_NAME, NAMESPACE, FUNDING_CSV_PATH
from utils import fmt, safe_parse_deadline

# ---- Clients (created once per process; Streamlit will cache wrappers in app) ----
_oai_client = None
_pc_client = None

def openai_client():
    global _oai_client
    if _oai_client is None:
        _oai_client = get_openai_client()
    return _oai_client

def pinecone_client():
    global _pc_client
    if _pc_client is None:
        _pc_client = get_pinecone_client()
    return _pc_client

# ---- Data/Index helpers (no Streamlit decorators here) ----
def get_index():
    pc = pinecone_client()
    return pc.Index(INDEX_NAME)

def load_full_df(path: str = FUNDING_CSV_PATH) -> pd.DataFrame:
    import os
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()

# ---- Embeddings ----
def get_embedding(text: str):
    client = openai_client()
    return client.embeddings.create(input=[text], model="text-embedding-3-small").data[0].embedding

# ---- Scoring & Hybrid ----
def compute_relevance_score(row, query, funding_need=0, target_domain="", user_location=""):
    get = (row.get if isinstance(row, dict) else lambda k, d=None: row.get(k, d))
    score = 0.0
    if target_domain and target_domain.lower() in str(get("domain","")).lower():
        score += 0.4
    try:
        nums = re.findall(r"\d+", str(get("amount","0")))
        amount_val = int(nums[-1]) if nums else 0
        if funding_need and amount_val >= funding_need:
            score += 0.3
    except Exception:
        pass
    dd = get("deadline_date")
    if isinstance(dd, pd.Timestamp) and pd.notnull(dd) and dd >= pd.Timestamp.now(tz="UTC"):
        score += 0.2
    tokens = re.findall(r"\w+", query.lower())
    if any(tok in str(get("description","")).lower() for tok in tokens):
        score += 0.1
    if user_location and user_location.lower() in str(get("location","")).lower():
        score += 0.1
    return round(score * 100)

def _normalize_text(x): 
    return str(x or "").lower()

def keyword_candidates(df, query, dom_pref="", top_n=50):
    if df.empty or not query:
        return pd.DataFrame()
    fields = ["name","title","program","call","description","domain","eligibility","location"]
    toks = set(re.findall(r"\w+", query.lower()))
    dom_tok = set(re.findall(r"\w+", dom_pref.lower())) if dom_pref else set()

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

# ---- Retrieval + LLM pipeline ----
def query_funding_data(query, location="", top_k=8, need_eur=0, dom_pref=""):
    index = get_index()
    emb = get_embedding(query)
    res = index.query(vector=emb, top_k=top_k, include_metadata=True, namespace=NAMESPACE)
    matches = [m["metadata"] for m in res.get("matches", [])]
    if not matches:
        return []
    df = pd.DataFrame(matches)
    if "deadline" in df.columns:
        df["deadline"] = df["deadline"].replace(["", "deadline information not found"], np.nan)
        df["deadline_date"] = df["deadline"].apply(safe_parse_deadline)
        df["deadline_date"] = pd.to_datetime(df["deadline_date"], errors="coerce", utc=True)
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
        "For each pick, give a 1–2 sentence reason citing exact matches. "
        "Return JSON: {\"picks\":[{\"id\":<int>,\"why\":\"...\"}]}. Use only provided programs."
      )
    }

def llm_select_top(query, matches, wanted=3) -> Tuple[list, dict]:
    client = openai_client()
    try:
        payload = build_llm_selection_payload(query, matches, wanted=wanted)
        res = client.chat.completions.create(
            model="gpt-4-turbo",
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
                    if p.get("why"): reasons[pid] = str(p["why"])[:300]
            except Exception:
                continue
        ids = ids[:wanted]
        if not ids:
            ids = list(range(1, min(wanted, len(matches)) + 1))
        return ids, reasons
    except Exception:
        ids = list(range(1, min(wanted, len(matches)) + 1))
        return ids, {}

def llm_enrich_picks(chosen_ids, matches) -> dict:
    client = openai_client()
    items = []
    for cid in chosen_ids:
        m = matches[cid - 1]
        items.append({
            "id": cid,
            "name": m.get("name", ""),
            "title": m.get("title", ""),
            "description": (m.get("description", "") or "")[:800],
            "eligibility": (m.get("eligibility", "") or "")[:500],
            "procedure": (m.get("procedure", "") or "")[:500],
            "source": m.get("source", ""),
            "url": m.get("url", ""),
            "location": m.get("location", ""),
            "domain": m.get("domain", ""),
            "deadline": m.get("deadline", ""),
        })

    user_payload = {
        "instruction": (
            "For each program, write a concise 2-sentence brief about WHAT it funds and its goal. "
            "Use ONLY the provided text; do not invent facts. "
            "Then propose up to 3 concrete NEXT STEPS anchored in 'procedure' and/or 'eligibility' if present; "
            "otherwise generic steps. Each step ≤ 12 words. "
            "Return JSON: {\"items\":[{\"id\":<int>,\"brief\":\"..\",\"next_steps\":[\"..\",\"..\",\"..\"]}]}."
        ),
        "programs": items
    }

    try:
        res = client.chat.completions.create(
            model="gpt-4-turbo",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Compress and structure text precisely. Use ONLY provided fields; do not invent facts."},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
            ],
            max_tokens=600,
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
