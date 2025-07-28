import re
from dateutil import parser
from datetime import datetime

def safe_parse_deadline(deadline_str):
    try:
        return parser.parse(deadline_str, dayfirst=True, fuzzy=True)
    except:
        return None

def compute_relevance_score(metadata, query="", funding_need="200000", target_domain="AI", user_location="Rhineland-Palatinate"):
    score = 0

    # Domain match
    if target_domain.lower() in str(metadata.get("domain", "")).lower():
        score += 0.4

    # Funding amount
    try:
        amount_val = int(re.sub(r"[^\d]", "", str(metadata.get("amount", "0"))))
        if amount_val >= int(funding_need):
            score += 0.3
    except:
        pass

    # Deadline relevance
    if "month" in str(metadata.get("deadline", "")).lower() or "2025" in str(metadata.get("deadline", "")):
        score += 0.2

    # Keyword match
    if any(word.lower() in str(metadata.get("description", "")).lower() for word in query.split()):
        score += 0.1

    # Location match
    if user_location.lower() in str(metadata.get("location", "")).lower():
        score += 0.1

    return round(score * 100)

def add_deadline_and_score(docs, query, funding_need, target_domain, user_location):
    results = []
    for doc in docs:
        meta = doc.metadata.copy()
        meta["relevance_score"] = compute_relevance_score(meta, query, funding_need, target_domain, user_location)

        deadline_dt = safe_parse_deadline(meta.get("deadline", ""))
        if deadline_dt:
            meta["days_left"] = (deadline_dt - datetime.now()).days
        else:
            meta["days_left"] = None

        results.append(meta)
    return results
