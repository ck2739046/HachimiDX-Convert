import sys
import traceback
from PyQt6.QtWidgets import QApplication
from src.app.main_window import MainWindow
from src.services.all_services import AllServices


def main():

    try:
        app = QApplication(sys.argv)
        app.aboutToQuit.connect(AllServices.shutdown_all)

        AllServices.initialize_all()

        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    except Exception as e:
        print("\n------------------------ \
              \nError caught by main.py: \
              \n------------------------\n")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
