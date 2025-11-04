# 打印一个库的所有属性
# python -c "import torch; print([attr for attr in dir(torch) if not attr.startswith('_')])" 

def main(runtime):
    try:
        # 先统一检查 PyTorch
        try:
            import torch
            print(f"PyTorch 已安装, 版本 {torch.__version__}")
        except ImportError:
            print("PyTorch 未安装")
            return


        if runtime.lower() == 'openvino':
            # 检查 OpenVINO
            try:
                import openvino
                print(f"OpenVINO 已安装, 版本 {openvino.__version__}")
            except ImportError:
                print("OpenVINO 未安装")
                return
            # 列出可用设备
            core = openvino.Core()
            devices = core.available_devices
            if not devices:
                print("未找到任何可用的 OpenVINO 设备")
            else:
                print("OpenVINO 可用设备列表:")
                for device in devices:
                    device_name = core.get_property(device, "FULL_DEVICE_NAME")
                    print(f"  - '{device}': {device_name}")
        

        elif runtime.lower() == 'directml':
            # 检查 torch_directml
            try:
                import torch_directml
                if torch_directml.is_available():
                    print(f"torch_directml 已安装")
                else:
                    print(f"torch_directml 已安装但不可用")
                    return
            except ImportError:
                print("torch_directml 未安装")
                return
            # 列出可用设备
            device_count = torch_directml.device_count()
            if device_count == 0:
                print(f"未找到任何可用的 DirectML 设备")
            else:
                print(f"可用设备列表:")
                for i in range(device_count):
                    device_name = torch_directml.device_name(i)
                    print(f"  - 设备 {i}: {device_name}")
                # 打印默认设备
                print(f"  - 默认设备 {torch_directml.default_device()}")


        elif runtime.lower() == 'cuda' or runtime.lower() == 'tensorrt':
            # 检查 PyTorch cuda 版本
            print(f"  - CUDA 可用: {torch.cuda.is_available()}")
            print(f"  - CUDA 版本: {torch.version.cuda if hasattr(torch.version, 'cuda') else 'N/A'}")
            # 检查 TensorRT
            try:
                import tensorrt
                print(f"TensorRT 已安装, 版本 {tensorrt.__version__}")
            except ImportError:
                print("TensorRT 未安装")
            # 列出所有 CUDA 设备
            device_count = torch.cuda.device_count()
            if device_count == 0:
                print("未找到任何可用的 CUDA 设备")
            else:
                print("CUDA 可用设备列表:")
                for i in range(device_count):
                    device_name = torch.cuda.get_device_name(i)
                    print(f"  - {i}: {device_name}")

    except Exception as e:
        print(f"发生错误: {e}")



if __name__ == "__main__":

    runtime = 'cuda'
    main(runtime)
