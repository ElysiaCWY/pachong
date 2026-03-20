# -*- coding: utf-8 -*-
import sys
import os
import time

class DualOutput:
    """Helper class to duplicate stdout to a file."""
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.filename = filename
        self.log = None

    def _open(self):
        if self.log is None:
            self.log = open(self.filename, "a", encoding="utf-8")

    def write(self, message):
        self._open()
        try:
            self.terminal.write(message)
            self.log.write(message)
            self.log.flush()
        except Exception:
            pass

    def flush(self):
        try:
            self.terminal.flush()
            if self.log:
                self.log.flush()
        except Exception:
            pass

def setup_logging():
    """
    配置日志记录：将 print() 输出内容保存到 logs/ 目录下的文件中，便于排查问题。
    文件名格式：run_log_YYYYMMDD_HHMMSS.txt
    """
    log_dir = "logs"
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except Exception as e:
            print(f"Warning: Could not create log directory {log_dir}: {e}")
            return

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"run_log_{timestamp}.txt"
    filepath = os.path.join(log_dir, filename)

    try:
        # 重定向 stdout 和 stderr
        # 注意：这样会把所有后续的 print 都捕捉进文件
        sys.stdout = DualOutput(filepath)
        sys.stderr = sys.stdout 
        
        print(f"=================================================")
        print(f"日志记录已启动")
        print(f"日志文件: {os.path.abspath(filepath)}")
        print(f"启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"=================================================")

        # 清理旧日志（删除所有非当天的 run_log_*.txt）
        today_date_str = time.strftime("%Y%m%d")
        removed_count = 0
        for f in os.listdir(log_dir):
            if f.startswith("run_log_") and f.endswith(".txt"):
                # 检查文件名中是否包含今天的日期
                # 文件名格式: run_log_YYYYMMDD_HHMMSS.txt
                # split("_") -> ['run', 'log', 'YYYYMMDD', 'HHMMSS.txt']
                parts = f.split("_")
                if len(parts) >= 3:
                     file_date = parts[2]
                     if file_date != today_date_str:
                        try:
                            os.remove(os.path.join(log_dir, f))
                            print(f"[Log Cleanup] 已删除旧日志: {f}")
                            removed_count += 1
                        except Exception as e:
                            print(f"[Log Cleanup] 删除失败 {f}: {e}")
        
        if removed_count > 0:
            print(f"[Log Cleanup] 共清理 {removed_count} 个旧日志文件。")

    except Exception as e:
        print(f"Failed to setup logging: {e}")
