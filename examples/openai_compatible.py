"""Call TARCS-Mem through its OpenAI-compatible endpoint using only stdlib."""

from __future__ import annotations

import json
import os
import urllib.request


base_url = os.getenv("TARCSMEM_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/")
payload = {
    "model": "tarcsmem-governed",
    "messages": [
        {
            "role": "user",
            "content": "2026年8月华南区销售折扣上限是多少？",
        }
    ],
    "as_of": "2026-08-15",
    "stream": False,
}
headers = {"Content-Type": "application/json"}
api_key = os.getenv("TARCSMEM_API_KEY", "")
if api_key:
    headers["Authorization"] = f"Bearer {api_key}"

request = urllib.request.Request(
    f"{base_url}/chat/completions",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers=headers,
    method="POST",
)
with urllib.request.urlopen(request, timeout=30) as response:
    result = json.loads(response.read().decode("utf-8"))

print(result["choices"][0]["message"]["content"])
print("citations:", result["tarcsmem"]["citations"])
print("trace:", result["tarcsmem"]["observability"].get("trace_id"))
