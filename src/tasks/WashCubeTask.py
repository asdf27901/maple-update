import ctypes
from typing import Optional, Any, Generator, Tuple

from ok.__init__ import Box
from qfluentwidgets import FluentIcon
from ok.feature.Box import find_boxes_within_boundary

from src.tasks.MyBaseTask import MyBaseTask


class WashCubeTask(MyBaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "点我洗附加潜能"
        self.description = "展开配置项进行配置"
        self.icon = FluentIcon.CLOUD
        self.default_config.update({
            '魔方类型': [],
            '期望属性': [],
            '结果类型': [],
            '需要洗的装备件数': 1,
            '速率因子': 1.0
        })
        self.config_type["魔方类型"] = {'type': "multi_selection",
                                        'options': ['Precious cube', 'Absolute cube', 'Restore cube']}
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
        self.config_description.update({
            "魔方类型": "魔方会在已选中进行选择，\n优先珍贵附加魔方，如果都没有了则脚本结束",
            "需要洗的装备件数": "会根据输入数量生成n*4的矩阵\n例如输入：11，生成如下：\n□ □ □ □\n□ ■ □ □\n□ □ ■\n只会找其中有颜色的格子洗",
            "速率因子": "用于控制洗魔方速度，越小速率越快，建议值：1"
        })

        self.rate = 1

    def run(self) -> None:

        self._check_init()

        # 校验任务配置
        if not self.config['魔方类型'] \
                or not self.config['期望属性'] \
                or not self.config['结果类型']:
            self.notification("没有勾选任务配置，执行失败")
            return

        if self.config['需要洗的装备件数'] <= 0 or self.config['需要洗的装备件数'] > 28:
            self.notification("输入装备件数有误，任务无法执行")
            return

        self.open_wash_block()

        if self.check_switch():
            raise RuntimeError('没有关闭强化动画，先关闭再运行任务')

        self.sleep(0.5)
        self.click_relative(0.053, 0.615, key='left')
        self.sleep(0.5)


        # 第一个装备格子相对坐标: x=0.435, y=0.194, to_x=0.465, to_y=0.243
        slot_w = 0.030  # 0.465 - 0.435
        slot_h = 0.049  # 0.243 - 0.194
        # 格子间距 (实测中心到中心: y方向 0.276-0.220=0.056)
        step_x = 0.034  # 水平间距
        step_y = 0.060  # 垂直间距

        equ_boxes = (Box(
            x=int(self.width * (0.435 + (i % 4) * step_x)),
            y=int(self.height * (0.194 + (i // 4) * step_y)),
            width=int(self.width * slot_w),
            height=int(self.height * slot_h)
        ) for i in range(self.config['需要洗的装备件数'] or 1))
        
        try:
            self.wash_equipments(boxes=equ_boxes)
        except StopIteration:
            self.log_info("没有装备可以洗了")


    def wash_equipments(self, boxes: Generator):
        """
        洗装备逻辑
        Args:
            boxes:
            apd_box:
        Returns:
        """
        # 获取期望使用的魔方
        cubes = self.config["魔方类型"]
        equ_box = next(boxes)

        # 先找魔方，如果魔方都没，直接拜拜
        for cube in cubes:
            cube_box = self.find_one(feature_name=cube, vertical_variance=0.1, horizontal_variance=0.25)
            if cube_box is None:
                self.log_error(f"没有找到{cube}")
                continue

            # 根据灰度占比判断是否有装备放置
            while self.check_rgc_percentage(r=(200, 229), g=(200, 229), b=(200, 229), box=equ_box):
                # 进入此方法说明灰度占比超过80%，说明此时equ_box没有装备占用，调用生成器对象
                equ_box = next(boxes)

            # 说明已经找到了装备，那么就先选中魔方和装备
            self.select_cube_and_equ(cube_box, equ_box)
            just_switched = True  # 刚切换装备，首次只需按2下空格

            while True:
                # 按下空格开始洗（所有魔方至少按2下）
                self.send_key('space')
                self.sleep(0.4 * self.rate)
                self.send_key('space')
                self.sleep(0.4 * self.rate)
                # 记忆魔方：切换装备后首次按2下，之后每次按3下
                if cube == 'Restore cube' and not just_switched:
                    self.send_key('space')
                    self.sleep(0.4 * self.rate)
                just_switched = False
                self.sleep(0.5)
                flag = self.find_dialog()

                if flag:
                    self.send_key('esc')
                    self.log_info('识别到弹窗，按下esc')
                    self.sleep(0.5)
                    continue

                self.sleep(1 * self.rate)
                res = self.check_wash_result(is_memory=cube == 'Restore cube')

                if cube != 'Restore cube':
                    cube_box = self.find_one(
                        feature_name=cube,
                        vertical_variance=0.1,
                        horizontal_variance=0.25,
                        threshold=0.7  # 选中会出现蓝色背景，降低置信度
                    )
                else:
                    all_boxes = self.ocr(threshold=0.7)
                    boundary = self.box_of_screen(0.348, 0.816, 0.400, 0.891)
                    num_boxes = find_boxes_within_boundary(all_boxes, boundary)
                    cube_box = cube_box if num_boxes[0].name != '0' else None

                if res:
                    self.log_info("当前装备洗成功，切换下一个")
                    if cube == 'Restore cube':
                        # 防止没有点击成功，多点几次
                        self.click_relative(0.583, 0.492, key='left')
                        self.click_relative(0.583, 0.492, key='left')
                        self.click_relative(0.583, 0.492, key='left')
                        # 由于有渐变动画，需要等待，长时间等待
                        self.sleep(4)
                    equ_box = next(boxes)

                    # 检查新装备是否为空位
                    while self.check_rgc_percentage(r=(200, 229), g=(200, 229), b=(200, 229), box=equ_box):
                        equ_box = next(boxes)

                    self.select_cube_and_equ(cube_box, equ_box)
                    just_switched = True  # 切换了装备，重置标记
                    self.sleep(0.5)

                if cube_box:
                    self.click(cube_box)
                    self.sleep(0.5)
                    self.click(cube_box)
                    self.click_relative(0.053, 0.615, key='left')
                else:
                    self.log_info(f"{cube} 用完了，尝试下一种魔方")
                    if cube == 'Restore cube':
                        self.click_relative(0.410, 0.474, key='left')
                        self.click_relative(0.410, 0.474, key='left')
                        self.click_relative(0.410, 0.474, key='left')
                        # 由于有渐变动画，需要等待，长时间等待
                        self.sleep(4)
                    break

    def select_cube_and_equ(self, cube_box: Box, equ_box: Box):
        # 选中魔方
        self.click(cube_box)
        self.click(cube_box)

        self.sleep(0.5)

        # 右键选中装备
        self.right_click(equ_box)
        self.sleep(0.1)
        self.right_click(equ_box)
        self.sleep(0.1)
        self.right_click(equ_box)
        self.sleep(0.1)
        self.click_relative(0.529, 0.021, key='left')

    def check_wash_result(self, is_memory: bool = False) -> bool:

        if is_memory:
            results = self.cube_result_ocr(0.500, 0.410, 0.681, 0.544)
        else:
            results = self.cube_result_ocr(0.192, 0.409, 0.357, 0.514)

        if '测试' in "".join(self.config['期望属性']):
            return True

        # 将获取结果组装成列表传入
        lines = [r.encode('gbk') for r in results[:3]]
        res = self.get_result_from_washcube_dll(lines, expect_attr=self.config['期望属性'], expect_type=self.config['结果类型'])

        return res

    def get_result_from_washcube_dll(self, lines: list[bytes], expect_attr: list[str], expect_type: list[str]) -> bool:
        res_ptr: str = ctypes.cast(self.check_func(*lines), ctypes.c_char_p).value.decode('utf-8')

        self.info_set("dll返回结果为", res_ptr)

        if '垃圾' in res_ptr:
            return False

        res_l = res_ptr.split('|')
        res_type = res_l[0]
        res_attr = res_l[1]
        attr_num = res_l[2]
        extra_attr = res_l[3]

        if res_type not in expect_type:
            return False

        if res_attr not in "".join(expect_attr):
            return False

        # 如果是暴伤或者冷却，那么判断是否符合词条数目
        if res_attr in ['爆伤', '冷却'] \
                and (attr_num + res_attr) not in "".join(expect_attr) \
                or (extra_attr != '未知' and extra_attr not in expect_attr):
            return False

        return True

    def validate_config(self, key: str, value: Any) -> Optional[str]:
        """
        用于校验当前任务配置是否正确
        Args:
            key:
            value:
        Returns:
        """
        if key == "魔方类型" and not value:
            self.log_error("没有勾选魔方类型，任务无法执行")
            return "没有勾选魔方类型，任务无法执行"
        if key == "期望属性" and not value:
            self.log_error("没有勾选期望属性，任务无法执行")
            return "没有勾选期望属性，任务无法执行"
        if key == "结果类型" and not value:
            self.log_error("没有勾选结果类型，任务无法执行")
            return "没有勾选结果类型，任务无法执行"
        if key == "需要洗的装备件数" and (not value or value <= 0 or value > 28):
            self.log_error("输入装备件数有误，任务无法执行")
            return "输入装备件数有误，任务无法执行"
