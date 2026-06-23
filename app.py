# app.py

import os
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Import agent wrappers
from agents.issue_classifier import IssueClassifierAgent
from agents.root_cause_agent import RootCauseAgent
from agents.delay_prediction_agent import DelayPredictionAgent
from agents.resolution_agent import ResolutionAgent
from agents.communication_agent import CommunicationAgent
from agents.analytics_agent import AnalyticsAgent

# Page configuration
st.set_page_config(
    page_title="Smart Delivery Intelligence System (SDIS)",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium CSS styling injection
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    /* Global font customization */
    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', sans-serif;
    }

    /* Main background and card aesthetics */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: #f1f5f9;
    }
    
    /* Header styling */
    h1, h2, h3 {
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }
    
    .main-title {
        background: linear-gradient(90deg, #38bdf8 0%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    /* Status badge style */
    .status-badge {
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    .status-online {
        background-color: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-mock {
        background-color: rgba(245, 158, 11, 0.2);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }

    /* Glassmorphism containers */
    .glass-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
    }

    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        color: #f8fafc;
        margin-top: 0.5rem;
    }

    .kpi-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Timelines */
    .pipeline-step {
        border-left: 2px solid #6366f1;
        padding-left: 1.5rem;
        position: relative;
        margin-bottom: 1.5rem;
    }
    .pipeline-step::before {
        content: '';
        width: 12px;
        height: 12px;
        background-color: #6366f1;
        border: 2px solid #0f172a;
        border-radius: 50%;
        position: absolute;
        left: -7px;
        top: 4px;
        box-shadow: 0 0 8px #6366f1;
    }
    
    /* Code styling adjustment */
    code {
        color: #f472b6 !important;
        background-color: rgba(30, 41, 59, 0.8) !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to load mock database
@st.cache_data
def load_mock_shipments():
    data_path = os.path.join("data", "mock_shipments.json")
    try:
        with open(data_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback inline if file is missing (failsafe)
        return []

# Initialize Session States
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "historical_resolutions" not in st.session_state:
    # Hydrate with default metrics derived from mock data for visual aesthetic initially
    st.session_state.historical_resolutions = []

# Sidebar configuration
st.sidebar.markdown("<h2 style='margin-bottom: 0px;'>📦 SDIS Control Panel</h2>", unsafe_allow_html=True)

# API Mode Toggle
api_key_input = st.sidebar.text_input(
    "Enter Gemini API Key:",
    value=st.session_state.api_key,
    type="password",
    help="Provided key enables live Gemini 2.5 Flash agents; leave blank for Mock Agent mode."
)

if api_key_input:
    st.session_state.api_key = api_key_input
    os.environ["GEMINI_API_KEY"] = api_key_input
    st.sidebar.markdown('<span class="status-badge status-online">⚡ LIVE GEMINI MODE ONLINE</span>', unsafe_allow_html=True)
else:
    # Clear environment variable if blank
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
    st.sidebar.markdown('<span class="status-badge status-mock">⚡ OFFLINE MOCK MODE ACTIVE</span>', unsafe_allow_html=True)

st.sidebar.markdown("---")

# Load shipments
shipments = load_mock_shipments()

# Select scenario
st.sidebar.markdown("### Select Shipment Incident")
selected_shipment_id = st.sidebar.selectbox(
    "Choose a tracking incident:",
    options=[s["shipment_id"] for s in shipments] + ["Custom Incident"]
)

# Extract details of chosen shipment
current_shipment = None
if selected_shipment_id == "Custom Incident":
    current_shipment = {
        "shipment_id": f"SDIS-CUSTOM-{datetime.now().strftime('%M%S')}",
        "customer_name": "John Doe",
        "order_id": "ORD-CUSTOM",
        "order_value": 99.99,
        "ticket_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "customer_complaint": "",
        "tracking_history": [
            {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "location": "Warehouse", "activity": "Shipment packaged"}
        ],
        "route_info": {
            "origin": "Dallas, TX",
            "destination": "Austin, TX",
            "carrier": "FedEx",
            "distance_miles": 200,
            "historical_speed_mph": 50
        },
        "weather_telemetry": {
            "location": "Austin, TX",
            "condition": "Cloudy",
            "severity": "LOW"
        }
    }
else:
    current_shipment = next(s for s in shipments if s["shipment_id"] == selected_shipment_id)

# Allow customizing inputs in the sidebar
st.sidebar.markdown("### Incident Profile")
customer_name = st.sidebar.text_input("Customer Name", current_shipment["customer_name"])
order_value = st.sidebar.number_input("Order Value ($)", value=current_shipment["order_value"], min_value=0.0, step=10.0)
carrier = st.sidebar.selectbox("Carrier", ["FedEx", "DHL", "BlueDart", "Delhivery"], index=["FedEx", "DHL", "BlueDart", "Delhivery"].index(current_shipment["route_info"]["carrier"]))
weather_cond = st.sidebar.selectbox("Weather Condition", ["Clear and sunny", "Rainy", "Heavy Monsoonal Rain", "Severe Snowstorm and Ice Alerts"], index=["Clear and sunny", "Rainy", "Heavy Monsoonal Rain", "Severe Snowstorm and Ice Alerts"].index(current_shipment["weather_telemetry"]["condition"]) if current_shipment["weather_telemetry"]["condition"] in ["Clear and sunny", "Rainy", "Heavy Monsoonal Rain", "Severe Snowstorm and Ice Alerts"] else 0)

# Map selected weather condition to severity
weather_severity_map = {
    "Clear and sunny": "LOW",
    "Rainy": "MEDIUM",
    "Heavy Monsoonal Rain": "HIGH",
    "Severe Snowstorm and Ice Alerts": "CRITICAL"
}
weather_severity = weather_severity_map[weather_cond]

# Update current shipment state
current_shipment["customer_name"] = customer_name
current_shipment["order_value"] = order_value
current_shipment["route_info"]["carrier"] = carrier
current_shipment["weather_telemetry"]["condition"] = weather_cond
current_shipment["weather_telemetry"]["severity"] = weather_severity

# Core app title
st.markdown('<div class="main-title">Smart Delivery Intelligence System</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Multi-Agent AI Operations Control & Incident Resolution Dashboard</div>', unsafe_allow_html=True)

# Tabs
tab_res, tab_ana, tab_config = st.tabs([
    "🛠️ Resolution Workstation",
    "📊 System Analytics",
    "⚙️ Agent Configurations"
])

# Pre-populate historical resolutions list with mock statistics if empty, to ensure dashboard is beautiful on load
if not st.session_state.historical_resolutions:
    # Populate historical incidents with the base JSON instances pre-processed
    mock_history = []
    
    # Instance 1: Weather delay
    mock_history.append({
        "shipment_id": "SDIS-10029",
        "route_info": {"carrier": "FedEx"},
        "classification": {"category": "Courier issue"},
        "root_cause": {"root_cause": "WEATHER_DISRUPTION"},
        "delay_prediction": {"predicted_delay_hours": 18.5},
        "resolution": {"resolution_cost": 45.0, "sla_breach_risk": False}
    })
    # Instance 2: Damaged cargo
    mock_history.append({
        "shipment_id": "SDIS-20847",
        "route_info": {"carrier": "DHL"},
        "classification": {"category": "Warehouse issue"},
        "root_cause": {"root_cause": "CARRIER_OPERATIONAL"},
        "delay_prediction": {"predicted_delay_hours": 1.0},
        "resolution": {"resolution_cost": 89.99, "sla_breach_risk": False}
    })
    # Instance 3: Theft
    mock_history.append({
        "shipment_id": "SDIS-30911",
        "route_info": {"carrier": "BlueDart"},
        "classification": {"category": "Courier issue"},
        "root_cause": {"root_cause": "LOST_IN_TRANSIT"},
        "delay_prediction": {"predicted_delay_hours": 0.0},
        "resolution": {"resolution_cost": 450.0, "sla_breach_risk": False}
    })
    # Instance 4: Address hold
    mock_history.append({
        "shipment_id": "SDIS-50388",
        "route_info": {"carrier": "Delhivery"},
        "classification": {"category": "Location issue"},
        "root_cause": {"root_cause": "INCORRECT_ADDRESS"},
        "delay_prediction": {"predicted_delay_hours": 12.0},
        "resolution": {"resolution_cost": 15.0, "sla_breach_risk": True}
    })
    
    st.session_state.historical_resolutions = mock_history

# RESOLUTION WORKSTATION TAB
with tab_res:
    col_input, col_process = st.columns([1, 2])
    
    with col_input:
        st.markdown("### Incident Context & Telemetry")
        
        # Display selected ticket
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown(f"**Shipment ID:** `{current_shipment['shipment_id']}`")
        st.markdown(f"**Order ID:** `{current_shipment['order_id']}`  |  **Value:** `${current_shipment['order_value']}`")
        st.markdown(f"**Customer:** {current_shipment['customer_name']}")
        st.markdown(f"**Carrier:** {current_shipment['route_info']['carrier']}")
        
        # Edit/View Customer Complaint
        complaint_input = st.text_area(
            "Customer Complaint Details:",
            value=current_shipment["customer_complaint"] if selected_shipment_id != "Custom Incident" else "",
            placeholder="Type customer's delivery issue complaint here...",
            height=130
        )
        current_shipment["customer_complaint"] = complaint_input
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Telemetry Metadata
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("##### Route Telemetry")
        st.markdown(f"🛣️ **Transit Corridor:** {current_shipment['route_info']['origin']} ➡️ {current_shipment['route_info']['destination']}")
        st.markdown(f"📏 **Distance:** {current_shipment['route_info']['distance_miles']} miles")
        st.markdown(f"🌥️ **Corridor Weather:** {current_shipment['weather_telemetry']['condition']} (`{current_shipment['weather_telemetry']['severity']}`)")
        
        # Expandable Tracking Log
        with st.expander("🔍 View Transit Scan History", expanded=False):
            for t in current_shipment["tracking_history"]:
                st.markdown(f"⏱️ `{t['timestamp']}`\n*{t['location']}* - {t['activity']}")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Trigger Multi-Agent Pipeline
        trigger_btn = st.button("🚀 Run Multi-Agent SDIS Pipeline", use_container_width=True, type="primary")

    with col_process:
        st.markdown("### Orchestrated Pipeline Execution")
        
        if not trigger_btn:
            st.info("👈 Fill in incident telemetry details and click 'Run Multi-Agent SDIS Pipeline' to execute classification and resolution recommendation.")
            
            # Show a mock/preview block of the pipeline architecture
            st.markdown("""
            <div class="glass-card" style="text-align: center; border-style: dashed; opacity: 0.7;">
                <p style="margin-bottom: 5px; font-weight: 600;">System Pipeline Sequence Preview</p>
                <code style="display: block; margin: 10px 0; padding: 10px; border-radius: 8px;">
                Customer Complaint -> Classifier Agent -> Root Cause Agent -> Delay Predictor -> Resolution Agent -> Comms Agent
                </code>
                <span style="font-size: 0.8rem; color: #94a3b8;">When triggered, each agent runs sequentially. The output of the preceding agent acts as input to the next.</span>
            </div>
            """, unsafe_allow_html=True)
            
        else:
            if not current_shipment["customer_complaint"]:
                st.warning("Please enter a customer complaint text before triggering the pipeline.")
            else:
                st.write("Initializing agents...")
                
                # Instantiate agents
                classifier_agent = IssueClassifierAgent()
                rootcause_agent = RootCauseAgent()
                delay_agent = DelayPredictionAgent()
                res_agent = ResolutionAgent()
                comms_agent = CommunicationAgent()
                
                # Execution with loading animations
                with st.spinner("Executing Pipeline Sequence..."):
                    
                    # Step 1: Issue Classification
                    st.markdown('<div class="pipeline-step">', unsafe_allow_html=True)
                    st.markdown("##### Step 1: Issue Classification Agent")
                    classification_output = classifier_agent.run(
                        current_shipment["customer_complaint"],
                        current_shipment["ticket_time"]
                    )
                    st.json(classification_output)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Step 2: Root Cause Diagnostics
                    st.markdown('<div class="pipeline-step">', unsafe_allow_html=True)
                    st.markdown("##### Step 2: Root Cause Analysis Agent")
                    rootcause_output = rootcause_agent.run(
                        classification_output,
                        current_shipment["tracking_history"],
                        current_shipment["weather_telemetry"]
                    )
                    st.json(rootcause_output)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Step 3: Delay Prediction
                    st.markdown('<div class="pipeline-step">', unsafe_allow_html=True)
                    st.markdown("##### Step 3: Delay Prediction Agent")
                    delay_output = delay_agent.run(
                        issue_type=classification_output["category"],
                        root_cause=rootcause_output["root_cause"],
                        priority=classification_output["severity"],
                        customer_sentiment=classification_output["sentiment"]
                    )
                    st.json(delay_output)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Step 4: Resolution SOP Recommendation
                    st.markdown('<div class="pipeline-step">', unsafe_allow_html=True)
                    st.markdown("##### Step 4: Resolution strategist Agent")
                    resolution_output = res_agent.run(
                        classification_output,
                        rootcause_output,
                        delay_output,
                        current_shipment["order_value"]
                    )
                    st.json(resolution_output)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Step 5: Communications Drafting
                    st.markdown('<div class="pipeline-step">', unsafe_allow_html=True)
                    st.markdown("##### Step 5: Customer & Carrier Communication Agent")
                    comms_output = comms_agent.run(
                        current_shipment["customer_name"],
                        current_shipment["order_id"],
                        rootcause_output,
                        resolution_output
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                # Save resolution results back to session state analytics data
                completed_incident = {
                    "shipment_id": current_shipment["shipment_id"],
                    "route_info": current_shipment["route_info"],
                    "classification": classification_output,
                    "root_cause": rootcause_output,
                    "delay_prediction": delay_output,
                    "resolution": resolution_output
                }
                
                # Check for duplicate IDs in history before appending
                st.session_state.historical_resolutions = [
                    x for x in st.session_state.historical_resolutions 
                    if x["shipment_id"] != current_shipment["shipment_id"]
                ]
                st.session_state.historical_resolutions.append(completed_incident)
                
                # Display Results Workstation Layout
                st.markdown("### 🏆 Resolution Summary & Correspondence drafts")
                
                col_res_details, col_res_comms = st.columns([1, 1])
                
                with col_res_details:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.markdown("##### Actionable Decision Metrics")
                    action_color = "#34d399" if resolution_output["recommended_action"] != "REFUND" else "#f87171"
                    st.markdown(f"**Recommended Action:** <span style='color:{action_color}; font-size:1.2rem; font-weight:600;'>{resolution_output['recommended_action']}</span>", unsafe_allow_html=True)
                    st.markdown(f"**Estimated cost to resolve:** `${resolution_output['resolution_cost']}`")
                    st.markdown(f"**SLA Breach Risk:** `{'YES' if resolution_output['sla_breach_risk'] else 'NO'}`")
                    st.markdown(f"**SOP Logic Justification:** *{resolution_output['action_justification']}*")
                    st.markdown(f"**Alternative Option:** `{resolution_output['alternative_action']}`")
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                with col_res_comms:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.markdown("##### Correspondence Drafting Outputs")
                    
                    comm_tabs = st.tabs(["📧 Customer Email", "💬 Customer SMS", "🚛 Carrier Escalation"])
                    
                    with comm_tabs[0]:
                        st.markdown(f"**Subject:** {comms_output['customer_email']['subject']}")
                        st.text_area("Body:", value=comms_output['customer_email']['body'], height=200, key="cust_email_body_ta")
                        
                    with comm_tabs[1]:
                        st.text_input("SMS draft text:", value=comms_output['customer_sms'], key="cust_sms_ta")
                        char_cnt = len(comms_output['customer_sms'])
                        st.markdown(f"<span style='font-size:0.8rem; color:#94a3b8;'>Characters: {char_cnt} (SMS length limits: 160 max)</span>", unsafe_allow_html=True)
                        
                    with comm_tabs[2]:
                        st.markdown(f"**Send To:** `{comms_output['carrier_escalation_email']['recipient']}`")
                        st.markdown(f"**Subject:** {comms_output['carrier_escalation_email']['subject']}")
                        st.text_area("Body:", value=comms_output['carrier_escalation_email']['body'], height=150, key="carr_email_body_ta")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    st.success("Incident Processed Successfully! Metrics updated in the Analytics Dashboard.")

# SYSTEM ANALYTICS TAB
with tab_ana:
    st.markdown("### System SLA Performance & Cost Analytics")
    
    # Process history using AnalyticsAgent
    anal_agent = AnalyticsAgent()
    analytics_results = anal_agent.run(st.session_state.historical_resolutions)
    
    # Dashboard KPI Cards
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    
    with col_kpi1:
        st.markdown(f"""
        <div class="glass-card">
            <div class="kpi-label">Tickets Processed</div>
            <div class="kpi-value">{analytics_results['total_incidents_processed']}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_kpi2:
        sla_pct = int(analytics_results['sla_compliance_rate'] * 100)
        sla_color = "#34d399" if sla_pct >= 85 else "#fbbf24"
        st.markdown(f"""
        <div class="glass-card">
            <div class="kpi-label">SLA Compliance Rate</div>
            <div class="kpi-value" style="color: {sla_color};">{sla_pct}%</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_kpi3:
        st.markdown(f"""
        <div class="glass-card">
            <div class="kpi-label">Avg Cost to Resolve</div>
            <div class="kpi-value">${analytics_results['average_resolution_cost']:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col_kpi4:
        st.markdown(f"""
        <div class="glass-card">
            <div class="kpi-label">Active Warnings</div>
            <div class="kpi-value" style="color: #f87171;">{len([x for x in st.session_state.historical_resolutions if x['resolution'].get('sla_breach_risk')]):d}</div>
        </div>
        """, unsafe_allow_html=True)
        
    # Visual Analytics Plots
    col_plot1, col_plot2 = st.columns([1, 1])
    
    with col_plot1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("##### Issue Category Distribution")
        dist_data = analytics_results.get("issue_distribution", {})
        if dist_data:
            fig_pie = px.pie(
                names=list(dist_data.keys()),
                values=list(dist_data.values()),
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.Blues
            )
            fig_pie.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f1f5f9'),
                margin=dict(t=10, b=10, l=10, r=10),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No data distribution available.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_plot2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("##### Carrier Performance (SLA Compliance Rates)")
        carrier_data = analytics_results.get("carrier_performance", {})
        if carrier_data:
            carriers = list(carrier_data.keys())
            sla_rates = [v["sla_rate"] * 100 for v in carrier_data.values()]
            avg_delays = [v["avg_delay_hours"] for v in carrier_data.values()]
            
            fig_bar = go.Figure(data=[
                go.Bar(name='SLA Compliance %', x=carriers, y=sla_rates, marker_color='#6366f1'),
                go.Bar(name='Avg Delay Hours', x=carriers, y=avg_delays, marker_color='#fbbf24')
            ])
            fig_bar.update_layout(
                barmode='group',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f1f5f9'),
                margin=dict(t=20, b=10, l=10, r=10),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(gridcolor='rgba(255,255,255,0.05)')
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No carrier performance logs to plot.")
        st.markdown('</div>', unsafe_allow_html=True)

    # Historical Incidents Log
    st.markdown("### Incident Logging Database")
    if st.session_state.historical_resolutions:
        table_rows = []
        for inc in st.session_state.historical_resolutions:
            table_rows.append({
                "Shipment ID": inc["shipment_id"],
                "Carrier": inc["route_info"]["carrier"],
                "Category": inc["classification"]["category"],
                "Severity": inc["classification"]["severity"],
                "Root Cause": inc["root_cause"]["root_cause"],
                "Est. Delay": f"{inc['delay_prediction']['predicted_delay_hours']} hrs",
                "Action Taken": inc["resolution"]["recommended_action"],
                "Cost to Resolve": f"${inc['resolution']['resolution_cost']:.2f}",
                "SLA Compliance": "❌ Breached" if inc["resolution"]["sla_breach_risk"] else "✅ Compliant"
            })
        df_history = pd.DataFrame(table_rows)
        st.dataframe(df_history, use_container_width=True, hide_index=True)
    else:
        st.info("Incidents database is currently empty.")

# AGENT CONFIGURATIONS TAB
with tab_config:
    st.markdown("### System Prompt Templates & Agent Directives")
    
    st.markdown("""
    The SDIS system externalizes prompt specifications to enable operational flexibility and prompt engineering modifications.
    Below are the system prompt specifications compiled for LLM ingestion:
    """)
    
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        with st.expander("📄 View Classification Agent Prompt Template", expanded=False):
            from prompts.issue_prompt import ISSUE_CLASSIFICATION_SYSTEM_PROMPT
            st.code(ISSUE_CLASSIFICATION_SYSTEM_PROMPT)
            
        with st.expander("📄 View Root Cause forensic Prompt Template", expanded=False):
            from prompts.rootcause_prompt import ROOT_CAUSE_SYSTEM_PROMPT
            st.code(ROOT_CAUSE_SYSTEM_PROMPT)
            
    with col_c2:
        with st.expander("📄 View Resolution Strategist Prompt Template", expanded=False):
            from prompts.resolution_prompt import RESOLUTION_SYSTEM_PROMPT
            st.code(RESOLUTION_SYSTEM_PROMPT)
            
        with st.expander("📄 View Communication Agent Prompt Template", expanded=False):
            from prompts.communication_prompt import COMMUNICATION_SYSTEM_PROMPT
            st.code(COMMUNICATION_SYSTEM_PROMPT)
            
    st.markdown("### Multi-Agent Memory & Shared Execution State Design")
    st.markdown("""
    The agents share status records during execution utilizing a centralized mutable execution context.
    The timeline sequence operates recursively in downstream pipelines:
    """)
    st.code("""
# Pipeline State Execution Context Structure
context = {
    "shipment_id": "SDIS-10029",
    "customer_complaint": "complaint text...",
    "route_info": { ... },
    "weather_telemetry": { ... },
    "classification": { "category": "Courier issue", "severity": "CRITICAL", ... },
    "root_cause": { "root_cause": "WEATHER_DISRUPTION", ... },
    "delay_prediction": { "predicted_delay_hours": 18.5, ... },
    "resolution": { "recommended_action": "RESHIP_PRIORITY", ... },
    "communication": { "customer_email": { ... }, "customer_sms": "..." }
}
    """, language="python")
