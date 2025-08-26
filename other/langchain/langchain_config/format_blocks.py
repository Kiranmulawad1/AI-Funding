def format_for_prompt(matches):
    blocks = []
    for i, meta in enumerate(matches, 1):
        block = f"""**{i}. {meta.get("name", "Unnamed")}**\n"""
        for field in ["description", "domain", "eligibility", "amount", "deadline", "procedure", "contact", "location", "source"]:
            val = meta.get(field)
            if val:
                if field == "deadline" and meta.get("days_left"):
                    val += f" (🕒 {int(meta['days_left'])} days left)"
                block += f"- **{field.capitalize()}**: {val}\n"
        if meta.get("url"):
            block += f"- **More info**: {meta['url']}\n"
        blocks.append(block)
    return "\n".join(blocks)
