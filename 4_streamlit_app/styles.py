import streamlit as st

def apply_modern_styling():
    """Apply modern CSS styling to Streamlit app"""
    
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Variables */
    :root {
        --primary-color: #667eea;
        --secondary-color: #764ba2;
        --accent-color: #f093fb;
        --success-color: #4ade80;
        --warning-color: #fbbf24;
        --error-color: #f87171;
        --text-primary: #1f2937;
        --text-secondary: #6b7280;
        --background-primary: #ffffff;
        --background-secondary: #f8fafc;
        --border-color: #e5e7eb;
        --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
        --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
        --border-radius: 0.75rem;
    }
    
    /* Dark mode variables */
    @media (prefers-color-scheme: dark) {
        :root {
            --text-primary: #f9fafb;
            --text-secondary: #d1d5db;
            --background-primary: #111827;
            --background-secondary: #1f2937;
            --border-color: #374151;
        }
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* Custom fonts */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        color: var(--text-primary);
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        padding: 3rem 2rem;
        border-radius: var(--border-radius);
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: var(--shadow-lg);
    }
    
    .main-header h1 {
        color: white;
        font-size: 3rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .main-header p {
        color: rgba(255,255,255,0.9);
        font-size: 1.2rem;
        font-weight: 400;
        margin: 0;
    }
    
    /* Chat message styling */
    .stChatMessage {
        background: var(--background-secondary);
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease;
    }
    
    .stChatMessage:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-1px);
    }
    
    /* User messages */
    .stChatMessage[data-testid="chat-message-user"] {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        color: white;
        border: none;
    }
    
    /* Assistant messages */
    .stChatMessage[data-testid="chat-message-assistant"] {
        background: var(--background-primary);
        border-left: 4px solid var(--primary-color);
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        color: white;
        border: none;
        border-radius: var(--border-radius);
        padding: 0.75rem 2rem;
        font-weight: 500;
        font-size: 1rem;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: var(--shadow-sm);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
        opacity: 0.9;
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* Secondary button styling */
    .secondary-button > button {
        background: transparent;
        color: var(--primary-color);
        border: 2px solid var(--primary-color);
    }
    
    .secondary-button > button:hover {
        background: var(--primary-color);
        color: white;
    }
    
    /* Success button */
    .success-button > button {
        background: linear-gradient(135deg, var(--success-color) 0%, #22c55e 100%);
    }
    
    /* Warning button */
    .warning-button > button {
        background: linear-gradient(135deg, var(--warning-color) 0%, #f59e0b 100%);
    }
    
    /* Input styling */
    .stTextInput > div > div > input {
        border: 2px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 0.75rem 1rem;
        font-size: 1rem;
        transition: all 0.2s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        outline: none;
    }
    
    /* Text area styling */
    .stTextArea > div > div > textarea {
        border: 2px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 1rem;
        font-size: 1rem;
        transition: all 0.2s ease;
        font-family: 'Inter', sans-serif;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        outline: none;
    }
    
    /* Sidebar styling */
    .css-1d391kg, section[data-testid="stSidebar"] {
        background: var(--background-secondary);
        border-right: 1px solid var(--border-color);
    }
    
    /* Sidebar toggle - multiple selectors for compatibility */
    .css-1rs6os, .css-1rs6os.edgvbvh3, .css-1rs6os.edgvbvh10, 
    [data-testid="collapsedControl"], .css-9s5bis {
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 999 !important;
        position: fixed !important;
        top: 1rem !important;
        left: 1rem !important;
    }
    
    /* File uploader styling */
    .stFileUploader {
        border: 2px dashed var(--border-color);
        border-radius: var(--border-radius);
        padding: 2rem;
        text-align: center;
        transition: all 0.2s ease;
        background: var(--background-secondary);
    }
    
    .stFileUploader:hover {
        border-color: var(--primary-color);
        background: rgba(102, 126, 234, 0.05);
    }
    
    /* Expander styling */
    .stExpander {
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        overflow: hidden;
        box-shadow: var(--shadow-sm);
    }
    
    .stExpander > div:first-child {
        background: var(--background-secondary);
        padding: 1rem;
        border-bottom: 1px solid var(--border-color);
    }
    
    /* Spinner styling */
    .stSpinner {
        color: var(--primary-color) !important;
    }
    
    /* Success/Error/Warning messages */
    .stSuccess {
        background: rgba(74, 222, 128, 0.1);
        border-left: 4px solid var(--success-color);
        border-radius: var(--border-radius);
    }
    
    .stError {
        background: rgba(248, 113, 113, 0.1);
        border-left: 4px solid var(--error-color);
        border-radius: var(--border-radius);
    }
    
    .stWarning {
        background: rgba(251, 191, 36, 0.1);
        border-left: 4px solid var(--warning-color);
        border-radius: var(--border-radius);
    }
    
    /* Info boxes */
    .stInfo {
        background: rgba(102, 126, 234, 0.1);
        border-left: 4px solid var(--primary-color);
        border-radius: var(--border-radius);
    }
    
    /* Custom classes for specific components */
    .funding-card {
        background: var(--background-primary);
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: var(--shadow-sm);
        transition: all 0.3s ease;
    }
    
    .funding-card:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }
    
    .funding-card h3 {
        color: var(--primary-color);
        margin-bottom: 1rem;
        font-weight: 600;
    }
    
    .deadline-badge {
        background: linear-gradient(135deg, var(--accent-color) 0%, var(--primary-color) 100%);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        font-size: 0.875rem;
        font-weight: 500;
        display: inline-block;
        margin-left: 0.5rem;
    }
    
    /* Loading states */
    @keyframes shimmer {
        0% { background-position: -468px 0; }
        100% { background-position: 468px 0; }
    }
    
    .loading-shimmer {
        animation: shimmer 1.2s ease-in-out infinite;
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 37%, #f0f0f0 63%);
        background-size: 400px 100%;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 2rem;
        }
        
        .main-header p {
            font-size: 1rem;
        }
        
        .main .block-container {
            padding: 1rem;
        }
    }
    
    /* Custom checkbox styling */
    .stCheckbox > label {
        background: var(--background-secondary);
        padding: 1rem;
        border-radius: var(--border-radius);
        border: 2px solid var(--border-color);
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .stCheckbox > label:hover {
        border-color: var(--primary-color);
        background: rgba(102, 126, 234, 0.05);
    }
    
    /* Feature highlight boxes */
    .feature-box {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        border: 1px solid rgba(102, 126, 234, 0.2);
        border-radius: var(--border-radius);
        padding: 1.5rem;
        margin: 1rem 0;
        text-align: center;
    }
    
    .feature-icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
    }
    
    </style>
    """, unsafe_allow_html=True)

def create_modern_header(title: str, subtitle: str):
    """Create a modern header section"""
    st.markdown(f"""
    <div class="main-header">
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)

def create_feature_box(icon: str, title: str, description: str):
    """Create a feature highlight box"""
    st.markdown(f"""
    <div class="feature-box">
        <div class="feature-icon">{icon}</div>
        <h3>{title}</h3>
        <p>{description}</p>
    </div>
    """, unsafe_allow_html=True)

def create_funding_card(program_name: str, description: str, deadline: str = None, amount: str = None):
    """Create a styled funding program card"""
    deadline_html = f'<span class="deadline-badge">⏰ {deadline}</span>' if deadline else ''
    amount_html = f'<p><strong>💰 Amount:</strong> {amount}</p>' if amount else ''
    
    st.markdown(f"""
    <div class="funding-card">
        <h3>{program_name} {deadline_html}</h3>
        <p>{description}</p>
        {amount_html}
    </div>
    """, unsafe_allow_html=True)

def create_button_with_style(label: str, button_type: str = "primary"):
    """Create styled buttons"""
    if button_type == "secondary":
        return st.markdown(f'<div class="secondary-button">', unsafe_allow_html=True)
    elif button_type == "success":
        return st.markdown(f'<div class="success-button">', unsafe_allow_html=True)
    elif button_type == "warning":
        return st.markdown(f'<div class="warning-button">', unsafe_allow_html=True)
    
    # Default primary button styling is handled by CSS