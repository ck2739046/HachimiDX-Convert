import sys
from pathlib import Path

if len(sys.argv) <= 1:
    print("No args provided for auto_convert_worker. Exiting.")
    sys.exit(1)

# 第一个参数是项目根目录
# 确保能正确使用间接导入
root = str(Path(sys.argv[1]).resolve())
if root not in sys.path:
    sys.path.insert(0, root)

# 2026.03.20

# see https://github.com/pytorch/pytorch/issues/166628
# 当前最新版 pytorch + pyqt6 在一起使用时有问题
# 如果 pyqt6 比 torch 先导入，会产生 winerror1114 (dll加载失败)
# 解决方法是先导入 torch 再导入 pyqt6
import torch

# 不能使用 python -m 启动此 worker
# 因为 python -m 启动后，import torch 无法解决上述问题
# 原因不清楚，可能和 python -m 的模块导入机制有关？
# 只能通过传统 python xxx.py 启动
# 不管了，反正现在这样能正常工作了
# 以后哪天此问题修复了再改回 python -m 启动吧


from src.core.auto_convert.standardize.main import main as standardize_main
from src.core.auto_convert.detect.main import main as detect_main
from src.core.auto_convert.analyze.main import main as analyze_main


def main(args: list[str]):

    print(args)


if __name__ == "__main__":
    main(sys.argv[2:]) # 跳过第一个参数（脚本路径）和第二个参数（root路径）
