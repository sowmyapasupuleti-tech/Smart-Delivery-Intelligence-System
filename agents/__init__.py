# agents/__init__.py

import os
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SDIS_Agents")

def get_gemini_client():
    """
    Initializes and returns the Google GenAI client if a key is available.
    Returns None if no API key is set, signaling agents to run in Mock Mode.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY environment variable not found. Agents will fall back to Mock Mode.")
        return None
    
    try:
        from google import genai
        # Initialize Google GenAI client
        client = genai.Client(api_key=api_key)
        return client
    except ImportError:
        logger.error("google-genai SDK is not installed. Run 'pip install google-genai'. Falling back to Mock Mode.")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Gemini Client: {e}. Falling back to Mock Mode.")
        return None
