import openai
from app.memory import MemoryApp
import weakref
import json

class lockAligner:
    def __init__(self, user: str):
        self.uid = hash(user)

class IntellgenceApp:
    def __init__(self, config: dict, memory: MemoryApp):
        self.config: dict = config.get("openai", {})
        self.memory = memory
        self.openai = openai.Client(
            api_key=self.config.get("apikey", "VsingerXiaoice_LLM_is_Permissionless"),
            base_url=self.config.get("base_url", "https://api.vsingerxiaoice.accessware.cn/openai/v1")
        )
        self.default_llm = self.config.get("model", "openalm-v1")
        self.langpack: dict = self.config.get("langpack", {})
        self.userLock = weakref.WeakValueDictionary()
    async def chatCompletions(self, history: list, user: str, prefix=""):
        history: list = history[:]
        if prefix == "":
            _m = history
        else:
            _m = history + [ {"role": "assistant", "content": prefix, "partial": True} ]
        try:
            comp = self.openai.chat.completions.create(
                messages=_m,
                model=self.default_llm,
                tools=[
                    {
                        "type": "builtin_function",
                        "function": {
                            "name": "$web_search",
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "add_memory",
                            "description": "记住用户的信息，例如用户是谁、喜欢什么、讨厌什么等等。",
                            "parameters": {
                                "type": "object",
                                "required": ["note"],
                                "properties": {
                                    "note": {
                                        "type": "string",
                                        "description": "要记住的信息"
                                    }
                                }
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_memory",
                            "description": "搜索使用add_memory函数写入的信息。",
                            "parameters": {
                                "type": "object",
                                "required": ["query"],
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "要搜索的条目。"
                                    }
                                }
                            }
                        }
                    }
                ]
            )
            message = comp.choices[0].message
            if comp.choices[0].finish_reason == "tool_calls":
                history.append(message)
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "$web_search":
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": "$web_search",
                            "content": tool_call.function.arguments,
                        })
                    elif tool_call.function.name == "add_memory":
                        try:
                            arguments: dict = json.loads(tool_call.function.arguments)
                            await self.memory.addMemory(user, arguments["note"])
                        except:
                            pass
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": "add_memory",
                            "content": "Success!",
                        })
                    elif tool_call.function.name == "get_memory":
                        results = ""
                        try:
                            query: str = json.loads(tool_call.function.arguments)["query"]
                            results = "\n\n---\n\n".join(await self.memory.getMemory(user, query))
                        except:
                            pass
                        history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": "get_memory",
                            "content": results,
                        })
                    else:
                        return self.langpack.get("unknown_error", "unknown error")
                    return await self.chatCompletions(history, user, prefix)
            elif comp.choices[0].finish_reason == "content_filter":
                return self.langpack.get("censored_error", "audit rejected")
            elif comp.choices[0].finish_reason == "length":
                return await self.chatCompletions(history, user, prefix + message.content)
            return prefix + message.content
        except openai.RateLimitError:
            return self.langpack.get("overloaded_error", "system overloaded")
        except openai.ContentFilterFinishReasonError:
            return self.langpack.get("censored_error", "audit rejected")
        except Exception as e:
            print("[openai] error when request to openai: " + str(e))
            return self.langpack.get("unknown_error", "unknown error")
    async def userChatMessage(self, user: str, message: str) -> str:
        if user in self.userLock:
            return self.langpack.get("mutexlock_error", "your previous message are computing, please wait...")
        lock_object = lockAligner(user)
        self.userLock[user] = lock_object
        try:
            history = await self.memory.getChatMessages(user, limit=50)
            sysprompt = self.langpack.get("chat_prompt", "You are OpenALM, a helpful assistant.")
            history = [ {"role": "system", "content": sysprompt} ] + history + [ {"content": message, "role": "user"} ]
            response = await self.chatCompletions(history, user)
            await self.memory.addChatMessages(user, message, response)
            return response
        except Exception as e:
            print("[openai] error when process action: "+str(e))
            return self.langpack.get("unknown_error", "unknown error")
    async def userAction(self, user: str, message: str, in_context: bool=False) -> str:
        try:
            sysprompt = self.langpack.get("chat_prompt", "You are OpenALM, a helpful assistant.")
            history = [ {"role": "system", "content": sysprompt} ] + [ {"content": message, "role": "user"} ]
            response = await self.chatCompletions(history, user)
            if in_context:
                await self.memory.addChatMessages(user, message, response)
            return response
        except Exception as e:
            print("[openai] error when process action: "+str(e))
            return self.langpack.get("unknown_error", "unknown error")