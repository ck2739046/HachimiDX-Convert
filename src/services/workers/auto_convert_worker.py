import sys

from src.core.auto_convert.standardize.main import main as standardize_main
from src.core.auto_convert.detect.main import main as detect_main
from src.core.auto_convert.analyze.main import main as analyze_main


def main(args: list[str]):

    print(args)


if __name__ == "__main__":
    main(sys.argv)
