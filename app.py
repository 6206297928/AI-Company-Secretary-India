import streamlit as st
import google.generativeai as genai
import pandas as pd
import io
import os
import pypdf  # UPDATED: Works better with Python 3.13

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="AI Company Secretary Agent",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CONSTANTS ---
BASE_RULES_FILE = "A2013-18.pdf"

# --- 3. HELPER FUNCTIONS ---

def get_best_available_model(api_key):
    """
    Auto-detects the best model to prevent 404 Errors.
    """
    genai.configure(api_key=api_key)
    try:
        # Check what models your API key actually has access to
        models = genai.list_models()
        available_names = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
        
        # Priority Logic: Try Flash -> Pro -> Fallback
        for name in available_names:
            if "gemini-1.5-flash" in name: return genai.GenerativeModel(name)
        for name in available_names:
            if "gemini-1.5-pro" in name: return genai.GenerativeModel(name)
        
        return genai.GenerativeModel('gemini-pro') # Fallback
    except:
        return genai.GenerativeModel('gemini-pro')

@st.cache_resource
def load_base_rules_text():
    if not os.path.exists(BASE_RULES_FILE):
        return None, f"❌ Critical Error: '{BASE_RULES_FILE}' not found in repo."
    
    try:
        text = ""
        with open(BASE_RULES_FILE, "rb") as f:
            pdf_reader = pypdf.PdfReader(f) # Using pypdf
            # Limit pages to prevent memory crash on Cloud Free Tier
            for i, page in enumerate(pdf_reader.pages):
                if i > 150: break 
                text += page.extract_text() + "\n"
        return text, "✅ Companies Act, 2013 Loaded."
    except Exception as e:
        return None, f"❌ Error reading PDF: {e}"

def extract_text_from_uploaded_pdfs(uploaded_files):
    combined_text = ""
    for pdf_file in uploaded_files:
        try:
            pdf_reader = pypdf.PdfReader(pdf_file) # Using pypdf
            for page in pdf_reader.pages:
                combined_text += page.extract_text() + "\n"
        except Exception as e:
            st.error(f"Error reading {pdf_file.name}: {e}")
    return combined_text

def clean_csv_output(text):
    text = text.replace("```csv", "").replace("```", "").strip()
    lines = text.split('\n')
    return "\n".join([line for line in lines if "," in line])

def generate_compliance_checklist(company_type, base_text, extra_text, api_key):
    model = get_best_available_model(api_key)
    
    # Limit context to be safe with Token Limits on smaller models
    safe_context = (base_text + "\n\n" + extra_text)[:30000] 

    prompt = f"""
    Act as a Company Secretary in India.
    User Context: **{company_type}** Company.
    
    Knowledge Base:
    {safe_context}
    
    TASK: Generate a Yearly Compliance Checklist for {company_type}.
    
    LOGIC:
    1. Private: Check exemptions.
    2. Listed: Apply SEBI rules.
    
    OUTPUT:
    1. Strategy Summary.
    2. CSV Table (Headers: "Month","Activity","Section","Frequency","Risk")
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

# --- 4. MAIN APP UI ---

with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("🔑 Gemini API Key", type="password")
    st.header("🏢 Company")
    company_type = st.radio("Type:", ["Private Limited", "Public (Unlisted)", "Listed (BSE/NSE)"])

st.title("⚖️ AI Company Secretary Agent")
st.markdown(f"### Compliance Manager for **{company_type}**")

# Load Data
base_text, msg = load_base_rules_text()
if "❌" in msg:
    st.error(msg)
    st.stop()
else:
    st.success(msg)

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("**Docs Loaded:** Companies Act 2013")
    uploaded_files = st.file_uploader("Upload Extra PDFs (AoA/SEBI)", type=['pdf'], accept_multiple_files=True)

with col2:
    if st.button("Generate Checklist", type="primary"):
        if not api_key:
            st.error("Enter API Key")
        else:
            with st.spinner("Analyzing..."):
                extra = extract_text_from_uploaded_pdfs(uploaded_files) if uploaded_files else ""
                res = generate_compliance_checklist(company_type, base_text, extra, api_key)
                
                parts = res.split("Month")
                st.write(parts[0].replace("```csv",""))
                
                if len(parts) > 1:
                    csv_data = "Month" + parts[1].replace("```","")
                    clean = clean_csv_output(csv_data)
                    st.dataframe(pd.read_csv(io.StringIO(clean)), use_container_width=True)

st.divider()
st.subheader("💬 Ask a Legal Question")
user_query = st.text_input("e.g., 'Can we give a loan to a Director?'")

if user_query and api_key:
    if st.button("Consult the Act"):
        model = get_best_available_model(api_key)
        extra_context = extract_text_from_uploaded_pdfs(uploaded_files) if uploaded_files else ""
        safe_context = (base_text + extra_context)[:25000]
        
        q_prompt = f"""
        Role: Company Secretary.
        User: {company_type} Company.
        Context: {safe_context}
        Question: "{user_query}"
        """
        
        with st.spinner("Searching..."):
            try:
                answer = model.generate_content(q_prompt)
                st.markdown(answer.text)
            except Exception as e:
                st.error(f"Error: {e}")
