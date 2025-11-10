from ultralytics import YOLO

model = YOLO(r"D:\git\aaa-HachimiDX-Convert\src\models\detect.pt")
model.export(format="engine",
             task='detect',
             imgsz=960,
             half=True,
             dynamic=True,
             simplify=True,
             workspace=2,
             batch=2,
             device='0')



# model_path = os.path.join(os.path.dirname(__file__), 'pt', 'cls-break.pt')
# model = YOLO(model_path)
# model.export(format="engine",
#              imgsz=224,
#              half=True,
#              dynamic=True,
#              simplify=True,
#              workspace=2,
#              batch=16,
#              device='0')



# model_path = os.path.join(os.path.dirname(__file__), 'pt', 'cls-ex.pt')
# model = YOLO(model_path)
# model.export(format="engine",
#              imgsz=224,
#              half=True,
#              dynamic=True,
#              simplify=True,
#              workspace=2,
#              batch=16,
#              device='0')



# model = YOLO(r"D:\git\aaa-HachimiDX-Convert\src\models\detect.pt")
# model.export(format="openvino",
#              imgsz=960,
#              half=True,
#              dynamic=True,
#              batch=2)
