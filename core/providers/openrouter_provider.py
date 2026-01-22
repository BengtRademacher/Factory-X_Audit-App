import requests
import time
import base64
import re
import json
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
        if not self.model_name:
            return "Error: No model selected. Please select a model in the sidebar."

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
                # Use a more robust way to construct the URL
                url = f"{self.base_url.rstrip('/')}/chat/completions"
                response = requests.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=60
                )
                
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + 1
                    # Try to read retryDelay from header or body
                    try:
                        error_json = response.json()
                        retry_info = error_json.get("error", {}).get("details", [{}])[0].get("retryDelay", "")
                        if retry_info:
                            seconds = re.search(r'(\d+\.?\d*)', retry_info)
                            if seconds:
                                wait_time = float(seconds.group(1)) + 1
                    except:
                        pass
                    
                    time.sleep(wait_time)
                    continue

                if response.status_code != 200:
                    status_code = response.status_code
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", response.text)
                    except:
                        error_msg = response.text
                    
                    if status_code == 404:
                        return f"Error 404: Model '{self.model_name}' not found on OpenRouter. This can happen if the model is currently unavailable or the ID is incorrect."
                    elif status_code == 401:
                        return "Error 401: API key invalid or expired."
                    elif status_code == 400:
                        return f"Error 400: Bad Request. Model: {self.model_name}. Message: {error_msg}"
                    else:
                        return f"API Error ({status_code}): {error_msg}"

                result = response.json()
                return result["choices"][0]["message"]["content"].strip()

            except Exception as e:
                if attempt == max_retries - 1:
                    return f"Connection Error after {max_retries} attempts: {str(e)}"
                time.sleep(2 ** attempt)

        return "Error: Maximum retries reached."

    def generate_stream(self, prompt: str, system_instruction: Optional[str] = None, max_retries: int = 5):
        """Generates a streaming response from OpenRouter with retry logic for rate limits."""
        if not self.model_name:
            yield "Error: No model selected. Please select a model in the sidebar."
            return

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True
        }

        for attempt in range(max_retries):
            try:
                url = f"{self.base_url.rstrip('/')}/chat/completions"
                response = requests.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=90,
                    stream=True
                )
                
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + 1
                    try:
                        error_json = response.json()
                        retry_info = error_json.get("error", {}).get("details", [{}])[0].get("retryDelay", "")
                        if retry_info:
                            seconds = re.search(r'(\d+\.?\d*)', retry_info)
                            if seconds:
                                wait_time = float(seconds.group(1)) + 1
                    except:
                        pass
                    
                    time.sleep(wait_time)
                    continue

                if response.status_code != 200:
                    status_code = response.status_code
                    try:
                        # For streaming errors, the body might not be JSON if it failed early
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", response.text)
                    except:
                        error_msg = response.text
                    
                    yield f"API Error ({status_code}): {error_msg}"
                    return

                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                content = data['choices'][0]['delta'].get('content', '')
                                if content:
                                    yield content
                            except:
                                continue
                return # Success, exit retry loop

            except Exception as e:
                if attempt == max_retries - 1:
                    yield f"Connection Error after {max_retries} attempts: {str(e)}"
                    return
                time.sleep(2 ** attempt)

    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf", max_retries: int = 5) -> str:
        """
        Analyzes a document. 
        Note: OpenRouter supports files depending on the target model.
        We use the OpenAI-compatible format for vision/files.
        """
        if not self.model_name:
            return "Error: No model selected. Please select a model in the sidebar."

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

        for attempt in range(max_retries):
            try:
                url = f"{self.base_url.rstrip('/')}/chat/completions"
                response = requests.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=120 # Increased timeout for files
                )
                
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + 1
                    try:
                        error_json = response.json()
                        retry_info = error_json.get("error", {}).get("details", [{}])[0].get("retryDelay", "")
                        if retry_info:
                            seconds = re.search(r'(\d+\.?\d*)', retry_info)
                            if seconds:
                                wait_time = float(seconds.group(1)) + 1
                    except:
                        pass
                    
                    time.sleep(wait_time)
                    continue

                if response.status_code != 200:
                    status_code = response.status_code
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", response.text)
                    except:
                        error_msg = response.text
                    
                    if status_code == 404:
                        return f"Error 404: Model '{self.model_name}' not found on OpenRouter. Vision/PDF analysis might not be supported by this model."
                    elif status_code == 400:
                        return f"Error 400: Bad Request. The model might not support PDF files via OpenRouter. Details: {error_msg}"
                    elif status_code == 401:
                        return "Error 401: API key invalid or expired."
                    else:
                        return f"API Error ({status_code}): {error_msg}"

                return response.json()["choices"][0]["message"]["content"].strip()

            except Exception as e:
                if attempt == max_retries - 1:
                    return f"Connection Error after {max_retries} attempts: {str(e)}"
                time.sleep(2 ** attempt)
        
        return "Error: Maximum retries reached."
