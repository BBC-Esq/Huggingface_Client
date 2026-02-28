import sys
from PySide6.QtWidgets import QApplication, QStyleFactory
from logging_config import setup_logging
from ui.main_window import MainWindow


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
