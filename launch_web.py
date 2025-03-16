import webview

webview.create_window(
    'MajdataView',
    'http://localhost:5273',
    width=768,
    height=432
)

webview.start()

#pyinstaller --clean --onefile ./pywebview.py --name=launch_web
