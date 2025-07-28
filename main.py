from engine.funding_query import run_funding_query
from engine.chatbot_memory import get_chatbot_chain

query = "We are an AI company focused on AI for robotics. We are focusing on research right now."

# Step 1: Get recommendation
response = run_funding_query(query)
print("\n--- Initial Recommendation ---\n")
print(response)

# Step 2: Setup chatbot
chatbot = get_chatbot_chain()
print("\n--- Chatbot Conversation ---\n")
print(chatbot.invoke({"question": query})["answer"])

# Step 3: Follow-up with memory context manually injected
follow_up = "What is the deadline for the second program?"
print("\n--- Follow-up ---\n")
print(chatbot.invoke({
    "question": follow_up,
    "chat_history": [{"question": query, "answer": response}]
})["answer"])
