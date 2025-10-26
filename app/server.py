from flask import Flask, render_template, Response, send_file, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import os
import logging

# Filter out specific message logger
def log_filter(record):
    message = record.getMessage()
    filtered_paths = [
        '/socket.io/?EIO=',
        '/static/socket.io.js',
        '/static/majdata-wasm',
        '/static/MajdataView.ico',
        '/ImageFull/1',
        '/Track/1 HTTP/1.1',
    ]
    return not any(path in message for path in filtered_paths)
logging.getLogger('werkzeug').addFilter(log_filter)

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")





# Configure static folder path
static_folder = os.path.join(os.path.dirname(__file__), 'static')
app.static_folder = static_folder
app.template_folder = static_folder # render_template path

# Configure song folder path (aaa-result)
song_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'aaa-result')
app.song_folder = song_folder





# Root
@app.route('/')
def chart_player():
    return render_template('majdataView.html')

# MajdataView请求曲绘文件
@app.route('/MajdataView/src/<string:song>/bg')
def majdataView_bg(song):
    # Return the background image
    bg_png = os.path.join(song_folder, song, 'bg.png')
    bg_jpg = os.path.join(song_folder, song, 'bg.jpg')  
    if os.path.exists(bg_png):
        return send_file(bg_png)
    elif os.path.exists(bg_jpg):
        return send_file(bg_jpg)
    else:
        return "BG not found", 404

# MajdataView请求谱面文件  
@app.route('/MajdataView/src/<string:song>/maidata')
def majdataView_maidata(song):
    # Return the chart data
    maidata = os.path.join(song_folder, song, 'maidata.txt')
    try:
        with open(maidata, encoding='utf-8') as f:
            data = f.read()
        return Response(data, mimetype='text/plain')
    except Exception as e:
        return "Chart not found", 404

# MajdataView请求音频文件
@app.route('/MajdataView/src/<string:song>/<string:track>') 
def majdataView_track(song, track):
    # Return the audio track
    track_audio = os.path.join(song_folder, song, track)
    if os.path.exists(track_audio):
        return send_file(track_audio)
    else:
        return "Track not found", 404





def MajdataView_load_chart(song, track, level):
    # 0: no error, 1: no chart, 2: no track

    # Check if maidata.txt exists
    maidata_path = os.path.join(song_folder, song, 'maidata.txt')
    if not os.path.exists(maidata_path):
        socketio.emit('MajdataView_load_chart', {'song': song, 'track': track, 'level': level, 'error': 1})
        return
    # Check if track audio exists
    audio_path = os.path.join(song_folder, song, track)
    if not (os.path.exists(audio_path)):
        socketio.emit('MajdataView_load_chart', {'song': song, 'track': track, 'level': level, 'error': 2})
        return
    # No error
    socketio.emit('MajdataView_load_chart', {'song': song, 'track': track, 'level': level, 'error': 0})

def MajdataView_refresh_page():
    socketio.emit('MajdataView_refresh_page')

def start_server():
    socketio.run(app, port=5273, debug=False)

if __name__ == '__main__':
    start_server()
