from PySide6.QtCore import QObject
from ok import Logger

logger = Logger.get_logger(__name__)


# ！！！魔法级 UI 定制 Monkey Patch：将主窗口自带的关于页彻底无痛蒸发抹去！！！
try:
    import ok.gui.MainWindow

    # 保存原有的主窗口构造器
    original_main_window_init = ok.gui.MainWindow.MainWindow.__init__

    def custom_main_window_init(self, *args, **kwargs):
        # 先以 100% 的兼容性执行原生主窗口的初始化，生成所有组件
        original_main_window_init(self, *args, **kwargs)
        
        # 原生初始化结束后，赶在窗口被展现屏幕上的前一微秒，在内存中动态抹去关于页
        try:
            if hasattr(self, 'about_tab') and self.about_tab:
                # 1. 从 qfluentwidgets 侧边栏导航条中精准剥离关于按钮
                self.navigationInterface.removeWidget(self.about_tab.objectName())
                # 2. 从主页面叠层中移出关于页面
                self.stackedWidget.removeWidget(self.about_tab)
                # 3. 优雅地从内存中安全销毁组件
                self.about_tab.deleteLater()
                self.about_tab = None
                logger.info("[UI关于蒸发] 已成功将侧边栏底部的关于页在内存中彻底无痕蒸发抹除！")
        except Exception as e:
            logger.error(f"[UI关于蒸发] 蒸发失败: {e}")

    # 动态篡改替换，完成华丽的定制化变身！
    ok.gui.MainWindow.MainWindow.__init__ = custom_main_window_init
    logger.info("[UI黑客拦截] MainWindow 关于页动态蒸发拦截器部署成功！")
except Exception as e:
    logger.error(f"[UI黑客拦截] 关于页拦截器初始化失败: {e}")


# ！！！魔法级 模板定制 Monkey Patch：新建任务时仅擦除推广链接，保留空属性以完美支持 capture_config 自动填充！！！
# ！！！并且物理屏蔽左侧模板树中的 ADB 分类和所有 ADB 方法，让软件回归 Windows 专业级纯净！！！
try:
    import ok.gui.tasks.EditTaskTab
    from PySide6.QtWidgets import QTreeWidgetItem
    from PySide6.QtCore import Qt

    def custom_create_task(self):
        from qfluentwidgets import MessageBoxBase, LineEdit, SubtitleLabel
        from ok.gui.util.Alert import alert_error
        import re
        import os
        from ok import og

        class CreateTaskDialog(MessageBoxBase):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.titleLabel = SubtitleLabel(self.tr('Create Task'), self)

                self.class_name_input = LineEdit(self)
                self.class_name_input.setPlaceholderText(self.tr("Class Name (English only)"))

                self.task_name_input = LineEdit(self)
                self.task_name_input.setPlaceholderText(self.tr("Task Name"))

                self.task_desc_input = LineEdit(self)
                self.task_desc_input.setPlaceholderText(self.tr("Description (Optional)"))

                self.viewLayout.addWidget(self.titleLabel)
                self.viewLayout.addWidget(self.class_name_input)
                self.viewLayout.addWidget(self.task_name_input)
                self.viewLayout.addWidget(self.task_desc_input)
                self.yesButton.setText(self.tr('Confirm'))
                self.cancelButton.setText(self.tr('Cancel'))
                self.widget.setMinimumWidth(360)

        dialog = CreateTaskDialog(self.window())

        if dialog.exec():
            class_name = dialog.class_name_input.text().strip()
            task_name = dialog.task_name_input.text().strip()
            task_desc = dialog.task_desc_input.text().strip()

            if not class_name or not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', class_name):
                alert_error(self.tr("Invalid Class Name. Must be English characters only."))
                return
            if not task_name:
                alert_error(self.tr("Task Name is required."))
                return

            base_class = "BaseTask"  # Defaulting to BaseTask for custom tasks

            # 【黄金超纯净模板】：保留 self.instructions = "" 空属性，让框架完美在下方自动填充 capture_config！
            task_code = f"""from ok import {base_class}

class {class_name}({base_class}):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "{task_name}"
        self.description = "{task_desc}"
        self.instructions = ""

    def run(self):
        pass
"""
            file_path = os.path.join(og.task_manager.task_folder, f"{class_name}.py")
            if os.path.exists(file_path):
                alert_error(self.tr("Task file already exists."))
                return

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(task_code)
                self.refresh_dropdown()

                # Auto select the newly created task
                for i in range(self.task_dropdown.count()):
                    if self.task_dropdown.itemData(i) == file_path:
                        self.task_dropdown.setCurrentIndex(i)
                        break

                og.task_manager.load_single_user_task(file_path)
                from ok.gui.util.app import show_info_bar
                show_info_bar(self.window(), self.tr("Task created successfully."), title=self.tr("Success"))
            except Exception as e:
                alert_error(f"Error creating task: {e}")

    # 1. 动态挂载新建脚本函数
    ok.gui.tasks.EditTaskTab.EditTaskTab.create_task = custom_create_task
    
    # 2. 动态改写并过滤左侧模板列表的“ADB”选项，实现极致纯净化
    def custom_populate_template_list(self, query):
        from ok.gui.tasks.TemplateFactory import filter_templates
        self.template_list.clear()

        # 【核心过滤】：把包含类别为 'ADB' 的所有子模板，从数据源中彻底拦截剥离！
        filtered = [t for t in filter_templates(self.all_templates, query) if t.get('category') != 'ADB']

        groups = {}
        for t in filtered:
            cname = t.get('category', 'Other')
            if cname not in groups:
                groups[cname] = []
            groups[cname].append(t)

        # 彻底移除 ADB 排序节点
        categories_order = [
            "Mouse", "Key", "Control", "OCR", "Template Matching",
            "Box", "Window", "Logging", "Other"
        ]

        category_translations = {
            "Mouse": self.tr("Mouse"),
            "Key": self.tr("Key"),
            "Control": self.tr("Control"),
            "OCR": self.tr("OCR"),
            "Template Matching": self.tr("Template Matching"),
            "Box": self.tr("Box"),
            "Window": self.tr("Window"),
            "Logging": self.tr("Logging"),
            "Other": self.tr("Other"),
        }

        for cname in categories_order:
            if cname in groups:
                templates = groups[cname]
                display_name = category_translations.get(cname, cname)
                parent_item = QTreeWidgetItem([display_name])
                parent_item.setFlags(parent_item.flags() & ~Qt.ItemIsSelectable)
                self.template_list.addTopLevelItem(parent_item)

                for t in templates:
                    display_text = t['template_name']
                    item = QTreeWidgetItem([self.tr(display_text)])
                    item.setData(0, Qt.UserRole, t)
                    item.setToolTip(0, t.get('full_doc', t.get('doc', '')))
                    parent_item.addChild(item)

    # 3. 动态挂载过滤后的分类列表函数！
    ok.gui.tasks.EditTaskTab.EditTaskTab._populate_template_list = custom_populate_template_list

    logger.info("[UI黑客拦截] 脚本新建模板与 ADB 选项物理过滤拦截器部署成功！已彻底擦除推广和 ADB 选项！")
except Exception as e:
    logger.error(f"[UI黑客拦截] 脚本模板与 ADB 过滤器部署失败: {e}")


class Globals(QObject):

    def __init__(self, exit_event):
        super().__init__()
        # ！！！最高逼格 UI 整合 Monkey Patch：将自定义连点宏控制板无缝嵌入实时触发任务卡片！！！
        try:
            import ok.gui.tasks.ConfigCard
            from PySide6.QtCore import Qt

            # 保存原私有方法（利用 Python 的 Name Mangling 还原私有方法名）
            original_initWidget = ok.gui.tasks.ConfigCard.ConfigCard._ConfigCard__initWidget

            def custom_initWidget(self):
                if self.task and self.task.__class__.__name__ == 'CustomKeysTriggerTask':
                    self.viewLayout.setSpacing(0)
                    self.viewLayout.setAlignment(Qt.AlignTop)
                    self.viewLayout.setContentsMargins(0, 0, 0, 0)
                    self.card.expandButton.show()  # 强行确保折叠卡片的展开按钮处于显示状态
                    
                    # 动态延迟导入，完全避开循环依赖
                    from src.ui.CustomKeysTab import CustomKeysTab
                    # 直接将卡片自身已就绪的 task 实例无缝传给面板，彻底免去对 executor 的寻找！
                    custom_tab = CustomKeysTab(embed=True, task=self.task)
                    
                    # 【黄金撑高防线】：强制为内嵌面板灌注 580 像素完美舒展高度，诱导原生展开动画彻底拉开，消除滚动条！
                    custom_tab.setFixedHeight(580)
                    
                    self.viewLayout.addWidget(custom_tab)
                    self.config_widgets = [custom_tab]  # 记录在 config_widgets 中以配合 update_config()
                    self._adjustViewSize()
                    logger.info("[UI高度重塑] 已成功将 CustomKeysTab 控制面板强制撑高至 580px 展开形态！")
                    return
                else:
                    original_initWidget(self)

            # 动态替换，完成终极无缝大融合！
            ok.gui.tasks.ConfigCard.ConfigCard._ConfigCard__initWidget = custom_initWidget
            logger.info("[UI黑客拦截] 实时触发 ConfigCard Monkey Patch 动态拦截器部署成功！")
        except Exception as e:
            logger.error(f"[UI黑客拦截] 拦截器部署失败: {e}")
