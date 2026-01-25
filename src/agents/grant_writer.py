from typing import TypedDict, Annotated, Sequence, List
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from src.core.config import get_openai_client, OPENAI_API_KEY
from src.core.document_generator import generate_funding_draft
import json

# 1. Define State
class GrantWriterState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    funding_program: dict
    company_profile: dict
    missing_info: List[str]
    draft_ready: bool
    final_docx: bytes | None

# 2. Define Nodes

def interviewer_node(state: GrantWriterState):
    """
    Analyzes the profile vs funding requirements and asks questions.
    """
    messages = state['messages']
    profile = state['company_profile']
    program = state['funding_program']
    
    # If this is the start, analyze gaps
    if len(messages) == 0:
        system_prompt = f"""You are an expert Grant Writer Interviewer.
        Your goal is to gather missing information to write a perfect application for:
        '{program.get('name', 'Funding Program')}'
        
        Current Company Profile:
        {json.dumps(profile, indent=2)}
        
        Analyze the profile against standard grant requirements (Innovation, Commercialization, Team, Budget).
        Identify 1-3 CRITICAL missing pieces of information.
        
        If information is missing, ask the user ONE question at a time to get it.
        If you have enough information, say "READY_TO_DRAFT".
        """
        messages = [SystemMessage(content=system_prompt)]
    
    # Check current state again to remind the model
    reminder_prompt = """
    REMINDER:
    1. Ask ONE question at a time.
    2. When you have enough information, WRITE THE FULL GRANT PROPOSAL DRAFT directly in the chat.
    3. Use Markdown formatting.
    4. Start the draft with the title "Funding Application Draft".
    """
    messages.append(SystemMessage(content=reminder_prompt))
    
    model = ChatOpenAI(model="gpt-4-turbo", openai_api_key=OPENAI_API_KEY, temperature=0.7)
    response = model.invoke(messages)
    
    return {"messages": [response]}

def drafter_node(state: GrantWriterState):
    """
    Generates the final DOCX.
    """
    print("✍️ Generating Draft...")
    # implementation will happen in the UI wrapper mostly, but we can prepare the text here
    return {"draft_ready": True}

# 3. Define Logic (Edges)

def should_continue(state: GrantWriterState):
    msg = state['messages'][-1].content
    
    # 1. Strict Signal
    if "READY_TO_DRAFT" in msg:
        return "drafter"
        
    # 2. Header Signal
    if "Funding Application Draft" in msg:
        return "drafter"
        
    # 3. Content Signal (Heuristics)
    # If it has standard letter parts and is long enough, assume it's a draft
    if ("Subject:" in msg and "Dear" in msg) or ("Executive Summary" in msg and len(msg) > 500):
        return "drafter"
        
    return END  # Wait for user input

# 4. Build Graph
workflow = StateGraph(GrantWriterState)

workflow.add_node("interviewer", interviewer_node)
workflow.add_node("drafter", drafter_node)

workflow.set_entry_point("interviewer")

workflow.add_conditional_edges(
    "interviewer",
    should_continue,
    {
        "drafter": "drafter",
        END: END
    }
)

workflow.add_edge("drafter", END)

# Compile
grant_writer_app = workflow.compile()
