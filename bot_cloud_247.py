import time
import requests
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Servidor HTTP simples para o Health Check do Render Web Service
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Webhook Google Ativo 24/7")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        return

def start_health_server():
    try:
        port = int(os.environ.get("PORT", 10000))
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        print(f"[HEALTH CHECK SERVER] Rodando na porta {port}")
        server.serve_forever()
    except Exception as e:
        print(f"[WARN HEALTH SERVER]: {e}")

threading.Thread(target=start_health_server, daemon=True).start()

TELEGRAM_TOKEN = "8598409500:AAFQrj1Igkm1c5VwvFi3qvHeKqwTqu5w3io"
SHEETS_URL = "https://script.google.com/macros/s/AKfycbx_1MVLegN4fwaxS4bBLVq0u50DkF-BoFRC1qFB-uKyVJA4Df76H1sAvV6tJPlcd0KP/exec"

def set_webhook_automatico():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        payload = {"url": SHEETS_URL}
        resp = requests.post(url, json=payload, timeout=10)
        print(f"[WEBHOOK AUTO]: {resp.json()}")
    except Exception as e:
        print(f"[ERRO SET WEBHOOK]: {e}")

# Ativa o Webhook no arranque
set_webhook_automatico()

print("==================================================")
print("   ROBÔ MIGRADO PARA WEBHOOK GOOGLE SERVERLESS   ")
print("==================================================")

# Mantém o servidor de Health Check vivo sem interferir no Webhook
while True:
    time.sleep(3600)
