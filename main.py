import sys
import traceback
from PyQt6.QtWidgets import QApplication
from src.core.schemas.op_result import print_op_result
from src.app import MainWindow
from src.services import AllServices


def main():

    try:
        app = QApplication(sys.argv)
        app.aboutToQuit.connect(AllServices.shutdown_all)

        result = AllServices.initialize_all()
        if not result.is_ok:
            print("\n------------------------ \
                   \nInitialization Error: \
                   \n------------------------\n")
            print_op_result(result)
            sys.exit(1)

        window = MainWindow()
        window.show()
        sys.exit(app.exec())

    except Exception:
        print("\n------------------------ \
               \nError caught by main.py: \
               \n------------------------\n")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
