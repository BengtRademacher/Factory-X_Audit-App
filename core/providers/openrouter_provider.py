import base64
import json
import re
import time
from typing import Any, Dict, Optional

import requests


class OpenRouterAPIError(Exception):
    """Raised for non-success OpenRouter responses."""


class OpenRouterProvider:
    """Provider fuer OpenRouter API mit robustem Fehlerhandling und dynamischer Modell-Unterstuetzung."""

    def __init__(self, api_key: str, model_name: str = "openrouter/auto"):
        self.api_key = api_key
        self.model_name = model_name
        self.model_metadata = {}
        self.base_url = "https://openrouter.ai/api/v1"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/factory-x/audit-app",  # Empfohlen von OpenRouter
            "X-Title": "Factory-X Audit App"
        }

    def _chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _post_completion(
        self,
        payload: Dict[str, Any],
        timeout: int,
        stream: bool = False,
    ) -> requests.Response:
        return requests.post(
            self._chat_url(),
            json=payload,
            headers=self._get_headers(),
            timeout=timeout,
            stream=stream,
        )

    @staticmethod
    def _messages(prompt: str, system_instruction: Optional[str] = None) -> list[Dict[str, str]]:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _retry_wait_time(response: requests.Response, attempt: int) -> float:
        wait_time = (2 ** attempt) + 1
        try:
            error_json = response.json()
            retry_info = error_json.get("error", {}).get("details", [{}])[0].get("retryDelay", "")
            if retry_info:
                seconds = re.search(r'(\d+\.?\d*)', retry_info)
                if seconds:
                    wait_time = max(float(seconds.group(1)) + 1, wait_time)
        except (ValueError, KeyError, IndexError, TypeError):
            pass
        return wait_time

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            error_data = response.json()
            return error_data.get("error", {}).get("message", response.text)
        except ValueError:
            return response.text

    def _generate_error_response(self, status_code: int, error_msg: str) -> str:
        if status_code == 404:
            return f"Error 404: Model '{self.model_name}' not found on OpenRouter. This can happen if the model is currently unavailable or the ID is incorrect."
        if status_code == 401:
            return "Error 401: API key invalid or expired."
        if status_code == 400:
            return f"Error 400: Bad Request. Model: {self.model_name}. Message: {error_msg}"
        return f"API Error ({status_code}): {error_msg}"

    def _file_error_response(self, status_code: int, error_msg: str) -> str:
        if status_code == 404:
            return f"Error 404: Model '{self.model_name}' not found on OpenRouter. Vision/PDF analysis might not be supported by this model."
        if status_code == 400:
            return f"Error 400: Bad Request. The model might not support PDF files via OpenRouter. Details: {error_msg}"
        if status_code == 401:
            return "Error 401: API key invalid or expired."
        return f"API Error ({status_code}): {error_msg}"

    @staticmethod
    def _content_from_response(response: requests.Response) -> str:
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()

    def _apply_reasoning_parameters(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        supported = set(self.model_metadata.get("supported_parameters", []) or [])
        if "reasoning" in supported:
            payload["reasoning"] = {"effort": "high"}
        if "reasoning_effort" in supported:
            payload["reasoning_effort"] = "high"
        if "include_reasoning" in supported:
            payload["include_reasoning"] = True
        return payload

    def generate(self, prompt: str, system_instruction: Optional[str] = None, max_retries: int = 5) -> str:
        """Generates a response with retry logic for rate limits."""
        if not self.model_name:
            return "Error: No model selected. Please select a model in the sidebar."

        payload = {
            "model": self.model_name,
            "messages": self._messages(prompt, system_instruction)
        }
        payload = self._apply_reasoning_parameters(payload)

        for attempt in range(max_retries):
            try:
                response = self._post_completion(payload, timeout=60)

                if response.status_code == 429:
                    time.sleep(self._retry_wait_time(response, attempt))
                    continue

                if response.status_code != 200:
                    return self._generate_error_response(response.status_code, self._error_message(response))

                return self._content_from_response(response)

            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
                if attempt == max_retries - 1:
                    return f"Connection Error after {max_retries} attempts: {str(e)}"
                time.sleep(2 ** attempt + 1)

        return "Error: Rate limit exceeded after multiple retries. Please wait a moment and try again, or select a different model."

    def generate_stream(self, prompt: str, system_instruction: Optional[str] = None, max_retries: int = 5):
        """Generates a streaming response from OpenRouter with retry logic for rate limits."""
        if not self.model_name:
            yield "Error: No model selected. Please select a model in the sidebar."
            return

        payload = {
            "model": self.model_name,
            "messages": self._messages(prompt, system_instruction),
            "stream": True
        }
        payload = self._apply_reasoning_parameters(payload)

        for attempt in range(max_retries):
            try:
                response = self._post_completion(payload, timeout=90, stream=True)

                if response.status_code == 429:
                    time.sleep(self._retry_wait_time(response, attempt))
                    continue

                if response.status_code != 200:
                    error_msg = self._error_message(response)
                    raise OpenRouterAPIError(f"API Error ({response.status_code}): {error_msg}")

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
                            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                                continue
                return  # Success, exit retry loop

            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError, OpenRouterAPIError) as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(2 ** attempt + 1)

    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf", max_retries: int = 5) -> str:
        """
        Analyzes a document.
        Note: OpenRouter supports files depending on the target model.
        We use the OpenAI-compatible format for vision/files.
        """
        if not self.model_name:
            return "Error: No model selected. Please select a model in the sidebar."

        base64_file = base64.b64encode(file_bytes).decode("utf-8")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",  # Many providers use image_url for PDFs/Docs too
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
        payload = self._apply_reasoning_parameters(payload)

        for attempt in range(max_retries):
            try:
                response = self._post_completion(payload, timeout=120)

                if response.status_code == 429:
                    time.sleep(self._retry_wait_time(response, attempt))
                    continue

                if response.status_code != 200:
                    return self._file_error_response(response.status_code, self._error_message(response))

                return self._content_from_response(response)

            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
                if attempt == max_retries - 1:
                    return f"Connection Error after {max_retries} attempts: {str(e)}"
                time.sleep(2 ** attempt + 1)

        return "Error: Rate limit exceeded after multiple retries. Please wait a moment and try again, or select a different model."
