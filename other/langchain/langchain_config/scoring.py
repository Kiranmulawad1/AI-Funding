import re
from dateutil import parser
from datetime import datetime

def safe_parse_deadline(deadline_str):
    try:
        return parser.parse(deadline_str, dayfirst=True, fuzzy=True)
    except:
        return None

def compute_relevance_score(metadata, query="", funding_need="200000", target_domain="AI", user_location="Rhineland-Palatinate"):
    score = 0.0

    # 1. Domain match - more flexible
    domain_text = (metadata.get("domain", "") + " " + metadata.get("description", "")).lower()
    if target_domain.lower() in domain_text:
        score += 0.4

    # 2. Funding amount - allow slight shortfall
    try:
        amount_val = int(re.sub(r"[^\d]", "", str(metadata.get("amount", "0"))))
        if amount_val >= int(funding_need) * 0.8:
            score += 0.3
    except:
        pass

    # 3. Deadline quality - boost if year or month mentioned
    deadline = metadata.get("deadline", "").lower()
    if "month" in deadline or "2025" in deadline:
        score += 0.15
    elif deadline.strip():
        score += 0.05

    # 4. Keyword match - relaxed condition
    description = metadata.get("description", "").lower()
    if any(word.lower() in description for word in query.split()):
        score += 0.1

    # 5. Location match (optional)
    location = metadata.get("location", "").lower()
    if user_location.lower() in location:
        score += 0.05

    return round(score * 100)  # Return score as a percentage

def add_deadline_and_score(docs, query, funding_need, target_domain, user_location):
    results = []
    for doc in docs:
        meta = doc.metadata.copy()
        meta["relevance_score"] = compute_relevance_score(
            meta,
            query=query,
            funding_need=funding_need,
            target_domain=target_domain,
            user_location=user_location
        )

        deadline_dt = safe_parse_deadline(meta.get("deadline", ""))
        if deadline_dt:
            meta["days_left"] = (deadline_dt - datetime.now()).days
        else:
            meta["days_left"] = None

        results.append(meta)
    return results
