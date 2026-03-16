import ee
import os
import json
import requests
import logging
import time
import re

# =========================
# INIT EARTH ENGINE
# =========================

service_account = json.loads(os.environ["GEE_KEY"])

credentials = ee.ServiceAccountCredentials(
    service_account["client_email"],
    key_data=json.dumps(service_account)
)

ee.Initialize(credentials)

# =========================
# TELEGRAM CONFIG
# =========================

TELEGRAM_TOKEN = "8385287062:AAGgwYA0l7-Cuq4jA7dgcy5GkFAvDp7X1GM"
TELEGRAM_CHAT_ID = "1145085024"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

last_update_id = 0

# =========================
# TELEGRAM SEND
# =========================

def tg(msg, chat_id=None):

    cid = chat_id or TELEGRAM_CHAT_ID

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": cid, "text": msg, "parse_mode": "HTML"},
        timeout=15
    )

# =========================
# SOIL DATA FROM GEE
# =========================

depths = ["0-5cm","5-15cm","15-30cm","30-60cm","60-100cm","100-200cm"]

datasets = {
"clay":"projects/soilgrids-isric/clay_mean",
"sand":"projects/soilgrids-isric/sand_mean",
"silt":"projects/soilgrids-isric/silt_mean",
"bdod":"projects/soilgrids-isric/bdod_mean",
"soc":"projects/soilgrids-isric/soc_mean",
"cec":"projects/soilgrids-isric/cec_mean"
}

def get_soil_all(lat,lon):

    point = ee.Geometry.Point([lon,lat])
    result = {}

    for depth in depths:

        result[depth] = {}

        for prop,ds in datasets.items():

            img = ee.Image(ds).select(depth)

            val = img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=250
            ).get(depth)

            if val:
                result[depth][prop] = ee.Number(val).getInfo()

    return result

# =========================
# TERRAIN DATA
# =========================

def get_terrain(lat,lon):

    point = ee.Geometry.Point([lon,lat])

    dem = ee.Image("USGS/SRTMGL1_003")

    slope = ee.Terrain.slope(dem)

    elevation = dem.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point,
        scale=30
    ).get("elevation")

    slope_val = slope.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point,
        scale=30
    ).get("slope")

    return {
        "elevation": ee.Number(elevation).getInfo(),
        "slope": ee.Number(slope_val).getInfo()
    }

# =========================
# SOIL CLASSIFICATION
# =========================

def classify_soil(clay,sand,silt):

    if clay >= 40 and silt >= 40:
        return "Silty Clay"

    if clay >= 40:
        return "Clay"

    if sand >= 85:
        return "Sand"

    if sand >= 70:
        return "Loamy Sand"

    if clay >= 27:
        return "Clay Loam"

    if silt >= 50:
        return "Silt Loam"

    return "Loam"

# =========================
# ANALYSIS
# =========================

def analyze_soil(lat,lon,chat_id):

    tg(f"⏳ Analisis tanah...\n📍 {lat}, {lon}", chat_id)

    try:

        soil = get_soil_all(lat,lon)
        terrain = get_terrain(lat,lon)

    except Exception as e:

        tg(f"❌ Error: {str(e)}", chat_id)
        return

    msg = (
    f"📍 <b>SOIL REPORT</b>\n"
    f"Koordinat: {lat},{lon}\n\n"
    )

    for depth,data in soil.items():

        clay = data.get("clay",0)
        sand = data.get("sand",0)
        silt = data.get("silt",0)

        soil_type = classify_soil(clay,sand,silt)

        msg += (
        f"━━ {depth} ━━\n"
        f"Clay: {clay:.1f}%\n"
        f"Sand: {sand:.1f}%\n"
        f"Silt: {silt:.1f}%\n"
        f"Soil: {soil_type}\n\n"
        )

    msg += (
    "━━ TERRAIN ━━\n"
    f"Elevation: {terrain['elevation']:.1f} m\n"
    f"Slope: {terrain['slope']:.2f}°\n"
    )

    tg(msg,chat_id)

# =========================
# TELEGRAM LOOP
# =========================

def check_messages():

    global last_update_id

    while True:

        try:

            url = (
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            f"?offset={last_update_id+1}&timeout=30"
            )

            r = requests.get(url,timeout=35).json()

            for update in r.get("result",[]):

                last_update_id = update["update_id"]

                msg = update.get("message",{})
                chat_id = str(msg.get("chat",{}).get("id",""))

                text = msg.get("text","").strip()

                coord = re.search(
                r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)",
                text
                )

                if coord:

                    lat = float(coord.group(1))
                    lon = float(coord.group(2))

                    analyze_soil(lat,lon,chat_id)

                else:

                    tg(
                    "Kirim koordinat:\n<code>-7.6048,111.9102</code>",
                    chat_id
                    )

        except Exception as e:

            log.error(e)

        time.sleep(2)

# =========================
# MAIN
# =========================

def main():

    tg("✅ Soil Bot GEE aktif")
    check_messages()

main()