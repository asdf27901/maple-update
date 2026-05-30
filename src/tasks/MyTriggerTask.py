import pyttsx3

from ok import TriggerTask
from src.enums.LabelEnum import LabelEnum


class MyTriggerTask(TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "光柱检测"
        self.description = "检测游戏画面中是否出现光柱，出现则语音提醒"

    def run(self):
        self.log_info('正在寻找是否有光柱~')
        light1 = self.find_one(LabelEnum.LIGHT1, horizontal_variance=1.0, vertical_variance=1.0)
        light2 = self.find_one(LabelEnum.LIGHT2, horizontal_variance=1.0, vertical_variance=1.0)

        if light1 or light2:
            found = []
            if light1:
                found.append('LIGHT1')
            if light2:
                found.append('LIGHT2')
            self.log_info(f'检测到光柱特征: {", ".join(found)}')

            engine = pyttsx3.init()
            for _ in range(2):
                engine.say("出现了光柱，请查看！")
            engine.runAndWait()
            engine.stop()
