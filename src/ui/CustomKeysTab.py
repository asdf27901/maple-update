import time
from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QWidget, QTableWidgetItem, QHeaderView, QComboBox
)
from qfluentwidgets import (
    BodyLabel, FluentIcon, PushButton, PrimaryPushButton,
    DoubleSpinBox, SpinBox, SwitchButton, TableWidget, InfoBar, InfoBarPosition, SubtitleLabel, StrongBodyLabel
)

from ok.gui.widget.CustomTab import CustomTab
from src.tasks.CustomKeysTriggerTask import CustomKeysTriggerTask

class CustomKeysTab(CustomTab):

    def __init__(self, embed=False, task=None):
        super().__init__()
        self.embed = embed
        self._task = task  # 【防崩溃金刚防线】直接接收并持有外部传入的已就绪 task 实例！
        self.logger.info(f"CustomKeysTab init {self.__class__.__name__} (embed={embed})")
        self.icon = FluentIcon.ROBOT
        
        # 内嵌在卡片展开容器内时的黄金自适应布局调整！
        if self.embed:
            self.setContentsMargins(0, 0, 0, 0)
            if self.layout():
                self.layout().setContentsMargins(0, 0, 0, 0)
        self.icon = FluentIcon.ROBOT
        
        # Curated list of common keys for fast selection
        self.common_keys = [
            'space', 'enter', 'esc', 'tab', 'shift', 'ctrl', 'alt', 'backspace', 'delete', 
            'up', 'down', 'left', 'right', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
            'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
            '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'
        ]

        # 1. Title section
        self.title_label = SubtitleLabel("自定义按键连点")
        self.desc_label = BodyLabel("在下方配置多个按键连点计划。任务运行时，脚本将在前台游戏聚焦时循环按下这些按键，失焦自动静默避让。")
        self.desc_label.setStyleSheet("color: gray;")
        
        if not self.embed:
            self.add_widget(self.title_label)
            self.add_widget(self.desc_label)

        # 2. Add Key Control Panel (改为垂直主布局嵌套双水平行布局)
        self.form_layout = QVBoxLayout()
        self.form_layout.setSpacing(15)

        self.row1_layout = QHBoxLayout()
        self.row1_layout.setSpacing(20)

        self.row2_layout = QHBoxLayout()
        self.row2_layout.setSpacing(20)

        # Key Selector
        self.key_label = StrongBodyLabel("按键:")
        self.key_combo = QComboBox()
        self.key_combo.addItems(self.common_keys)
        self.key_combo.setEditable(True)
        self.key_combo.setCurrentIndex(0)
        self.key_combo.setMinimumWidth(120)

        # Interval Selector
        self.interval_label = StrongBodyLabel("按下间隔 (秒):")
        self.interval_spin = DoubleSpinBox()
        self.interval_spin.setRange(0.01, 3600.0)
        self.interval_spin.setValue(1.0)
        self.interval_spin.setSingleStep(0.1)
        self.interval_spin.setDecimals(2)
        self.interval_spin.setMinimumWidth(100)

        # Press Count Selector
        self.count_label = StrongBodyLabel("每次按下次数:")
        self.count_spin = SpinBox()
        self.count_spin.setRange(1, 999999)
        self.count_spin.setValue(1)
        self.count_spin.setMinimumWidth(100)
        
        # 每次敲击间隔（秒）选择器
        self.click_interval_label = StrongBodyLabel("敲击间隔 (秒):")
        self.click_interval_spin = DoubleSpinBox()
        self.click_interval_spin.setRange(0.01, 10.0)
        self.click_interval_spin.setValue(0.2)
        self.click_interval_spin.setSingleStep(0.05)
        self.click_interval_spin.setDecimals(2)
        self.click_interval_spin.setMinimumWidth(100)

        # 首次聚焦即发表单开关（默认开启）
        self.focus_label = StrongBodyLabel("首次聚焦即发:")
        self.focus_switch = SwitchButton()
        self.focus_switch.setOnText("是")
        self.focus_switch.setOffText("否")
        self.focus_switch.setChecked(True)
        self.focus_switch.setMinimumWidth(80)

        # Add Button
        self.add_btn = PrimaryPushButton("添加按键")
        self.add_btn.setIcon(FluentIcon.ADD)
        self.add_btn.clicked.connect(self.add_key_config)

        # 装配第一行 (参数配置区)
        self.row1_layout.addWidget(self.key_label)
        self.row1_layout.addWidget(self.key_combo)
        self.row1_layout.addWidget(self.interval_label)
        self.row1_layout.addWidget(self.interval_spin)
        self.row1_layout.addWidget(self.count_label)
        self.row1_layout.addWidget(self.count_spin)
        self.row1_layout.addStretch(1)

        # 装配第二行 (高级属性与动作触发区)
        self.row2_layout.addWidget(self.focus_label)
        self.row2_layout.addWidget(self.focus_switch)
        # ！！！敲击间隔优雅分流至第二行，享受无阻碍撑满舒展空间！！！
        self.row2_layout.addWidget(self.click_interval_label)
        self.row2_layout.addWidget(self.click_interval_spin)
        self.row2_layout.addStretch(1)  # 水平弹簧把主按钮优雅推向右侧
        self.row2_layout.addWidget(self.add_btn)

        # 装入垂直主表单
        self.form_layout.addLayout(self.row1_layout)
        self.form_layout.addLayout(self.row2_layout)

        self.add_card("添加连点配置", self.form_layout)

        # 3. Table of Key Configs (升级为8列以支持每次敲击间隔与聚焦即发)
        self.table = TableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "启用状态", "目标按键", "间隔 (秒)", "每次按下次数", "敲击间隔 (秒)", "首次聚焦即发", "已执行次数 (事件轮数)", "操作"
        ])
        
        # Style table headers nicely (混态黄金占满排布)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # 默认占满全屏，杜绝右侧虚无！
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)  # 启用状态固定
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)  # 目标按键固定 (短按键专用)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)  # 聚焦即发固定
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)  # 操作删除固定
        
        self.table.setColumnWidth(0, 70)   # 启用状态
        self.table.setColumnWidth(1, 110)  # 目标按键 (短按键固定110px足够)
        self.table.setColumnWidth(5, 90)   # 聚焦即发
        self.table.setColumnWidth(7, 100)  # 操作删除
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(350)
        
        # Actions bar below table
        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(10)
        
        self.enable_all_btn = PushButton("全部启用")
        self.enable_all_btn.clicked.connect(lambda: self.toggle_all_keys(True))
        
        self.disable_all_btn = PushButton("全部禁用")
        self.disable_all_btn.clicked.connect(lambda: self.toggle_all_keys(False))
        
        self.reset_btn = PrimaryPushButton("重置已执行次数")
        self.reset_btn.setIcon(FluentIcon.SYNC)
        self.reset_btn.clicked.connect(self.reset_counts)
        
        self.actions_layout.addWidget(self.enable_all_btn)
        self.actions_layout.addWidget(self.disable_all_btn)
        self.actions_layout.addStretch(1)
        self.actions_layout.addWidget(self.reset_btn)

        table_container_layout = QVBoxLayout()
        table_container_layout.addWidget(self.table)
        table_container_layout.addLayout(self.actions_layout)

        self.add_card("连点按键列表 (实时状态)", table_container_layout, stretch=1)

        # 4. Timer for refreshing executed count in real-time
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(200)  # Refresh every 200ms
        self.refresh_timer.timeout.connect(self.update_dynamic_stats)
        self.refresh_timer.start()  # 在构造函数内即刻安全启动，确保折叠展开全生命周期数据绝对动态刷新！

    @property
    def name(self):
        return "自定义连点"

    @property
    def add_after_default_tabs(self):
        return True

    def showEvent(self, event):
        super().showEvent(event)
        if event.type() == QEvent.Show:
            self.load_table_data()
            self.refresh_timer.start()
            self.logger.info("CustomKeysTab shown, refresh timer started")

    def hideEvent(self, event: QEvent):
        super().hideEvent(event)
        self.refresh_timer.stop()
        self.logger.info("CustomKeysTab hidden, refresh timer stopped")

    def get_trigger_task(self) -> CustomKeysTriggerTask:
        if not hasattr(self, '_task') or self._task is None:
            # 必须安全守卫：如果当前尚无 executor（例如在复杂的生命周期初始化早期），直接安稳返回 None！
            if not hasattr(self, 'executor') or self.executor is None:
                return None
            try:
                self._task = self.get_task(CustomKeysTriggerTask)
            except Exception:
                return None
        return self._task

    def load_table_data(self):
        """
        Populate the TableWidget rows from the task configuration.
        """
        task = self.get_trigger_task()
        if not task:
            return

        with task.lock:
            key_configs = list(task.config.get('_key_configs', []))

        self.table.setRowCount(0)
        self.table.setRowCount(len(key_configs))

        for row, key_cfg in enumerate(key_configs):
            cfg_id = key_cfg.get('id')
            key = key_cfg.get('key')
            interval = key_cfg.get('interval', 1.0)
            count = key_cfg.get('count', 1)
            enabled = key_cfg.get('enabled', False)
            trigger_on_focus = key_cfg.get('trigger_on_focus', True)
            click_interval = key_cfg.get('click_interval', 0.2)

            # Col 0: SwitchButton (启用状态)
            switch_btn = SwitchButton()
            switch_btn.setChecked(enabled)
            switch_btn.setOnText("")
            switch_btn.setOffText("")
            switch_btn.setProperty("cfg_id", cfg_id)
            switch_btn.checkedChanged.connect(self.make_toggle_handler(cfg_id))
            
            cell_widget = QWidget()
            cell_widget.setFixedHeight(50)
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(0)
            cell_layout.addWidget(switch_btn, 0, Qt.AlignCenter)
            self.table.setCellWidget(row, 0, cell_widget)

            # Col 1: Key (目标按键，下拉/键盘打字可实时更改，精致固定列宽！)
            key_combo = QComboBox()
            key_combo.addItems(self.common_keys)
            key_combo.setEditable(True)
            key_combo.setMinimumWidth(95)
            key_combo.setFixedWidth(95)
            key_combo.setCurrentText(str(key))
            key_combo.currentTextChanged.connect(self.make_key_change_handler(cfg_id))
            
            key_widget = QWidget()
            key_widget.setFixedHeight(50)
            key_layout = QHBoxLayout(key_widget)
            key_layout.setContentsMargins(0, 0, 0, 0)  # 边距归零，在固定110px格里吃满
            key_layout.setSpacing(0)
            key_layout.addWidget(key_combo)
            self.table.setCellWidget(row, 1, key_widget)

            # Col 2: Interval (间隔秒数，滚动滚轮可实时更改，彻底自适应拉伸！)
            interval_spin = DoubleSpinBox()
            interval_spin.setRange(0.01, 3600.0)
            interval_spin.setValue(interval)
            interval_spin.setSingleStep(0.1)
            interval_spin.setDecimals(2)
            interval_spin.setMinimumWidth(80)
            interval_spin.valueChanged.connect(self.make_interval_change_handler(cfg_id))
            
            interval_widget = QWidget()
            interval_widget.setFixedHeight(50)
            interval_layout = QHBoxLayout(interval_widget)
            interval_layout.setContentsMargins(5, 0, 5, 0)
            interval_layout.setSpacing(0)
            interval_layout.addWidget(interval_spin)
            self.table.setCellWidget(row, 2, interval_widget)

            # Col 3: Press Count (每次按下次数，微调可更改，彻底升级为大户自适应拉伸！)
            count_spin = SpinBox()
            count_spin.setRange(1, 999999)
            count_spin.setValue(max(1, count))
            count_spin.setMinimumWidth(80)
            count_spin.valueChanged.connect(self.make_count_change_handler(cfg_id))
            
            count_widget = QWidget()
            count_widget.setFixedHeight(50)
            count_layout = QHBoxLayout(count_widget)
            count_layout.setContentsMargins(5, 0, 5, 0)  # 弹性Stretch列，留出5像素边缘呼吸感！
            count_layout.setSpacing(0)
            count_layout.addWidget(count_spin)
            self.table.setCellWidget(row, 3, count_widget)

            # Col 4: click_interval DoubleSpinBox (敲击间隔秒数可调节，彻底自适应拉伸！)
            click_interval_spin = DoubleSpinBox()
            click_interval_spin.setRange(0.01, 10.0)
            click_interval_spin.setValue(click_interval)
            click_interval_spin.setSingleStep(0.05)
            click_interval_spin.setDecimals(2)
            click_interval_spin.setMinimumWidth(90)
            click_interval_spin.valueChanged.connect(self.make_click_interval_handler(cfg_id))
            
            click_interval_widget = QWidget()
            click_interval_widget.setFixedHeight(50)
            click_interval_layout = QHBoxLayout(click_interval_widget)
            click_interval_layout.setContentsMargins(5, 0, 5, 0)
            click_interval_layout.setSpacing(0)
            click_interval_layout.addWidget(click_interval_spin)
            self.table.setCellWidget(row, 4, click_interval_widget)

            # Col 5: Trigger on Focus Switch (聚焦即发单独控制)
            trigger_switch = SwitchButton()
            trigger_switch.setChecked(trigger_on_focus)
            trigger_switch.setOnText("")
            trigger_switch.setOffText("")
            trigger_switch.setProperty("cfg_id", cfg_id)
            trigger_switch.checkedChanged.connect(self.make_trigger_toggle_handler(cfg_id))
            
            trigger_widget = QWidget()
            trigger_widget.setFixedHeight(50)
            trigger_layout = QHBoxLayout(trigger_widget)
            trigger_layout.setContentsMargins(0, 0, 0, 0)
            trigger_layout.setSpacing(0)
            trigger_layout.addWidget(trigger_switch, 0, Qt.AlignCenter)
            self.table.setCellWidget(row, 5, trigger_widget)

            # Col 6: Dynamic Executed Count (已执行次数)
            runtime_state = task.runtime_state.get(cfg_id, {})
            current_count = runtime_state.get('pressed_count', 0)
            exec_item = QTableWidgetItem(str(current_count))
            exec_item.setTextAlignment(Qt.AlignCenter)
            exec_item.setFlags(exec_item.flags() & ~Qt.ItemIsEditable)
            exec_item.setData(Qt.UserRole, cfg_id)
            self.table.setItem(row, 6, exec_item)

            # Col 7: Delete button (操作删除)
            del_btn = PushButton("删除")
            del_btn.setIcon(FluentIcon.DELETE)
            del_btn.clicked.connect(self.make_delete_handler(cfg_id))
            
            del_widget = QWidget()
            del_widget.setFixedHeight(50)
            del_layout = QHBoxLayout(del_widget)
            del_layout.setContentsMargins(0, 0, 0, 0)
            del_layout.setSpacing(0)
            del_layout.addWidget(del_btn, 0, Qt.AlignCenter)
            self.table.setCellWidget(row, 7, del_widget)

    def update_dynamic_stats(self):
        """
        Dynamic QTimer handler to update execution counts from background task runtime state.
        """
        task = self.get_trigger_task()
        if not task:
            return

        with task.lock:
            # Create a quick local copy of the task's in-memory runtime counts
            counts_map = {cfg_id: state.get('pressed_count', 0) for cfg_id, state in task.runtime_state.items()}

        # Scan each row and update Column 6 item matching the cfg_id
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 6)
            if item:
                cfg_id = item.data(Qt.UserRole)
                if cfg_id:
                    current_val = counts_map.get(cfg_id, 0)
                    if item.text() != str(current_val):
                        item.setText(str(current_val))

    def make_toggle_handler(self, cfg_id):
        def handle_toggle(checked):
            task = self.get_trigger_task()
            if not task:
                return
            with task.lock:
                configs = list(task.config.get('_key_configs', []))
                for cfg in configs:
                    if cfg.get('id') == cfg_id:
                        cfg['enabled'] = checked
                        break
                task.config['_key_configs'] = list(configs)
                task.config.save_file()  # 强力显式落盘，确保即刻物理保存！
            task.reset_timer(cfg_id)  # 状态改变，立刻物理重置该按键的定时器！
            self.logger.info(f"Toggled config {cfg_id} to {checked}")
        return handle_toggle

    def make_delete_handler(self, cfg_id):
        def handle_delete():
            task = self.get_trigger_task()
            if not task:
                return
            with task.lock:
                configs = list(task.config.get('_key_configs', []))
                new_configs = [cfg for cfg in configs if cfg.get('id') != cfg_id]
                task.config['_key_configs'] = list(new_configs)
                task.config.save_file()  # 强力显式落盘，确保即刻物理保存！
                
                # Also prune the runtime state from memory
                task.runtime_state.pop(cfg_id, None)
                
            self.logger.info(f"Deleted config {cfg_id}")
            self.load_table_data()
            InfoBar.success(
                title="操作成功",
                content="连点按键删除成功",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.window()
            )
        return handle_delete

    def add_key_config(self):
        task = self.get_trigger_task()
        if not task:
            return

        key = self.key_combo.currentText().strip()
        if not key:
            InfoBar.error(
                title="输入错误",
                content="请输入或选择一个有效按键！",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window()
            )
            return

        # Validate with task.validate_key to catch unsupported keys immediately
        try:
            task.validate_key(key)
        except Exception as e:
            InfoBar.error(
                title="不支持的按键",
                content=f"按键 '{key}' 无法被系统识别，请选择内置按键或单字符！",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window()
            )
            return

        interval = self.interval_spin.value()
        count = self.count_spin.value()
        trigger_on_focus = self.focus_switch.isChecked()
        click_interval = self.click_interval_spin.value()
        cfg_id = f"k_{int(time.time() * 1000)}"  # Generate milliseconds-based unique ID

        new_cfg = {
            'id': cfg_id,
            'key': key,
            'interval': interval,
            'count': count,
            'click_interval': click_interval,
            'enabled': True,
            'trigger_on_focus': trigger_on_focus
        }

        with task.lock:
            configs = list(task.config.get('_key_configs', []))
            configs.append(new_cfg)
            task.config['_key_configs'] = configs
            task.config.save_file()  # 强力显式落盘，确保即刻物理保存！
        task.reset_timer(cfg_id)  # 新添加按键，立刻为该特定按键初始化重置定时器！

        self.logger.info(f"Added new config: {new_cfg}")
        self.load_table_data()
        
        InfoBar.success(
            title="添加成功",
            content=f"按键 '{key}' 连点配置已成功添加并生效！",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self.window()
        )

    def toggle_all_keys(self, enabled):
        task = self.get_trigger_task()
        if not task:
            return
        with task.lock:
            configs = list(task.config.get('_key_configs', []))
            for cfg in configs:
                cfg['enabled'] = enabled
            task.config['_key_configs'] = list(configs)
            task.config.save_file()  # 强力显式落盘，确保即刻物理保存！
        task.reset_timer()  # 全部启用/禁用，重置所有按键定时器！
            
        self.logger.info(f"Toggled all keys to: {enabled}")
        self.load_table_data()

    def reset_counts(self):
        task = self.get_trigger_task()
        if not task:
            return
        task.reset_runtime_state()
        task.reset_timer()  # 用户手动重置次数时，也强制全重置定时器起步！
        self.load_table_data()
        
        InfoBar.success(
            title="重置成功",
            content="所有连点按键的执行次数已归零，定时器已重置并重新开始！",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self.window()
        )

    def make_trigger_toggle_handler(self, cfg_id):
        """
        用于处理表格中“聚焦即发”Switch按钮切换的事件闭包。
        """
        def handler(checked):
            task = self.get_trigger_task()
            if not task:
                return
            with task.lock:
                configs = list(task.config.get('_key_configs', []))
                for cfg in configs:
                    if cfg.get('id') == cfg_id:
                        cfg['trigger_on_focus'] = checked
                        break
                task.config['_key_configs'] = list(configs)
                task.config.save_file()  # 强力显式落盘，确保即刻物理保存！
            task.reset_timer(cfg_id)  # 首次聚焦即发开关改变，立刻重置该按键定时器！
            self.logger.info(f"CustomKeysTab: trigger_on_focus for {cfg_id} toggled to {checked}, config saved")
        return handler

    def make_click_interval_handler(self, cfg_id):
        """
        用于处理表格中“每次敲击间隔”数值微调改变的事件闭包。
        """
        def handler(val):
            val = round(val, 2)  # 约束浮点精度
            task = self.get_trigger_task()
            if not task:
                return
            with task.lock:
                configs = list(task.config.get('_key_configs', []))
                for cfg in configs:
                    if cfg.get('id') == cfg_id:
                        cfg['click_interval'] = val
                        break
                task.config['_key_configs'] = list(configs)
                task.config.save_file()  # 强力显式落盘，确保即刻物理保存！
            task.reset_timer(cfg_id)  # 敲击间隔改变，立刻重置该按键定时器！
            self.logger.info(f"CustomKeysTab: click_interval for {cfg_id} changed to {val}, config saved")
        return handler

    def make_key_change_handler(self, cfg_id):
        """
        用于处理表格中“目标按键”ComboBox文本改变的事件闭包。
        """
        def handler(new_key):
            new_key = new_key.strip()
            if not new_key:
                return
            task = self.get_trigger_task()
            if not task:
                return
            try:
                task.validate_key(new_key)
            except Exception as e:
                InfoBar.error(
                    title="不支持的按键",
                    content=f"按键 '{new_key}' 无法被系统识别，请选择内置按键或单字符！",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self.window()
                )
                self.load_table_data()  # 非法字符回滚重载
                return

            with task.lock:
                configs = list(task.config.get('_key_configs', []))
                for cfg in configs:
                    if cfg.get('id') == cfg_id:
                        cfg['key'] = new_key
                        break
                task.config['_key_configs'] = list(configs)
                task.config.save_file()
            task.reset_timer(cfg_id)  # 目标按键改变，立刻重置该按键定时器！
            self.logger.info(f"CustomKeysTab: key for {cfg_id} changed to {new_key}, config saved")
        return handler

    def make_interval_change_handler(self, cfg_id):
        """
        用于处理表格中“按下间隔”数值微调改变的事件闭包。
        """
        def handler(val):
            val = round(val, 2)
            task = self.get_trigger_task()
            if not task:
                return
            with task.lock:
                configs = list(task.config.get('_key_configs', []))
                for cfg in configs:
                    if cfg.get('id') == cfg_id:
                        cfg['interval'] = val
                        break
                task.config['_key_configs'] = list(configs)
                task.config.save_file()
            task.reset_timer(cfg_id)  # 冷却间隔修改，立刻以新间隔重新重置计时！
            self.logger.info(f"CustomKeysTab: interval for {cfg_id} changed to {val}, config saved")
        return handler

    def make_count_change_handler(self, cfg_id):
        """
        用于处理表格中“每次按下次数”数值微调改变的事件闭包。
        """
        def handler(val):
            task = self.get_trigger_task()
            if not task:
                return
            with task.lock:
                configs = list(task.config.get('_key_configs', []))
                for cfg in configs:
                    if cfg.get('id') == cfg_id:
                        cfg['count'] = val
                        break
                task.config['_key_configs'] = list(configs)
                task.config.save_file()
            task.reset_timer(cfg_id)  # 按下次数修改，立刻重置该按键定时器！
            self.logger.info(f"CustomKeysTab: count for {cfg_id} changed to {val}, config saved")
        return handler
