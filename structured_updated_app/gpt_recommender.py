# gpt_recommender.py
import re
from utils import present, program_name

def build_gpt_prompt(query: str, top_matches: list) -> str:
    def deduplicate_programs(matches):
        seen = set()
        unique = []
        for m in matches:
            name = program_name(m)
            src = present(m.get("source", "Unknown"))
            url = present(m.get("url", ""))
            key = f"{name.lower()}::{src.lower()}::{url.lower()}"
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return unique

    def format_semantic_results(matches):
        formatted = ""
        for idx, m in enumerate(matches[:3], 1):
            name = program_name(m)
            src = present(m.get("source", "Unknown"))
            description = present(m.get("description"))
            domain = present(m.get("domain"))
            eligibility = present(m.get("eligibility"))
            amount = present(m.get("amount"))
            deadline = present(m.get("deadline"))
            location = present(m.get("location"))
            contact = present(m.get("contact"))
            url = present(m.get("url"))

            formatted += f"""{idx}. {name} ({src})
- **Description**: {description}
- **Domain**: {domain}
- **Eligibility**: {eligibility}
- **Amount**: {amount}
- **Deadline**: {deadline}
- **Location**: {location}
- **Contact**: {contact}
- **URL**: {url}\n\n"""
        return formatted

    deduped = deduplicate_programs(top_matches)
    semantic_output = format_semantic_results(deduped)

    prompt = f"""
The company described itself as:

"{query}"

Here are the top 3 most relevant public funding programs in Germany, based on a semantic search match to their needs:

{semantic_output}

Now:

Please write a concise and professional recommendation containing **only the top 2–3 most relevant funding programs** in this format:

Only select the top programs that most directly match the company’s domain, maturity stage, or funding needs.
**Do not repeat the same program more than once.**
If a program is already listed, do not list it again even if it appears multiple times above.

1. <Program Name> (Source)  
**Why it fits**: <1–2 lines about relevance to company’s domain or goals>  
**Description**: <What this program funds>  
**Domain**: <Domain>  
**Eligibility**: <Eligibility>  
**Amount**: <Amount>  
**Deadline**: <Deadline>  
**Location**: <Location or say "Not specified">  
**Contact**: <Email / phone or "Not specified">  
**Next Steps**:  
- Step 1: [Visit the official page]({{url}})  
- Step 2: <Action step>  
- Step 3: <Action step>  

Only return the final formatted recommendation in markdown. Do not include preamble or commentary.
"""
    return prompt.strip()

def generate_gpt_recommendation(query: str, results: list, client) -> str:
    prompt = build_gpt_prompt(query, results)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a funding assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def extract_sources_from_response(response_text: str) -> list:
    sources = set()
    for line in response_text.splitlines():
        match = re.match(r"\d+\.\s+.+\s\(([^)]+)\)", line)
        if match:
            sources.add(match.group(1))
    return list(sources)
