import streamlit as st
from google import genai
from google.genai import types
import json

st.set_page_config(
    page_title="ComplyHub Entity Extractor",
    page_icon="🏢",
    layout="wide"
)

st.markdown("""
<style>
    .entity-card {
        background: #f0f4ff;
        border-left: 4px solid #4f46e5;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .relationship-card {
        background: #f0fdf4;
        border-left: 4px solid #16a34a;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .service-card {
        background: #fff7ed;
        border-left: 4px solid #ea580c;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .individual-card {
        background: #fdf4ff;
        border-left: 4px solid #9333ea;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .summary-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏢 ComplyHub Entity Extractor")
st.markdown(
    "**Advisory-First Onboarding** — Enter client details in plain English. "
    "ComplyHub will automatically extract entities, map relationships and flag compliance services."
)
st.divider()

SYSTEM_PROMPT = """You are a Senior Tax & Compliance Analyst specialising in Australian accounting and financial services.

Extract structured information from plain-English client descriptions provided by accountants or advisors.

Return ONLY valid JSON — no explanation, no preamble, no markdown code fences. Raw JSON only.

Use this exact structure:
{
  "entities": [
    {
      "id": "E1",
      "name": "Full legal entity name",
      "type": "Company | SMSF | Trust | Individual | Corporate Trustee",
      "subtype": "Pty Ltd | Family Trust | Unit Trust | SMSF | Individual",
      "role": "e.g. Operating Company, Corporate Trustee, Fund Member",
      "contact": {
        "email": "if mentioned else null",
        "phone": "if mentioned else null"
      },
      "abn_lookup": "ASIC | ATO | Not Required",
      "data_source": "ASIC | ATO | Xero"
    }
  ],
  "relationships": [
    {
      "from": "Person or entity name",
      "to": "Entity name",
      "relationship": "Director | Trustee | Beneficiary | Member | Shareholder"
    }
  ],
  "compliance_services": [
    {
      "service": "Tax Return | BAS | SMSF Audit | Tax Planning | ASIC Review",
      "entity": "Which entity this applies to",
      "frequency": "Annual | Quarterly | Monthly | One-off",
      "deadline": "31 Oct | 28 Feb | null"
    }
  ],
  "individuals": [
    {
      "name": "Full name",
      "roles": ["Director", "Trustee", "Member"],
      "idv_required": true
    }
  ],
  "summary": "One paragraph plain-English summary of the full client structure"
}

Priority order for entity identification:
1. Companies (Pty Ltd) — find Directors
2. Individuals — find roles across entities
3. Family Trusts — find Trustees and Beneficiaries
4. SMSFs — find Corporate Trustee and Members
5. Unit Trusts — find Unit Holders

Rules:
- Companies -> ABN via ASIC
- SMSFs and Trusts -> ABN via ATO
- Always set idv_required: true for every individual
"""

EXAMPLE_TEXT = (
    "New client — Priya Mehta, runs a wholesale company called Mehta Holdings Pty Ltd, sole director. "
    "Her email is priya@mehta.com.au, mobile 0412 345 678. "
    "She also has an SMSF — Mehta Family Super Fund — with a corporate trustee called Mehta SMSF Pty Ltd. "
    "We're doing tax planning and BAS for the company plus the SMSF audit."
)

if "result" not in st.session_state:
    st.session_state.result = None
if "input_text" not in st.session_state:
    st.session_state.input_text = ""

# ---------------------------------------------------------------------------
# API key — read directly from secrets.toml, never shown in UI
# ---------------------------------------------------------------------------
def get_api_key() -> str:
    return st.secrets["GEMINI_API_KEY"]


with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("**Entity Priority Order:**")
    st.markdown("1. 🏢 Companies (Pty Ltd)")
    st.markdown("2. 👤 Individuals")
    st.markdown("3. 🏦 Family Trusts")
    st.markdown("4. 💼 SMSFs")
    st.markdown("5. 📦 Unit Trusts")

col1, col2 = st.columns([3, 1])
with col1:
    st.subheader("📝 Enter Client Details")
with col2:
    if st.button("📋 Load Example"):
        st.session_state.input_text = EXAMPLE_TEXT
        st.session_state.result = None
        st.rerun()

user_input = st.text_area(
    label="Client description",
    value=st.session_state.input_text,
    height=200,
    placeholder="e.g. New client — Priya Mehta, runs Mehta Holdings Pty Ltd, sole director...",
    label_visibility="collapsed"
)

col_btn1, col_btn2, _ = st.columns([2, 1, 4])
with col_btn1:
    extract_btn = st.button("🔍 Extract Client Structure", type="primary", use_container_width=True)
with col_btn2:
    clear_btn = st.button("🗑️ Clear", use_container_width=True)

if clear_btn:
    st.session_state.result = None
    st.session_state.input_text = ""
    st.rerun()


def call_gemini(text: str, api_key: str) -> dict:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


if extract_btn:
    api_key = get_api_key()
    if not api_key:
        st.error("⚠️ No Gemini API key found. Enter it in the sidebar or configure GEMINI_API_KEY in Streamlit Cloud Secrets.")
    elif not user_input.strip():
        st.warning("⚠️ Please enter client details first.")
    else:
        with st.status("🤖 Gemini is analysing...", expanded=True) as status:
            st.write("📖 Reading text...")
            st.write("🔍 Identifying entities...")
            st.write("🗺️ Mapping relationships...")
            try:
                result = call_gemini(user_input, api_key)
                st.session_state.result = result
                st.write("✅ Extraction complete!")
                status.update(label="✅ Analysis Complete!", state="complete")
            except json.JSONDecodeError as e:
                status.update(label="❌ JSON Parse Error", state="error")
                st.error(f"JSON parse error: {e}")
            except Exception as e:
                status.update(label="❌ Error", state="error")
                st.error(f"Error: {e}")

if st.session_state.result:
    data = st.session_state.result
    st.divider()
    st.subheader("📊 Extraction Results")

    if data.get("summary"):
        st.markdown("### 📋 Summary")
        st.markdown(f'<div class="summary-box">{data["summary"]}</div>', unsafe_allow_html=True)

    st.markdown("---")
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏢 Entities",
        "🔗 Relationships",
        "✅ Compliance Services",
        "👤 Individuals",
        "📄 Raw JSON"
    ])

    with tab1:
        entities = data.get("entities", [])
        st.markdown(f"**{len(entities)} entities found**")
        for e in entities:
            badge_color = {
                "Company": "#4f46e5",
                "SMSF": "#0891b2",
                "Trust": "#16a34a",
                "Individual": "#9333ea",
                "Corporate Trustee": "#b45309"
            }.get(e.get("type", ""), "#6b7280")
            contact_html = ""
            if e.get("contact"):
                if e["contact"].get("email"):
                    contact_html += f"📧 {e['contact']['email']}  "
                if e["contact"].get("phone"):
                    contact_html += f"📱 {e['contact']['phone']}"
            st.markdown(f"""
<div class="entity-card">
    <strong style="font-size:16px">{e.get('name','Unknown')}</strong>
    <span style="background:{badge_color};color:white;border-radius:20px;padding:2px 10px;font-size:12px;margin-left:8px">{e.get('type','')}</span>
    <br><small style="color:#555">🏷️ {e.get('subtype','')} &nbsp;|&nbsp; 🎯 {e.get('role','')}</small>
    <br><small style="color:#555">🔎 ABN: {e.get('abn_lookup','')} &nbsp;|&nbsp; 💾 Source: {e.get('data_source','')}</small>
    {'<br><small style="color:#555">' + contact_html + '</small>' if contact_html else ''}
</div>""", unsafe_allow_html=True)

    with tab2:
        relationships = data.get("relationships", [])
        st.markdown(f"**{len(relationships)} relationships found**")
        for r in relationships:
            st.markdown(f"""
<div class="relationship-card">
    <strong>{r.get('from','')}</strong>
    <span style="color:#16a34a;margin:0 8px">→ {r.get('relationship','')} →</span>
    <strong>{r.get('to','')}</strong>
</div>""", unsafe_allow_html=True)

    with tab3:
        services = data.get("compliance_services", [])
        st.markdown(f"**{len(services)} compliance services flagged**")
        for s in services:
            st.markdown(f"""
<div class="service-card">
    <strong>📌 {s.get('service','')}</strong>
    <br><small style="color:#555">🏢 {s.get('entity','')} &nbsp;|&nbsp; 🔄 {s.get('frequency','')} &nbsp;|&nbsp; 📅 {s.get('deadline','N/A')}</small>
</div>""", unsafe_allow_html=True)

    with tab4:
        individuals = data.get("individuals", [])
        st.markdown(f"**{len(individuals)} individuals found**")
        for i in individuals:
            roles_html = " ".join([
                f'<span style="background:#9333ea;color:white;border-radius:20px;padding:2px 8px;font-size:11px;margin-right:4px">{r}</span>'
                for r in i.get("roles", [])
            ])
            idv = "✅ IDV Required" if i.get("idv_required") else "❌ IDV Not Required"
            st.markdown(f"""
<div class="individual-card">
    <strong>👤 {i.get('name','')}</strong> &nbsp; <small style="color:#9333ea">{idv}</small>
    <br><div style="margin-top:6px">{roles_html}</div>
</div>""", unsafe_allow_html=True)

    with tab5:
        st.json(data)
        st.download_button(
            label="⬇️ Download JSON",
            data=json.dumps(data, indent=2),
            file_name="complyhub_extraction.json",
            mime="application/json"
        )
