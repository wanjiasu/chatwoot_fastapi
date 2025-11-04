import os
import re
import html
from urllib.parse import urlparse
from typing import List
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from pymongo import MongoClient
from .chatwoot_client import ChatwootClient

load_dotenv()

app = FastAPI(title="Chatwoot Webhook (FastAPI)")

CHATWOOT_BASE_URL = os.getenv("CHATWOOT_BASE_URL", "https://app.chatwoot.com")
CHATWOOT_API_TOKEN = os.getenv("CHATWOOT_API_TOKEN", "")

client = ChatwootClient(base_url=CHATWOOT_BASE_URL, api_token=CHATWOOT_API_TOKEN)


def _get_mongo_client() -> MongoClient:
    host = os.getenv("MONGODB_HOST")
    port = int(os.getenv("MONGODB_PORT", "27017"))
    username = os.getenv("MONGODB_USERNAME")
    password = os.getenv("MONGODB_PASSWORD")
    auth_source = os.getenv("MONGODB_AUTH_SOURCE", "admin")
    return MongoClient(host=host, port=port, username=username, password=password, authSource=auth_source)


def _is_valid_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _clean_url(url: str) -> str:
    s = str(url).strip()
    if not s:
        return ""
    # Remove common wrapping characters/backticks and stray angle brackets/spaces
    s = s.strip("`\"' <>")
    return s


def _format_tasks(docs: List[dict], email: str) -> str:
    if not docs:
        return f"查询邮箱：{email}\n未找到该邮箱的相关任务。"

    header_lines = [f"查询邮箱：{email}", "最新 5 条任务："]
    task_blocks: List[str] = []
    status_emoji_map = {
        "completed": "✅",
        "failed": "❌",
        "running": "⏳",
        "queued": "🕒",
    }
    for idx, doc in enumerate(docs, start=1):
        task_id = doc.get("task_id", "-")
        status = doc.get("status", "-")
        req = (doc.get("request") or {})
        market = req.get("market_type", "-")
        ticker = req.get("ticker", "-")
        # 回退逻辑：优先顶层 report_url，其次 request.report_url
        report_url_raw = (doc.get("report_url") or req.get("report_url") or "-") if status == "completed" else "-"
        if status == "completed" and report_url_raw and report_url_raw != "-":
            cleaned_url = _clean_url(report_url_raw)
            if _is_valid_http_url(cleaned_url):
                # 使用原始 URL，确保 Telegram 自动识别并可点击
                report_display = cleaned_url
            else:
                report_display = "-"
        else:
            report_display = "-"

        status_emoji = status_emoji_map.get(str(status).lower(), "❔")
        block = (
            f"{idx}. 🆔 任务ID: {task_id}\n"
            f"   状态: {status_emoji} {status}\n"
            f"   市场: 📈 {market}\n"
            f"   代码: 🔖 {ticker}\n"
            f"   报告: 🔗 {report_display}"
        )
        task_blocks.append(block)

    return "\n".join(header_lines) + ("\n" if task_blocks else "") + "\n\n".join(task_blocks)


@app.post(f"/webhook/chatwoot/telegram/tele_stocktrade")
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
        # Optional: restrict handling to a specific inbox via env var
        allowed_inbox_id = os.getenv("TELE_STOCKTRADE_INBOX_ID")
        inbox_id = (conversation or {}).get("inbox_id")
        if allowed_inbox_id and inbox_id is not None and str(inbox_id) != str(allowed_inbox_id):
            # Ignore messages from other inboxes
            return {"status": "ignored", "reason": "inbox_not_allowed", "inbox_id": inbox_id}

        text = (content or "").strip()

        if text == "/start":
            if not (CHATWOOT_API_TOKEN and account_id and conversation_id):
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

        if text.lower().startswith("/query"):
            if not (CHATWOOT_API_TOKEN and account_id and conversation_id):
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

            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                usage = "用法：/query 邮箱\n例如：/query user@example.com"
                try:
                    resp = await client.create_outgoing_message(
                        account_id=account_id,
                        conversation_id=conversation_id,
                        content=usage,
                    )
                    return {"status": "ok", "sent_message_id": resp.get("id")}
                except Exception as e:
                    return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

            email = parts[1].strip()
            email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            if not re.match(email_pattern, email):
                msg = "邮箱格式不正确，请使用类似 user@example.com 的格式。"
                try:
                    resp = await client.create_outgoing_message(
                        account_id=account_id,
                        conversation_id=conversation_id,
                        content=msg,
                    )
                    return {"status": "ok", "sent_message_id": resp.get("id")}
                except Exception as e:
                    return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

            try:
                mongo_client = _get_mongo_client()
                db_name = os.getenv("MONGODB_DATABASE")
                coll = mongo_client[db_name]["analysis_tasks"]
                cursor = coll.find({"request.notify_email": email}).sort("created_time", -1).limit(5)
                docs = list(cursor)
                reply_text = _format_tasks(docs, email)
            except Exception as e:
                reply_text = f"查询失败：{str(e)}"
            finally:
                try:
                    mongo_client.close()
                except Exception:
                    pass

            try:
                resp = await client.create_outgoing_message(
                    account_id=account_id,
                    conversation_id=conversation_id,
                    content=reply_text,
                )
                return {"status": "ok", "sent_message_id": resp.get("id")}
            except Exception as e:
                return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    # No action needed for other events; acknowledge receipt
    return {"status": "ignored"}


@app.get("/")
async def health():
    return {"ok": True}