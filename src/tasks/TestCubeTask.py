import ctypes

from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask


class TestCubeTask(MyBaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = FluentIcon.ROBOT
        self.name = "用于测试执行结果，不会洗魔方"
        self.description = "需要打开洗魔方界面，并把装备放入，选择附加潜能"
        self.default_config.update({
            "第一条测试属性": "物理攻击力+12%",
            "第二条测试属性": "物理攻击力+12%",
            "第三条测试属性": "物理攻击力+12%",
            '期望属性': [],
            '结果类型': [],
            "是否循环执行": True
        })

        self.config_type['期望属性'] = {'type': 'multi_selection',
                                        'options': [
                                            '物攻', '魔攻',
                                            '力量', '敏捷', '智力', '运气', '血量', '全属性',
                                            '1爆伤(需要勾选上方属性)', '2爆伤(需要勾选上方属性)', '3爆伤(需要勾选上方属性)',
                                            '1冷却(需要勾选上方属性)', '2冷却(需要勾选上方属性)', '3冷却(需要勾选上方属性)',
                                            '测试(勾选了之后洗一下就换装备)'
                                        ]}
        self.config_type['结果类型'] = {'type': 'multi_selection',
                                        'options': ["大大大", "大大小"]}

    def run(self) -> None:
        if not self.check_func:
            self._load_dll()

        while True:
            # 使用全屏 OCR + 正则解析（与 WashCubeTask 一致）
            results = self.cube_result_ocr(0.192, 0.409, 0.357, 0.514)

            ocr_res1, ocr_res2, ocr_res3 = results[0], results[1], results[2]

            # 校验 OCR 识别结果是否与期望一致
            res1 = ocr_res1 == self.config["第一条测试属性"]
            res2 = ocr_res2 == self.config["第二条测试属性"]
            res3 = ocr_res3 == self.config["第三条测试属性"]

            self.info_set(key="第一条属性测试结果", value=res1)
            self.info_set(key="第二条属性测试结果", value=res2)
            self.info_set(key="第三条属性测试结果", value=res3)

            # 调用 DLL 校验
            lines = [r.encode('gbk') for r in results[:3]]
            res_ptr: str = ctypes.cast(
                self.check_func(*lines), ctypes.c_char_p
            ).value.decode('utf-8')

            self.info_set("dll输出结果为", res_ptr)

            if '垃圾' in res_ptr:
                self.info_set(key="dll校验结果", value="垃圾")
            else:
                res_l = res_ptr.split('|')
                res_type = res_l[0]
                res_attr = res_l[1]
                attr_num = res_l[2]
                extra_attr = res_l[3]

                if res_type not in self.config['结果类型']:
                    self.info_set(key="期望结果类型不一致", value=f"结果类型为: {res_type}")

                if res_attr not in "".join(self.config['期望属性']):
                    self.info_set(key=f"洗的出属性：{res_attr}", value="不在期望属性中")

                if res_attr in ['爆伤', '冷却'] \
                        and (attr_num + res_attr) not in "".join(self.config['期望属性']) \
                        or (extra_attr != '未知' and extra_attr not in self.config['期望属性']):
                    self.info_set(key=f"洗的出属性：{attr_num + res_attr + extra_attr}", value="不在期望属性中")

            # 显示不一致的识别结果
            if not res1 or not res2 or not res3:
                self.info_set(key="第一条识别结果", value=ocr_res1)
                self.info_set(key="第二条识别结果", value=ocr_res2)
                self.info_set(key="第三条识别结果", value=ocr_res3)
                break

            if not self.config["是否循环执行"]:
                break

            self.sleep(0.5)
