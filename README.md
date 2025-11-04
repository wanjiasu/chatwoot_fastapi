# Chatwoot Webhook (FastAPI)

一个最小可运行的 FastAPI 项目，用于接收 Chatwoot webhook 并在用户输入 `/start` 时通过 Chatwoot API 回发欢迎语。

## 本地运行

1. 创建并激活虚拟环境（可选）：
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置环境变量：
   - 复制 `.env.example` 为 `.env` 并填写：
     - `CHATWOOT_BASE_URL` （如 `https://app.chatwoot.com` 或你的自托管域名）
     - `CHATWOOT_API_TOKEN` （在 Chatwoot 个人资料 -> Access Token 获取）

4. 启动服务：
   ```bash
   uvicorn app.main:app --reload --port 8100
   ```

5. 本地测试：
   - 健康检查：`GET http://localhost:8003/`
   - 模拟 webhook：
     ```bash
     curl -X POST http://localhost:8003/webhook/chatwoot \
       -H 'Content-Type: application/json' \
       -d '{
         "event": "message_created",
         "content": "/start",
         "message_type": "incoming",
         "conversation": {"id": 123},
         "account": {"id": 1}
       }'
     ```

   收到 `/start` 时，服务会调用 Chatwoot API 在该会话中发送：
   > 欢迎来到客服！请问有什么可以帮助您？

## 在 Chatwoot 端配置

- 如果使用「Webhooks」：
  - 前往 Settings → Integrations → Webhooks，添加 `http(s)://<your-host>/webhook/chatwoot`，订阅 `message_created` 事件。
  - 注意：Webhook 仅通知事件，机器人回复需要调用 Chatwoot API（本项目已实现）。

- 如果使用「Agent Bot」：
  - 前往 Settings → Bots，新增一个 Bot，Webhook URL 填 `http(s)://<your-host>/webhook/chatwoot`。
  - 在目标 Inbox 的 Bot Configuration 选择该 Bot。

## 环境变量说明

- `CHATWOOT_BASE_URL`：Chatwoot 的基础地址。
- `CHATWOOT_API_TOKEN`：用于调用 Chatwoot API 的 `api_access_token`（请求头）。

## 参考

- Chatwoot Webhook 事件与示例负载：
  - https://www.chatwoot.com/hc/user-guide/articles/1677693021-how-to-use-webhooks
- 创建消息 API：
  - https://developers.chatwoot.com/api-reference/messages/create-new-message