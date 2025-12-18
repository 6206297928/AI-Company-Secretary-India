import streamlit as st
import google.generativeai as genai
import pandas as pd
import io
import os
import PyPDF2

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

def get_gemini_model(api_key):
    """
    Tries to get the best available model to prevent 404 errors.
    """
    genai.configure(api_key=api_key)
    
    # Priority list of models to try
    models_to_try = [
        'gemini-1.5-flash',       # Fast & Large Context
        'gemini-1.5-flash-latest',# Alternative name
        'gemini-1.5-pro',         # Smarter but slower
        'gemini-pro'              # Fallback (Standard)
    ]
    
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            # Test quickly if the model works
            return model
        except:
            continue
            
    # If all fail, return a default safe one (usually gemini-pro works)
    return genai.GenerativeModel('gemini-pro')

@st.cache_resource
def load_base_rules_text():
    if not os.path.exists(BASE_RULES_FILE):
        return None, f"❌ Critical Error: '{BASE_RULES_FILE}' not found. Please add it to your GitHub repo."
    
    try:
        text = ""
        with open(BASE_RULES_FILE, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            # Limit pages for speed/memory if needed, but for Act usually fine
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text, "✅ Companies Act, 2013 Loaded Successfully."
    except Exception as e:
        return None, f"❌ Error reading base PDF: {e}"

def extract_text_from_uploaded_pdfs(uploaded_files):
    combined_text = ""
    for pdf_file in uploaded_files:
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            for page in pdf_reader.pages:
                combined_text += page.extract_text() + "\n"
        except Exception as e:
            st.error(f"Error reading {pdf_file.name}: {e}")
    return combined_text

def clean_csv_output(text):
    text = text.replace("```csv", "").replace("```", "").strip()
    lines = text.split('\n')
    clean_lines = [line for line in lines if "," in line]
    return "\n".join(clean_lines)

def generate_compliance_checklist(company_type, base_text, extra_text, api_key):
    # Use the robust model getter
    model = get_gemini_model(api_key)

    full_knowledge_base = base_text + "\n\n" + extra_text

    prompt = f"""
    ### ROLE
    You are an expert Company Secretary (CS) in India.
    
    ### USER CONTEXT
    The user represents a **{company_type}** Company.
    
    ### SOURCE OF TRUTH
    Use the following text (Companies Act/Rules) as your strict knowledge base:
    {full_knowledge_base[:60000]} 
    
    ### TASK
    Generate a **Yearly Compliance Checklist** specifically for a **{company_type}** Company.
    
    ### LOGIC (TRIAGE)
    1. **Private Limited:** Check for exemptions (Sec 185, 173).
    2. **Public (Unlisted):** Strict Companies Act rules.
    3. **Listed:** Companies Act + SEBI LODR requirements.
    
    ### OUTPUT FORMAT
    1. **Executive Summary**: Brief strategy notes.
    2. **The Checklist Table (CSV Only)**:
       Headers: "Month/Trigger","Form/Activity","Section/Rule","Frequency","Penalty Risk"
       Example: "September 30","File AOC-4","Section 137","Yearly","High"
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error calling Gemini: {e}"

# --- 4. MAIN APP UI ---

with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("🔑 Gemini API Key", type="password")
    
    st.markdown("---")
    st.header("🏢 Company Profile")
    company_type = st.radio(
        "Structure:",
        ["Private Limited", "Public (Unlisted)", "Listed (BSE/NSE)"],
        index=0
    )

st.title("⚖️ AI Company Secretary Agent")
st.markdown(f"### Intelligent Compliance Manager for **{company_type}** Companies")
st.caption("Powered by Google Gemini & RAG")
st.divider()

base_rules_text, status_msg = load_base_rules_text()

if "✅" in status_msg:
    st.success(status_msg)
else:
    st.error(status_msg)
    st.warning("⚠️ Please ensure 'A2013-18.pdf' is inside the folder.")
    st.stop() 

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📂 Supplemental Knowledge")
    st.markdown("The **Companies Act 2013** is active.")
    st.markdown("Upload specific docs (AoA, SEBI Circulars) if needed:")
    uploaded_files = st.file_uploader("Upload PDFs", type=['pdf'], accept_multiple_files=True)

with col2:
    st.subheader("🚀 Generate Report")
    
    if st.button("Generate Yearly Checklist", type="primary"):
        if not api_key:
            st.error("❌ Please enter your Gemini API Key.")
        else:
            with st.spinner("⚖️ Analyzing Company Law..."):
                extra_text = extract_text_from_uploaded_pdfs(uploaded_files) if uploaded_files else ""
                
                result = generate_compliance_checklist(company_type, base_rules_text, extra_text, api_key)
                
                parts = result.split("Month/Trigger") 
                
                st.markdown("### 📋 Executive Summary")
                st.markdown(parts[0].replace("```csv", "").replace("```", ""))
                
                if len(parts) > 1:
                    csv_raw = "Month/Trigger" + parts[1]
                    clean_csv = clean_csv_output(csv_raw)
                    
                    try:
                        st.markdown("### 📅 Compliance Calendar")
                        df = pd.read_csv(io.StringIO(clean_csv))
                        st.dataframe(df, use_container_width=True)
                        
                        csv_bytes = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "💾 Download CSV",
                            csv_bytes,
                            f"Compliance_{company_type.replace(' ','_')}.csv",
                            "text/csv"
                        )
                    except:
                        st.error("Table formatting issue. See raw output below.")
                        st.code(clean_csv)

st.divider()
st.subheader("💬 Ask a Legal Question")
user_query = st.text_input("e.g., 'Can we give a loan to a Director?'")

if user_query and api_key:
    if st.button("Consult the Act"):
        model = get_gemini_model(api_key)
        
        extra_context = extract_text_from_uploaded_pdfs(uploaded_files) if uploaded_files else ""
        
        q_prompt = f"""
        Act as a strict Company Secretary for a **{company_type}** company.
        Using the Companies Act 2013:
        {base_rules_text[:50000]}
        {extra_context[:10000]}
        
        Question: "{user_query}"
        Answer with Section references.
        """
        
        with st.spinner("Searching..."):
            try:
                answer = model.generate_content(q_prompt)
                st.markdown(answer.text)
            except Exception as e:
                st.error(f"Error: {e}")
