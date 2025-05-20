import fastapi
import uvicorn

class RestfulApp(fastapi.FastAPI):
    def __init__(self, config: dict):
        super().__init__()
        self.__aik_config: dict = config.get("restful", {})
    def startService(self):
        uvicorn.run(self, host='0.0.0.0', port=self.__aik_config.get("port", 81))