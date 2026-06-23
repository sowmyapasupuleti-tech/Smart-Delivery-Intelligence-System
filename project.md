# Smart Delivery Intelligence System (SDIS) - System Architecture

This document provides a production-grade architectural specification for the Smart Delivery Intelligence System (SDIS), designed to orchestrate agentic resolutions for logistics disruptions in e-commerce workflows.

---

## 1. System Overview

SDIS is a multi-agent system built to classify delivery complaints, diagnose transit failures, predict delays, recommend cost-effective SOP actions, draft communications, and summarize analytics.

```
+---------------------------------------------------------------------------------+
|                               SDIS Application                                  |
|                                                                                 |
|  +--------------------------+                      +-------------------------+  |
|  |     Streamlit UI         |                      |    Analytical DB        |  |
|  |  (Incident Workstation & |                      |    (mock_shipments)     |  |
|  |   Operations Dashboard)  |                      |                         |  |
|  +------------+-------------+                      +------------+------------+  |
|               |                                                 ^               |
|               v                                                 |               |
|  +------------+-------------------------------------------------+------------+  |
|  |                   Orchestration Engine (Pipeline context)                  |  |
|  |                                                                            |  |
|  |  [IssueClassifier] -> [RootCause] -> [DelayPrediction] -> [Resolution]     |  |
|  |                                                                 |          |  |
|  |                                                                 v          |  |
|  |                                                          [Communication]   |  |
|  +-------------------------------------+--------------------------------------+  |
|                                        |                                        |
|                                        v                                        |
|                          +-------------+-------------+                          |
|                          |     Google GenAI client   |                          |
|                          |    (Gemini 2.5 Flash API) |                          |
|                          +---------------------------+                          |
+---------------------------------------------------------------------------------+
```

---

## 2. Multi-Agent Pipeline Specifications

### A. Core Agent Roles

1.  **Issue Classification Agent**
    *   *Purpose*: Natural language understanding of unstructured complaint tickets.
    *   *Prompt Location*: `prompts/issue_prompt.py`
    *   *Implementation*: `agents/issue_classifier.py`
2.  **Root Cause Analysis Agent**
    *   *Purpose*: Log analysis and multi-source correlation (telemetry, weather, routing events).
    *   *Prompt Location*: `prompts/rootcause_prompt.py`
    *   *Implementation*: `agents/root_cause_agent.py`
3.  **Delay Prediction Agent**
    *   *Purpose*: Analytics for delay forecasting.
    *   *Implementation*: `agents/delay_prediction_agent.py`
4.  **Resolution Recommendation Agent**
    *   *Purpose*: Financial evaluation and SOP compliance.
    *   *Prompt Location*: `prompts/resolution_prompt.py`
    *   *Implementation*: `agents/resolution_agent.py`
5.  **Customer & Carrier Communication Agent**
    *   *Purpose*: Drafting personalized notifications.
    *   *Prompt Location*: `prompts/communication_prompt.py`
    *   *Implementation*: `agents/communication_agent.py`
6.  **Analytics Agent**
    *   *Purpose*: Dashboard statistics compilation.
    *   *Implementation*: `agents/analytics_agent.py`

### B. Shared Context Contract
The pipeline passes a mutable dictionary context downstream:
```json
{
  "shipment_id": "SDIS-10029",
  "customer_name": "Sarah Connor",
  "order_id": "ORD-99081",
  "order_value": 249.99,
  "ticket_time": "2026-06-23 08:30:00",
  "customer_complaint": "complaint text...",
  "tracking_history": [...],
  "route_info": {...},
  "weather_telemetry": {...},
  "classification": {
    "category": "DELAYED",
    "severity": "CRITICAL",
    "sentiment": "FRUSTRATED",
    "urgency_score": 8,
    "summary": "Control board delivery delayed at Chicago."
  },
  "root_cause": {
    "root_cause_type": "WEATHER_DISRUPTION",
    "responsible_party": "EXTERNAL_FORCE",
    "confidence_score": 0.95,
    "technical_details": "Chicago Blizzard halted ground logistics.",
    "carrier_notes": "Corridor closed; hold transit."
  },
  "delay_prediction": {
    "predicted_delay_hours": 18.5,
    "adjusted_eta": "2026-06-24 12:00:00",
    "delay_probability": 0.90,
    "risk_factors": ["Storm front", "Hub congestion"]
  },
  "resolution": {
    "recommended_action": "RESHIP_PRIORITY",
    "action_justification": "High value delayed over 48h.",
    "resolution_cost": 45.00,
    "sla_breach_risk": false,
    "alternative_action": "REFUND"
  },
  "communication": {
    "customer_email": {
      "subject": "Update on your order...",
      "body": "Dear Sarah..."
    },
    "customer_sms": "Hi Sarah...",
    "carrier_escalation_email": {
      "recipient": "support@fedex.com",
      "subject": "Urgent SLA...",
      "body": "Carrier Support..."
    }
  }
}
```

---

## 3. Reliability and Fallback Modes

To support offline, demo-friendly configurations, each agent class checks for the presence of a `GEMINI_API_KEY` environmental variable:
- **Live Mode**: Utilizes the Google GenAI SDK `google-genai` to invoke `gemini-2.5-flash` with a JSON-mode configuration forcing structure conformity.
- **Mock Mode**: Implements high-fidelity rule-based heuristic calculations to mimic logical agent outputs instantly, enabling full application operations without API quotas or latency overheads.
