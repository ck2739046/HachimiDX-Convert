from ultralytics import YOLO
import path_config

def convert_to_tensorRT(batch=2, workspace=1):
    
    try:
        batch = int(batch)
        workspace = int(workspace)
    except Exception as e:
        print(f"Invalid parameter: {e}")
        return
    
    if batch < 1:
        print("Batch size must be at least 1.")
        return

    # 仅将 detect.pt 转换为 TensorRT 引擎
    model = YOLO(path_config.detect_pt)
    model.export(format="engine",
                 imgsz=960,
                 half=True,
                 dynamic=True,
                 simplify=True,
                 workspace=workspace,
                 batch=batch)



def convert_to_onnx():
    
    # 转换所有模型
    for model_path in [path_config.detect_pt, path_config.obb_pt, path_config.cls_break_pt, path_config.cls_ex_pt]:
        model = YOLO(model_path)
        model.export(format="onnx",
                     opset=20,
                     half=True,
                     dynamic=True,
                     simplify=True)
        


if __name__ == "__main__":
    convert_to_onnx()
    # convert_to_tensorRT(batch=2, workspace=1)
