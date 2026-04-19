import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../..")))

import json
import logging
from typing import Optional, Dict, Any

import requests
from src.app.products.gen.genai.llm.config import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


class OpenRouterClient:

    def __init__(
        self,
        temperature: float = 0.0,
        timeout: int = 30
    ):
        self.conf = get_settings()

        self.api_key = self.conf.OPENROUTER_API_KEY 
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in .env")

        self.model = self.conf.MODEL

        self.base_url = self.conf.BASE_URL

        self.temperature = temperature
        self.timeout = timeout

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",

            "HTTP-Referer": "http://localhost",
            "X-Title": "telecom-bundle-optimizer"
        }

    def _build_payload(self, prompt: str) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt 
                }
            ],
            "temperature": self.temperature,
        }

    def run(self, prompt: str) -> Optional[str]:
        payload = self._build_payload(prompt)

        try:
            response = requests.post(
                url=self.base_url,
                headers=self.headers,
                json=payload,  
                timeout=self.timeout,
            )

            logger.info(f"HTTP {response.status_code}")

            response.raise_for_status()

            data = response.json()
            return self._parse_response(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return None

        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Parsing error: {e}")
            return None

    def _parse_response(self, data: Dict[str, Any]) -> Optional[str]:
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            logger.error(f"Unexpected response format: {data}")
            return None