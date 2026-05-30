import ok
from src.config import config
from main import _patch_gui

if __name__ == '__main__':
    _patch_gui()
    config = config
    config['debug'] = True
    ok = ok.OK(config)
    ok.start()
