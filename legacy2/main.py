import sys
from PyQt6.QtWidgets import QApplication
from app.main_window import MainWindow
from tasks.task_scheduler import TaskScheduler


def main():

    try:
        app = QApplication(sys.argv)
        app.aboutToQuit.connect(TaskScheduler.shutdown_instance)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Critical Error: main.py error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
