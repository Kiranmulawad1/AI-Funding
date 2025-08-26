from engine.funding_query import run_funding_query
from engine.chatbot_memory import get_chatbot_chain

query = "We are an AI company focused on AI for robotics. We are focusing on research right now."

# ✅ Use OpenAI first, fallback to LLaMA automatically
provider = "auto"

response = run_funding_query(query, provider="openai")
print("Using OpenAI retriever...")
print("\n--- Initial Recommendation ---\n")
print(response)

chatbot = get_chatbot_chain(provider=provider)
print("\n--- Chatbot Conversation ---\n")
print(chatbot.invoke({"question": query})["answer"])

follow_up = "What is the deadline for the second program?"
print("\n--- Follow-up ---\n")
print(chatbot.invoke({
    "question": follow_up,
    "chat_history": [{"question": query, "answer": response}]
})["answer"])
