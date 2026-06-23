# agents/issue_classifier.py

import json
from typing import Dict, Any, List
from agents import get_gemini_client, logger
from prompts.issue_prompt import ISSUE_CLASSIFICATION_SYSTEM_PROMPT, ISSUE_CLASSIFICATION_USER_TEMPLATE

# Defined allowed values as per architectural specifications
VALID_CATEGORIES = {
    "Location issue",
    "Warehouse issue",
    "Courier issue",
    "Website issue",
    "Customer unavailable",
    "Weather issue",
    "Payment issue"
}

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
VALID_SENTIMENTS = {"ANGRY", "FRUSTRATED", "NEUTRAL"}

class ValidationError(Exception):
    """Exception raised for validation errors in the agent's output schema."""
    pass

class IssueClassifierAgent:
    """
    Agent 1: Issue Classification Agent (Production-Grade)
    Analyzes unstructured e-commerce customer complaints to extract structural issue parameters.
    Supports both live Gemini 2.5 Flash execution (structured JSON mode) and offline heuristic models.
    """

    def __init__(self):
        """Initializes the agent, loading Gemini client if credentials exist."""
        self.client = get_gemini_client()
        self.name = "IssueClassifierAgent"

    def run(self, complaint_text: str, ticket_time: str) -> Dict[str, Any]:
        """
        Main entry point for executing classification.
        
        Args:
            complaint_text: The unstructured raw text from the customer complaint.
            ticket_time: The ISO format string representing ticket creation time.
            
        Returns:
            A validated dict matching the classification JSON contract.
        """
        logger.info(f"[{self.name}] Initiating issue classification. Client state: {'Live' if self.client else 'Mock'}")
        
        # Guard clause: Ensure inputs are strings and non-empty
        if not complaint_text or not isinstance(complaint_text, str):
            logger.warning(f"[{self.name}] Empty or invalid complaint_text provided. Defaulting to Courier issue.")
            return self._get_fallback_response("Empty/invalid input complaint.")

        try:
            if self.client:
                result = self._run_live(complaint_text, ticket_time)
            else:
                result = self._run_mock(complaint_text, ticket_time)
            
            # Perform schema validation
            self.validate_output(result)
            return result

        except ValidationError as ve:
            logger.error(f"[{self.name}] Schema validation failed: {ve}. Applying fallback correction.")
            return self._sanitize_and_correct(result if 'result' in locals() else {}, complaint_text)
            
        except Exception as e:
            logger.critical(f"[{self.name}] Unhandled system exception in classification pipeline: {e}")
            return self._get_fallback_response(f"Pipeline error: {str(e)}")

    def _run_live(self, complaint_text: str, ticket_time: str) -> Dict[str, Any]:
        """Runs inference via Google GenAI SDK client with forced JSON formatting."""
        try:
            from google.genai import types
            
            prompt = ISSUE_CLASSIFICATION_USER_TEMPLATE.format(
                ticket_time=ticket_time,
                complaint_text=complaint_text
            )
            
            config = types.GenerateContentConfig(
                system_instruction=ISSUE_CLASSIFICATION_SYSTEM_PROMPT,
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
            logger.info(f"[{self.name}] Successfully retrieved and parsed live Gemini classification.")
            return result
            
        except json.JSONDecodeError as jde:
            logger.error(f"[{self.name}] Failed to parse JSON response from LLM: {jde}. Raw text: {response.text if 'response' in locals() else 'None'}")
            raise ValidationError("LLM response is not a valid JSON structure.")
        except Exception as e:
            logger.error(f"[{self.name}] Gemini live model generation failed: {e}")
            raise RuntimeError(f"Live inference execution failure: {e}")

    def _run_mock(self, complaint_text: str, ticket_time: str) -> Dict[str, Any]:
        """Provides heuristic-based keyword classifier fallback for offline/development environments."""
        logger.info(f"[{self.name}] Processing heuristics over complaint text...")
        
        text_lower = complaint_text.lower()
        
        # Default baseline values
        category = "Courier issue"
        severity = "MEDIUM"
        sentiment = "NEUTRAL"
        urgency_score = 5
        summary = "Standard customer inquiry."

        # Heuristic rules matching requested categories
        if any(w in text_lower for w in ["address", "zip code", "wrong gate", "routing", "apartment", "street number", "wrong location"]):
            category = "Location issue"
            summary = "Customer reported incorrect address marker or delivery location routing issues."
            urgency_score = 6
        elif any(w in text_lower for w in ["damaged", "broken", "shattered", "cracked", "torn", "squashed", "leaking", "missing item", "missing from box"]):
            category = "Warehouse issue"
            summary = "Customer claims item arrived damaged or packaging check failed in warehouse selection."
            urgency_score = 7
            severity = "HIGH"
        elif any(w in text_lower for w in ["checkout", "website", "application", "app", "login", "portal", "tracking status online", "status says", "page error"]):
            category = "Website issue"
            summary = "Customer complaining about digital infrastructure errors or checkout portal issues."
            urgency_score = 4
        elif any(w in text_lower for w in ["not home", "missed delivery", "nobody was there", "unreachable", "attempt failed", "customer unavailable", "gate code needed"]):
            category = "Customer unavailable"
            summary = "Delivery attempt failed due to customer absence or gate access blocks."
            urgency_score = 5
        elif any(w in text_lower for w in ["snow", "blizzard", "storm", "hurricane", "flood", "rain", "cyclone", "weather"]):
            category = "Weather issue"
            summary = "Logistics corridor delayed due to inclement weather conditions."
            urgency_score = 6
        elif any(w in text_lower for w in ["charge", "double bill", "refund pending", "transaction", "cod payment", "payment", "card fail", "gateway"]):
            category = "Payment issue"
            summary = "Customer reports payment billing discrepancy or credit transaction hold."
            urgency_score = 8
            severity = "HIGH"
        elif any(w in text_lower for w in ["late", "delayed", "slow", "tracking", "lost", "never arrived", "stuck", "transit", "delivery boy", "courier"]):
            category = "Courier issue"
            summary = "Customer complaining about courier delivery transit speed or lost tracking status."
            urgency_score = 7

        # Sentiment heuristics
        if any(w in text_lower for w in ["angry", "furious", "terrible", "worst", "unacceptable", "sue", "fraud", "scam"]):
            sentiment = "ANGRY"
            urgency_score = min(urgency_score + 2, 10)
        elif any(w in text_lower for w in ["frustrated", "disappointed", "annoyed", "delay", "please help"]):
            sentiment = "FRUSTRATED"
            urgency_score = min(urgency_score + 1, 10)

        # Severity auto-escalation
        if urgency_score >= 8:
            severity = "HIGH"
        if urgency_score >= 10:
            severity = "CRITICAL"

        return {
            "category": category,
            "severity": severity,
            "sentiment": sentiment,
            "urgency_score": urgency_score,
            "summary": summary
        }

    def validate_output(self, output: Dict[str, Any]) -> None:
        """
        Validates the output payload against data constraints.
        Raises ValidationError if any attributes violate contracts.
        """
        if not isinstance(output, dict):
            raise ValidationError("Output structure is not a dictionary.")
            
        required_keys = {"category", "severity", "sentiment", "urgency_score", "summary"}
        missing_keys = required_keys - output.keys()
        if missing_keys:
            raise ValidationError(f"Missing required schema keys: {missing_keys}")

        if output["category"] not in VALID_CATEGORIES:
            raise ValidationError(f"Invalid category '{output['category']}'. Must be one of {VALID_CATEGORIES}")

        if output["severity"] not in VALID_SEVERITIES:
            raise ValidationError(f"Invalid severity '{output['severity']}'. Must be one of {VALID_SEVERITIES}")

        if output["sentiment"] not in VALID_SENTIMENTS:
            raise ValidationError(f"Invalid sentiment '{output['sentiment']}'. Must be one of {VALID_SENTIMENTS}")

        if not isinstance(output["urgency_score"], (int, float)):
            raise ValidationError("Urgency score must be numeric.")
            
        if not (1 <= output["urgency_score"] <= 10):
            raise ValidationError("Urgency score must be between 1 and 10 inclusive.")

        if not isinstance(output["summary"], str) or not output["summary"].strip():
            raise ValidationError("Summary must be a non-empty string.")

    def _sanitize_and_correct(self, raw_output: Dict[str, Any], complaint_text: str) -> Dict[str, Any]:
        """Corrects minor validation formatting issues dynamically to maintain pipeline continuity."""
        logger.warning(f"[{self.name}] Attempting payload sanitization for: {raw_output}")
        
        # Fallback dictionary initialization
        sanitized = {
            "category": "Courier issue",
            "severity": "MEDIUM",
            "sentiment": "NEUTRAL",
            "urgency_score": 5,
            "summary": "Auto-sanitized shipping complaint summary."
        }

        if not isinstance(raw_output, dict):
            return sanitized

        # Category correction
        cat = raw_output.get("category")
        if cat in VALID_CATEGORIES:
            sanitized["category"] = cat
        else:
            # Map close string variations if applicable
            for valid_cat in VALID_CATEGORIES:
                if str(cat).lower() in valid_cat.lower() or valid_cat.lower() in str(cat).lower():
                    sanitized["category"] = valid_cat
                    break

        # Severity correction
        sev = str(raw_output.get("severity", "")).upper()
        if sev in VALID_SEVERITIES:
            sanitized["severity"] = sev

        # Sentiment correction
        sent = str(raw_output.get("sentiment", "")).upper()
        if sent in VALID_SENTIMENTS:
            sanitized["sentiment"] = sent

        # Urgency correction
        try:
            urgency = int(float(raw_output.get("urgency_score", 5)))
            sanitized["urgency_score"] = max(1, min(urgency, 10))
        except (ValueError, TypeError):
            pass

        # Summary correction
        summary = raw_output.get("summary")
        if isinstance(summary, str) and summary.strip():
            sanitized["summary"] = summary.strip()
        else:
            # Extract basic truncated complaint text
            sanitized["summary"] = (complaint_text[:60] + "...") if len(complaint_text) > 60 else complaint_text

        logger.info(f"[{self.name}] Payload successfully sanitized to: {sanitized}")
        return sanitized

    def _get_fallback_response(self, reason: str) -> Dict[str, Any]:
        """Provides a safe default classification context if execution crashes."""
        return {
            "category": "Courier issue",
            "severity": "LOW",
            "sentiment": "NEUTRAL",
            "urgency_score": 3,
            "summary": f"Default fallback system ticket. Reason: {reason}"
        }

