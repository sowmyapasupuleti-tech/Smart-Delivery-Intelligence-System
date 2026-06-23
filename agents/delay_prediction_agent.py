# agents/delay_prediction_agent.py

import json
from typing import Dict, Any, Set
from agents import get_gemini_client, logger

VALID_RISK_LEVELS: Set[str] = {"Low", "Medium", "High"}

class ValidationError(Exception):
    """Exception raised for validation errors in the agent's output schema."""
    pass

class DelayPredictionAgent:
    """
    Agent 3: Delay Prediction Agent (Production-Grade)
    Estimates the likelihood and duration of delivery delays based on issue classification and root cause diagnostics.
    """

    def __init__(self):
        """Initializes the agent, loading Gemini client if credentials exist."""
        self.client = get_gemini_client()
        self.name = "DelayPredictionAgent"

    def run(self, issue_type: str, root_cause: str, priority: str, customer_sentiment: str) -> Dict[str, Any]:
        """
        Main entry point for executing delay predictions.

        Args:
            issue_type: Category from issue classification (e.g., Courier issue).
            root_cause: Diagnosed cause of bottleneck (e.g., WEATHER_DISRUPTION).
            priority: Severity of the incident (e.g., HIGH).
            customer_sentiment: Sentiment of the customer (e.g., ANGRY).

        Returns:
            A validated dict matching the delay prediction JSON contract:
            {
                "risk_level": "Low" | "Medium" | "High",
                "estimated_delay_days": float,
                "confidence_score": float,
                "explanation": str,
                # Backward-compatibility key:
                "predicted_delay_hours": float
            }
        """
        logger.info(f"[{self.name}] Running delay prediction. Client state: {'Live' if self.client else 'Mock'}")

        # Input validation and sanitization
        issue_type = str(issue_type or "Courier issue").strip()
        root_cause = str(root_cause or "CARRIER_OPERATIONAL").strip()
        priority = str(priority or "MEDIUM").strip().upper()
        customer_sentiment = str(customer_sentiment or "NEUTRAL").strip().upper()

        try:
            if self.client:
                result = self._run_live(issue_type, root_cause, priority, customer_sentiment)
            else:
                result = self._run_mock(issue_type, root_cause, priority, customer_sentiment)

            # Perform schema validation
            self.validate_output(result)
            return result

        except ValidationError as ve:
            logger.error(f"[{self.name}] Schema validation failed: {ve}. Applying fallback correction.")
            return self._sanitize_and_correct(result if 'result' in locals() else {}, issue_type, root_cause, priority, customer_sentiment)

        except Exception as e:
            logger.critical(f"[{self.name}] Unhandled system exception in prediction pipeline: {e}")
            return self._get_fallback_response(f"Pipeline error: {str(e)}")

    def _run_live(self, issue_type: str, root_cause: str, priority: str, customer_sentiment: str) -> Dict[str, Any]:
        """Runs predictions via Gemini 2.5 Flash with structured output instructions."""
        try:
            from google.genai import types

            prompt = f"""
            Predict logistics delivery delay metrics based on these inputs:
            - Issue Type: {issue_type}
            - Root Cause Diagnostics: {root_cause}
            - Incident Priority: {priority}
            - Customer Sentiment: {customer_sentiment}
            
            Determine:
            1. risk_level: Must be exactly one of: "Low", "Medium", "High".
            2. estimated_delay_days: Float value representing expected delay duration in days.
            3. confidence_score: Float value between 0.0 and 1.0 indicating prediction confidence.
            4. explanation: Detailed description explaining how inputs led to this estimation.

            You MUST respond strictly in the following JSON format:
            {{
              "risk_level": "Low" | "Medium" | "High",
              "estimated_delay_days": 1.5,
              "confidence_score": 0.85,
              "explanation": "Explanation details here."
            }}
            """

            config = types.GenerateContentConfig(
                system_instruction="You are a logistics delay prediction system. Respond strictly with valid JSON conforming to the requested schema.",
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
            
            # Map backward compatibility keys
            if "estimated_delay_days" in result:
                result["predicted_delay_hours"] = round(float(result["estimated_delay_days"]) * 24.0, 1)

            logger.info(f"[{self.name}] Successfully predicted delay metrics via Gemini API.")
            return result

        except json.JSONDecodeError as jde:
            logger.error(f"[{self.name}] Failed to parse JSON response from LLM: {jde}. Raw text: {response.text if 'response' in locals() else 'None'}")
            raise ValidationError("LLM response is not a valid JSON structure.")
        except Exception as e:
            logger.error(f"[{self.name}] Gemini live model generation failed: {e}")
            raise RuntimeError(f"Live inference execution failure: {e}")

    def _run_mock(self, issue_type: str, root_cause: str, priority: str, customer_sentiment: str) -> Dict[str, Any]:
        """Provides rule-based delay prediction calculations (Mock Mode)."""
        logger.info(f"[{self.name}] Evaluating prediction rules over operational metrics...")

        # Base default mappings by Root Cause
        base_delays = {
            "WEATHER_DISRUPTION": {"days": 3.0, "risk": "High", "confidence": 0.90},
            "CUSTOMS_HOLD": {"days": 5.0, "risk": "High", "confidence": 0.85},
            "LOST_IN_TRANSIT": {"days": 6.0, "risk": "High", "confidence": 0.80},
            "INCORRECT_ADDRESS": {"days": 2.0, "risk": "Medium", "confidence": 0.85},
            "CARRIER_OPERATIONAL": {"days": 1.5, "risk": "Medium", "confidence": 0.80}
        }

        # Retrieve base values or use carrier operational default
        metrics = base_delays.get(root_cause, {"days": 1.5, "risk": "Medium", "confidence": 0.75})
        
        delay_days = metrics["days"]
        risk_level = metrics["risk"]
        confidence_score = metrics["confidence"]

        # 1. Adjust for Issue Type categories
        if issue_type == "Website issue" or issue_type == "Payment issue":
            # Digital errors solve faster
            delay_days = min(delay_days, 1.0)
            risk_level = "Low"
        elif issue_type == "Customer unavailable":
            # Missed attempt adds typical dispatch cycle duration
            delay_days = max(delay_days, 1.5)
            risk_level = "Medium"

        # 2. Adjust for Priority Severity levels
        if priority == "CRITICAL":
            # Priority processing accelerates handling schedules
            delay_days = max(0.5, delay_days - 0.5)
            confidence_score = min(1.0, confidence_score + 0.05)
        elif priority == "LOW":
            # Low urgency queue processing increases backlog risk
            delay_days += 1.0
            risk_level = "High" if risk_level == "Medium" else risk_level

        # 3. Adjust for Customer Sentiment
        if customer_sentiment == "ANGRY" and risk_level == "Medium":
            # Escalate risk indicators due to customer escalation risk
            risk_level = "High"

        # Generate detailed explanation string
        explanation = (
            f"Predicted {delay_days:.1f} days delay under {risk_level} risk indicators. "
            f"Root cause diagnosed as {root_cause} (Confidence: {confidence_score:.2f}). "
            f"Priority class {priority} is factoring into expedited shipping schedules."
        )

        return {
            "risk_level": risk_level,
            "estimated_delay_days": float(round(delay_days, 1)),
            "confidence_score": float(round(confidence_score, 2)),
            "explanation": explanation,
            "predicted_delay_hours": float(round(delay_days * 24.0, 1))
        }

    def validate_output(self, output: Dict[str, Any]) -> None:
        """
        Validates output schema against strict constraints.
        Raises ValidationError if fields are missing or invalid.
        """
        if not isinstance(output, dict):
            raise ValidationError("Output structure is not a dictionary.")

        required_keys = {"risk_level", "estimated_delay_days", "confidence_score", "explanation"}
        missing_keys = required_keys - output.keys()
        if missing_keys:
            raise ValidationError(f"Missing required schema keys: {missing_keys}")

        if output["risk_level"] not in VALID_RISK_LEVELS:
            raise ValidationError(f"Invalid risk_level '{output['risk_level']}'. Must be one of {VALID_RISK_LEVELS}")

        if not isinstance(output["estimated_delay_days"], (int, float)):
            raise ValidationError("estimated_delay_days must be numeric.")

        if output["estimated_delay_days"] < 0:
            raise ValidationError("estimated_delay_days cannot be negative.")

        if not isinstance(output["confidence_score"], (int, float)):
            raise ValidationError("confidence_score must be numeric.")

        if not (0.0 <= output["confidence_score"] <= 1.0):
            raise ValidationError("confidence_score must be between 0.0 and 1.0 inclusive.")

        if not isinstance(output["explanation"], str) or not output["explanation"].strip():
            raise ValidationError("explanation must be a non-empty string.")

    def _sanitize_and_correct(self, raw_output: Dict[str, Any], issue_type: str, root_cause: str, priority: str, customer_sentiment: str) -> Dict[str, Any]:
        """Dynamically corrects minor schema violations to prevent pipeline failures."""
        logger.warning(f"[{self.name}] Sanitizing output payload: {raw_output}")

        sanitized = {
            "risk_level": "Medium",
            "estimated_delay_days": 2.0,
            "confidence_score": 0.80,
            "explanation": "Auto-corrected fallback predictions.",
            "predicted_delay_hours": 48.0
        }

        if not isinstance(raw_output, dict):
            return sanitized

        # risk_level correction
        risk = str(raw_output.get("risk_level", "")).capitalize().strip()
        if risk in VALID_RISK_LEVELS:
            sanitized["risk_level"] = risk

        # estimated_delay_days correction
        try:
            days = float(raw_output.get("estimated_delay_days", 2.0))
            sanitized["estimated_delay_days"] = float(round(max(0.0, days), 1))
        except (ValueError, TypeError):
            pass

        # confidence_score correction
        try:
            score = float(raw_output.get("confidence_score", 0.80))
            sanitized["confidence_score"] = float(round(max(0.0, min(score, 1.0)), 2))
        except (ValueError, TypeError):
            pass

        # explanation correction
        exp = raw_output.get("explanation")
        if isinstance(exp, str) and exp.strip():
            sanitized["explanation"] = exp.strip()
        else:
            fallback_mock = self._run_mock(issue_type, root_cause, priority, customer_sentiment)
            sanitized["explanation"] = fallback_mock["explanation"]

        # Backwards compatibility calculation
        sanitized["predicted_delay_hours"] = float(round(sanitized["estimated_delay_days"] * 24.0, 1))

        logger.info(f"[{self.name}] Payload successfully sanitized to: {sanitized}")
        return sanitized

    def _get_fallback_response(self, reason: str) -> Dict[str, Any]:
        """Provides a safe default prediction payload if execution crashes."""
        return {
            "risk_level": "Medium",
            "estimated_delay_days": 2.5,
            "confidence_score": 0.50,
            "explanation": f"Default fallback predictions. Reason: {reason}",
            "predicted_delay_hours": 60.0
        }

