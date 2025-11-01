import json
from datetime import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

class MediaPlayerController:
    
    def __init__(self, media_player):
        self.media_player = media_player
        self.is_playing = False
        
    def play_video(self, start_time, delay_seconds, playback_speed):
        print(f"播放视频 - 起始时间: {start_time}s, 延迟: {delay_seconds}s, 速度: {playback_speed}")
        if self.media_player:
            self.media_player.setPlaybackRate(playback_speed)
            self.media_player.setPosition(int(start_time * 1000))  # 转换为毫秒
            self.media_player.play()
        self.is_playing = True
        
    def pause_video(self):
        print("暂停视频")
        if self.media_player:
            self.media_player.pause()
        self.is_playing = False
        
    def resume_video(self, start_time, delay_seconds, playback_speed):
        print(f"继续播放 - 起始时间: {start_time}s, 延迟: {delay_seconds}s, 速度: {playback_speed}")
        if self.media_player:
            self.media_player.setPlaybackRate(playback_speed)
            self.media_player.setPosition(int(start_time * 1000))
            self.media_player.play()
        self.is_playing = True
        
    def stop_video(self):
        print("停止视频")
        if self.media_player:
            self.media_player.stop()
        self.is_playing = False


class MajdataListenerHandler(BaseHTTPRequestHandler):
    
    def __init__(self, *args, media_controller=None, **kwargs):
        self.media_controller = media_controller
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        try:
            # 读取请求数据
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            print(f"监听收到MajdataEdit请求: {data.get('control')}")
            
            # 控制媒体播放器
            self.control_media_player(data)
            
            # 返回成功响应（MajdataEdit和MajdataView的正常通信不受影响）
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b"OK")
            
        except Exception as e:
            print(f"监听处理请求时出错: {e}")
            self.send_error(500, f"Internal Server Error: {e}")
    
    def control_media_player(self, data):
        if not self.media_controller:
            return
            
        control = data.get('control')
        
        if control in ['Start', 'Continue']:
            start_at = data.get('startAt', 0)
            start_time = data.get('startTime', 0)
            audio_speed = data.get('audioSpeed', 1.0)
            
            # 计算延迟时间
            target_time = datetime.fromtimestamp(start_at / 10000000)  # Ticks转DateTime
            current_time = datetime.now()
            delay_seconds = max(0, (target_time - current_time).total_seconds())
            
            if control == 'Start':
                self.media_controller.play_video(start_time, delay_seconds, audio_speed)
            else:  # Continue
                self.media_controller.resume_video(start_time, delay_seconds, audio_speed)
                
        elif control == 'Pause':
            self.media_controller.pause_video()
            
        elif control == 'Stop':
            self.media_controller.stop_video()
    
    def log_message(self, format, *args):
        """自定义日志输出"""
        # 静默日志，避免过多输出
        pass


class MajdataListenerServer:
    
    def __init__(self, media_controller, listen_port=8013):
        self.media_controller = media_controller
        self.listen_port = listen_port
        self.server_thread = None
        self.http_server = None
        
    def start(self):
        # 创建自定义的Handler类，传入media_controller
        def handler_factory(*args, **kwargs):
            return MajdataListenerHandler(*args, 
                                        media_controller=self.media_controller, 
                                        **kwargs)
        
        # 启动HTTP服务器
        self.http_server = HTTPServer(('localhost', self.listen_port), handler_factory)
        print(f"Majdata监听服务器启动 - 监听端口: {self.listen_port} (纯监听模式)")
        
        # 在后台线程中运行服务器
        def run_server():
            try:
                self.http_server.serve_forever()
            except KeyboardInterrupt:
                print("Majdata监听服务器停止")
            except Exception as e:
                print(f"Majdata监听服务器错误: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
    def stop(self):
        print("Majdata监听服务器正在停止...")
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()
            print("Majdata监听服务器已停止")
