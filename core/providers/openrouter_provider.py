import requests
import time
import base64
import re
from typing import Optional, List, Dict, Any

class OpenRouterProvider:
    """Provider fuer OpenRouter API mit robustem Fehlerhandling und dynamischer Modell-Unterstuetzung."""
    
    def __init__(self, api_key: str, model_name: str = "openrouter/auto"):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://openrouter.ai/api/v1"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/factory-x/audit-app", # Empfohlen von OpenRouter
            "X-Title": "Factory-X Audit App"
        }

    def generate(self, prompt: str, system_instruction: Optional[str] = None, max_retries: int = 5) -> str:
        """Generates a response with retry logic for rate limits."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._get_headers(),
                    timeout=60
                )
                
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + 1
                    # Try to read retryDelay from header or body
                    retry_info = response.json().get("error", {}).get("details", [{}])[0].get("retryDelay", "")
                    if retry_info:
                        try:
                            # Extract seconds if possible
                            seconds = re.search(r'(\d+\.?\d*)', retry_info)
                            if seconds:
                                wait_time = float(seconds.group(1)) + 1
                        except:
                            pass
                    
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()

            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(2 ** attempt)

        return "Error: Maximum retries reached (Rate limit or timeout)."

    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        """
        Analyzes a document. 
        Note: OpenRouter supports files depending on the target model.
        We use the OpenAI-compatible format for vision/files.
        """
        base64_file = base64.b64encode(file_bytes).decode("utf-8")
        
        # For PDFs we need to check if the model supports them directly.
        # Most vision models prefer images. 
        # If it's a PDF, we send it as a document part.
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url", # Many providers use image_url for PDFs/Docs too
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_file}"
                        }
                    }
                ]
            }
        ]

        payload = {
            "model": self.model_name,
            "messages": messages
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._get_headers(),
                timeout=90
            )
            
            if response.status_code != 200:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                
                status_code = response.status_code
                error_msg = error_data.get("error", {}).get("message", response.text)
                
                if status_code == 404:
                    return f"Error 404: Model '{self.model_name}' not found or endpoint is incorrect."
                elif status_code == 400:
                    return f"Error 400: Invalid request. The model might not support PDF files via OpenRouter. Details: {error_msg}"
                elif status_code == 401:
                    return "Error 401: API key invalid or expired."
                elif status_code == 429:
                    return "Error 429: Rate limit reached. Please wait a moment."
                else:
                    return f"API Error ({status_code}): {error_msg}"

            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Connection error: {str(e)}"
