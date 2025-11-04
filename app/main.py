import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from .chatwoot_client import ChatwootClient

load_dotenv()

app = FastAPI(title="Chatwoot Webhook (FastAPI)")

CHATWOOT_BASE_URL = os.getenv("CHATWOOT_BASE_URL", "https://app.chatwoot.com")
CHATWOOT_API_TOKEN = os.getenv("CHATWOOT_API_TOKEN", "")

client = ChatwootClient(base_url=CHATWOOT_BASE_URL, api_token=CHATWOOT_API_TOKEN)


@app.post("/webhook/chatwoot")
async def chatwoot_webhook(request: Request):
    payload = await request.json()

    event = payload.get("event")
    content = payload.get("content", "")
    message_type = payload.get("message_type")

    # Conversation & account info may appear in different shapes depending on channel/docs version
    conversation = payload.get("conversation") or {}
    conversation_id = (
        conversation.get("id")
        or conversation.get("display_id")  # display_id is not ideal for API calls, but log it if used
    )
    account = payload.get("account") or {}
    account_id = account.get("id")

    # Only act on incoming user messages
    if event == "message_created" and message_type == "incoming":
        text = (content or "").strip()

        if text == "/start":
            # Send a welcome message back into the conversation via Chatwoot API
            if not (CHATWOOT_API_TOKEN and account_id and conversation_id):
                # Missing configuration or IDs; return 400 with explanation
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Missing CHATWOOT_API_TOKEN or conversation/account id in payload",
                        "debug": {
                            "has_token": bool(CHATWOOT_API_TOKEN),
                            "account_id": account_id,
                            "conversation_id": conversation_id,
                        },
                    },
                )

            welcome_text = "欢迎来到客服！请问有什么可以帮助您？"
            try:
                resp = await client.create_outgoing_message(
                    account_id=account_id,
                    conversation_id=conversation_id,
                    content=welcome_text,
                )
                return {"status": "ok", "sent_message_id": resp.get("id")}
            except Exception as e:
                return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    # No action needed for other events; acknowledge receipt
    return {"status": "ignored"}


@app.get("/")
async def health():
    return {"ok": True}