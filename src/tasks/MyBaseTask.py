import ctypes
import os
import re
from typing import List, Tuple

import cv2

from ok import BaseTask
from ok.feature.Box import find_boxes_within_boundary, Box
from src.enums.LabelEnum import LabelEnum

# OCR 结果正则匹配
ATTR_PATTERNS = [
    (re.compile(r'[物勿][里理]攻.{0,2}力'), '物理攻击力'),
    (re.compile(r'[磨麽魔][法去]攻.{0,2}力'), '魔法攻击力'),
    (re.compile(r'攻.{0,2}力'), '攻击力'),
    (re.compile(r'[暴爆].{0,3}害'), '暴击伤害'),
    (re.compile(r'全[属屬国座厨]?.{0,1}性'), '全属性'),
    (re.compile(r'技能冷卻[時时]間'), '技能冷却时间'),
    (re.compile(r'跳[躍跃].{0,1}力'), '跳跃力'),
    (re.compile(r'移[動动].{0,2}度'), '移动速度'),
    (re.compile(r'防[禦御].{0,1}力'), '防御力'),
    (re.compile(r'[装裝].{0,2}[等級级].{0,2}[减減]'), '装备等级减少'),
    (re.compile(r'最大[HI][PM]'), '最大HP'),
    (re.compile(r'MaxHP'), 'MaxHP'),
    (re.compile(r'STR'),  'STR'),
    (re.compile(r'DEX'),  'DEX'),
    (re.compile(r'INT'),  'INT'),
    (re.compile(r'LUK'),  'LUK')
]

# OCR 常见误识别修正
OCR_FIXES = {
    'IHT': 'INT',
    '1NT': 'INT',
    'lNT': 'INT',
    'IIT': 'INT',
    'IT': 'INT',
    'IMT': 'INT',
    'IRT': 'INT',
    'DEK': 'DEX',
    'DE+': 'DEX+',
    'LUx': 'LUK',
    'LJK': 'LUK',
    'STl': 'STR',
    '5TR': 'STR',
    'Max}P': 'MaxHP',
    'MaxlCP': 'MaxHP',
    'Max)P': 'MaxHP',
    'axHP': 'MaxHP',
}


class MyBaseTask(BaseTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.check_func = None

    def _check_init(self):
        if not self.check_func:
            self._load_dll()

        self.log_info(f"任务执行配置为：{self.config}")
        self.rate = self.config['速率因子']
        self.log_info(f"配置速率因子为: {self.config['速率因子']}")

    def check_switch(self) -> bool:
        return True if self.find_one(LabelEnum.SWITCH) else False

    def _load_dll(self):
        root_path = self.executor.config["project_root"]
        # 加载dll
        dll_path = os.path.join(root_path, 'src', 'libcube64.dll')
        lib = ctypes.CDLL(dll_path)

        self.check_func = lib['?washcube@@YAPEADPEBD00@Z']
        self.check_func.restype = ctypes.c_char_p
        self.check_func.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]

    def parse_attr(self, text: str) -> str:
        """解析单条潜能文本，修正 OCR 误识别并提取属性名+数值"""
        text = text.replace(' ', '')
        for wrong, right in OCR_FIXES.items():
            text = text.replace(wrong, right)
        for pattern, name in ATTR_PATTERNS:
            m = pattern.search(text)
            if m:
                after = text[m.end():]
                vm = re.search(r'([+-]?\d+[%秒]?)', after)
                value = vm.group(1) if vm else ''
                if value and not value.startswith(('+', '-')):
                    value = '+' + value
                # 修正前导0误读：游戏数值不会有前导零，0多为8的误识别
                leading_zero = re.match(r'([+-])0(\d+)', value)
                if leading_zero:
                    value = f"{leading_zero.group(1)}8{leading_zero.group(2)}"
                return f"{name}{value}"
        return text

    @staticmethod
    def _merge_same_line_boxes(boxes, y_tolerance=10):
        """将 Y 坐标相近的 OCR box 合并为同一行文本"""
        if not boxes:
            return []
        # 按 Y 排序
        sorted_boxes = sorted(boxes, key=lambda b: b.y)
        lines = []
        current_line = [sorted_boxes[0]]

        for box in sorted_boxes[1:]:
            # 判断是否在同一行（Y 坐标差值在容差内）
            if abs(box.y - current_line[0].y) <= y_tolerance:
                current_line.append(box)
            else:
                lines.append(current_line)
                current_line = [box]
        lines.append(current_line)

        # 每行按 X 排序后拼接文本
        merged = []
        for line in lines:
            line.sort(key=lambda b: b.x)
            text = ''.join(b.name for b in line)
            merged.append(text)
        return merged

    def _ocr_enlarged(self, x, y, to_x, to_y, scale=3, threshold=0.5):
        """裁剪指定区域，灰度+二值化+放大后 OCR，用于检测小字（如个位数）"""
        frame = self.executor.frame
        h, w = frame.shape[:2]
        x1, y1 = int(w * x), int(h * y)
        x2, y2 = int(w * to_x), int(h * to_y)
        cropped = frame[y1:y2, x1:x2]
        # 灰度 + 二值化，让小字更清晰
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # 转回3通道（OCR模型需要）
        binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        enlarged = cv2.resize(binary_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        return self.ocr(frame=enlarged, threshold=threshold)

    def cube_result_ocr(self, x: float, y: float, to_x: float, to_y: float, max_retries: int = 3) -> List[str]:
        """全屏 OCR 识别后过滤潜能区域，返回解析后的属性列表"""
        boundary = self.box_of_screen(x, y, to_x, to_y)

        for attempt in range(max_retries):
            all_boxes = self.ocr(threshold=0.6)
            potential_boxes = find_boxes_within_boundary(all_boxes, boundary)

            # 合并同一行的 box（防止 OCR 将一行拆成多个 box）
            merged_lines = self._merge_same_line_boxes(potential_boxes)

            results = []
            for line_text in merged_lines:
                results.append(self.parse_attr(line_text))

            if len(results) >= 3:
                break

            if attempt < max_retries - 1:
                self.log_info(f"OCR 只识别到 {len(results)} 条，重试第 {attempt + 2} 次...")
                self.sleep(0.3)

        # 补齐到3条
        while len(results) < 3:
            results.append("没有识别到结果")

        for i, res in enumerate(results[:3]):
            self.info_set(key=f"第{i+1}条属性", value=res)

        self.log_info('洗出的属性为：\n' + '\n'.join(f'第{i+1}条：{r}' for i, r in enumerate(results[:3])))
        return results[:3]

    def _drag_to_target(self, feature, target_rx, target_ry, duration=3, tolerance=3, max_retries=5):
        """将指定特征拖动到目标相对坐标位置，自动重试直到到位"""
        target_x = int(self.width * target_rx)
        target_y = int(self.height * target_ry)
        feature_name = feature.name if hasattr(feature, 'name') else str(feature)

        for _ in range(max_retries):
            cx, cy = feature.center()
            if abs(cx - target_x) <= tolerance and abs(cy - target_y) <= tolerance:
                self.log_info(f"{feature_name} 已到达目标位置 ({cx},{cy})")
                return feature
            self.log_info(f"{feature_name} 当前中心 ({cx},{cy})，目标 ({target_x},{target_y})，继续拖动")
            self.swipe(cx, cy, target_x, target_y, duration=duration)
            # 避免鼠标遮挡特征
            self.click_relative(0.405, 0.475, key='left')
            self.sleep(0.5)
            feature = self.find_one(feature_name, horizontal_variance=1.0, vertical_variance=1.0)
            if not feature:
                raise RuntimeError(f"拖动后没有找到{feature_name}特征")

        # 重试耗尽仍未到位
        cx, cy = feature.center()
        raise RuntimeError(
            f"{feature_name} 经过{max_retries}次拖动仍未到达目标位置，"
            f"当前 ({cx},{cy})，目标 ({target_x},{target_y})"
        )

    def open_wash_block(self) -> None:
        # 自动聚焦到游戏窗口
        self.ensure_in_front()
        self.sleep(0.5)

        self.click_relative(0.5, 0.5)
        self.sleep(1)

        for i in range(3):
            inventory = self.find_one(LabelEnum.INVENTORY, horizontal_variance=1.0, vertical_variance=1.0)
            if inventory:
                self.log_info("找到了INVENTORY特征")
                break
            self.send_key('i')
            self.sleep(i + 1)
        else:
            raise RuntimeError("没有找到INVENTORY特征")

        self._drag_to_target(inventory, 0.448, 0.151, duration=2)

        self.sleep(0.5)
        equipment = self.find_one(LabelEnum.EQUIPMENT, horizontal_variance=1.0, vertical_variance=1.0)
        if not equipment:
            raise RuntimeError("没有找到EQUIPMENT特征")
        self.log_info("找到了EQUIPMENT特征")
        self.click(equipment)

        self.sleep(0.5)
        enchant = self.find_one(LabelEnum.ENCHANT, horizontal_variance=1.0, vertical_variance=1.0)
        if not enchant:
            ex, ey = equipment.center()
            self.click(ex, ey)
            self.sleep(0.5)
            enchant = self.find_one(LabelEnum.ENCHANT, horizontal_variance=1.0, vertical_variance=1.0)
            if not enchant:
                raise RuntimeError("没有找到ENCHANT特征")

        self._drag_to_target(enchant, 0.029, 0.020, duration=5)

        self.sleep(0.5)

        inventory = self.find_one(LabelEnum.INVENTORY, horizontal_variance=1.0, vertical_variance=1.0)
        if not inventory:
            raise RuntimeError("没有找到INVENTORY特征")

        self._drag_to_target(inventory, 0.447, 0.021, duration=3)

    def check_rgc_percentage(
            self,
            r: Tuple[int, int], g: Tuple[int, int], b: Tuple[int, int],
            box: Box
    ) -> bool:
        """
        计算所选Box中灰度占比
        """
        rgb_p = self.calculate_color_percentage({'r': r, 'g': g, 'b': b}, box)
        return rgb_p > 0.8

    def find_dialog(self) -> bool:
        return self.check_rgc_percentage(
            r=(44, 44),
            g=(164, 164),
            b=(186, 186),
            box=self.box_of_screen(0.397, 0.467, to_x=0.400, to_y=0.474)
        )
