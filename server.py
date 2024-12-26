from flask import Flask, render_template, Response, send_file
from flask_cors import CORS
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configure static folder path
static_folder = os.path.join(os.path.dirname(__file__), 'static')
app.static_folder = static_folder

# Configure song folder path (brooooo)
song_folder = os.path.join(os.path.dirname(__file__), 'brooooo')
app.song_folder = song_folder

# Render base
@app.route('/')
def chart_player():
    return render_template('chart.html')

@app.route('/MajdataView/<string:name>/<int:level>/ImageFull/1')
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
        
@app.route('/MajdataView/<string:name>/<int:level>/Maidata/1')
def majdataView_maidata(name, level):
    # Return the chart data
    maidata = os.path.join(song_folder, name, 'maidata.txt')
    try:
        with open(maidata, encoding='utf-8') as f:
            data = f.read()
        return Response(data, mimetype='text/plain')
    except Exception as e:
        return "Chart not found", 404

@app.route('/MajdataView/<string:name>/<int:level>/Track/1') 
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
    
@app.route('/MajdataView/start_song')
    # Return the song_name and inote_level
def get_current_song():
    return {
        'name': 'snooze',
        'level': 5
    }

def start_server():
    logger.info("Starting Flask server...")
    app.run(port=5000, debug=False)

if __name__ == '__main__':
    start_server()



#     try:
#         with open(maidata, encoding='utf-8') as f:
#             data = f.read()

#         # Extract first value
#         first_key = "&first="
#         first_start = data.find(first_key)
#         if first_start == -1:
#             return "First value not found", 404
        
#         first_start += len(first_key)
#         first_end = data.find("\n", first_start)
#         first_value = data[first_start:first_end].strip()

#         # Extract inote content
#         inote_key = f"&inote_{level}="
#         start_index = data.find(inote_key)
#         if start_index == -1:
#             return f"inote_{level} not found", 404
        
#         start_index += len(inote_key)
#         end_index = data.find("&inote_", start_index)
#         if end_index == -1:
#             end_index = len(data)
        
#         inote_content = data[start_index:end_index].strip()
        
#         # Construct final response
#         final_maidata = f"&first={first_value}\n&lv_1=1\n&inote_1={inote_content}"

#         # Write to output file
#         output_path = r"C:\Users\ck273\Desktop\output.txt"
#         try:
#             with open(output_path, 'w', encoding='utf-8') as f:
#                 f.write(final_maidata)
#         except Exception as e:
#             logger.error(f"Error writing to output file: {e}")

#         return Response(final_maidata, mimetype='text/plain')

#     except Exception as e:
#         return "Chart not found", 404

        

#     # trim audio from &first=
#     try:
#         # Get first value from maidata
#         maidata_path = os.path.join(song_folder, name, 'maidata.txt')
#         with open(maidata_path, encoding='utf-8') as f:
#             data = f.read()
#             first_key = "&first="
#             first_start = data.find(first_key) + len(first_key)
#             first_end = data.find("\n", first_start)
#             first_value = float(data[first_start:first_end].strip())

#         # Check audio files
#         track_mp3 = os.path.join(song_folder, name, 'track.mp3')
#         track_ogg = os.path.join(song_folder, name, 'track.ogg')
#         track_trim = os.path.join(song_folder, name, 'track_trim.mp3')

#         # Delete existing trim if exists
#         if os.path.exists(track_trim):
#             os.remove(track_trim)

#         # Load and trim audio
#         if os.path.exists(track_mp3):
#             audio = AudioSegment.from_mp3(track_mp3)
#         elif os.path.exists(track_ogg):
#             audio = AudioSegment.from_ogg(track_ogg)
#         else:
#             return "Track not found", 404

#         # Trim audio
#         trim_ms = int(first_value * 1000)
#         trimmed_audio = audio[trim_ms:]
        
#         # Export trimmed version
#         trimmed_audio.export(track_trim, format='mp3')
        
#         return send_file(track_trim)

#     except Exception as e:
#         logger.error(f"Error processing audio: {e}")
#         return "Error processing track", 404
