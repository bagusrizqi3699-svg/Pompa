TELEGRAM_TOKEN = "8461262353:AAEqHf4cYS_A-owVheW23DSZuX8QPEzvpNk"
TELEGRAM_CHAT_ID = "1145085024"
TOMORROW_API_KEY = "mafGBXd8wO6o1DHn7Ok8PwpG4zJvFIWB"

import time, requests, logging, threading
from datetime import datetime
import pytz

LAT = -7.6048403
LON = 111.9102329
THRESHOLD = 4.0
INTERVAL_MONITOR = 15 * 60
INTERVAL_RAIN_UPDATE = 30 * 60
WIB = pytz.timezone("Asia/Jakarta")
REPORT_HOURS = {5, 9, 15, 16, 17, 20}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)
alerted = False
last_report_hour = -1
last_update_id = 0
last_rain_notif = 0

def get_weather_openmeteo():
    url = (f"https://api.open-meteo.com/v1/forecast"
           f"?latitude={LAT}&longitude={LON}"
           f"&current=rain,precipitation,temperature_2m,relative_humidity_2m,"
           f"wind_speed_10m,cloud_cover"
           f"&timezone=Asia%2FJakarta")
    d = requests.get(url, timeout=10).json()["current"]
    rain = d.get("rain") or d.get("precipitation") or 0.0
    return {
        "rain": rain,
        "temp": d.get("temperature_2m"),
        "humid": d.get("relative_humidity_2m"),
        "wind": d.get("wind_speed_10m"),
        "cloud": d.get("cloud_cover"),
    }

def get_weather_tomorrow():
    url = (f"https://api.tomorrow.io/v4/timelines"
           f"?location={LAT},{LON}"
           f"&fields=precipitationIntensity,temperature,humidity,windSpeed,cloudCover"
           f"&timesteps=current"
           f"&units=metric"
           f"&apikey={TOMORROW_API_KEY}")
    r = requests.get(url, timeout=10).json()
    d = r["data"]["timelines"][0]["intervals"][0]["values"]
    return {
        "rain": d.get("precipitationIntensity", 0.0),
        "temp": d.get("temperature"),
        "humid": d.get("humidity"),
        "wind": d.get("windSpeed"),
        "cloud": d.get("cloudCover"),
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
    elif rain <= 4:
        rain_interp = "Hujan sedang — pantau terus ⚠️"
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

def format_openmeteo(w, title="📊 <b>Laporan Cuaca</b>"):
    rain_interp, cloud_interp = interpret(w)
    now = datetime.now(WIB).strftime("%H:%M WIB, %d %b %Y")
    return (
        f"🔵 <b>[OPEN-METEO]</b>\n"
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

def format_tomorrow(w, title="🚨 <b>POMPA PERLU DINYALAKAN!</b>"):
    rain_interp, cloud_interp = interpret(w)
    now = datetime.now(WIB).strftime("%H:%M WIB, %d %b %Y")
    return (
        f"🔴 <b>[TOMORROW.IO LIVE]</b>\n"
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
                if chat_id == TELEGRAM_CHAT_ID:
                    if text in ["cek", "/cek"]:
                        log.info("Cek manual Open-Meteo")
                        w = get_weather_openmeteo()
                        tg(format_openmeteo(w, "🔍 <b>Cek Manual</b>"))
                    elif text in ["live", "/live"]:
                        log.info("Cek manual Tomorrow.io")
                        w = get_weather_tomorrow()
                        tg(format_tomorrow(w, "🔍 <b>Cek Live</b>"))
        except Exception as e:
            log.error(f"Error cek pesan: {e}")
        time.sleep(2)

def main():
    global alerted, last_report_hour, last_rain_notif
    log.info("Bot start")
    tg("✅ <b>Penjaga Pompa aktif!</b>\n"
       "📍 Mangundikaran, Nganjuk\n"
       "🔵 Ketik <b>cek</b> → Open-Meteo (unlimited)\n"
       "🔴 Ketik <b>live</b> → Tomorrow.io (real-time)\n"
       "📊 Laporan rutin: 05.00, 09.00, 15.00, 16.00, 17.00, 20.00 WIB\n"
       "🚨 Alert otomatis Tomorrow.io jika hujan &gt;4 mm/jam")

    t = threading.Thread(target=check_messages, daemon=True)
    t.start()

    while True:
        try:
            now = datetime.now(WIB)
            hour = now.hour

            w_tomorrow = get_weather_tomorrow()
            log.info(f"[Tomorrow.io] Hujan: {w_tomorrow['rain']} mm/jam")

            if w_tomorrow["rain"] > THRESHOLD:
                now_ts = time.time()
                if not alerted:
                    tg(format_tomorrow(w_tomorrow) +
                       "\n\n⚡ <b>Segera hubungi tetangga!</b>")
                    alerted = True
                    last_rain_notif = now_ts
                elif now_ts - last_rain_notif >= INTERVAL_RAIN_UPDATE:
                    tg(format_tomorrow(w_tomorrow, "🚨 <b>Masih hujan deras!</b>") +
                       "\n\n⚡ Pompa tetap nyalakan!")
                    last_rain_notif = now_ts
            else:
                if alerted:
                    tg(format_tomorrow(w_tomorrow, "✅ <b>Hujan reda</b>") +
                       "\n\nPompa bisa dimatikan.")
                alerted = False
                last_rain_notif = 0

            if hour in REPORT_HOURS and hour != last_report_hour:
                w_open = get_weather_openmeteo()
                tg(format_openmeteo(w_open))
                last_report_hour = hour

        except Exception as e:
            log.error(e)

        time.sleep(INTERVAL_MONITOR)

main()