import json
import signal
import sys

from PySide6.QtWidgets import QApplication

from src.gui import MainWindow

def main():
    with open("config.json", "r") as f:
        config = json.load(f)

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    window = MainWindow(config)
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
