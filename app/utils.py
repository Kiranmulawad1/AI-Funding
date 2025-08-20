# utils.py
import re
import html
from urllib.parse import unquote
import pandas as pd

def fmt(x, fallback="Not specified"):
    if x is None:
        return fallback
    try:
        import math
        if isinstance(x, float) and math.isnan(x):
            return fallback
    except Exception:
        pass
    s = str(x).strip()
    if not s:
        return fallback
    lower = s.lower()
    if any(phrase in lower for phrase in ("information not found", "not specified", "n/a", "na", "none", "null")):
        return fallback
    return s

def two_sentences(text, max_sentences=2):
    s = str(text or "").strip()
    if not s or s.lower() == "not specified":
        return "Not specified"
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[.…]+$', '', s).strip()
    parts = re.split(r'(?<=[.!?])\s+', s)
    parts = [p.strip() for p in parts if p.strip()]
    out = ' '.join(parts[:max_sentences]) if parts else "Not specified"
    if out and out[-1] not in ".!?":
        out += "."
    return out

def safe_parse_deadline(deadline_str):
    from dateutil import parser
    try:
        if pd.isna(deadline_str) or str(deadline_str).strip() == "":
            return None
        return parser.parse(str(deadline_str), dayfirst=True, fuzzy=True)
    except Exception:
        return None

def steps_from_dataset(m: dict):
    steps = []
    url = (m.get("url") or "").strip()
    elig = fmt(m.get("eligibility"))
    proc = fmt(m.get("procedure"))
    deadline = fmt(m.get("deadline"))

    if url and url != "Not specified":
        steps.append(f'Visit the <a href="{html.escape(url)}" target="_blank">official page</a>')
    if elig and elig != "Not specified":
        steps.append("Confirm you meet eligibility requirements")
    if proc and proc != "Not specified":
        steps.append("Follow the described application procedure")
    if deadline and deadline != "Not specified" and len(steps) < 3:
        steps.append(f"Note the deadline: {deadline}")

    return steps[:3] if steps else [
        "Visit the official page",
        "Prepare a 1–2 page project summary & budget",
        "Contact the program office for clarifications",
    ]

# ---- Program name normalization ----
ACRONYMS = ("AI","R&D","EU","BMBF","EFRE","ERDF","SME","ML","KI")

def _fix_acronyms(s: str) -> str:
    for ac in ACRONYMS:
        s = re.sub(rf"\b{ac.title()}\b", ac, s)
    return s

def normalize_program_title(candidate: str, url: str = "") -> str:
    s = str(candidate or "").strip()
    if not s:
        return ""
    if s.lower().endswith((".html", ".htm", ".php")) or re.fullmatch(r"[a-z0-9\-\._]+", s.lower()):
        s = re.sub(r"\.(html?|php)$", "", s, flags=re.I)
        s = s.replace("-", " ").replace("_", " ")
        s = unquote(s)
        s = re.sub(r"\s+", " ", s).strip().title()
        s = _fix_acronyms(s)
        return s
    return s

def program_name(m: dict) -> str:
    candidates = [
        m.get("name"), m.get("title"), m.get("program"), m.get("call"),
        m.get("call_title"), m.get("funding_title"), m.get("display_name")
    ]
    url = (m.get("url") or "").strip()
    for c in candidates:
        c = fmt(c, "")
        if c:
            return normalize_program_title(c, url=url)
    if url:
        slug = url.rstrip("/").split("/")[-1]
        return normalize_program_title(slug, url=url) or "Unnamed"
    return "Unnamed"

def deadline_with_badge(m: dict):
    dl = fmt(m.get("deadline"))
    dl_days = m.get("days_left")
    if dl != "Not specified":
        try:
            if isinstance(dl_days, (int, float)) and not pd.isna(dl_days):
                return f"{dl} (🕒 {int(dl_days)} days left)"
        except Exception:
            pass
        return dl
    return "Not specified"
