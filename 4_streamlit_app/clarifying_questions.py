# from typing import List, Dict, Optional
# import json
# from config import get_openai_client
# import streamlit as st

# class ClarifyingQuestionsManager:
#     def __init__(self):
#         self.client = get_openai_client()
        
#     def should_ask_funding_questions(self, query: str) -> bool:
#         """Determine if the query needs clarification for better funding search"""
        
#         prompt = f"""
#         Analyze this funding search query to determine if it needs clarification.
        
#         Query: "{query}"
        
#         A query needs clarification if it's:
#         - Too vague or generic
#         - Missing key details like funding amount, stage, or specific domain
#         - Could benefit from more specificity about company type, location, or goals
        
#         Respond with only "YES" or "NO":
#         """
        
#         response = self.client.chat.completions.create(
#             model="gpt-3.5-turbo",
#             messages=[{"role": "user", "content": prompt}],
#             max_tokens=10
#         )
        
#         return response.choices[0].message.content.strip().upper() == "YES"
    
#     def should_ask_draft_questions(self, funding_program: Dict, user_query: str) -> bool:
#         """Determine if we need more info for application draft"""
        
#         prompt = f"""
#         Determine if we need more information to create a high-quality funding application draft.
        
#         User Query: "{user_query}"
#         Funding Program: {funding_program.get('name', 'Unknown')}
#         Available Info: {', '.join([k for k, v in funding_program.items() if v and str(v).lower() not in ['not specified', 'information not found']])}
        
#         We should ask for clarification if the user query is:
#         - Generic or lacks specific project details
#         - Missing technical specifications
#         - Unclear about business model or implementation plan
#         - Vague about team qualifications or experience
        
#         Respond with only "YES" or "NO":
#         """
        
#         response = self.client.chat.completions.create(
#             model="gpt-3.5-turbo",
#             messages=[{"role": "user", "content": prompt}],
#             max_tokens=10
#         )
        
#         return response.choices[0].message.content.strip().upper() == "YES"
    
    
#     def process_funding_answers(self, original_query: str, answers: Dict[str, str]) -> str:
#         """Combine original query with clarifying answers for better search"""
        
#         prompt = f"""
#         Enhance this funding search query using the additional information provided.
        
#         Original Query: "{original_query}"
        
#         Additional Information:
#         {json.dumps(answers, indent=2)}
        
#         Create an improved, more specific query that incorporates the clarifying details.
#         Keep it natural and comprehensive but concise.
        
#         Enhanced Query:
#         """
        
#         response = self.client.chat.completions.create(
#             model="gpt-3.5-turbo",
#             messages=[{"role": "user", "content": prompt}],
#             max_tokens=200
#         )
        
#         return response.choices[0].message.content.strip()
    
#     def process_draft_answers(self, original_query: str, funding_program: Dict, answers: Dict[str, str]) -> Dict[str, str]:
#         """Process clarifying answers for better application draft"""
        
#         prompt = f"""
#         Create an enhanced company/project profile using the original query and clarifying answers.
        
#         Original Query: "{original_query}"
#         Funding Program: {funding_program.get('name', 'Unknown')}
        
#         Clarifying Answers:
#         {json.dumps(answers, indent=2)}
        
#         Return a JSON object with enhanced profile information:
#         {{
#             "enhanced_project_description": "...",
#             "technical_approach": "...",
#             "market_opportunity": "...",
#             "timeline": "...",
#             "expected_outcomes": "...",
#             "team_expertise": "...",
#             "innovation_aspects": "..."
#         }}
        
#         Fill in only the fields that have sufficient information from the answers.
#         """
        
#         response = self.client.chat.completions.create(
#             model="gpt-4",
#             messages=[{"role": "user", "content": prompt}],
#             max_tokens=1200
#         )
        
#         try:
#             enhanced_profile = json.loads(response.choices[0].message.content.strip())
#             # Validate it's a dictionary
#             if isinstance(enhanced_profile, dict):
#                 return enhanced_profile
#             else:
#                 raise ValueError("Invalid enhanced profile format")
#         except (json.JSONDecodeError, ValueError) as e:
#             print(f"Error parsing enhanced profile: {e}")
#             # Return basic enhanced info if JSON parsing fails
#             return {
#                 "enhanced_project_description": f"Enhanced project based on: {original_query}",
#                 "additional_details": str(answers)
#             }

# def display_funding_questions_ui(questions_manager: ClarifyingQuestionsManager, query: str):
#     """Display clarifying questions UI for funding search"""
    
#     if not questions_manager.should_ask_funding_questions(query):
#         return None, query
    
#     st.info("🤔 I'd like to ask a few questions to find better funding matches for you:")
    
#     questions = questions_manager.generate_funding_questions(query)
#     answers = {}
    
#     for i, question_data in enumerate(questions):
#         question = question_data['question']
#         category = question_data['category']
#         options = question_data.get('options', [])
        
#         if options:
#             answer = st.selectbox(
#                 question,
#                 ["Select an option..."] + options,
#                 key=f"funding_q_{i}_{category}"
#             )
#             if answer != "Select an option...":
#                 answers[category] = answer
#         else:
#             answer = st.text_input(
#                 question,
#                 key=f"funding_q_{i}_{category}"
#             )
#             if answer.strip():
#                 answers[category] = answer.strip()
    
#     if st.button("🔍 Search with Enhanced Details", key="enhanced_search"):
#         if answers:
#             enhanced_query = questions_manager.process_funding_answers(query, answers)
#             return answers, enhanced_query
#         else:
#             st.warning("Please answer at least one question to enhance your search.")
#             return None, query
    
#     return None, query

# def display_draft_questions_ui(questions_manager: ClarifyingQuestionsManager, funding_program: Dict, user_query: str):
#     """Display clarifying questions UI for application draft"""
    
#     if not questions_manager.should_ask_draft_questions(funding_program, user_query):
#         return None
    
#     st.info("📝 A few questions to create a more detailed application draft:")
    
#     questions = questions_manager.generate_draft_questions(funding_program, user_query)
#     answers = {}
    
#     for i, question_data in enumerate(questions):
#         question = question_data['question']
#         category = question_data['category']
#         question_type = question_data.get('type', 'text')
        
#         if question_type == 'select' and 'options' in question_data:
#             answer = st.selectbox(
#                 question,
#                 ["Select an option..."] + question_data['options'],
#                 key=f"draft_q_{i}_{category}"
#             )
#             if answer != "Select an option...":
#                 answers[category] = answer
#         else:
#             answer = st.text_area(
#                 question,
#                 height=100,
#                 key=f"draft_q_{i}_{category}"
#             )
#             if answer.strip():
#                 answers[category] = answer.strip()
    
#     if st.button("📄 Generate Enhanced Draft", key="enhanced_draft"):
#         if answers:
#             enhanced_profile = questions_manager.process_draft_answers(user_query, funding_program, answers)
#             return enhanced_profile
#         else:
#             st.warning("Please answer at least one question to enhance your draft.")
#             return None
    
#     return None

from typing import List, Dict, Optional
import streamlit as st
from config import get_openai_client

class ClarifyingQuestionsManager:
    def __init__(self):
        self.client = get_openai_client()
        
    def should_ask_funding_questions(self, query: str) -> bool:
        """Simple check if query needs clarification"""
        return len(query.split()) < 8 or any(word in query.lower() for word in [
            'funding', 'help', 'need', 'startup', 'sources', 'what', 'how', 'grant'
        ])
    
    def generate_funding_questions(self, query: str) -> List[Dict[str, str]]:
        """Return predefined questions - no f-strings!"""
        return [
            {
                "question": "What funding amount range are you targeting?",
                "category": "amount", 
                "options": ["Under €50K", "€50K-€200K", "€200K-€500K", "€500K-€1M", "Over €1M", "Not sure"]
            },
            {
                "question": "What stage is your project/company in?",
                "category": "stage",
                "options": ["Research/Idea", "Prototype development", "Early-stage startup", "Growing company", "Established business", "Other"]
            },
            {
                "question": "Which region are you located in?", 
                "category": "location",
                "options": ["Baden-Württemberg", "Bavaria", "Berlin", "North Rhine-Westphalia", "Hamburg", "Hessen", "Other German state", "Not sure"]
            }
        ]
    
    def should_ask_draft_questions(self, funding_program: Dict, user_query: str) -> bool:
        return len(user_query.split()) < 10
    
    def generate_draft_questions(self, funding_program: Dict, user_query: str) -> List[Dict[str, str]]:
        return [
            {
                "question": "What specific technical approach will your project use?",
                "category": "technical",
                "type": "text"
            },
            {
                "question": "What is your expected project timeline?",
                "category": "timeline",
                "type": "select", 
                "options": ["6 months", "1 year", "18 months", "2+ years", "Flexible"]
            },
            {
                "question": "What is the main problem or market need your project addresses?",
                "category": "problem",
                "type": "text"
            }
        ]
    
    def process_funding_answers(self, original_query: str, answers: Dict[str, str]) -> str:
        enhanced_parts = [original_query]
        
        if answers.get('amount'):
            enhanced_parts.append(f"Funding needed: {answers['amount']}")
        if answers.get('stage'):
            enhanced_parts.append(f"Stage: {answers['stage']}")  
        if answers.get('location'):
            enhanced_parts.append(f"Location: {answers['location']}")
            
        return ". ".join(enhanced_parts)
    
    def process_draft_answers(self, original_query: str, funding_program: Dict, answers: Dict[str, str]) -> Dict[str, str]:
        enhanced_profile = {"enhanced_project_description": original_query}
        
        if answers.get('technical'):
            enhanced_profile['technical_approach'] = answers['technical']
        if answers.get('timeline'):
            enhanced_profile['timeline'] = answers['timeline']
        if answers.get('problem'):
            enhanced_profile['market_opportunity'] = answers['problem']
            
        return enhanced_profile

def display_funding_questions_ui(questions_manager: ClarifyingQuestionsManager, query: str):
    """Display funding questions UI"""
    
    if not questions_manager.should_ask_funding_questions(query):
        return None, query
    
    st.info("🤔 A few quick questions to find better funding matches:")
    
    questions = questions_manager.generate_funding_questions(query)
    answers = {}
    
    for i, question_data in enumerate(questions):
        question = question_data['question']
        category = question_data['category']
        options = question_data.get('options', [])
        
        if options:
            answer = st.selectbox(
                question,
                ["Select an option..."] + options,
                key=f"funding_q_{i}_{category}"
            )
            if answer != "Select an option...":
                answers[category] = answer
    
    if st.button("🔍 Search with Enhanced Details", key="enhanced_search"):
        if answers:
            enhanced_query = questions_manager.process_funding_answers(query, answers)
            return answers, enhanced_query
        else:
            st.warning("Please answer at least one question.")
            return None, query
    
    return None, query

def display_draft_questions_ui(questions_manager: ClarifyingQuestionsManager, funding_program: Dict, user_query: str):
    """Display draft questions UI"""
    
    if not questions_manager.should_ask_draft_questions(funding_program, user_query):
        return None
    
    st.info("📝 A few questions to create a better application draft:")
    
    questions = questions_manager.generate_draft_questions(funding_program, user_query)
    answers = {}
    
    for i, question_data in enumerate(questions):
        question = question_data['question']
        category = question_data['category']
        question_type = question_data.get('type', 'text')
        
        if question_type == 'select' and 'options' in question_data:
            answer = st.selectbox(
                question,
                ["Select an option..."] + question_data['options'],
                key=f"draft_q_{i}_{category}"
            )
            if answer != "Select an option...":
                answers[category] = answer
        else:
            answer = st.text_area(
                question,
                height=100,
                key=f"draft_q_{i}_{category}"
            )
            if answer.strip():
                answers[category] = answer.strip()
    
    if st.button("📄 Generate Enhanced Draft", key="enhanced_draft"):
        if answers:
            enhanced_profile = questions_manager.process_draft_answers(user_query, funding_program, answers)
            return enhanced_profile
        else:
            st.warning("Please answer at least one question.")
            return None
    
    return None