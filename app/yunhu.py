import aiohttp
from app.intellgence import IntellgenceApp
import fastapi
import pydantic
import typing
import json

class YunhuWebhookHeader(pydantic.BaseModel):
    eventId: str
    eventTime: int
    eventType: str

class YunhuWebhookModel(pydantic.BaseModel):
    version: typing.Literal["1.0"]
    header: YunhuWebhookHeader
    event: dict

class ChatMessageData(pydantic.BaseModel):
    content: str
    isGroup: bool
    action: str
    sender: str
    responseTo: str
    replyTo: typing.Optional[str]

class YunhuApp:
    def __init__(self, config: dict, llm: IntellgenceApp, app: fastapi.FastAPI):
        self.config: dict = config.get("yunhu", {})
        self.instructs: typing.Dict[int, str] = { v: k for k, v in self.config.get("instruct", {}).items() }
        self.llm: IntellgenceApp = llm
        self.fastapi: fastapi.FastAPI = app
        if self.config.get("enabled", False):
            print("[yunhu] yunhu listener started.")
            self.fastapi.post(self.config.get("webhook", "/yunhu-webhook"))(self.welcome)
        self.prompts: dict = self.config.get("prompt", {})
    async def welcome(self, req: YunhuWebhookModel):
        print("[yunhu] getted a event.")
        try:
            if req.header.eventType == "message.receive.normal" or req.header.eventType == "message.receive.instruction":
                isGroup = req.event["message"]["chatType"] == "group"
                await self.acceptMessage(ChatMessageData(
                    content=req.event["message"]["content"]["text"],
                    isGroup=isGroup,
                    sender=req.event["sender"]["senderId"],
                    responseTo=(req.event["chat"]["chatId"] if isGroup else req.event["sender"]["senderId"]),
                    replyTo=(req.event["message"]["msgId"] if isGroup else None),
                    action=self.instructs.get(req.event["message"].get("commandId", -1), "none")
                ))
            return {"code": 200}
        except Exception as e:
            print("[yunhu][error] ", e)
            return {"code": -404}
    async def response(self, message: ChatMessageData, response: str, ctype: typing.Literal["text", "markdown", "html"] = "markdown", buttons: list=[]):
        async with aiohttp.ClientSession() as s:
            rqd = {
                "recvId": message.responseTo,
                "recvType": "group" if message.isGroup else "user",
                "contentType": ctype,
                "content": {
                    "text": response
                }
            }
            if len(buttons) >= 0:
                rqd["content"]["buttons"] = buttons
            if message.replyTo is not None:
                rqd["parentId"] = message.replyTo
            await s.post(
                "https://chat-go.jwzhd.com/open-apis/v1/bot/send?token="+self.config.get("token", ""),
                data=json.dumps(rqd)
            )
    async def acceptMessage(self, message: ChatMessageData):
        if message.action == "none":
            if message.isGroup:
                return
            response = await self.llm.userChatMessage("yunhu:"+message.sender, message.content)
            await self.response(message, response, "markdown")
        elif message.action == "news":
            response = await self.llm.userAction("yunhu:"+message.sender, self.prompts.get("search_news", "please search the news"), in_context=not message.isGroup)
            await self.response(message, response, "markdown")
        elif message.action == "weather":
            prompt: str = self.prompts.get("search_weather", "please search the weather of: {{address}}")
            prompt = prompt.replace("{{address}}", message.content)
            response = await self.llm.userAction("yunhu:"+message.sender, prompt, in_context=not message.isGroup)
            await self.response(message, response, "markdown")
        elif message.action == "search":
            prompt: str = self.prompts.get("search_internet", "please search: {{search}}")
            prompt = prompt.replace("{{search}}", message.content)
            response = await self.llm.userAction("yunhu:"+message.sender, prompt, in_context=not message.isGroup)
            await self.response(message, response, "markdown")