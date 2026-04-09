import json
import signal
import sys

from PySide6.QtWidgets import QApplication

from src.gui import MainWindow

def main():
    config_path = "config.json"
    with open(config_path, "r") as f:
        config = json.load(f)

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    window = MainWindow(config, config_path=config_path)
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
