from flask import Flask, render_template, Response, send_file, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import os
import logging

# Filter out socket.io massage logger
logging.getLogger('werkzeug').addFilter(lambda r: not('/socket.io/?EIO=' in r.getMessage()))

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

"""
# State management class
class AppState:
    def __init__(self):
        self._current_song = "None"
        self._current_level = "None"
    
    @property
    def current_song(self):
        return self._current_song
    
    @current_song.setter 
    def current_song(self, value):
        self._current_song = value
    
    @property
    def current_level(self):
        return self._current_level
    
    @current_level.setter
    def current_level(self, value):
        self._current_level = value

# Create global state instance
state = AppState()
"""

# Configure static folder path
static_folder = os.path.join(os.path.dirname(__file__), 'static')
app.static_folder = static_folder

# Configure song folder path (brooooo)
song_folder = os.path.join(os.path.dirname(__file__), 'brooooo')
app.song_folder = song_folder

# Root
@app.route('/')
def chart_player():
    return render_template('chart.html')

@app.route('/MajdataView/src/<string:name>/<int:level>/ImageFull/1')
def majdataView_bg(name, level):
    # Return the background image
    bg_png = os.path.join(song_folder, name, 'bg.png')
    bg_jpg = os.path.join(song_folder, name, 'bg.jpg')  
    if os.path.exists(bg_png):
        return send_file(bg_png)
    elif os.path.exists(bg_jpg):
        return send_file(bg_jpg)
    else:
        return "BG not found", 404
        
@app.route('/MajdataView/src/<string:name>/<int:level>/Maidata/1')
def majdataView_maidata(name, level):
    # Return the chart data
    maidata = os.path.join(song_folder, name, 'maidata.txt')
    try:
        with open(maidata, encoding='utf-8') as f:
            data = f.read()
        return Response(data, mimetype='text/plain')
    except Exception as e:
        return "Chart not found", 404

@app.route('/MajdataView/src/<string:name>/<int:level>/Track/1') 
def majdataView_track(name, level):
    # Return the audio track
    track_mp3 = os.path.join(song_folder, name, 'track.mp3')
    track_ogg = os.path.join(song_folder, name, 'track.ogg')
    if os.path.exists(track_mp3):
        return send_file(track_mp3)
    elif os.path.exists(track_ogg):
        return send_file(track_ogg)
    else:
        return "Track not found", 404

def MajdataView_load_chart(song, level):
    # 0: no error, 1: no chart, 2: no track

    # Check if maidata.txt exists
    maidata_path = os.path.join(song_folder, song, 'maidata.txt')
    if not os.path.exists(maidata_path):
        socketio.emit('MajdataView_load_chart', {'song': song, 'level': level, 'error': 1})
        return
    # Check if audio track exists
    track_mp3 = os.path.join(song_folder, song, 'track.mp3')
    track_ogg = os.path.join(song_folder, song, 'track.ogg')
    if not (os.path.exists(track_mp3) or os.path.exists(track_ogg)):
        socketio.emit('MajdataView_load_chart', {'song': song, 'level': level, 'error': 2})
        return
    # No error
    socketio.emit('MajdataView_load_chart', {'song': song, 'level': level, 'error': 0})

def MajdataView_refresh_page():
    socketio.emit('MajdataView_refresh_page')

def start_server():
    socketio.run(app, port=5000, debug=False)

if __name__ == '__main__':
    start_server()
