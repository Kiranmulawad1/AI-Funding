from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import Tool
from langgraph.graph import StateGraph, END
from src.agents.tools import BrowserTools
from src.core.config import get_openai_client, OPENAI_API_KEY

# 1. Define State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    current_url: str | None
    findings: str

# 2. Define Nodes

def researcher_node(state: AgentState):
    """
    The brain of the agent. Decides whether to search, visit a page, or finish.
    """
    messages = state['messages']
    model = ChatOpenAI(model="gpt-4-turbo", openai_api_key=OPENAI_API_KEY, temperature=0)
    
    # Bind tools to the model
    tools = [BrowserTools.search_web, BrowserTools.visit_page]
    model_with_tools = model.bind_tools(tools)
    
    # Get response
    response = model_with_tools.invoke(messages)
    return {"messages": [response]}

def tool_node(state: AgentState):
    """
    Executes the tool calls made by the researcher node.
    """
    messages = state['messages']
    last_message = messages[-1]
    
    # Check if there are tool calls
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        # If no tool calls, we shouldn't be here, but just return empty to be safe
        return {"messages": []}
    
    results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        call_id = tool_call['id']
        
        print(f"🛠️ Executing {tool_name} with {tool_args}")
        
        # Execute the corresponding tool
        output = "Error: Tool not found"
        if tool_name == "search_web":
            output = BrowserTools.search_web.invoke(tool_args)
        elif tool_name == "visit_page":
            # For async tools, we need to run them synchronously here for simplicity in this node
            # In a full async graph we would await them
            import asyncio
            output = asyncio.run(BrowserTools.visit_page.ainvoke(tool_args))
            
        results.append(
            {"role": "tool", "content": str(output), "tool_call_id": call_id}
        )
        
    return {"messages": results}

# 3. Define Logic (Edges)

def should_continue(state: AgentState):
    """
    Decides if we should go to the tool node or end.
    """
    last_message = state['messages'][-1]
    
    # If the LLM just made a tool call -> Go to Tool Node
    if last_message.tool_calls:
        return "continue"
    
    # If the LLM provided a final answer -> End
    return "end"

# 4. Build Graph

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("researcher", researcher_node)
workflow.add_node("tools", tool_node)

# Add edges
workflow.set_entry_point("researcher")

workflow.add_conditional_edges(
    "researcher",
    should_continue,
    {
        "continue": "tools",
        "end": END
    }
)

workflow.add_edge("tools", "researcher")

# Compile
app = workflow.compile()

# 5. Helper Function to Run
def run_deep_research(query: str):
    print(f"🚀 Starting Deep Research for: '{query}'")
    initial_state = {
        "messages": [HumanMessage(content=f"""You are a Deep Research Agent. Your goal is to find concrete public funding opportunities for: '{query}'.

RULES:
1. **LANGUAGE**: If the target region is Germany, you MUST search in **German** (e.g., translate "AI grants" to "KI Förderung").
2. Search for portals or official grant pages (look for .de domains).
3. Visit the most promising links to extract details.
4. **CRITICAL**: If a page is generic or lacks specific grant details (Deadline, Amount, Eligibility), you MUST **search again** with a refined query or **visit a different link**.
5. Do NOT give up after checking just one page. Try at least 3 different sources if needed.
6. Only stop when you have found concrete funding data or exhausted all options.

Output the final result as a clear summary of the specific grants found (in English).""")],
        "current_url": None,
        "findings": ""
    }
    
    output = app.invoke(initial_state)
    return output['messages'][-1].content

if __name__ == "__main__":
    # Test run
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "AI grants Berlin"
    result = run_deep_research(query)
    print("\n✅ FINAL FINDINGS:\n")
    print(result)
