import shutil
import socket
import psutil

def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r", encoding="utf-8") as f:
            return float(f.read().strip()) / 1000
    except Exception:
        return None

def summary():
    ram = psutil.virtual_memory()
    disk = shutil.disk_usage("/")
    return {
        "hostname": socket.gethostname(),
        "cpu": psutil.cpu_percent(interval=None),
        "ram": ram.percent,
        "disk": disk.used / disk.total * 100,
        "temp": cpu_temp(),
    }
