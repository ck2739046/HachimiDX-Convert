import json
from datetime import datetime, timedelta
import threading
import socket
import time
import traceback

class VideoSyncServer:
    
    # Constants for time conversion
    TICKS_AT_UNIX_EPOCH = 621355968000000000
    TICKS_TO_SECONDS = 10000000.0
    
    def __init__(self, media_player, listen_port=8014):
        self.media_player = media_player
        self.listen_port = listen_port
        self.server_thread = None
        self.udp_socket = None
        self.running = False
        self.pending_play_timer = None    # For delayed playback
        self.main_thread_callback = None  # Callback to execute in main thread
        self.last_play_speed = None
        
    
    def start(self):
        self.running = True
        
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        self.udp_socket.bind(('localhost', self.listen_port))
        self.udp_socket.settimeout(1.0)
        
        print(f"[VideoSync] Server started on port {self.listen_port}")
        
        def run_server():
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(65535)
                    message = json.loads(data.decode('utf-8'))
                    
                    # Handle message directly
                    self.handle_control_message(message)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[VideoSync] Error: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
    
    
    def stop(self):
        self.running = False
        
        # Cancel any pending delayed playback
        if self.pending_play_timer:
            self.pending_play_timer.cancel()
            self.pending_play_timer = None
        
        if self.udp_socket:
            self.udp_socket.close()
            print("[VideoSync] Server stopped")
    
    
    def set_main_thread_callback(self, callback):
        self.main_thread_callback = callback
    
    
    def handle_control_message(self, data):
        # Fast check for valid media player
        if not self.media_player or not self._has_video(): return
        
        # 0: 'Start', 1: 'Stop', 2: 'OpStart', 3: 'Pause', 4: 'Continue', 5: 'Record'
        control_value = data.get('control')
        try:
            if control_value in (0, 4):  # Start or Continue
                self._handle_play(data, control_value == 0)
            elif control_value in (1, 3):  # Stop or Pause
                self._handle_pause(control_value == 1)
        except Exception as e:
            control_name = {0: 'Start', 1: 'Stop', 2: 'OpStart', 3: 'Pause', 4: 'Continue', 5: 'Record'}.get(control_value, f'Unknown({control_value})')
            print(f"[VideoSync] Error handling {control_name}: {e}")
            traceback.print_exc()
    
    
    def _handle_play(self, data, is_start):
        # extract data
        start_at_ticks = data.get('startAt', 0)
        start_time = data.get('startTime', 0.0)  # Audio position in seconds
        playback_speed = data.get('audioSpeed', 1.0)
        # Convert C# Ticks to Unix timestamp
        current_timestamp = time.time()
        unix_timestamp = (start_at_ticks - self.TICKS_AT_UNIX_EPOCH) / self.TICKS_TO_SECONDS
        delay_seconds = unix_timestamp - current_timestamp
        # Timezone correction
        if abs(delay_seconds) > 3600:
            hours_to_adjust = round(delay_seconds / 3600)
            delay_seconds -= hours_to_adjust * 3600
        # Cancel any previous pending play
        if self.pending_play_timer:
            self.pending_play_timer.cancel()
        
        if delay_seconds > 0.01:
            # Schedule delayed playback
            self.pending_play_timer = threading.Timer(
                delay_seconds, self._do_play, args=[start_time, playback_speed, delay_seconds, is_start]
            )
            self.pending_play_timer.start()
        else:
            # Play immediately
            self._do_play(start_time, playback_speed, delay_seconds, is_start)


    def _do_play(self, start_time, playback_speed, delay_seconds, is_start):
        try:
            if not self.media_player or not self._has_video(): return
            
            # Use callback to execute in main thread
            if self.main_thread_callback:
                def play_action():

                    if self.last_play_speed != playback_speed:
                        self.media_player.setPlaybackRate(playback_speed)
                        self.last_play_speed = playback_speed
                    
                    if is_start:
                        # Start: set position and play
                        self.media_player.setPosition(int(start_time * 1000))
                        self.media_player.play()
                        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] video start: {start_time:.3f}s, delay {delay_seconds:.3f}s")
                    else: 
                        # Continue: skip setPosition
                        self.media_player.play()
                        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] video continue, delay {delay_seconds:.3f}s")
                
                self.main_thread_callback(play_action)
            
        except Exception as e:
            import traceback
            print(f"[VideoSync] Error during playback: {e}")
            traceback.print_exc()
    
    
    def _handle_pause(self, is_stop):
        try:
            if not self.media_player or not self._has_video(): return
            
            # Cancel any pending delayed playback
            if self.pending_play_timer:
                self.pending_play_timer.cancel()
                self.pending_play_timer = None
            
            # Use callback to execute in main thread
            if self.main_thread_callback:
                def pause_action():
                    self.media_player.pause()
                    action_name = "stop" if is_stop else "pause"
                    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] video {action_name}")
                
                self.main_thread_callback(pause_action)
            
        except Exception as e:
            print(f"[VideoSync] Error during pause: {e}")
    
    
    def _has_video(self):
        try:
            return self.media_player.hasVideo()
        except:
            return False
