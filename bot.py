TELEGRAM_TOKEN = "8461262353:AAEqHf4cYS_A-owVheW23DSZuX8QPEzvpNk"
TELEGRAM_CHAT_ID = "1145085024"

import time, requests, logging, threading
from datetime import datetime
import pytz

LAT = -7.6048403
LON = 111.9102329
THRESHOLD = 5.0
INTERVAL = 15 * 60
WIB = pytz.timezone("Asia/Jakarta")
REPORT_HOURS = {5, 9, 15, 16, 17, 20}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)
alerted = False
last_report_hour = -1
last_update_id = 0

def get_weather():
    url = (f"https://api.open-meteo.com/v1/forecast"
           f"?latitude={LAT}&longitude={LON}"
           f"&current=rain,precipitation,temperature_2m,relative_humidity_2m,"
           f"wind_speed_10m,cloud_cover,weather_code"
           f"&timezone=Asia%2FJakarta")
    d = requests.get(url, timeout=10).json()["current"]
    rain = d.get("rain") or d.get("precipitation") or 0.0
    return {
        "rain": rain,
        "temp": d.get("temperature_2m"),
        "humid": d.get("relative_humidity_2m"),
        "wind": d.get("wind_speed_10m"),
        "cloud": d.get("cloud_cover"),
        "code": d.get("weather_code"),
    }

def interpret(w):
    rain = w["rain"]
    cloud = w["cloud"]
    if rain == 0:
        if cloud >= 75:
            rain_interp = "Tidak hujan, tapi langit sangat mendung ☁️ — berpotensi hujan"
        elif cloud >= 40:
            rain_interp = "Tidak hujan, langit agak berawan 🌤"
        else:
            rain_interp = "Cerah, tidak ada tanda hujan ☀️"
    elif rain <= 1:
        rain_interp = "Gerimis ringan — belum perlu khawatir 🌦"
    elif rain <= 5:
        rain_interp = "Hujan sedang — pantau terus, mendekati ambang batas ⚠️"
    elif rain <= 10:
        rain_interp = "Hujan deras — risiko banjir, pompa perlu dinyalakan! 🚨"
    elif rain <= 20:
        rain_interp = "Hujan sangat deras — bahaya banjir tinggi! 🆘"
    else:
        rain_interp = "Hujan ekstrem — segera ambil tindakan! 🆘🆘"

    if cloud >= 90:
        cloud_interp = "Sangat mendung ({}%) — hujan bisa turun kapan saja".format(cloud)
    elif cloud >= 75:
        cloud_interp = "Mendung tebal ({}%) — waspada".format(cloud)
    elif cloud >= 40:
        cloud_interp = "Berawan ({}%)".format(cloud)
    elif cloud >= 10:
        cloud_interp = "Sedikit berawan ({}%)".format(cloud)
    else:
        cloud_interp = "Cerah ({}%)".format(cloud)

    return rain_interp, cloud_interp

def tg(msg):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                  json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
                  timeout=10)

def format_report(w, title="📊 <b>Laporan Cuaca</b>"):
    rain_interp, cloud_interp = interpret(w)
    now = datetime.now(WIB).strftime("%H:%M WIB, %d %b %Y")
    return (
        f"{title} — {now}\n"
        f"📍 Mangundikaran, Nganjuk\n\n"
        f"🌧 Curah hujan: <b>{w['rain']:.1f} mm/jam</b>\n"
        f"↳ {rain_interp}\n\n"
        f"☁️ Tutupan awan: <b>{w['cloud']}%</b>\n"
        f"↳ {cloud_interp}\n\n"
        f"🌡 Suhu: {w['temp']:.1f}°C\n"
        f"💧 Kelembaban: {w['humid']}%\n"
        f"💨 Angin: {w['wind']:.0f} km/jam"
    )

def check_messages():
    global last_update_id
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            r = requests.get(url, timeout=35).json()
            for update in r.get("result", []):
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "").strip().lower()
                if chat_id == TELEGRAM_CHAT_ID and text in ["cek", "/cek"]:
                    log.info("Perintah 'cek' diterima")
                    w = get_weather()
                    tg(format_report(w, "🔍 <b>Cek Manual</b>"))
        except Exception as e:
            log.error(f"Error cek pesan: {e}")
        time.sleep(2)

def main():
    global alerted, last_report_hour
    log.info("Bot start")
    tg("✅ <b>Penjaga Pompa aktif!</b>\n"
       "📍 Mangundikaran, Nganjuk\n"
       "🔁 Cek tiap 15 menit\n"
       "📊 Laporan rutin: 05.00, 09.00, 15.00, 16.00, 17.00, 20.00 WIB\n"
       "⚠️ Alert otomatis + update tiap 15 menit jika hujan deras\n"
       "☁️ Info mendung disertakan\n"
       "💬 Ketik <b>cek</b> kapan saja untuk cek manual!")

    # Jalankan listener pesan di thread terpisah
    t = threading.Thread(target=check_messages, daemon=True)
    t.start()

    while True:
        try:
            w = get_weather()
            now = datetime.now(WIB)
            hour = now.hour
            log.info(f"Hujan: {w['rain']} mm/jam | Awan: {w['cloud']}% | Jam: {hour}")

            # Laporan rutin
            if hour in REPORT_HOURS and hour != last_report_hour:
                tg(format_report(w))
                last_report_hour = hour

            # Alert hujan deras
            if w["rain"] > THRESHOLD:
                if not alerted:
                    tg(format_report(w, "🚨 <b>POMPA PERLU DINYALAKAN!</b>") +
                       "\n\n⚡ <b>Segera hubungi tetangga!</b>")
                    alerted = True
                else:
                    tg(f"🚨 <b>Masih hujan deras!</b> — {now.strftime('%H:%M WIB')}\n"
                       f"🌧 <b>{w['rain']:.1f} mm/jam</b>\n"
                       f"☁️ Awan: {w['cloud']}%\n"
                       f"⚡ Pompa tetap nyalakan!")
            else:
                if alerted:
                    tg(format_report(w, "✅ <b>Hujan reda</b>") +
                       "\n\nPompa bisa dimatikan.")
                alerted = False

        except Exception as e:
            log.error(e)

        time.sleep(INTERVAL)

main()