import json
from datetime import datetime, timedelta
import threading
import socket


class VideoSyncServer:
    
    def __init__(self, media_player, listen_port=8014):
        self.media_player = media_player
        self.listen_port = listen_port
        self.server_thread = None
        self.udp_socket = None
        self.running = False
        self.pending_play_timer = None    # For delayed playback
        self.main_thread_callback = None  # Callback to execute in main thread
        
    
    def start(self):
        self.running = True
        
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('localhost', self.listen_port))
        self.udp_socket.settimeout(1.0)
        
        print(f"[VideoSync] Server started on port {self.listen_port}")
        
        def run_server():
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(65535)
                    message = json.loads(data.decode('utf-8'))
                    
                    threading.Thread(
                        target=self.handle_control_message,
                        args=(message,),
                        daemon=True
                    ).start()
                    
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
        CONTROL_MAP = {0: 'Start', 1: 'Stop', 2: 'OpStart', 3: 'Pause', 4: 'Continue', 5: 'Record'}
        
        control_value = data.get('control')
        if isinstance(control_value, int):
            control = CONTROL_MAP.get(control_value, f'Unknown({control_value})')
        else:
            control = str(control_value)
        
        if not self.media_player or not self._has_video():
            return
        
        try:
            if control in ['Start', 'Continue']:
                self._handle_play(data)
            elif control in ['Stop', 'Pause']:
                self._handle_pause()
        except Exception as e:
            print(f"[VideoSync] Error handling {control}: {e}")
            import traceback
            traceback.print_exc()
    
    
    def _handle_play(self, data):
        start_at_ticks = data.get('startAt', 0)
        start_time = data.get('startTime', 0.0)  # Audio position in seconds
        playback_speed = data.get('audioSpeed', 1.0)
        
        # Convert C# Ticks to Python datetime
        TICKS_AT_UNIX_EPOCH = 621355968000000000
        unix_timestamp = (start_at_ticks - TICKS_AT_UNIX_EPOCH) / 10000000.0
        target_time = datetime.fromtimestamp(unix_timestamp)
        delay_seconds = (target_time - datetime.now()).total_seconds()
        
        # Timezone correction
        if abs(delay_seconds) > 3600:
            hours_to_adjust = round(delay_seconds / 3600)
            target_time = target_time - timedelta(hours=hours_to_adjust)
            delay_seconds = (target_time - datetime.now()).total_seconds()
        
        # Cancel any previous pending play
        if self.pending_play_timer:
            self.pending_play_timer.cancel()
        
        if delay_seconds < -0.5:
            self._do_play(start_time, playback_speed)
        elif delay_seconds > 0.01:
            # Schedule delayed playback
            self.pending_play_timer = threading.Timer(
                delay_seconds, self._do_play, args=[start_time, playback_speed]
            )
            self.pending_play_timer.start()
        else:
            # Play immediately
            self._do_play(start_time, playback_speed)
    
    
    def _do_play(self, start_time, playback_speed):
        try:
            if not self.media_player or not self._has_video():
                return
            
            # Use callback to execute in main thread
            if self.main_thread_callback:
                def play_action():
                    self.media_player.setPlaybackRate(playback_speed)
                    self.media_player.setPosition(int(start_time * 1000))
                    self.media_player.play()
                    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] video play: {start_time:.3f}s")
                
                self.main_thread_callback(play_action)
            
        except Exception as e:
            import traceback
            print(f"[VideoSync] Error during playback: {e}")
            traceback.print_exc()
    
    
    def _handle_pause(self):
        try:
            if not self.media_player:
                return
            
            # Cancel any pending delayed playback
            if self.pending_play_timer:
                self.pending_play_timer.cancel()
                self.pending_play_timer = None
            
            # Use callback to execute in main thread
            if self.main_thread_callback:
                def pause_action():
                    self.media_player.pause()
                    print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] video pause")
                
                self.main_thread_callback(pause_action)
            
        except Exception as e:
            print(f"[VideoSync] Error during pause: {e}")
    
    
    def _has_video(self):
        try:
            return self.media_player.hasVideo()
        except:
            return False
