# agents/resolution_agent.py

import json
from typing import Dict, Any, List, Set
from agents import get_gemini_client, logger
from prompts.resolution_prompt import RESOLUTION_SYSTEM_PROMPT, RESOLUTION_USER_TEMPLATE

VALID_ACTIONS: Set[str] = {
    "REFUND",
    "RESHIP_PRIORITY",
    "REROUTE",
    "COMPENSATION_VOUCHER",
    "CARRIER_ESCALATION"
}

class ValidationError(Exception):
    """Exception raised for validation errors in the agent's output schema."""
    pass

class ResolutionAgent:
    """
    Agent 4: Resolution Recommendation Agent (Production-Grade)
    Maps diagnostics outputs to business Standard Operating Procedures (SOPs) to recommend resolution actions,
    priority sequence, escalation requirements, and timeframes.
    """

    def __init__(self):
        """Initializes the agent, loading Gemini client if credentials exist."""
        self.client = get_gemini_client()
        self.name = "ResolutionAgent"

    def run(self, issue_classification: Dict[str, Any], root_cause: Dict[str, Any], delay_prediction: Dict[str, Any], order_value: float) -> Dict[str, Any]:
        """
        Main entry point for executing resolution recommendation.

        Args:
            issue_classification: Classification dictionary containing category and severity.
            root_cause: Root cause diagnostics dictionary.
            delay_prediction: Prediction dictionary containing delay metrics.
            order_value: The financial price of the customer's order.

        Returns:
            A validated dict matching the resolution JSON contract:
            {
                "recommended_actions": List[str],
                "priority_order": List[int],
                "escalation_required": bool,
                "estimated_resolution_time": str,
                # Legacies keys for backwards-compatibility:
                "recommended_action": str,
                "action_justification": str,
                "resolution_cost": float,
                "sla_breach_risk": bool,
                "alternative_action": str
            }
        """
        logger.info(f"[{self.name}] Recommended resolution scheduling. Client state: {'Live' if self.client else 'Mock'}")

        # Input sanity checks
        if not issue_classification or not isinstance(issue_classification, dict):
            issue_classification = {"category": "Courier issue", "severity": "MEDIUM"}
        if not root_cause or not isinstance(root_cause, dict):
            root_cause = {"root_cause": "CARRIER_OPERATIONAL", "explanation": "Transit hold"}
        if not delay_prediction or not isinstance(delay_prediction, dict):
            delay_prediction = {"estimated_delay_days": 2.0, "predicted_delay_hours": 48.0}

        try:
            if self.client:
                result = self._run_live(issue_classification, root_cause, delay_prediction, order_value)
            else:
                result = self._run_mock(issue_classification, root_cause, delay_prediction, order_value)

            # Perform schema validation
            self.validate_output(result)
            return result

        except ValidationError as ve:
            logger.error(f"[{self.name}] Schema validation failed: {ve}. Applying fallback correction.")
            return self._sanitize_and_correct(result if 'result' in locals() else {}, issue_classification, root_cause, delay_prediction, order_value)

        except Exception as e:
            logger.critical(f"[{self.name}] Unhandled system exception in resolution pipeline: {e}")
            return self._get_fallback_response(f"Pipeline error: {str(e)}", order_value)

    def _run_live(self, issue_classification: Dict[str, Any], root_cause: Dict[str, Any], delay_prediction: Dict[str, Any], order_value: float) -> Dict[str, Any]:
        """Runs strategist inference via Gemini 2.5 Flash."""
        try:
            from google.genai import types

            prompt = RESOLUTION_USER_TEMPLATE.format(
                issue_json=json.dumps(issue_classification, indent=2),
                rootcause_json=json.dumps(root_cause, indent=2),
                delay_json=json.dumps(delay_prediction, indent=2),
                order_value=order_value
            )

            config = types.GenerateContentConfig(
                system_instruction=RESOLUTION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.1
            )

            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config
            )

            if not response.text:
                raise ValueError("Received empty text response from Gemini API.")

            result = json.loads(response.text.strip())
            logger.info(f"[{self.name}] Successfully formulated resolution actions via live Gemini.")
            return result

        except json.JSONDecodeError as jde:
            logger.error(f"[{self.name}] Failed to parse JSON response from LLM: {jde}. Raw text: {response.text if 'response' in locals() else 'None'}")
            raise ValidationError("LLM response is not a valid JSON structure.")
        except Exception as e:
            logger.error(f"[{self.name}] Gemini live model generation failed: {e}")
            raise RuntimeError(f"Live inference execution failure: {e}")

    def _run_mock(self, issue_classification: Dict[str, Any], root_cause: Dict[str, Any], delay_prediction: Dict[str, Any], order_value: float) -> Dict[str, Any]:
        """Provides rule-based resolution recommendations mapping to SOP guidelines."""
        logger.info(f"[{self.name}] Evaluating business rule SOP mapper (Mock Mode)")

        category = issue_classification.get("category", "Courier issue")
        severity = issue_classification.get("severity", "MEDIUM")
        rc_type = root_cause.get("root_cause", "CARRIER_OPERATIONAL")
        delay_days = delay_prediction.get("estimated_delay_days", 2.0)

        # Standard baseline values
        recommended_actions = ["COMPENSATION_VOUCHER", "CARRIER_ESCALATION", "REROUTE"]
        priority_order = [1, 2, 3]
        escalation_required = False
        resolution_time = "24-48 hours"
        cost = 10.00
        sla_risk = False
        justification = "Standard compensation for transit delay inconveniences."

        if category in ["Courier issue", "Weather issue"]:
            if delay_days > 2.0:
                if order_value > 150.0:
                    recommended_actions = ["RESHIP_PRIORITY", "CARRIER_ESCALATION", "COMPENSATION_VOUCHER"]
                    justification = f"High-value order (${order_value}) delayed over 48 hours ({delay_days} days). Dispatching priority express replacement shipment."
                    cost = 45.00
                    escalation_required = True
                    resolution_time = "12-24 hours"
                else:
                    recommended_actions = ["REROUTE", "COMPENSATION_VOUCHER", "CARRIER_ESCALATION"]
                    justification = f"Standard value order delayed over 48 hours. Rerouting cargo to bypass the weather or sorting corridor backlog."
                    cost = 15.00
                    sla_risk = True
                    resolution_time = "24-48 hours"
            else:
                recommended_actions = ["COMPENSATION_VOUCHER", "CARRIER_ESCALATION", "REROUTE"]
                justification = f"Minor delay predicted ({delay_days} days). Issuing compensatory store credit for inconvenience."
                cost = 10.00
                resolution_time = "2-4 hours"

        elif category == "Warehouse issue":
            # Packaging error or broken contents
            if "missing" in issue_classification.get("summary", "").lower():
                recommended_actions = ["RESHIP_PRIORITY", "COMPENSATION_VOUCHER", "CARRIER_ESCALATION"]
                justification = "Fulfillment selection check error. Dispatching replacement content free of charge."
                cost = order_value
                resolution_time = "24 hours"
            else:
                recommended_actions = ["RESHIP_PRIORITY", "REFUND", "COMPENSATION_VOUCHER"]
                justification = "Content reported damaged or broken in warehouse corridor. Issuing priority reshipment with supervisor audit checks."
                cost = order_value + 10.00
                resolution_time = "12-24 hours"

        elif category == "Location issue":
            recommended_actions = ["REROUTE", "CARRIER_ESCALATION", "COMPENSATION_VOUCHER"]
            justification = "Address metadata invalid in transit files. Rerouting shipment to verified customer coordinates."
            cost = 15.00
            sla_risk = True
            resolution_time = "24-48 hours"

        elif category == "Customer unavailable":
            recommended_actions = ["RESHIP_PRIORITY", "CARRIER_ESCALATION", "COMPENSATION_VOUCHER"]
            justification = "Recipient not present at delivery attempt. Scheduling prioritized express re-attempt window."
            cost = 5.00
            sla_risk = True
            resolution_time = "24 hours"

        elif category == "Website issue":
            recommended_actions = ["COMPENSATION_VOUCHER", "CARRIER_ESCALATION", "REROUTE"]
            justification = "Checkout catalog sync or status tracking bug reported. Crediting store coupon compensation."
            cost = 15.00
            resolution_time = "1-2 hours"

        elif category == "Payment issue":
            recommended_actions = ["REFUND", "COMPENSATION_VOUCHER", "CARRIER_ESCALATION"]
            justification = "Transaction invoice mismatch or payment gateway audit hold. Refund processing completed."
            cost = order_value
            resolution_time = "4-12 hours"

        return {
            "recommended_actions": recommended_actions,
            "priority_order": priority_order,
            "escalation_required": escalation_required,
            "estimated_resolution_time": resolution_time,
            "recommended_action": recommended_actions[0],
            "action_justification": justification,
            "resolution_cost": float(round(cost, 2)),
            "sla_breach_risk": sla_risk,
            "alternative_action": recommended_actions[1]
        }

    def validate_output(self, output: Dict[str, Any]) -> None:
        """
        Validates output schema against strict constraints.
        Raises ValidationError if fields are missing or invalid.
        """
        if not isinstance(output, dict):
            raise ValidationError("Output structure is not a dictionary.")

        # Core required keys
        required_keys = {"recommended_actions", "priority_order", "escalation_required", "estimated_resolution_time"}
        missing_keys = required_keys - output.keys()
        if missing_keys:
            raise ValidationError(f"Missing required schema keys: {missing_keys}")

        actions = output["recommended_actions"]
        if not isinstance(actions, list) or len(actions) < 3:
            raise ValidationError("recommended_actions must be a list containing at least 3 actions.")

        for action in actions:
            if not isinstance(action, str) or action.upper().strip() not in VALID_ACTIONS:
                raise ValidationError(f"Invalid recommended action '{action}'. Must be one of {VALID_ACTIONS}")

        priority = output["priority_order"]
        if not isinstance(priority, list) or len(priority) < 3:
            raise ValidationError("priority_order must be a list containing at least 3 priority ranks.")

        if not isinstance(output["escalation_required"], bool):
            raise ValidationError("escalation_required must be a boolean.")

        if not isinstance(output["estimated_resolution_time"], str) or not output["estimated_resolution_time"].strip():
            raise ValidationError("estimated_resolution_time must be a non-empty string.")

        # Legacy backward-compatibility validation
        legacy_keys = {"recommended_action", "action_justification", "resolution_cost", "sla_breach_risk", "alternative_action"}
        missing_legacy = legacy_keys - output.keys()
        if missing_legacy:
            raise ValidationError(f"Missing backwards compatibility legacy keys: {missing_legacy}")

    def _sanitize_and_correct(self, raw_output: Dict[str, Any], issue_classification: Dict[str, Any], root_cause: Dict[str, Any], delay_prediction: Dict[str, Any], order_value: float) -> Dict[str, Any]:
        """Dynamically corrects minor schema violations to prevent pipeline failures."""
        logger.warning(f"[{self.name}] Sanitizing output payload: {raw_output}")

        # Fallback values
        sanitized = {
            "recommended_actions": ["COMPENSATION_VOUCHER", "CARRIER_ESCALATION", "REROUTE"],
            "priority_order": [1, 2, 3],
            "escalation_required": False,
            "estimated_resolution_time": "24 hours",
            "recommended_action": "COMPENSATION_VOUCHER",
            "action_justification": "Standard baseline resolution mapping.",
            "resolution_cost": 10.00,
            "sla_breach_risk": False,
            "alternative_action": "CARRIER_ESCALATION"
        }

        if not isinstance(raw_output, dict):
            return sanitized

        # recommended_actions correction
        actions = raw_output.get("recommended_actions")
        if isinstance(actions, list):
            valid_list = []
            for item in actions:
                if isinstance(item, str):
                    item_upper = item.upper().strip()
                    if item_upper in VALID_ACTIONS:
                        valid_list.append(item_upper)
            
            # Pad list to reach size of 3
            if len(valid_list) < 3:
                for choice in ["COMPENSATION_VOUCHER", "CARRIER_ESCALATION", "REROUTE"]:
                    if choice not in valid_list:
                        valid_list.append(choice)
                    if len(valid_list) == 3:
                        break
            sanitized["recommended_actions"] = valid_list
        elif "recommended_action" in raw_output:
            primary = str(raw_output.get("recommended_action")).upper().strip()
            alternative = str(raw_output.get("alternative_action", "CARRIER_ESCALATION")).upper().strip()
            
            # Map old keys directly into actions list
            valid_list = [
                primary if primary in VALID_ACTIONS else "COMPENSATION_VOUCHER",
                alternative if alternative in VALID_ACTIONS else "CARRIER_ESCALATION",
                "REROUTE"
            ]
            sanitized["recommended_actions"] = valid_list

        # priority_order correction
        p_order = raw_output.get("priority_order")
        if isinstance(p_order, list) and len(p_order) >= 3:
            sanitized["priority_order"] = p_order[:len(sanitized["recommended_actions"])]
        else:
            sanitized["priority_order"] = list(range(1, len(sanitized["recommended_actions"]) + 1))

        # escalation_required correction
        if isinstance(raw_output.get("escalation_required"), bool):
            sanitized["escalation_required"] = raw_output["escalation_required"]

        # estimated_resolution_time correction
        est_time = raw_output.get("estimated_resolution_time")
        if isinstance(est_time, str) and est_time.strip():
            sanitized["estimated_resolution_time"] = est_time.strip()

        # Legacy keys correction
        sanitized["recommended_action"] = sanitized["recommended_actions"][0]
        sanitized["alternative_action"] = sanitized["recommended_actions"][1]

        just = raw_output.get("action_justification")
        if isinstance(just, str) and just.strip():
            sanitized["action_justification"] = just.strip()

        try:
            cost = float(raw_output.get("resolution_cost", 10.00))
            sanitized["resolution_cost"] = float(round(max(0.0, cost), 2))
        except (ValueError, TypeError):
            pass

        if isinstance(raw_output.get("sla_breach_risk"), bool):
            sanitized["sla_breach_risk"] = raw_output["sla_breach_risk"]

        logger.info(f"[{self.name}] Payload successfully sanitized to: {sanitized}")
        return sanitized

    def _get_fallback_response(self, reason: str, order_value: float) -> Dict[str, Any]:
        """Provides a safe default prediction payload if execution crashes."""
        return {
            "recommended_actions": ["COMPENSATION_VOUCHER", "CARRIER_ESCALATION", "REROUTE"],
            "priority_order": [1, 2, 3],
            "escalation_required": False,
            "estimated_resolution_time": "24-48 hours",
            "recommended_action": "COMPENSATION_VOUCHER",
            "action_justification": f"Default fallback due to exception check. Reason: {reason}",
            "resolution_cost": 15.00,
            "sla_breach_risk": True,
            "alternative_action": "CARRIER_ESCALATION"
        }

