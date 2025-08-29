# utils.py
import re
import html
import pandas as pd

# ---------------------------
# Missing / presence helpers
# ---------------------------
MISSING_SENTINELS = {
    "", None,
    "n/a", "na", "null", "nan", "none",
    "not specified",
}
# Substrings that indicate "missing" even if preceded by a field name (e.g., "domain information not found")
MISSING_SUBSTRS = (
    "information not found",
    "not available",
    "no information",
    "tbd",
    "to be determined",
    "unknown",
)

def is_missing(val) -> bool:
    try:
        s = str(val).strip()
    except Exception:
        return True
    if not s:
        return True
    low = s.lower()
    if low in MISSING_SENTINELS:
        return True
    if any(sub in low for sub in MISSING_SUBSTRS):
        return True
    return False

def present(val):
    """Return clean string if present; otherwise None (renderer can skip)."""
    return None if is_missing(val) else str(val).strip()

def pick(*vals):
    """Return first present value among candidates."""
    for v in vals:
        p = present(v)
        if p:
            return p
    return None

# ---------------------------
# Formatting helpers
# ---------------------------
def fmt(x, fallback="Not specified"):
    """Legacy formatter; newer code prefers `present()`."""
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
    if any(phrase in lower for phrase in (
        "information not found", "not specified", "n/a", "na", "none", "null", "nan",
    )):
        return fallback
    return s

def two_sentences(text, max_sentences=2):
    s = str(text or "").strip()
    if not s or s.lower() == "not specified":
        return None
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[.…]+$', '', s).strip()
    parts = re.split(r'(?<=[.!?])\s+', s)
    parts = [p.strip() for p in parts if p.strip()]
    out = ' '.join(parts[:max_sentences]) if parts else None
    if out and out[-1] not in ".!?":
        out += "."
    return out

def short_text(text, max_sentences=2, max_chars=220):
    """2 sentences max, then hard cap characters with ellipsis."""
    t = two_sentences(text, max_sentences=max_sentences)
    if not t:
        return t
    if len(t) <= max_chars:
        return t
    # trim to last space before limit
    cut = t[:max_chars].rsplit(" ", 1)[0]
    return cut + "…"

def deadline_with_badge(m: dict):
    dl = present(m.get("deadline"))
    dl_days = m.get("days_left")
    if dl:
        try:
            if isinstance(dl_days, (int, float)) and not pd.isna(dl_days):
                return f"{dl} (🕒 {int(dl_days)} days left)"
        except Exception:
            pass
        return dl
    return "Not specified"

# ---------- Strong, deduped Next Steps ----------
def steps_from_dataset(m):
    """Generate clear, action-oriented next steps with no duplicate 'visit page'."""
    steps = []
    url = present(m.get("url"))
    elig = present(m.get("eligibility"))
    proc = present(m.get("procedure"))
    deadline = present(m.get("deadline"))

    # Single canonical visit step if URL exists
    if url:
        steps.append(f'Visit the <a href="{html.escape(url)}" target="_blank">official page</a>')

    generic = []
    if elig:
        generic.append("Confirm you meet eligibility requirements")
    if proc:
        generic.append("Follow the described application procedure")

    # Strong defaults if procedure is missing
    generic += [
        "Draft a 1–2 page project outline",
        "Prepare a basic budget & timeline",
        "Contact the program office to confirm fit",
    ]
    if deadline:
        generic.append(f"Plan internal deadline before: {deadline}")

    # Merge + dedupe
    final, seen = [], set()
    def norm(s): return re.sub(r'[\s\W]+', ' ', (s or "").lower()).strip()
    have_visit = any("visit" in norm(s) and ("page" in norm(s) or "official" in norm(s)) for s in steps)

    for s in (steps + generic):
        if not s:
            continue
        n = norm(s)
        is_visit = "visit" in n and ("page" in n or "official" in n or "website" in n or "site" in n)
        if is_visit:
            if have_visit:
                continue
            have_visit = True
        if n not in seen:
            final.append(s); seen.add(n)

    return (final or [
        "Visit the official page",
        "Draft a 1–2 page project outline",
        "Contact the program office for clarifications",
    ])[:3]

# ---------------------------
# Program name normalization
# ---------------------------
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
        from urllib.parse import unquote
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
