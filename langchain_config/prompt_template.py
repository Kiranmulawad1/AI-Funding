from langchain.prompts import PromptTemplate

def get_prompt_template():
    return PromptTemplate(
        input_variables=["context", "question"],
        template="""
The company described itself as:

"{question}"

Below are the top 5 most relevant public funding programs in Germany, identified through semantic search based on the company’s goals and funding needs:

{context}

---

Your task:

Write a **concise, professional funding recommendation** featuring only the **top 2–3 most relevant programs**.

For each program, include:
- A short explanation of **why it fits**
- Clear, structured details
- Helpful **next steps**, including a link

### Output Format (follow exactly):

1. <Program Name>  
**Why it fits**: <1–2 lines on why it suits the company — e.g., funding area, maturity stage, amount>  
**Description**: <Brief summary of the program’s goal and what it funds>  
**Domain**: <Domain>  
**Eligibility**: <Eligibility criteria>  
**Amount**: <Amount>  
**Deadline**: <Deadline (date or timeframe)>  
**Location**: <Location or applicable regions>
**Source**: <Source>
**Contact**: <Email or organization name>  
**Next Steps**:  
- Step 1: [Visit the official page:]({{url}})  
- Step 2: <One key action the company must take>  
- Step 3: <Another action (e.g., submit proposal, form consortium)>

If any field (like Amount, Deadline, or Contact) is missing, say “Not specified” or skip that line.

Important:
- Prioritize the programs that **best match the company’s domain (e.g., AI, robotics), funding stage (early-stage/startup), or funding amount**.
- Do **not** list all 5 programs. Only return the **top 2 or 3**.
- Use **bullet points under “Next Steps”**, not a paragraph.
- Keep the tone helpful, formal, and easy to read for a German startup audience.
"""
    )
