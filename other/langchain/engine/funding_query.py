from langchain_config.pinecone_retriever import get_retriever
from langchain_config.prompt_template import get_prompt_template
from langchain_config.llm_provider import get_llm
from langchain_config.scoring import add_deadline_and_score
from langchain_config.format_blocks import format_for_prompt

def run_funding_query(user_query: str, target_domain="AI", funding_need="200000", user_location="Rhineland-Palatinate", provider="openai"):
    retriever = get_retriever()
    # Get documents from Pinecone
    docs = retriever.invoke(user_query)
    # Add relevance score and deadline countdown
    enriched = add_deadline_and_score(
        docs,
        query=user_query,
        funding_need=funding_need,
        target_domain=target_domain,
        user_location=user_location
    )
    # Sort and select top 5
    top_matches = sorted(enriched, key=lambda x: x["relevance_score"], reverse=True)[:5]
    # Format for LLM prompt
    context_text = format_for_prompt(top_matches)
    prompt = get_prompt_template().format(context=context_text, question=user_query)
    # Run through LLM
    llm = get_llm(model_name=provider) # Pass the provider to get_llm
    response = llm.invoke(prompt)
    return response