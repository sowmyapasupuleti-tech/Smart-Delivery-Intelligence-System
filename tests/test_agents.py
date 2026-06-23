# tests/test_agents.py

import pytest
from agents.issue_classifier import IssueClassifierAgent
from agents.root_cause_agent import RootCauseAgent
from agents.delay_prediction_agent import DelayPredictionAgent
from agents.resolution_agent import ResolutionAgent
from agents.communication_agent import CommunicationAgent
from agents.analytics_agent import AnalyticsAgent

def test_issue_classifier_mock():
    agent = IssueClassifierAgent()
    # Test delayed complaint -> Courier issue
    res = agent.run("My package is extremely late! Where is it?", "2026-06-23 12:00:00")
    assert res["category"] == "Courier issue"
    assert "severity" in res
    assert "sentiment" in res
    assert "urgency_score" in res
    assert "summary" in res
    
    # Test damaged complaint -> Warehouse issue
    res2 = agent.run("The glass box inside arrived completely broken and shattered.", "2026-06-23 12:00:00")
    assert res2["category"] == "Warehouse issue"

def test_root_cause_mock():
    agent = RootCauseAgent()
    classification = {"category": "Courier issue", "severity": "HIGH"}
    tracking = [{"location": "Chicago", "activity": "Sorting"}]
    weather = {"condition": "Severe Snowstorm", "severity": "CRITICAL"}
    
    res = agent.run(classification, tracking, weather)
    assert res["root_cause"] == "WEATHER_DISRUPTION"
    assert "confidence_score" in res
    assert "explanation" in res

def test_delay_prediction_mock():
    agent = DelayPredictionAgent()
    res = agent.run(
        issue_type="Courier issue",
        root_cause="WEATHER_DISRUPTION",
        priority="HIGH",
        customer_sentiment="ANGRY"
    )
    assert res["risk_level"] == "High"
    assert res["estimated_delay_days"] > 0
    assert "confidence_score" in res
    assert "explanation" in res

def test_resolution_mock():
    agent = ResolutionAgent()
    classification = {"category": "Warehouse issue", "severity": "HIGH", "summary": "missing pack item"}
    rootcause = {"root_cause": "LOST_IN_TRANSIT"}
    delay = {"predicted_delay_hours": 0}
    
    # High value reship check
    res_high = agent.run(classification, rootcause, delay, 200.00)
    assert res_high["recommended_action"] == "RESHIP_PRIORITY"
    assert len(res_high["recommended_actions"]) >= 3
    assert "priority_order" in res_high
    assert "escalation_required" in res_high
    assert "estimated_resolution_time" in res_high
    
    # Low value refund check
    payment_classification = {"category": "Payment issue", "severity": "HIGH"}
    res_low = agent.run(payment_classification, rootcause, delay, 20.00)
    assert res_low["recommended_action"] == "REFUND"
    assert len(res_low["recommended_actions"]) >= 3

def test_communication_mock():
    agent = CommunicationAgent()
    rootcause = {"root_cause": "WEATHER_DISRUPTION", "explanation": "snow blockage"}
    resolution = {"recommended_action": "RESHIP_PRIORITY", "resolution_cost": 50.0}
    
    res = agent.run("Sarah Connor", "ORD-12345", rootcause, resolution)
    assert "customer_email" in res
    assert "customer_sms" in res
    assert "carrier_escalation_email" in res
    assert "support_executive_message" in res
    assert res["customer_email"]["subject"] is not None
    assert len(res["customer_sms"]) <= 160

def test_analytics_mock():
    agent = AnalyticsAgent()
    history = [
        {
            "route_info": {"carrier": "FedEx"},
            "classification": {"category": "Courier issue"},
            "delay_prediction": {"predicted_delay_hours": 10.0},
            "resolution": {"resolution_cost": 15.0, "sla_breach_risk": True}
        },
        {
            "route_info": {"carrier": "FedEx"},
            "classification": {"category": "Warehouse issue"},
            "delay_prediction": {"predicted_delay_hours": 2.0},
            "resolution": {"resolution_cost": 50.0, "sla_breach_risk": False}
        }
    ]
    
    res = agent.run(history)
    assert res["total_incidents_processed"] == 2
    assert res["average_resolution_cost"] == 32.5
    assert res["sla_compliance_rate"] == 0.5
    assert "FedEx" in res["carrier_performance"]
    assert len(res["most_common_issue_types"]) > 0
    assert res["average_delivery_delay_days"] > 0
    assert res["resolution_success_rate"] == 0.5
    assert isinstance(res["issue_frequencies"], dict)
    assert len(res["business_recommendations"]) > 0
    assert len(res["top_root_causes"]) > 0
    assert "plotly_issues_json" in res
    assert "plotly_carriers_json" in res
