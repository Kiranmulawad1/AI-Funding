# utils.py

import re
import pandas as pd

def present(val):
    if not val or str(val).strip().lower() in ["", "n/a", "null", "none", "not specified"]:
        return "Not specified"
    return str(val).strip()

def two_sentences(text, max_sentences=2):
    s = str(text or "").strip()
    s = re.sub(r'\s+', ' ', s)
    parts = re.split(r'(?<=[.!?])\s+', s)
    out = ' '.join(parts[:max_sentences])
    return out if out.endswith('.') else out + '.'

def program_name(m: dict) -> str:
    for k in ["name", "title", "program", "call"]:
        if m.get(k):
            return str(m[k]).strip()
    return "Unnamed Program"

def deadline_with_badge(m: dict):
    deadline = present(m.get("deadline"))
    days_left = m.get("days_left")
    if deadline != "Not specified" and isinstance(days_left, int):
        return f"{deadline} (🕒 {days_left} days left)"
    return deadline

def safe_parse_deadline(deadline_str):
    try:
        return pd.to_datetime(str(deadline_str), dayfirst=True, utc=True)
    except Exception:
        return None
