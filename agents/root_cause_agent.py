# agents/root_cause_agent.py

import json
from typing import Dict, Any, Set
from agents import get_gemini_client, logger
from prompts.rootcause_prompt import ROOT_CAUSE_SYSTEM_PROMPT, ROOT_CAUSE_USER_TEMPLATE

# Defined allowed values as per specifications
VALID_ROOT_CAUSES: Set[str] = {
    "WEATHER_DISRUPTION",
    "CUSTOMS_HOLD",
    "CARRIER_OPERATIONAL",
    "INCORRECT_ADDRESS",
    "LOST_IN_TRANSIT"
}

class ValidationError(Exception):
    """Exception raised for validation errors in the agent's output schema."""
    pass

class RootCauseAgent:
    """
    Agent 2: Root Cause Analysis Agent (Production-Grade)
    Correlates tracking history scan logs, local weather conditions, and issue classifications
    to identify the root cause of shipment failure, diagnostics confidence, and details.
    """

    def __init__(self):
        """Initializes the agent, loading Gemini client if credentials exist."""
        self.client = get_gemini_client()
        self.name = "RootCauseAgent"

    def run(self, issue_classification: Dict[str, Any], tracking_history: list, weather_telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for executing root cause diagnostics.

        Args:
            issue_classification: Structured dict from Agent 1 (category, severity, sentiment).
            tracking_history: List of scanning logs containing timestamps and activities.
            weather_telemetry: Current local conditions at bottleneck location.

        Returns:
            A validated dict matching the root cause JSON contract:
            {
                "root_cause": str,
                "confidence_score": float,
                "explanation": str
            }
        """
        logger.info(f"[{self.name}] Initiating root-cause forensic correlation. Client state: {'Live' if self.client else 'Mock'}")

        # Guard clause: Verify input sanity
        if not issue_classification or not isinstance(issue_classification, dict):
            logger.warning(f"[{self.name}] Invalid issue_classification provided. Running fallback.")
            return self._get_fallback_response("Invalid classification input.")

        try:
            if self.client:
                result = self._run_live(issue_classification, tracking_history, weather_telemetry)
            else:
                result = self._run_mock(issue_classification, tracking_history, weather_telemetry)

            # Perform schema validation
            self.validate_output(result)
            return result

        except ValidationError as ve:
            logger.error(f"[{self.name}] Schema validation failed: {ve}. Applying fallback correction.")
            return self._sanitize_and_correct(result if 'result' in locals() else {}, issue_classification, tracking_history, weather_telemetry)

        except Exception as e:
            logger.critical(f"[{self.name}] Unhandled system exception in diagnostics pipeline: {e}")
            return self._get_fallback_response(f"Pipeline error: {str(e)}")

    def _run_live(self, issue_classification: Dict[str, Any], tracking_history: list, weather_telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Runs diagnostics via Gemini 2.5 Flash with structured output instructions."""
        try:
            from google.genai import types

            prompt = ROOT_CAUSE_USER_TEMPLATE.format(
                issue_json=json.dumps(issue_classification, indent=2),
                tracking_logs=json.dumps(tracking_history, indent=2),
                weather_conditions=json.dumps(weather_telemetry, indent=2)
            )

            config = types.GenerateContentConfig(
                system_instruction=ROOT_CAUSE_SYSTEM_PROMPT,
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
            logger.info(f"[{self.name}] Successfully diagnosed root cause via Gemini API.")
            return result

        except json.JSONDecodeError as jde:
            logger.error(f"[{self.name}] Failed to parse JSON response from LLM: {jde}. Raw text: {response.text if 'response' in locals() else 'None'}")
            raise ValidationError("LLM response is not a valid JSON structure.")
        except Exception as e:
            logger.error(f"[{self.name}] Gemini live model generation failed: {e}")
            raise RuntimeError(f"Live inference execution failure: {e}")

    def _run_mock(self, issue_classification: Dict[str, Any], tracking_history: list, weather_telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Provides heuristic-based forensics parser fallback for offline/development environments."""
        logger.info(f"[{self.name}] Evaluating heuristics over telemetry variables...")

        category = issue_classification.get("category", "Courier issue")
        weather_cond = weather_telemetry.get("condition", "").lower()
        
        # Check weather conditions first (cross-cutting concern)
        is_bad_weather = any(w in weather_cond for w in ["storm", "snow", "heavy rain", "blizzard", "cyclone", "flood"])

        # Defaults
        root_cause = "CARRIER_OPERATIONAL"
        confidence_score = 0.80
        explanation = "Shipment routing delayed due to standard sorting queue backlogs at transit hubs."

        if category == "Weather issue" or (category == "Courier issue" and is_bad_weather):
            root_cause = "WEATHER_DISRUPTION"
            confidence_score = 0.95
            explanation = (
                f"Transit corridor disrupted by severe weather conditions ({weather_telemetry.get('condition', 'inclement weather')}). "
                f"Ground logistics routes at {weather_telemetry.get('location', 'transit hub')} reported temporary speed limitations "
                f"and flight delays."
            )
        elif category == "Location issue":
            root_cause = "INCORRECT_ADDRESS"
            confidence_score = 0.88
            explanation = (
                "The delivery courier flagged the shipping address metadata as invalid or incomplete (e.g., missing street number "
                "or incorrect ZIP code). Cargo held at final hub coordinates awaiting customer confirmation."
            )
        elif category == "Customer unavailable":
            root_cause = "CARRIER_OPERATIONAL"
            confidence_score = 0.90
            explanation = (
                "Carrier delivery logs indicate a delivery attempt was made, but the recipient was unavailable or the "
                "courier could not gain entry due to secure gate restrictions."
            )
        elif category == "Website issue":
            root_cause = "CARRIER_OPERATIONAL"
            confidence_score = 0.85
            explanation = (
                "System integration log sync error. Database sync latency delayed generating pick lists and packing slips "
                "at the regional warehouse."
            )
        elif category == "Payment issue":
            root_cause = "CARRIER_OPERATIONAL"
            confidence_score = 0.92
            explanation = (
                "Financial authorization hold. The order transaction remains unconfirmed in billing databases, forcing "
                "fulfillment holds to prevent credit loss risk."
            )
        elif category == "Warehouse issue":
            root_cause = "CARRIER_OPERATIONAL"
            confidence_score = 0.85
            explanation = (
                "Warehouse packing slip inspection failed. Content damage occurred during package handling or picking, "
                "or item mismatch forced a manual hold for audit check overrides."
            )
        elif category == "Courier issue":
            history_str = str(tracking_history).lower()
            if "customs" in history_str or "clearance" in history_str:
                root_cause = "CUSTOMS_HOLD"
                confidence_score = 0.94
                explanation = (
                    "International custom clearance check hold. The shipment is placed on hold at border controls "
                    "awaiting tariff validation and invoice updates."
                )
            elif "delivered" in history_str:
                root_cause = "LOST_IN_TRANSIT"
                confidence_score = 0.75
                explanation = (
                    "Tracking indicates successful scan at target address, but customer claims package is missing. "
                    "Forensic profile implies package misdelivery or package theft (porch piracy)."
                )
            else:
                root_cause = "LOST_IN_TRANSIT"
                confidence_score = 0.90
                explanation = (
                    "Logs check shows the shipment has not received physical scan status updates for over 5 business days. "
                    "Package lost inside carrier routing terminal."
                )

        return {
            "root_cause": root_cause,
            "confidence_score": confidence_score,
            "explanation": explanation
        }

    def validate_output(self, output: Dict[str, Any]) -> None:
        """
        Validates the output payload against data constraints.
        Raises ValidationError if any attributes violate contracts.
        """
        if not isinstance(output, dict):
            raise ValidationError("Output structure is not a dictionary.")

        required_keys = {"root_cause", "confidence_score", "explanation"}
        missing_keys = required_keys - output.keys()
        if missing_keys:
            raise ValidationError(f"Missing required schema keys: {missing_keys}")

        if output["root_cause"] not in VALID_ROOT_CAUSES:
            raise ValidationError(f"Invalid root_cause '{output['root_cause']}'. Must be one of {VALID_ROOT_CAUSES}")

        if not isinstance(output["confidence_score"], (int, float)):
            raise ValidationError("confidence_score must be numeric.")

        if not (0.0 <= output["confidence_score"] <= 1.0):
            raise ValidationError("confidence_score must be between 0.0 and 1.0 inclusive.")

        if not isinstance(output["explanation"], str) or not output["explanation"].strip():
            raise ValidationError("explanation must be a non-empty string.")

    def _sanitize_and_correct(self, raw_output: Dict[str, Any], issue_classification: Dict[str, Any], tracking_history: list, weather_telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """Corrects schema violations dynamically to maintain pipeline continuity."""
        logger.warning(f"[{self.name}] Sanitizing output payload: {raw_output}")

        sanitized = {
            "root_cause": "CARRIER_OPERATIONAL",
            "confidence_score": 0.70,
            "explanation": "Auto-corrected diagnostics fallback."
        }

        if not isinstance(raw_output, dict):
            return sanitized

        # root_cause correction
        rc = raw_output.get("root_cause")
        # Handle simple casing deviations
        if isinstance(rc, str):
            rc_upper = rc.upper().strip()
            if rc_upper in VALID_ROOT_CAUSES:
                sanitized["root_cause"] = rc_upper
            # Look for sub-string matches
            else:
                for valid_rc in VALID_ROOT_CAUSES:
                    if rc_upper in valid_rc or valid_rc in rc_upper:
                        sanitized["root_cause"] = valid_rc
                        break
        # If root_cause_type (the old schema key) is present, map it
        elif "root_cause_type" in raw_output:
            rc_old = str(raw_output.get("root_cause_type")).upper().strip()
            if rc_old in VALID_ROOT_CAUSES:
                sanitized["root_cause"] = rc_old

        # confidence_score correction
        try:
            score = float(raw_output.get("confidence_score", 0.70))
            sanitized["confidence_score"] = max(0.0, min(score, 1.0))
        except (ValueError, TypeError):
            pass

        # explanation correction
        exp = raw_output.get("explanation")
        if not exp and "technical_details" in raw_output:
            # Fallback to old schema key
            exp = raw_output.get("technical_details")

        if isinstance(exp, str) and exp.strip():
            sanitized["explanation"] = exp.strip()
        else:
            # Build explanation fallback based on mock
            fallback_mock = self._run_mock(issue_classification, tracking_history, weather_telemetry)
            sanitized["explanation"] = fallback_mock["explanation"]

        logger.info(f"[{self.name}] Payload successfully sanitized to: {sanitized}")
        return sanitized

    def _get_fallback_response(self, reason: str) -> Dict[str, Any]:
        """Provides a safe default diagnostics record if execution crashes."""
        return {
            "root_cause": "CARRIER_OPERATIONAL",
            "confidence_score": 0.50,
            "explanation": f"Default fallback diagnostics. Reason: {reason}"
        }

