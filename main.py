"""
天气查询 API
App 端直接调用，无需注册、无需 key。

启动:  uvicorn main:app --host 0.0.0.0 --port 8000
示例:  GET /weather?city=Tokyo
       GET /weather?lat=35.68&lon=139.69
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import httpx
import os
from pathlib import Path

app = FastAPI(title="Weather API", version="1.2.0")

# 前端页面：访问 / 即可打开天气查询页面
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 显式读取代理配置，避免 httpx 解析系统 no_proxy 时出错
_PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")


def make_client() -> httpx.AsyncClient:
    # SSL_CERT_FILE: 某些代理环境需要指定系统 CA 证书路径
    verify = os.environ.get("SSL_CERT_FILE", True)
    return httpx.AsyncClient(timeout=10, trust_env=False, proxy=_PROXY, verify=verify)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO 天气代码 -> 中文描述
WEATHER_DESC = {
    0: "晴", 1: "多云转晴", 2: "多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨",
    56: "冻毛毛雨", 57: "冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "阵雨", 82: "暴雨",
    85: "阵雪", 86: "阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "雷阵雨伴冰雹",
}


async def geocode(city: str) -> dict:
    async with make_client() as client:
        r = await client.get(GEOCODE_URL, params={"name": city, "count": 1, "language": "zh"})
    data = r.json()
    if not data.get("results"):
        raise HTTPException(status_code=404, detail=f"找不到城市: {city}")
    return data["results"][0]


async def current_weather(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
        "timezone": "auto",
    }
    async with make_client() as client:
        r = await client.get(FORECAST_URL, params=params)
    data = r.json()
    if "current" not in data:
        raise HTTPException(status_code=502, detail="天气数据获取失败")
    return data["current"]


def build_response(place: dict, cur: dict) -> dict:
    code = cur.get("weather_code")
    return {
        "city": place.get("name"),
        "country": place.get("country"),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude"),
        "weather": {
            "description": WEATHER_DESC.get(code, "未知"),
            "code": code,
            "temperature": cur.get("temperature_2m"),
            "feels_like": cur.get("apparent_temperature"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind_speed_kmh": cur.get("wind_speed_10m"),
            "unit": {"temperature": "°C", "wind_speed": "km/h", "humidity": "%"},
        },
        "updated_at": cur.get("time"),
    }


async def daily_forecast(lat: float, lon: float, days: int) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
        "timezone": "auto",
        "forecast_days": days,
    }
    async with make_client() as client:
        r = await client.get(FORECAST_URL, params=params)
    data = r.json()
    if "daily" not in data:
        raise HTTPException(status_code=502, detail="预报数据获取失败")
    return data["daily"]


def build_forecast_response(place: dict, daily: dict) -> dict:
    days = []
    n = len(daily.get("time", []))
    for i in range(n):
        code = daily["weather_code"][i]
        days.append({
            "date": daily["time"][i],
            "description": WEATHER_DESC.get(code, "未知"),
            "code": code,
            "temp_max": daily["temperature_2m_max"][i],
            "temp_min": daily["temperature_2m_min"][i],
            "precipitation_probability": daily["precipitation_probability_max"][i],
            "wind_speed_max_kmh": daily["wind_speed_10m_max"][i],
        })
    return {
        "city": place.get("name"),
        "country": place.get("country"),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude"),
        "unit": {"temperature": "°C", "wind_speed": "km/h", "precipitation_probability": "%"},
        "forecast": days,
    }


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/", include_in_schema=False)
async def index():
    """天气查询前端页面。"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/weather")
async def weather(
    city: str | None = Query(default=None, description="城市名，如 Tokyo、巴黎、New York"),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
):
    if city:
        place = await geocode(city)
        cur = await current_weather(place["latitude"], place["longitude"])
        return build_response(place, cur)
    if lat is not None and lon is not None:
        place = {"name": None, "country": None, "latitude": lat, "longitude": lon}
        cur = await current_weather(lat, lon)
        return build_response(place, cur)
    raise HTTPException(status_code=400, detail="请提供 city 或 lat+lon 参数")


@app.get("/forecast")
async def forecast(
    city: str | None = Query(default=None, description="城市名，如 Tokyo、巴黎、New York"),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    days: int = Query(default=3, ge=1, le=7, description="预报天数，1~7"),
):
    """未来若干天的每日预报（含最高/最低温、天气描述、降水概率）。"""
    if city:
        place = await geocode(city)
    elif lat is not None and lon is not None:
        place = {"name": None, "country": None, "latitude": lat, "longitude": lon}
    else:
        raise HTTPException(status_code=400, detail="请提供 city 或 lat+lon 参数")
    daily = await daily_forecast(place["latitude"], place["longitude"], days)
    return build_forecast_response(place, daily)
