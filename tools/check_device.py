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
        


        if runtime.lower() == 'cuda' or runtime.lower() == 'tensorrt':
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



        elif runtime.lower() == 'onnx' or runtime.lower() == 'directml':
            # 检查 ONNX Runtime
            try:
                import onnxruntime as ort
                print(f"ONNX Runtime 已安装, 版本 {ort.__version__}")
            except ImportError:
                print("ONNX Runtime 未安装")
                return
            # 检查 DirectML 支持
            available_providers = ort.get_available_providers()
            print(f"可用的执行提供程序: {available_providers}")
            if 'DmlExecutionProvider' not in available_providers:
                print("DirectML 执行提供程序不可用")
                return
            # 获取 DirectML 支持的设备列表
            print("DirectML 执行提供程序可用")
            try:
                # 获取所有 EP 设备
                all_devices = ort.get_ep_devices()
                if not all_devices:
                    print("未找到任何可用的 EP 设备")
                    return
                # 筛选出 DML 设备
                dml_devices_list = []
                for device in all_devices:
                    # print([attr for attr in dir(device) if not attr.startswith('_')])
                    if device.ep_name == 'DmlExecutionProvider':
                        # print([attr for attr in dir(device.device) if not attr.startswith('_')])
                        device_name = device.device.metadata.get('Description', '未知设备名称')
                        dml_devices_list.append(device_name)
                if not dml_devices_list:
                    print("未找到任何可用的 DirectML 设备")
                else:
                    print("DirectML 可用设备列表:")
                    for i, device_name in enumerate(dml_devices_list):
                        print(f"  - 设备 {i}: {device_name}")
            except Exception as e:
                print(f"获取 DirectML 设备信息失败: {e}")



        # elif runtime.lower() == 'openvino':
        #     # 检查 OpenVINO
        #     try:
        #         import openvino
        #         print(f"OpenVINO 已安装, 版本 {openvino.__version__}")
        #     except ImportError:
        #         print("OpenVINO 未安装")
        #         return
        #     # 列出可用设备
        #     core = openvino.Core()
        #     devices = core.available_devices
        #     if not devices:
        #         print("未找到任何可用的 OpenVINO 设备")
        #     else:
        #         print("OpenVINO 可用设备列表:")
        #         for device in devices:
        #             device_name = core.get_property(device, "FULL_DEVICE_NAME")
        #             print(f"  - '{device}': {device_name}")


    except Exception as e:
        print(f"发生错误: {e}")



if __name__ == "__main__":

    runtime = 'onnx'
    main(runtime)
