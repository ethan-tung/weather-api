# 天气查询服务（API + 前端页面）

给 App 用的天气服务：后端接口 + 一个可直接打开的天气查询网页。
数据源是 Open-Meteo（免费、无需注册、无需 key，覆盖全球）。

## 网页

启动服务后，浏览器打开 `http://localhost:8000/`（或服务器地址）即可使用：
输入城市名 → 显示实时天气 + 未来 5 天预报。页面自带 8 个热门城市快捷按钮。

## 接口

### GET /weather
| 参数 | 说明 | 示例 |
|---|---|---|
| `city` | 城市名（中英文都行） | `?city=东京` |
| `lat` + `lon` | 经纬度（和 city 二选一） | `?lat=35.68&lon=139.69` |

返回示例：
```json
{
  "city": "东京",
  "country": "日本",
  "latitude": 35.6895,
  "longitude": 139.69171,
  "weather": {
    "description": "晴",
    "code": 0,
    "temperature": 24.7,
    "feels_like": 25.8,
    "humidity": 55,
    "wind_speed_kmh": 6.4,
    "unit": {"temperature": "°C", "wind_speed": "km/h", "humidity": "%"}
  },
  "updated_at": "2026-10-12T13:30"
}
```

### GET /forecast
未来每日预报（App 做 3~7 天天气卡片用）。

| 参数 | 说明 | 示例 |
|---|---|---|
| `city` 或 `lat`+`lon` | 同上 | `?city=东京&days=5` |
| `days` | 预报天数，1~7，默认 3 | `?city=巴黎&days=7` |

返回每天的日期、中文天气描述、最高/最低温、降水概率、最大风速。

### GET /health
健康检查，返回 `{"ok": true}`。

## 本地运行

```bash
cd weather-api
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn httpx
uvicorn main:app --host 0.0.0.0 --port 8000
```

然后访问 `http://localhost:8000/weather?city=巴黎`，交互文档在 `http://localhost:8000/docs`。

## 部署到服务器（给 App 调用）

### 方式一：Docker 一键部署（推荐）

```bash
cd weather-api
docker build -t weather-api .
docker run -d --name weather-api -p 8000:8000 --restart unless-stopped weather-api
```

### 方式二：直接运行

1. 把 `weather-api` 整个文件夹传到你的云服务器
2. 按上面步骤安装依赖并启动（生产环境建议加 `--workers 2`，并用 systemd / Docker 保持运行）
3. App 里请求 `http://你的服务器IP:8000/weather?city=xxx` 即可

Swift 示例：
```swift
let url = URL(string: "http://你的服务器IP:8000/weather?city=东京")!
let (data, _) = try await URLSession.shared.data(from: url)
// 解析 JSON 里的 weather.description / temperature
```

## 说明

- 城市名支持中文、英文、拼音，内部会自动转成经纬度查询
- 天气描述已翻译成中文（晴、多云、小雨、雷阵雨等）
- 免费额度足够个人 App 使用
- 前端页面在 `static/index.html`，改样式直接编辑这个文件即可
