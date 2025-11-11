from ultralytics import YOLO
import path_config
import sys



def convert_to_tensorRT(batch=2, workspace=None):
    
    try:
        batch = int(batch)
        if batch < 1:
            print("Batch size must be at least 1.")
            return
        
        # workspace如果是auto视为None
        if workspace == 'auto':
            workspace = None
        elif workspace is not None:
            workspace = int(workspace)
        
        print(f"Converting to TensorRT with batch size {batch}, workspace {workspace}...")

        # 仅将 detect.pt 转换为 TensorRT 引擎
        model = YOLO(path_config.detect_pt)
        model.export(format="engine",
                    imgsz=960,
                    half=True,
                    dynamic=True,
                    simplify=True,
                    workspace=workspace,
                    batch=batch)
        
        return True
        
    except Exception as e:
        print(f"Error during TensorRT conversion: {e}")
        return False



def convert_to_onnx():
    
    try:
        # 转换所有模型
        for model_path in [path_config.detect_pt, path_config.obb_pt, path_config.cls_break_pt, path_config.cls_ex_pt]:
            model = YOLO(model_path)
            model.export(format="onnx",
                        opset=20,
                        half=True,
                        dynamic=True,
                        simplify=True)
            
        return True
    
    except Exception as e:
        print(f"Error during ONNX conversion: {e}")
        return False        
    
        


if __name__ == "__main__":
    
    # 从命令行参数获取转换类型、batch size 和 workspace
    if len(sys.argv) > 1:
        backend = sys.argv[1].lower()
        
        if backend == "tensorrt":
            batch = int(sys.argv[2]) if len(sys.argv) > 2 else 2 # 默认batch=2
            workspace = sys.argv[3] if len(sys.argv) > 3 else None  # 默认workspace=None
            result = convert_to_tensorRT(batch=batch, workspace=workspace)
        elif backend == "directml" or backend == "onnx":
            result = convert_to_onnx()
        else:
            print(f"Unknown backend: {backend}")
            sys.exit(1)
        
        sys.exit(0 if result else 1)
    else:
        sys.exit(1)
