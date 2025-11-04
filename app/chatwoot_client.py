import httpx
from typing import Any, Dict

class ChatwootClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.headers = {
            "Content-Type": "application/json",
            # Chatwoot expects api_access_token header for auth
            "api_access_token": self.api_token,
        }

    async def create_outgoing_message(
        self, account_id: int, conversation_id: int, content: str, private: bool = False
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
        payload = {
            "content": content,
            "message_type": "outgoing",
            "private": private,
            "content_type": "text",
            "content_attributes": {},
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, headers=self.headers, json=payload)
            r.raise_for_status()
            return r.json()