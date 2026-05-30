import re
from typing import Generator, List, Tuple

import cv2

from ok import Box, find_boxes_within_boundary
from qfluentwidgets import FluentIcon

from src.tasks.MyBaseTask import MyBaseTask, ATTR_PATTERNS


class WashFireTask(MyBaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "自动洗火花"
        self.description = "展开配置项进行配置"
        self.icon = FluentIcon.CLOUD
        self.default_config.update({
            '火花类型': [],
            '期望属性': [],
            '装备等级': '160',
            '需要洗的装备件数': 1,
            '速率因子': 1.0
        })
        self.config_type["火花类型"] = {'type': "multi_selection",
                                        'options': ['WHITEFIRE', 'COLORFIRE', 'BLACKFIRE']}
        self.config_type['期望属性'] = {'type': 'multi_selection',
                                        'options': ['STR', 'DEX', 'INT', 'LUK', '测试']}
        self.config_type['装备等级'] = {'type': 'drop_down',
                                        'options': ['160', '200', '250']}
        self.config_description.update({
            "火花类型": "火花会在已选中进行选择，\n顺序为：白火->彩火->黑火，如果都没有了则脚本结束",
            "装备等级": "根据装备等级决定期望火花分值阈值：\n160级->150分, 200级->170分, 250级->190分\n（按照物理/魔法攻击力=2, 1%ALL=10, 1att=1计算，达到阈值则保留）",
            "需要洗的装备件数": "会根据输入数量生成n*4的矩阵\n例如输入：11，生成如下：\n□ □ □ □\n□ ■ □ □\n□ □ ■\n只会找其中有颜色的格子洗",
            "速率因子": "用于控制洗魔方速度，越小速率越快，建议值：1"
        })

        self.rate = 1

    def run(self) -> None:

        # 校验任务配置
        if not self.config['火花类型'] \
                or not self.config['期望属性']:
            self.notification("没有勾选任务配置，执行失败")
            return

        if self.config['需要洗的装备件数'] <= 0 or self.config['需要洗的装备件数'] > 28:
            self.notification("输入装备件数有误，任务无法执行")
            return

        self.open_wash_block()

        if self.check_switch():
            raise RuntimeError('没有关闭强化动画，先关闭再运行任务')

        self.sleep(0.5)
        self.click_relative(0.053, 0.374, key='left')
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
        # 获取期望使用的火花
        fires = self.config["火花类型"]
        equ_box = next(boxes)

        # 先找火花，如果火花都没，直接拜拜
        for fire in fires:
            fire_box = self.find_one(feature_name=fire, vertical_variance=0.1, horizontal_variance=0.25, threshold=0.9)
            if fire_box is None:
                self.log_error(f"没有找到{fire}")
                continue

            # 根据灰度占比判断是否有装备放置
            while self.check_rgc_percentage(r=(200, 229), g=(200, 229), b=(200, 229), box=equ_box):
                # 进入此方法说明灰度占比超过80%，说明此时equ_box没有装备占用，调用生成器对象
                equ_box = next(boxes)

            # 说明已经找到了装备，那么就先选中火花和装备
            self.select_fire_and_equ(fire_box, equ_box)
            just_switched = True  # 刚切换装备，首次只需按2下空格

            while True:
                # 按下空格开始洗（所有火花至少按2下）
                self.send_key('space')
                self.sleep(0.4 * self.rate)
                self.send_key('space')
                self.sleep(0.4 * self.rate)
                # 黑火：切换装备后首次按2下，之后每次按3下
                if fire == 'BLACKFIRE' and not just_switched:
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
                res = self.check_wash_result(is_memory=fire == 'BLACKFIRE')

                if fire != 'BLACKFIRE':
                    fire_box = self.find_one(
                        feature_name=fire,
                        vertical_variance=0.1,
                        horizontal_variance=0.25,
                        threshold=0.9
                    )
                else:
                    all_boxes = self.ocr(threshold=0.7)
                    boundary = self.box_of_screen(0.348, 0.816, 0.400, 0.891)
                    num_boxes = find_boxes_within_boundary(all_boxes, boundary)
                    fire_box = fire_box if num_boxes[0].name != '0' else None

                if res:
                    self.log_info("当前装备洗成功，切换下一个")
                    if fire == 'BLACKFIRE':
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

                    self.select_fire_and_equ(fire_box, equ_box)
                    just_switched = True  # 切换了装备，重置标记
                    self.sleep(0.5)

                if fire_box:
                    self.click(fire_box)
                    self.sleep(0.5)
                    self.click(fire_box)
                    self.click_relative(0.053, 0.374, key='left')
                else:
                    self.log_info(f"{fire} 用完了，尝试下一种火花")
                    if fire == 'BLACKFIRE':
                        self.click_relative(0.410, 0.474, key='left')
                        self.click_relative(0.410, 0.474, key='left')
                        self.click_relative(0.410, 0.474, key='left')
                        # 由于有渐变动画，需要等待，长时间等待
                        self.sleep(4)
                    break


    def select_fire_and_equ(self, fire_box: Box, equ_box: Box):
        # 选中火花
        self.click(fire_box)
        self.click(fire_box)

        self.sleep(0.5)

        # 右键选中装备
        self.right_click(equ_box)
        self.sleep(0.1)
        self.right_click(equ_box)
        self.sleep(0.1)
        self.right_click(equ_box)
        self.sleep(0.4)
        self.click_relative(0.529, 0.021, key='left')

    def check_wash_result(self, is_memory: bool = False) -> bool:

        if is_memory:
            all_results, results = self.fire_result_ocr(0.511, 0.432, 0.667, 0.624)
        else:
            all_results, results = self.fire_result_ocr(0.163, 0.341, 0.341, 0.544)

        if '测试' in "".join(self.config['期望属性']):
            return True

        # 解析每条属性的数值
        parsed = {}
        for r in results:
            m = re.match(r'^(.+?)([+-]\d+)(%?)$', r)
            if m:
                name = m.group(1)
                val = int(m.group(2))
                is_percent = m.group(3) == '%'
                parsed[name] = (val, is_percent)

        # 取出公共属性
        all_stat_val = parsed.get('全属性', (0, True))[0]  # 全属性+X%
        atk_val = parsed.get('攻击力', (0, False))[0]       # 物理攻击力
        matk_val = parsed.get('魔法攻击力', (0, False))[0]  # 魔法攻击力

        equ_level = int(self.config.get('装备等级', 160))
        target, max_score = self._level_params(equ_level)
        desired = self.config.get('期望属性', [])

        # 预计算所有期望属性分值
        attr_scores = {}
        for attr in desired:
            main_val = parsed.get(attr, (0, False))[0]
            atk = matk_val if attr == 'INT' else atk_val
            attr_scores[attr] = main_val + all_stat_val * 10 + atk * 2

        if any(s > max_score for s in attr_scores.values()):
            return False

        #更新 UI 并打印本轮 OCR 识别结果（过滤前全部属性）
        for i, res in enumerate(all_results):
            self.info_set(key=f"第{i + 1}条属性", value=res)
        self.log_info('洗出的属性为：\n' + '\n'.join(f'第{i + 1}条：{r}' for i, r in enumerate(all_results)))

        for attr in desired:
            score = attr_scores[attr]
            main_val = parsed.get(attr, (0, False))[0]
            atk = matk_val if attr == 'INT' else atk_val
            self.log_info(f" {attr} 分值: {main_val}(主) + {all_stat_val}*10(ALL%) + {atk}*2(攻击) = {score}")
            if score >= target:
                self.log_info(f" {attr} 分值 {score} >= {target}，保留！")
                return True

        return False

    def fire_result_ocr(self, x: float, y: float, to_x: float, to_y: float) -> Tuple[List[str], List[str]]:
        # 裁剪 + 二值化（不放大），提升小字对比度
        cropped_boxes = self._ocr_enlarged(x, y, to_x, to_y, scale=1, threshold=0)
        merged_lines = self._merge_same_line_boxes(cropped_boxes)

        results = []
        # 记录每行最右侧 box 的位置，用于缺值时针对性放大
        line_right_edges = []
        if cropped_boxes:
            sorted_boxes = sorted(cropped_boxes, key=lambda b: b.y)
            lines_raw = []
            current = [sorted_boxes[0]]
            for box in sorted_boxes[1:]:
                if abs(box.y - current[0].y) <= 10:
                    current.append(box)
                else:
                    lines_raw.append(current)
                    current = [box]
            lines_raw.append(current)
            for line in lines_raw:
                line.sort(key=lambda b: b.x)
                # 记录这一行第一个 box 的右边界（属性名右侧开始找数值）
                first = line[0]
                line_right_edges.append(first.x + first.width)

        for line_text in merged_lines:
            results.append(self.parse_attr(line_text))

        attr_names = [p[1] for p in ATTR_PATTERNS]

        # 对缺少数值的属性，针对性放大其右侧区域补值
        frame = self.executor.frame
        fh, fw = frame.shape[:2]
        crop_x1, crop_y1 = int(fw * x), int(fh * y)

        kept_prefixes = ('STR', 'DEX', 'INT', 'LUK', '全属性', '攻击力', '魔法攻击力')
        for i, r in enumerate(results):
            if re.search(r'\d', r):
                continue  # 已有数值，跳过
            if not r.startswith(kept_prefixes):
                continue  # 非关注属性，跳过补值
            # 这个属性没有数值，尝试放大其右侧
            if i < len(line_right_edges):
                # 右侧起点（裁剪区域内坐标）
                right_x = line_right_edges[i]
                # 转为全屏坐标，取右侧一小块区域
                abs_x = crop_x1 + max(0, right_x)
                abs_y = crop_y1 + lines_raw[i][0].y
                abs_x2 = min(abs_x + 60, int(fw * to_x))  # 只取属性名右侧60px
                abs_y2 = abs_y + lines_raw[i][0].height

                # 裁剪并放大右侧区域
                strip = frame[max(0,abs_y):min(fh,abs_y2), max(0,abs_x):min(fw,abs_x2)]
                if strip.size > 0:
                    self.log_info(f"补值裁剪区域: ({abs_x},{abs_y})->({abs_x2},{abs_y2}), strip大小: {strip.shape}")
                    # 多种预处理尝试
                    attempts = []
                    # 1. 原图放大8倍
                    e1 = cv2.resize(strip, None, fx=8, fy=8, interpolation=cv2.INTER_LANCZOS4)
                    attempts.append(cv2.copyMakeBorder(e1, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(0,0,0)))
                    # 2. 原图放大12倍
                    e2 = cv2.resize(strip, None, fx=12, fy=12, interpolation=cv2.INTER_LANCZOS4)
                    attempts.append(cv2.copyMakeBorder(e2, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(0,0,0)))
                    # 3. 二值化反色放大8倍（黑字白底）
                    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
                    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                    e3 = cv2.resize(cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR), None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
                    attempts.append(cv2.copyMakeBorder(e3, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(255,255,255)))
                    best_val = None
                    for attempt_idx, img in enumerate(attempts):
                        if best_val:
                            break
                        value_boxes = self.ocr(frame=img, threshold=0)
                        # 优先取带 +/- 前缀的数值
                        for vb in value_boxes:
                            vm = re.search(r'([+-]\d+[%]?)', vb.name)
                            if vm:
                                best_val = vm.group(1)
                                break
                        # +5 常被误读为 +a/+s/+S
                        if not best_val:
                            for vb in value_boxes:
                                fixed = vb.name.replace('a', '5').replace('s', '5').replace('S', '5')
                                vm = re.search(r'([+-]\d+[%]?)', fixed)
                                if vm:
                                    best_val = vm.group(1)
                                    break
                        # 只检测到纯数字（无+/-前缀），默认加+
                        if not best_val:
                            for vb in value_boxes:
                                vm = re.search(r'(\d+)', vb.name)
                                if vm:
                                    best_val = '+' + vm.group(1)
                                    break
                    if best_val:
                        results[i] = f"{r}{best_val}"
                    else:
                        # 兜底：缺值基本都是+5
                        default_val = '+5%' if r == '全属性' else '+5'
                        results[i] = f"{r}{default_val}"
                        self.log_info(f"补值 OCR 所有尝试均失败，使用默认值: {results[i]}")


        kept_prefixes = ('STR', 'DEX', 'INT', 'LUK', '全属性', '攻击力', '魔法攻击力')
        filtered = [r for r in results if r.startswith(kept_prefixes)]
        return results, filtered

    def _level_params(self, level: int) -> Tuple[int, int]:
        _t = {160: 150, 200: 170, 250: 190}
        _m = {160: 160, 200: 180, 250: 200}
        return _t.get(level, 150), _m.get(level, 160)