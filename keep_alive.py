import requests
import threading
import time
import os

def keep_alive():
    """Botni uxlab qolmasligi uchun har 5 daqiqada ping yuborish"""
    url = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:10000')
    
    def ping():
        while True:
            try:
                requests.get(url, timeout=10)
                print("✅ Keep-alive ping yuborildi")
            except Exception as e:
                print(f"⚠️ Ping xatolik: {e}")
            time.sleep(300)  # 5 daqiqa
    
    thread = threading.Thread(target=ping, daemon=True)
    thread.start()
