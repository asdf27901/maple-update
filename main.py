import ok
from src.config import config


def _patch_gui():
    try:
        from ok.gui.tasks.EditTaskTab import EditTaskTab
        _original_init_ui = EditTaskTab.init_ui

        def _patched_init_ui(self):
            _original_init_ui(self)
            if hasattr(self, 'guide_button'):
                self.guide_button.setVisible(False)

        EditTaskTab.init_ui = _patched_init_ui
    except Exception:
        pass


if __name__ == '__main__':
    _patch_gui()
    config = config
    ok = ok.OK(config)
    ok.start()
