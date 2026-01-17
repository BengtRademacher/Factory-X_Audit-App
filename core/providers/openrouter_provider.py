import requests
from typing import Optional

class OpenRouterProvider:
    def __init__(self, api_key: str, model_name: str = "openrouter/auto"):
        self.api_key = api_key
        self.model_name = model_name

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "input": prompt
        }
        if system_instruction:
            payload["system"] = system_instruction

        response = requests.post("https://openrouter.ai/v1/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def generate_from_file(self, prompt: str, file_bytes: bytes, mime_type: str = "application/pdf") -> str:
        # 1) upload file
        files = {
            "file": ("file.pdf", file_bytes, mime_type)
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        upload_response = requests.post(
            "https://openrouter.ai/v1/files",
            files=files,
            headers=headers
        )
        upload_response.raise_for_status()

        file_id = upload_response.json()["id"]

        # 2) use file in prompt
        payload = {
            "model": self.model_name,
            "input": prompt,
            "file": file_id
        }

        response = requests.post(
            "https://openrouter.ai/v1/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
