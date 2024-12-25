from flask import Flask, render_template
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

@app.route('/')
def chart_player():
    return render_template('chart.html')

def start_server():
    logger.info("Starting Flask server...")
    app.run(port=5000, debug=False)

if __name__ == '__main__':
    start_server()