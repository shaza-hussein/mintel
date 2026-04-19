import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../..")))


from src.app.products.gen.genai.llm.client import OpenRouterClient
from src.app.products.gen.genai.llm.prompts import selector_prompt
from typing import Optional, Dict, Any
import json
import re

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

class Selector:

    def __init__(self):
        self._client = OpenRouterClient()

    def selecting(self, mba: str) -> Optional[Dict[str, Any]]:
        prompt = selector_prompt(mba_results=mba)
        response = self._client.run(prompt=prompt)
        if not response:
            return None
        
        return self._safe_json_parse(response)
        

    def _safe_json_parse(self, response: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Raw JSON failed. Attempting extraction...")

            # Extract JSON block using regex
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                json_str = match.group(0)

                # remove ```json fences if present
                json_str = json_str.replace("```json", "").replace("```", "").strip()

                try:
                    return json.loads(json_str)
                except Exception as e:
                    logger.error(f"Extraction failed: {e}")

            logger.error(f"Invalid JSON:\n{response}")
            return None