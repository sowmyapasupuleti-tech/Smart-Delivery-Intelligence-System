# agents/communication_agent.py

import json
from typing import Dict, Any
from agents import get_gemini_client, logger
from prompts.communication_prompt import COMMUNICATION_SYSTEM_PROMPT, COMMUNICATION_USER_TEMPLATE

class ValidationError(Exception):
    """Exception raised for validation errors in the agent's output schema."""
    pass

class CommunicationAgent:
    """
    Agent 5: Customer & Carrier Communication Agent (Production-Grade)
    Drafts tailored customer notification messages (Email + SMS) and support rep guidelines
    in an empathetic, professional, and clear tone. Supports multiple categories.
    """

    def __init__(self):
        """Initializes the agent, loading Gemini client if credentials exist."""
        self.client = get_gemini_client()
        self.name = "CommunicationAgent"

    def run(self, customer_name: str, order_id: str, root_cause: Dict[str, Any], resolution: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for executing communication drafting.

        Args:
            customer_name: The target customer's name.
            order_id: The e-commerce order identification string.
            root_cause: Diagnostics output dictionary from Agent 2.
            resolution: Strategy recommendations from Agent 4.

        Returns:
            A validated dict matching the communication JSON contract:
            {
                "customer_email": {
                    "subject": str,
                    "body": str
                },
                "customer_sms": str,
                "support_executive_message": str,
                # Legacy key for backward-compatibility:
                "carrier_escalation_email": {
                    "recipient": str,
                    "subject": str,
                    "body": str
                }
            }
        """
        logger.info(f"[{self.name}] Drafting customized notification messages. Client state: {'Live' if self.client else 'Mock'}")

        # Input validation
        customer_name = str(customer_name or "Valued Customer").strip()
        order_id = str(order_id or "ORD-UNKNOWN").strip()
        if not root_cause or not isinstance(root_cause, dict):
            root_cause = {"root_cause": "CARRIER_OPERATIONAL", "explanation": "logistics hold"}
        if not resolution or not isinstance(resolution, dict):
            resolution = {"recommended_action": "COMPENSATION_VOUCHER", "resolution_cost": 10.00}

        try:
            if self.client:
                result = self._run_live(customer_name, order_id, root_cause, resolution)
            else:
                result = self._run_mock(customer_name, order_id, root_cause, resolution)

            # Perform schema validation
            self.validate_output(result)
            return result

        except ValidationError as ve:
            logger.error(f"[{self.name}] Schema validation failed: {ve}. Applying fallback correction.")
            return self._sanitize_and_correct(result if 'result' in locals() else {}, customer_name, order_id, root_cause, resolution)

        except Exception as e:
            logger.critical(f"[{self.name}] Unhandled system exception in communication pipeline: {e}")
            return self._get_fallback_response(f"Pipeline error: {str(e)}", customer_name, order_id)

    def _run_live(self, customer_name: str, order_id: str, root_cause: Dict[str, Any], resolution: Dict[str, Any]) -> Dict[str, Any]:
        """Runs drafting via Gemini 2.5 Flash."""
        try:
            from google.genai import types

            prompt = COMMUNICATION_USER_TEMPLATE.format(
                customer_name=customer_name,
                order_id=order_id,
                rootcause_json=json.dumps(root_cause, indent=2),
                resolution_json=json.dumps(resolution, indent=2)
            )

            config = types.GenerateContentConfig(
                system_instruction=COMMUNICATION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.3
            )

            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config
            )

            if not response.text:
                raise ValueError("Received empty response from Gemini API.")

            result = json.loads(response.text.strip())
            logger.info(f"[{self.name}] Successfully drafted communications via live Gemini.")
            return result

        except json.JSONDecodeError as jde:
            logger.error(f"[{self.name}] Failed to parse JSON response from LLM: {jde}. Raw text: {response.text if 'response' in locals() else 'None'}")
            raise ValidationError("LLM response is not a valid JSON structure.")
        except Exception as e:
            logger.error(f"[{self.name}] Gemini live model generation failed: {e}")
            raise RuntimeError(f"Live inference execution failure: {e}")

    def _run_mock(self, customer_name: str, order_id: str, root_cause: Dict[str, Any], resolution: Dict[str, Any]) -> Dict[str, Any]:
        """Provides category-specific template drafting rules (Mock Mode) maintaining empathetic tone."""
        logger.info(f"[{self.name}] Running template draft engines (Mock Mode)")

        action = resolution.get("recommended_action", "COMPENSATION_VOUCHER")
        rc_type = root_cause.get("root_cause", "CARRIER_OPERATIONAL")
        explanation = root_cause.get("explanation", "logistics backlog")
        cost = resolution.get("resolution_cost", 0.0)

        # Mapping action descriptions for customer emails
        action_mapping = {
            "RESHIP_PRIORITY": "expediting a priority replacement package free of charge",
            "REROUTE": "rerouting your package to bypass transit corridors experiencing delays",
            "COMPENSATION_VOUCHER": "applying a compensatory store credit voucher to your profile balance",
            "REFUND": f"processing a full refund of ${cost} back to your payment account"
        }
        action_text = action_mapping.get(action, "processing a priority support escalation ticket")

        # Map actions to executive directives
        exec_directives = {
            "RESHIP_PRIORITY": f"Initiate priority replacement dispatch. Update warehouse item queues and attach complimentary delivery checks.",
            "REROUTE": "Contact logistics supervisor to override shipment routing maps. Coordinate package tag re-labeling.",
            "COMPENSATION_VOUCHER": "Issue store credit code. Confirm credit balances update in customer profile directories.",
            "REFUND": f"Trigger billing gateway refund transaction in ERP billing systems for sum of ${cost}."
        }
        exec_action_guide = exec_directives.get(action, "Monitor ticket status closely.")

        # Category-specific template definitions (supports multiple categories)
        if rc_type == "WEATHER_DISRUPTION":
            reason = "severe weather delays disrupting ground and flight transport lines"
            sms_text = f"Hi {customer_name}, order #{order_id} is delayed due to weather safety holds. We are resolving this by {action_text}."
            exec_guide = f"Empathize with weather disruptions. Confirm corridor clearance status. SOP directive: {exec_action_guide}"
        elif rc_type == "CUSTOMS_HOLD":
            reason = "international import customs clearance audit checks at border terminals"
            sms_text = f"Hi {customer_name}, order #{order_id} is undergoing customs verification. We are resolving this by {action_text}."
            exec_guide = f"Acknowledge customs verification latency. Request commercial invoice checks from trade logs. SOP directive: {exec_action_guide}"
        elif rc_type == "INCORRECT_ADDRESS":
            reason = "an undeliverable shipping address marker in carrier files"
            sms_text = f"Hi {customer_name}, address issues detected for order #{order_id}. Please check street number details."
            exec_guide = f"Ask customer for apartment number/street spellings. Verify ZIP zone mapping. SOP directive: {exec_action_guide}"
        elif rc_type == "LOST_IN_TRANSIT":
            reason = "a transit handling discrepancy reported by our delivery courier"
            sms_text = f"Hi {customer_name}, shipment discrepancy reported for order #{order_id}. We are resolving this by {action_text}."
            exec_guide = f"Lost package escalation triggered. Initiate cargo terminal search with carrier support teams. SOP directive: {exec_action_guide}"
        else: # CARRIER_OPERATIONAL
            reason = "standard routing congestions and carrier sorting backlogs"
            sms_text = f"Hi {customer_name}, order #{order_id} transit delay confirmed. We are resolving this by {action_text}."
            exec_guide = f"Apologize for operational cargo sorting backlog. Give client express tracking code updates. SOP directive: {exec_action_guide}"

        # Truncate SMS to 160 character limits safely
        if len(sms_text) > 160:
            sms_text = sms_text[:157] + "..."

        # Email templates
        email_subject = f"Logistics updates regarding your order #{order_id}"
        email_body = (
            f"Dear {customer_name},\n\n"
            f"We are writing to update you on a shipping delay with your package. "
            f"Our logs indicate that transit timelines were impacted due to {reason}.\n\n"
            f"We understand your package is critical, and we sincerely apologize for the inconvenience this causes. "
            f"To resolve this, we are {action_text}.\n\n"
            f"If you have further questions or need immediate support, please reply directly to this email.\n\n"
            f"Warm regards,\n"
            f"Customer Operations Team"
        )

        # Support Executive Script
        executive_message = (
            f"[INTERNAL AGENT NOTE]\n"
            f"Customer Tone context: Empathetic & transparent. "
            f"Incident Category: {rc_type} diagnostics. "
            f"Explanation details: {explanation}.\n\n"
            f"Operational Checklist for Representative:\n"
            f"- {exec_guide}\n"
            f"- Verify customer name is {customer_name} before modifying records."
        )

        # Carrier Escalation Email (Backwards-compatibility legacy mapping)
        carrier_subj = f"URGENT: Logistics SLA Hold Escalation - Order #{order_id}"
        carrier_body = (
            f"Logistics Carrier Support,\n\n"
            f"Formal SLA service hold escalation initiated for Order #{order_id}.\n"
            f"Incident diagnostics report: {rc_type} (Forensic details: {explanation}).\n"
            f"Recommended dispatch action taken: {action}.\n\n"
            f"SLA terms demand immediate package scan update checks.\n\n"
            f"Regards,\n"
            f"Logistics operations controller"
        )

        return {
            "customer_email": {
                "subject": email_subject,
                "body": email_body
            },
            "customer_sms": sms_text,
            "support_executive_message": executive_message,
            "carrier_escalation_email": {
                "recipient": "logistics-escalations@carrier.com",
                "subject": carrier_subj,
                "body": carrier_body
            }
        }

    def validate_output(self, output: Dict[str, Any]) -> None:
        """
        Validates output schema against strict constraints.
        Raises ValidationError if fields are missing or invalid.
        """
        if not isinstance(output, dict):
            raise ValidationError("Output structure is not a dictionary.")

        # Required fields
        required_keys = {"customer_email", "customer_sms", "support_executive_message"}
        missing_keys = required_keys - output.keys()
        if missing_keys:
            raise ValidationError(f"Missing required schema keys: {missing_keys}")

        email = output["customer_email"]
        if not isinstance(email, dict) or "subject" not in email or "body" not in email:
            raise ValidationError("customer_email must be a dictionary containing 'subject' and 'body'.")

        if not isinstance(email["subject"], str) or not email["subject"].strip():
            raise ValidationError("Customer email subject must be a non-empty string.")

        if not isinstance(email["body"], str) or not email["body"].strip():
            raise ValidationError("Customer email body must be a non-empty string.")

        if not isinstance(output["customer_sms"], str) or not output["customer_sms"].strip():
            raise ValidationError("customer_sms must be a non-empty string.")

        if len(output["customer_sms"]) > 160:
            raise ValidationError("customer_sms exceeds standard length limits of 160 characters.")

        if not isinstance(output["support_executive_message"], str) or not output["support_executive_message"].strip():
            raise ValidationError("support_executive_message must be a non-empty string.")

        # Legacy backward-compatibility validation check
        if "carrier_escalation_email" not in output:
            raise ValidationError("Missing legacy key 'carrier_escalation_email' required for backward compatibility.")

    def _sanitize_and_correct(self, raw_output: Dict[str, Any], customer_name: str, order_id: str, root_cause: Dict[str, Any], resolution: Dict[str, Any]) -> Dict[str, Any]:
        """Dynamically corrects minor schema violations to prevent pipeline failures."""
        logger.warning(f"[{self.name}] Sanitizing output payload: {raw_output}")

        sanitized = {
            "customer_email": {
                "subject": f"Shipping update regarding your order #{order_id}",
                "body": f"Dear {customer_name},\n\nWe are experiencing a minor shipping hold. We apologize for the delay.\n\nRegards,\nCustomer Support"
            },
            "customer_sms": f"Hi {customer_name}, order #{order_id} is delayed. We are resolving this. Sorry for the delay!",
            "support_executive_message": f"Help customer query regarding order #{order_id}. Verify details.",
            "carrier_escalation_email": {
                "recipient": "logistics-support@carrier.com",
                "subject": f"Logistics Escalation: #{order_id}",
                "body": "Formal SLA escalation details. Scan updates required."
            }
        }

        if not isinstance(raw_output, dict):
            return sanitized

        # customer_email correction
        email = raw_output.get("customer_email")
        if isinstance(email, dict) and "subject" in email and "body" in email:
            sanitized["customer_email"]["subject"] = str(email["subject"]).strip() or sanitized["customer_email"]["subject"]
            sanitized["customer_email"]["body"] = str(email["body"]).strip() or sanitized["customer_email"]["body"]

        # customer_sms correction
        sms = raw_output.get("customer_sms")
        if isinstance(sms, str) and sms.strip():
            sanitized["customer_sms"] = sms.strip()[:157] + "..." if len(sms) > 160 else sms.strip()

        # support_executive_message correction
        exec_msg = raw_output.get("support_executive_message")
        if isinstance(exec_msg, str) and exec_msg.strip():
            sanitized["support_executive_message"] = exec_msg.strip()
        else:
            # Build support executive message based on mock
            fallback_mock = self._run_mock(customer_name, order_id, root_cause, resolution)
            sanitized["support_executive_message"] = fallback_mock["support_executive_message"]

        # carrier_escalation_email correction (Legacy)
        carrier_email = raw_output.get("carrier_escalation_email")
        if isinstance(carrier_email, dict) and "subject" in carrier_email and "body" in carrier_email:
            sanitized["carrier_escalation_email"]["recipient"] = str(carrier_email.get("recipient", "logistics-support@carrier.com"))
            sanitized["carrier_escalation_email"]["subject"] = str(carrier_email["subject"]).strip()
            sanitized["carrier_escalation_email"]["body"] = str(carrier_email["body"]).strip()

        logger.info(f"[{self.name}] Payload successfully sanitized to: {sanitized}")
        return sanitized

    def _get_fallback_response(self, reason: str, customer_name: str, order_id: str) -> Dict[str, Any]:
        """Provides a safe default prediction payload if execution crashes."""
        return {
            "customer_email": {
                "subject": f"Shipping update: Order #{order_id}",
                "body": f"Dear {customer_name},\n\nWe are looking into a logistics transit hold on your shipment. We apologize for the delay.\n\nWarm regards,\nCustomer Operations"
            },
            "customer_sms": f"Hi {customer_name}, order #{order_id} has a shipping delay. We are resolving it.",
            "support_executive_message": f"Incident exception hold: {reason}. Guide customer to await express resolution status updates.",
            "carrier_escalation_email": {
                "recipient": "support@carrier.com",
                "subject": f"SLA Hold - Order #{order_id}",
                "body": f"Logistics Exception checks triggered. Reason: {reason}"
            }
        }

