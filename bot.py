TELEGRAM_TOKEN = "8461262353:AAEqHf4cYS_A-owVheW23DSZuX8QPEzvpNk"
TELEGRAM_CHAT_ID = "1145085024"

import time, requests, logging
from datetime import datetime

LAT = -7.6048403
LON = 111.9102329
THRESHOLD = 5.0
INTERVAL = 15 * 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)
alerted = False

def get_rain():
    url = (f"https://api.open-meteo.com/v1/forecast"
           f"?latitude={LAT}&longitude={LON}"
           f"&current=rain,precipitation,temperature_2m"
           f"&timezone=Asia%2FJakarta")
    d = requests.get(url, timeout=10).json()["current"]
    return d.get("rain") or d.get("precipitation") or 0.0, d.get("temperature_2m")

def tg(msg):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                  json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
                  timeout=10)

def main():
    global alerted
    log.info("Bot start")
    tg("✅ <b>Penjaga Pompa aktif!</b>\n📍 Mangundikaran, Nganjuk\n🔁 Cek tiap 15 menit | ⚠️ Alert jika hujan &gt;5 mm/jam")
    while True:
        try:
            rain, temp = get_rain()
            now = datetime.now().strftime("%H:%M WIB")
            log.info(f"Hujan: {rain} mm/jam | Suhu: {temp}°C")
            if rain > THRESHOLD:
                if not alerted:
                    tg(f"🚨 <b>POMPA PERLU DINYALAKAN!</b>\n\n📍 Mangundikaran, Nganjuk\n🕐 {now}\n🌧 <b>Hujan: {rain:.1f} mm/jam</b>\n🌡 Suhu: {temp:.1f}°C\n\n⚡ Segera hubungi tetangga!")
                    alerted = True
            else:
                if alerted:
                    tg(f"✅ <b>Hujan reda</b> — {now}\n🌧 Sekarang: {rain:.1f} mm/jam\nPompa bisa dimatikan.")
                alerted = False
        except Exception as e:
            log.error(e)
        time.sleep(INTERVAL)

main()
