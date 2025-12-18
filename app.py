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
# The app expects this specific file in the same directory
BASE_RULES_FILE = "A2013-18.pdf"

# --- 3. HELPER FUNCTIONS ---

@st.cache_resource
def load_base_rules_text():
    """
    Loads the Companies Act 2013 PDF from the repository/local folder.
    """
    if not os.path.exists(BASE_RULES_FILE):
        return None, f"❌ Critical Error: '{BASE_RULES_FILE}' not found. Please add it to your GitHub repo."
    
    try:
        text = ""
        with open(BASE_RULES_FILE, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            # Iterate through pages (Limit to first 300 pages if memory issues arise, otherwise read all)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text, "✅ Companies Act, 2013 Loaded Successfully."
    except Exception as e:
        return None, f"❌ Error reading base PDF: {e}"

def extract_text_from_uploaded_pdfs(uploaded_files):
    """
    Extracts text from additional PDFs uploaded by the user (e.g., SEBI Circulars).
    """
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
    """
    Cleans the AI response to extract only valid CSV rows.
    """
    text = text.replace("```csv", "").replace("```", "").strip()
    lines = text.split('\n')
    # Filter for lines that look like CSV data (contain commas)
    clean_lines = [line for line in lines if "," in line]
    return "\n".join(clean_lines)

def generate_compliance_checklist(company_type, base_text, extra_text, api_key):
    """
    Core Agent Logic: Generates the checklist based on Company Type and Laws.
    """
    genai.configure(api_key=api_key)
    # Gemini 1.5 Flash is recommended for its large context window (1M tokens)
    model = genai.GenerativeModel('gemini-1.5-flash') 

    # Combine Base Act + Any Extra User Uploads
    full_knowledge_base = base_text + "\n\n" + extra_text

    prompt = f"""
    ### ROLE
    You are an expert Company Secretary (CS) in India, specializing in the Companies Act, 2013 and SEBI Regulations.
    
    ### USER CONTEXT
    The user represents a **{company_type}** Company.
    
    ### SOURCE OF TRUTH (CONTEXT)
    Use the following text (Companies Act/Rules) as your strict knowledge base:
    {full_knowledge_base[:60000]} 
    
    ### TASK
    Generate a **Yearly Compliance Checklist** specifically for a **{company_type}** Company.
    
    ### STRICT LOGIC (TRIAGE)
    1. **If Private Limited:** - Check for exemptions (e.g., Section 185 loan exemptions, Section 173 meeting notice).
       - Exclude strict public company filings like MGT-14 for certain resolutions.
    2. **If Public (Unlisted):** - Apply strict Companies Act rules (KMP appointment Sec 203, Secretarial Audit Sec 204 if applicable).
    3. **If Listed:** - Apply Companies Act + MENTION SEBI LODR requirements (Quarterly Results, Shareholding Pattern, Intimations).
    
    ### OUTPUT FORMAT
    1. **Executive Summary**: A brief, professional strategy note (bullet points) on the compliance burden for this year.
    2. **The Checklist Table (CSV Only)**:
       - Strictly output a CSV format block.
       - Headers: "Month/Trigger","Form/Activity","Section/Rule","Frequency","Penalty Risk"
       - Do NOT add markdown tables, only CSV text.
    
    Example CSV row:
    "September 30","File AOC-4 (Financials)","Section 137","Yearly","High"
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error calling Gemini: {e}"

# --- 4. MAIN APP UI ---

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("🔑 Gemini API Key", type="password")
    
    st.markdown("---")
    st.header("🏢 Company Profile")
    st.info("Select your company structure to filter the rules:")
    company_type = st.radio(
        "Structure:",
        ["Private Limited", "Public (Unlisted)", "Listed (BSE/NSE)"],
        index=0
    )

# Main Title
st.title("⚖️ AI Company Secretary Agent")
st.markdown(f"### Intelligent Compliance Manager for **{company_type}** Companies")
st.caption("Powered by Google Gemini & RAG (Retrieval Augmented Generation)")
st.divider()

# Load System Knowledge
base_rules_text, status_msg = load_base_rules_text()

# Check System Status
if "✅" in status_msg:
    st.success(status_msg)
else:
    st.error(status_msg)
    st.warning("⚠️ Please ensure 'A2013-18.pdf' is inside the GitHub repository folder.")
    st.stop() # Halt execution if core file is missing

# Layout: Two Columns
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📂 Supplemental Knowledge")
    st.markdown("The **Companies Act 2013** is already loaded.")
    st.markdown("Upload specific docs (e.g., AoA, SEBI Circulars) here if needed:")
    uploaded_files = st.file_uploader("Upload PDFs", type=['pdf'], accept_multiple_files=True)

with col2:
    st.subheader("🚀 Generate Compliance Report")
    st.write(f"Click below to generate a checklist tailored for a **{company_type}** entity.")
    
    if st.button("Generate Yearly Checklist", type="primary"):
        if not api_key:
            st.error("❌ Please enter your Gemini API Key in the sidebar.")
        else:
            with st.spinner("⚖️ Analyzing Company Law & Generating Strategy..."):
                # 1. Prepare Context
                extra_text = extract_text_from_uploaded_pdfs(uploaded_files) if uploaded_files else ""
                
                # 2. Call AI
                result = generate_compliance_checklist(company_type, base_rules_text, extra_text, api_key)
                
                # 3. Process Output
                parts = result.split("Month/Trigger") # Rough split between summary and CSV
                
                # Display Summary
                st.markdown("### 📋 Executive Summary")
                st.markdown(parts[0].replace("```csv", "").replace("```", ""))
                
                # Display CSV & Download
                if len(parts) > 1:
                    csv_raw = "Month/Trigger" + parts[1]
                    clean_csv = clean_csv_output(csv_raw)
                    
                    try:
                        st.markdown("### 📅 Compliance Calendar")
                        df = pd.read_csv(io.StringIO(clean_csv))
                        st.dataframe(df, use_container_width=True)
                        
                        # Download Button
                        csv_bytes = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="💾 Download Checklist (CSV)",
                            data=csv_bytes,
                            file_name=f"Compliance_{company_type.replace(' ','_')}.csv",
                            mime="text/csv"
                        )
                    except Exception as e:
                        st.error("⚠️ AI generated the text, but the CSV format was slightly off.")
                        with st.expander("View Raw Output"):
                            st.code(clean_csv)

# Query Section
st.divider()
st.subheader("💬 Ask a Legal Question")
user_query = st.text_input("e.g., 'What is the penalty for late filing of Annual Return (MGT-7)?' or 'Can we give a loan to a Director?'")

if user_query and api_key:
    if st.button("Consult the Act"):
        genai.configure(api_key=api_key)
        q_model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Add optional text if present
        extra_context = extract_text_from_uploaded_pdfs(uploaded_files) if uploaded_files else ""
        
        q_prompt = f"""
        Act as a strict Company Secretary for a **{company_type}** company.
        Using the Companies Act 2013 (provided below) as your authority:
        {base_rules_text[:50000]}
        {extra_context[:10000]}
        
        Question: "{user_query}"
        
        Answer Requirement:
        1. Cite the specific **Section** or **Rule**.
        2. If {company_type} is Private, mention specific exemptions if applicable.
        3. Be concise and professional.
        """
        
        with st.spinner("Searching the Act..."):
            try:
                answer = q_model.generate_content(q_prompt)
                st.markdown(f"**Answer:** \n{answer.text}")
            except Exception as e:
                st.error(f"Error: {e}")