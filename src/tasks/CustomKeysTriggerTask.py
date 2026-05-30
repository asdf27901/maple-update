import time
import threading
import ctypes
from ok import TriggerTask

class CustomKeysTriggerTask(TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "自定义连点"
        self.description = "根据用户配置的按键、时间间隔与执行次数，前台物理模拟（Pynput）循环触发连点。"
        
        # Default configuration
        self.default_config = {
            '_enabled': False,
            'trigger_on_focus': True,  # 首次聚焦是否立即触发
            '_key_configs': []  # 增加下划线，获得官方自动序列化白名单，同时避开卡片 UI 渲染！
        }
        
        self.runtime_state = {}  # Format: {id: {'last_press_time': 0.0, 'pressed_count': 0}}
        self.lock = threading.RLock()  # 升级为可重入锁，彻底扫清同一个线程嵌套调用所造成的潜在未响应死锁！

        # 高精度线程专属Event令牌控制
        self.clicker_thread = None
        self.clicker_stop_event = None
        self.was_foreground = False

    def post_init(self):
        """
        任务初始化完成后，由框架自动调用。轻量拉起，避免强制销毁重建造成的卡顿。
        """
        # 平滑无感数据迁移：将旧的 'key_configs' 迁移到带下划线的官方白名单 '_key_configs'
        with self.lock:
            old_configs = self.config.get('key_configs')
            new_configs = self.config.get('_key_configs')
            if old_configs and not new_configs:
                self.config['_key_configs'] = old_configs
                self.config['key_configs'] = []  # 抹除旧键净化JSON，彻底防止任何潜在的解析冲突
                self.log_info("[数据迁移] 监测到旧版连点按键配置，已成功将其平滑无感升级迁移至持久化白名单 '_key_configs' 中！")

        # 如果任务启动时就是开启状态，立即启动连点线程
        if self.enabled:
            self.reset_timer(reset_first_focus=True)  # F9引擎启动大启用，彻底重洗首次聚焦防线！
            self.start_thread()

    def enable(self):
        """
        当任务在界面中被启用时调用。
        """
        super().enable()
        self.reset_timer(reset_first_focus=True)  # 任务开关拨至启用大启用，彻底重洗首次聚焦防线！
        self.start_thread()

    def disable(self):
        """
        当任务在界面中被禁用时调用。
        """
        super().disable()
        self.reset_timer(reset_first_focus=False)  # 关闭任务仅重置冷却状态
        self.stop_thread()

    def start_thread(self):
        """
        安全启动高精度连点线程。
        """
        with self.lock:
            # 1. 核心优化：如果已有线程正在健康存活地奔跑，直接复用，完全无需重建！
            if self.clicker_thread and self.clicker_thread.is_alive():
                return
            
            # 2. 如果已留有旧令牌，强制 set 确保其旧线程立即寿终正寝
            if self.clicker_stop_event:
                self.clicker_stop_event.set()
            
            # 3. 创建全新的专属退出令牌
            self.clicker_stop_event = threading.Event()
            
            # 4. 启动新线程并传入其专属令牌
            self.clicker_thread = threading.Thread(
                target=self._clicker_loop, 
                args=(self.clicker_stop_event,), 
                daemon=True
            )
            self.clicker_thread.start()
            self.log_info(f"高精度连点后台守护线程已安全启动！(线程名: {self.clicker_thread.name})")

    def stop_thread(self):
        """
        安全停止高精度连点线程。
        """
        with self.lock:
            if self.clicker_stop_event:
                self.clicker_stop_event.set()
                self.clicker_stop_event = None
                self.log_info("已下达连点守护线程停止指令。")
            self.clicker_thread = None

    def reset_runtime_state(self):
        """
        Resets executed counts and timers for all configured keys.
        """
        with self.lock:
            self.runtime_state.clear()
        self.log_info("已重置所有按键连点的执行次数！")

    def is_game_foreground(self) -> bool:
        """
        利用 Windows 底层 API 零延迟（微秒级）判断当前游戏窗口是否早已经聚焦在前台。
        """
        try:
            hw = None
            if hasattr(self, 'executor') and hasattr(self.executor, 'device_manager'):
                hw = getattr(self.executor.device_manager, 'hwnd_window', None)
            
            if hw:
                # 必须窗口可见且存在，防止大启动加载期间句柄“伪激活”偷跑冷却！
                visible = True
                if hasattr(hw, 'visible'):
                    v_attr = getattr(hw, 'visible')
                    visible = v_attr() if callable(v_attr) else v_attr
                
                exists = True
                if hasattr(hw, 'exists'):
                    e_attr = getattr(hw, 'exists')
                    exists = e_attr() if callable(e_attr) else e_attr
                
                if not visible or not exists:
                    return False

            hwnd_val = None
            if hw:
                # 1. 智能提取句柄：兼容属性与 Callable 方法调用，彻底扫清 Bound Method 陷阱！
                if hasattr(hw, 'hwnd'):
                    attr = getattr(hw, 'hwnd')
                    hwnd_val = attr() if callable(attr) else attr
                if not hwnd_val and hasattr(hw, '_hwnd'):
                    attr = getattr(hw, '_hwnd')
                    hwnd_val = attr() if callable(attr) else attr
            
            if not hwnd_val and hasattr(self, 'executor') and hasattr(self.executor, 'device_manager'):
                dm = self.executor.device_manager
                hwnd_val = dm.config.get('selected_hwnd') if hasattr(dm, 'config') else None

            if hwnd_val and isinstance(hwnd_val, int):
                foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()
                # A. 句柄直连匹配
                if foreground_hwnd == hwnd_val:
                    return True
                
                # B. 进程 PID 深度匹配（最强抗断连、抗窗口层级变动方案！）
                foreground_pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(foreground_hwnd, ctypes.byref(foreground_pid))
                
                game_pid = ctypes.c_ulong()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd_val, ctypes.byref(game_pid))
                
                if foreground_pid.value > 0 and foreground_pid.value == game_pid.value:
                    return True
            
            # 2. 兜底匹配：获取当前最前台的窗口标题进行模糊比对
            if hw:
                foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(foreground_hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(foreground_hwnd, buf, length + 1)
                    title = buf.value
                    
                    target_title = ''
                    if hasattr(hw, 'title'):
                        attr = getattr(hw, 'title')
                        target_title = attr() if callable(attr) else attr
                    
                    if not target_title and hasattr(self.executor, 'device_manager'):
                        dm = self.executor.device_manager
                        if hasattr(dm, 'windows_capture_config'):
                            target_title = dm.windows_capture_config.get('title', '')
                    
                    if target_title and target_title in title:
                        return True
        except Exception:
            pass
        return False

    def reset_timer(self, cfg_id=None, reset_first_focus=False):
        """
        物理重置按键定时器。
        - cfg_id: 如果指定了，则只重置该特定按键；否则重置所有按键。
        - reset_first_focus: 仅在全局大启用（点击启用开关/F9引擎开始）时才为 True。
                            如果为 False，则属于运行中参数微调，绝对保留首次聚焦防线状态不变！
        """
        with self.lock:
            key_configs = list(self.config.get('_key_configs', []))
            
            if cfg_id is None:
                # 情况 A：重置所有按键
                if reset_first_focus:
                    self.runtime_state.clear()
                    self.log_info("[定时器] 全局大启用启动！已彻底重置所有按键的冷却时间与首次聚焦防线！")
                else:
                    # 仅拉直冷却时间，绝不触碰首次聚焦状态
                    for key_cfg in key_configs:
                        if not isinstance(key_cfg, dict):
                            continue
                        cid = key_cfg.get('id')
                        if cid:
                            state = self.runtime_state.setdefault(
                                cid,
                                {
                                    'remaining_cooldown': key_cfg.get('interval', 1.0),
                                    'pressed_count': 0,
                                    'first_focus_triggered': True  # 运行中重置默认已处理，不抢跑
                                }
                            )
                            state['remaining_cooldown'] = key_cfg.get('interval', 1.0)
                    self.log_info("[定时器] 运行中全局更新，已拉直各通道冷却时间，首次聚焦防线状态保持不变。")
            else:
                # 情况 B：重置单个特定按键 cfg_id
                key_cfg = None
                for cfg in key_configs:
                    if isinstance(cfg, dict) and cfg.get('id') == cfg_id:
                        key_cfg = cfg
                        break
                
                if key_cfg:
                    state = self.runtime_state.get(cfg_id)
                    if state:
                        # 内存中已有状态：重置冷却，但保留 first_focus_triggered 判定状态不变！
                        state['remaining_cooldown'] = key_cfg.get('interval', 1.0)
                        if reset_first_focus:
                            state['first_focus_triggered'] = False
                        self.log_info(
                            f"[定时器] 运行中微调按键 {cfg_id}，已重置冷却为 {state['remaining_cooldown']}s，"
                            f"保留首次聚焦判定状态({state['first_focus_triggered']})"
                        )
                    else:
                        # 内存中尚未建立状态（比如运行中中途新添加的按键）：初始化状态，默认不抢跑
                        self.runtime_state[cfg_id] = {
                            'remaining_cooldown': key_cfg.get('interval', 1.0),
                            'pressed_count': 0,
                            'first_focus_triggered': False if reset_first_focus else True  # 运行中加的默认不抢跑
                        }
                        self.log_info(
                            f"[定时器] 运行中新加按键 {cfg_id}，初始化冷却为 {key_cfg.get('interval', 1.0)}s，"
                            f"首次聚焦判定置为 {self.runtime_state[cfg_id]['first_focus_triggered']}"
                        )

    def _clicker_loop(self, stop_event):
        """
        独立高精度毫秒级轮询循环，彻底绕过框架2秒一次的执行周期瓶颈。
        采用先进的“剩余冷却时间递减模型”，实现失焦物理暂停计时，聚焦继续计时！
        """
        # 初始化上一轮循环时间戳
        self.last_loop_time = time.time()
        
        while not stop_event.is_set():
            # 只有当任务处于启用状态，并且没有被用户暂停时才处理
            if not self.enabled or self.paused:
                time.sleep(0.05)
                # 暂停期间持续更新时间戳，防止恢复时瞬间扣减多余流逝时间
                self.last_loop_time = time.time()
                continue

            now = time.time()
            dt = now - self.last_loop_time if hasattr(self, 'last_loop_time') else 0.0
            self.last_loop_time = now

            with self.lock:
                key_configs = list(self.config.get('_key_configs', []))

            current_fg = self.is_game_foreground()
            
            # 首次聚焦即发与失焦暂停计时核心控制：只在游戏处于前台时，才扣除剩余冷却时间！
            if current_fg:
                triggered_keys = []
                for key_cfg in key_configs:
                    if not isinstance(key_cfg, dict) or not key_cfg.get('enabled', False):
                        continue
                    cfg_id = key_cfg.get('id')
                    if cfg_id:
                        # 确保 state 初始化，采用剩余冷却时间递减模型
                        state = self.runtime_state.setdefault(
                            cfg_id, 
                            {
                                'remaining_cooldown': 0.0 if key_cfg.get('trigger_on_focus', True) else key_cfg.get('interval', 1.0), 
                                'pressed_count': 0, 
                                'first_focus_triggered': False
                            }
                        )
                        # 如果还没处理过首次聚焦判定（只做记录，首帧判定后固化状态）
                        if not state.get('first_focus_triggered', False):
                            if key_cfg.get('trigger_on_focus', True):
                                triggered_keys.append(key_cfg.get('key'))
                                state['remaining_cooldown'] = 0.0  # 确保首帧瞬间秒发！
                            else:
                                # 首次聚焦不即发：在第一帧真正检测到前台聚焦的瞬间，强制无感重置冷却为满秒 interval！
                                # 彻底校准抹平任何因大启动句柄绑定延迟产生的偷跑时间差！
                                state['remaining_cooldown'] = key_cfg.get('interval', 1.0)
                            state['first_focus_triggered'] = True
                        
                        # 在游戏前台聚焦时，扣除本轮微小流逝时间dt！
                        state['remaining_cooldown'] = max(0.0, state['remaining_cooldown'] - dt)
                
                if triggered_keys:
                    self.log_info(f"[高精度] 监测到游戏首次聚焦，已抢先激活按键 {triggered_keys} 的首次立即触发！")
            else:
                # 游戏失焦在后台时，dt 照常计算更新，但不扣减剩余冷却时间（物理挂起/暂停计时！）
                time.sleep(0.05)  # 稍微睡眠，防止失焦期间空轮询无意义消耗 CPU
                continue

            # 3. 收集本轮需要触发的连点按键列表（只在游戏处于前台聚焦且冷却到期 0.0 时触发）
            pending_clicks = []
            if current_fg:
                for key_cfg in key_configs:
                    if not isinstance(key_cfg, dict) or not key_cfg.get('enabled', False):
                        continue
                    cfg_id = key_cfg.get('id')
                    if cfg_id:
                        state = self.runtime_state.get(cfg_id)
                        if state and state.get('remaining_cooldown', 0.0) <= 0.0:
                            pending_clicks.append((key_cfg, state))

            # 4. 执行本轮物理连点秒发
            if pending_clicks:
                for key_cfg, state in pending_clicks:
                    key = key_cfg.get('key')
                    interval = key_cfg.get('interval', 1.0)
                    count = max(1, key_cfg.get('count', 1))
                    click_interval = max(0.001, key_cfg.get('click_interval', 0.2))  # 提取专属敲击间隔，默认0.2秒，兜底1ms防死锁
                    
                    try:
                        # 物理极速连拍，每次冷却好后连续敲击 count 次
                        for i in range(count):
                            self.send_key(key)
                            
                            # 多次敲击之间引入玩家自定义的物理呼吸睡眠，防止按压太快粘连或漏识别
                            if count > 1 and i < count - 1:
                                time.sleep(click_interval)
                        
                        # 完成本轮连拍计划后，已执行次数仅增加 1 轮（代表该连点事件完整调度了1次！）
                        state['pressed_count'] += 1
                        
                        # 冷却到期触发完毕，瞬间重新装弹重置为满秒 interval 冷却！
                        state['remaining_cooldown'] = interval
                        
                        # 降级为后台 DEBUG 日志：挂机时普通 UI 界面 100% 毫无刷屏噪音，需要深度排查时底层日志依旧清晰可循！
                        self.logger.debug(
                            f"[高精度] 前台物理连点成功: '{key}' | "
                            f"冷却间隔: {interval}秒 | "
                            f"本次连击: {count}次 | "
                            f"敲击间隔: {click_interval}秒 | "
                            f"事件已执行轮次: {state['pressed_count']}轮"
                        )
                    except Exception as e:
                        self.log_error(f"前台物理按键 '{key}' 触发失败", e)

            # 超高频心跳睡眠（10ms），确保亚秒级连点极其流畅精准
            time.sleep(0.01)

        self.log_info("高精度连点后台守护线程已退出。")

    def run(self) -> bool:
        """
        由框架主线程每隔约2秒调用一次，这里作为后台高精度线程的双重保护心跳。
        """
        if self.enabled and (self.clicker_thread is None or not self.clicker_thread.is_alive()):
            self.start_thread()
        return False
