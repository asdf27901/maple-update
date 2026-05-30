from src.enums.LabelEnum import LabelEnum
from src.tasks.MyBaseTask import MyBaseTask
from qfluentwidgets import FluentIcon


class CheckImproveTask(MyBaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "校验黑火是否有提升"
        self.description = "需要你自己手动打开洗火栏位，并选中装备，然后开始\n 洗火窗口必须贴近窗口左上角"
        self.icon = FluentIcon.CLOUD

    def run(self) -> None:
        # 识别是否存在 blackfire
        blackfire_box = self.find_one(feature_name=LabelEnum.BLACKFIRE, vertical_variance=0.1, horizontal_variance=0.25, threshold=0.9)
        if blackfire_box is None:
            self.notification("未识别到 blackfire，请重新打开洗火栏位")
            return
        # 点击 blackfire
        self.click(blackfire_box)
        self.click(blackfire_box)

        # 之后进入死循环开始洗火，如果是首次洗，先按两下空格，之后每次按三下空格
        just_switched = True
        while True:
            self.send_key('space')
            self.sleep(0.4)
            self.send_key('space')
            self.sleep(0.4)
            if just_switched:
                just_switched = False
            else:
                self.send_key('space')
                self.sleep(0.4)

            self.click_relative(0.1, 0.1, key='left')

            # 识别弹窗
            flag = self.find_dialog()

            if flag:
                self.send_key('esc')
                self.log_info('识别到弹窗，按下esc')
                self.sleep(0.5)
                continue

            self.sleep(1)
            
            # 检查是否有IMPROVE特征
            improve_box = self.find_one(feature_name=LabelEnum.IMPROVE, threshold=0.7)
            if improve_box:
                self.log_info("识别到洗出了更好的火，收下！")
                 # 防止没有点击成功，多点几次
                self.click_relative(0.583, 0.492, key='left')
                self.click_relative(0.583, 0.492, key='left')
                self.click_relative(0.583, 0.492, key='left')
                break