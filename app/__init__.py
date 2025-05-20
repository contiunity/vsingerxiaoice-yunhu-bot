from app.intellgence import IntellgenceApp
from app.memory import MemoryApp
from app.restful import RestfulApp
from app.yunhu import YunhuApp

class CoreApp:
    def __init__(self, config: dict):
        self.memory: MemoryApp = MemoryApp(config)
        self.intellgence: IntellgenceApp = IntellgenceApp(config, self.memory)
        self.restful: RestfulApp = RestfulApp(config)
        self.yunhu: YunhuApp = YunhuApp(config, self.intellgence, self.restful)
    def startService(self):
        self.restful.startService()