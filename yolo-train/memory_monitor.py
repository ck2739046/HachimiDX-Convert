"""
实时内存监控脚本
在训练过程中监控内存使用情况
"""

import psutil
import torch
import time
import matplotlib.pyplot as plt
from datetime import datetime
import threading

class MemoryMonitor:
    def __init__(self):
        self.running = False
        self.ram_usage = []
        self.gpu_usage = []
        self.timestamps = []
        
    def monitor_memory(self):
        """监控内存使用"""
        while self.running:
            # RAM监控
            ram = psutil.virtual_memory()
            ram_percent = ram.percent
            ram_used_gb = (ram.total - ram.available) / (1024**3)
            
            # GPU监控
            gpu_used_gb = 0
            if torch.cuda.is_available():
                gpu_used_gb = torch.cuda.memory_allocated() / (1024**3)
            
            # 记录数据
            self.ram_usage.append(ram_used_gb)
            self.gpu_usage.append(gpu_used_gb)
            self.timestamps.append(datetime.now())
            
            # 控制台输出
            print(f"\r内存使用 - RAM: {ram_used_gb:.1f}GB ({ram_percent:.1f}%), "
                  f"GPU: {gpu_used_gb:.1f}GB", end="", flush=True)
            
            time.sleep(5)  # 每5秒监控一次
    
    def start_monitoring(self):
        """开始监控"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_memory)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print("内存监控已启动...")
    
    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join()
        print("\n内存监控已停止")
    
    def plot_usage(self):
        """绘制内存使用图表"""
        if not self.timestamps:
            print("没有监控数据")
            return
            
        plt.figure(figsize=(12, 6))
        
        # RAM使用图
        plt.subplot(2, 1, 1)
        plt.plot(self.timestamps, self.ram_usage, 'b-', label='RAM使用')
        plt.axhline(y=32, color='r', linestyle='--', label='32GB线')
        plt.ylabel('RAM使用 (GB)')
        plt.title('内存使用监控')
        plt.legend()
        plt.grid(True)
        
        # GPU使用图
        if torch.cuda.is_available():
            plt.subplot(2, 1, 2)
            plt.plot(self.timestamps, self.gpu_usage, 'g-', label='GPU内存使用')
            gpu_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            plt.axhline(y=gpu_total, color='r', linestyle='--', label=f'GPU总内存 ({gpu_total:.1f}GB)')
            plt.ylabel('GPU内存使用 (GB)')
            plt.xlabel('时间')
            plt.legend()
            plt.grid(True)
        
        plt.tight_layout()
        plt.savefig('memory_usage.png', dpi=300, bbox_inches='tight')
        plt.show()
        print("内存使用图表已保存为 memory_usage.png")

def get_memory_recommendations():
    """获取内存优化建议"""
    total_ram = psutil.virtual_memory().total / (1024**3)
    available_ram = psutil.virtual_memory().available / (1024**3)
    
    print("=== 内存优化建议 ===")
    print(f"总内存: {total_ram:.1f}GB")
    print(f"可用内存: {available_ram:.1f}GB")
    
    if total_ram >= 32:
        print("✅ 大内存系统检测到！建议配置:")
        print("  - 批次大小: 32-48")
        print("  - 数据加载进程: 8-12")
        print("  - 缓存模式: 'ram' (全内存缓存)")
        print("  - 启用复杂数据增强")
        print("  - 可以训练更大的模型")
    elif total_ram >= 16:
        print("✅ 中等内存系统，建议配置:")
        print("  - 批次大小: 16-24")
        print("  - 数据加载进程: 4-8")
        print("  - 缓存模式: 'ram'或True")
    else:
        print("⚠️ 内存较小，建议:")
        print("  - 批次大小: 8-16")
        print("  - 数据加载进程: 2-4")
        print("  - 缓存模式: True")
    
    if torch.cuda.is_available():
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"\nGPU内存: {gpu_memory:.1f}GB")
        if gpu_memory >= 8:
            print("✅ GPU内存充足，可以使用大批次训练")
        else:
            print("⚠️ GPU内存有限，建议减小批次大小")

if __name__ == "__main__":
    get_memory_recommendations()
    
    # 可选：启动监控
    choice = input("\n是否启动内存监控? (y/n): ")
    if choice.lower() == 'y':
        monitor = MemoryMonitor()
        monitor.start_monitoring()
        
        try:
            input("按Enter键停止监控...")
        except KeyboardInterrupt:
            pass
        finally:
            monitor.stop_monitoring()
            monitor.plot_usage()
