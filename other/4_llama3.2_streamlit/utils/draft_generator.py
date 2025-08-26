from ollama import Client
from docx import Document

def build_draft_prompt(profile, program):
    return f"""
You are a professional grant writer AI assistant.

Use the following company profile and the funding program details to generate a complete funding application draft.

## Company Profile
- Company Name: {profile["company_name"]}
- Location: {profile["location"]}
- Industry: {profile["industry"]}
- Goals: {profile["goals"]}
- Project Idea: {profile["project_idea"]}
- Funding Need: {profile["funding_need"]}

## Funding Program
- Name: {program["name"]}
- Amount: {program["amount"]}
- Deadline: {program["deadline"]}
- Eligibility: {program["eligibility"]}
- Description: {program["description"]}

## Format Output as:
1. Title
2. Executive Summary
3. Objectives
4. Innovation
5. Budget Estimate
6. Relevance to Program
7. Contact Details

Be professional and concise, but clear. Format the output as a ready-to-edit funding application.
"""

def generate_funding_draft(profile, program):
    client = Client(host="http://localhost:11434")
    prompt = build_draft_prompt(profile, program)
    response = client.generate(
        model="llama3.2",
        prompt=prompt,
        stream=False
    )
    return response["response"].strip()

def save_draft_to_docx(text, filename="application_draft.docx"):
    doc = Document()
    for para in text.split("\n\n"):
        doc.add_paragraph(para.strip())
    doc.save(filename)
    return filename
