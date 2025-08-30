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

            formatted += f"{idx}. {name} ({src})\n"
            formatted += f"- **Description**: {description}\n"

            domain = present(m.get("domain"), strict=True)
            if domain:
                formatted += f"- **Domain**: {domain}\n"

            eligibility = present(m.get("eligibility"), strict=True)
            if eligibility:
                formatted += f"- **Eligibility**: {eligibility}\n"

            amount = present(m.get("amount"), strict=True)
            if amount:
                formatted += f"- **Amount**: {amount}\n"

            deadline = present(m.get("deadline"), strict=True)
            if deadline:
                formatted += f"- **Deadline**: {deadline}\n"

            location = present(m.get("location"), strict=True)
            if location:
                formatted += f"- **Location**: {location}\n"

            contact = present(m.get("contact"), strict=True)
            if contact:
                formatted += f"- **Contact**: {contact}\n"

            url = present(m.get("url"), strict=True)
            if url:
                formatted += f"- **URL**: {url}\n"

            formatted += "\n"
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

⚠️ Important rules:  
- Use only the values explicitly provided in the context above.  
- If a field (e.g., Domain, Eligibility, Amount, Deadline, Location, Contact) has no value, **skip that field entirely**.  
- Do not invent or guess values.  

Format:

1. <Program Name> (Source)  
**Why it fits**: <1–2 lines about relevance to company’s domain or goals>  
**Description**: <What this program funds>  

[Optional fields — include only if present in the context]  
**Domain**: <Domain>  
**Eligibility**: <Eligibility>  
**Amount**: <Amount>  
**Deadline**: <Deadline>  
**Location**: <Location>  
**Contact**: <Email / phone>  

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
