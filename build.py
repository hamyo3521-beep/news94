#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
매일 당일 기준으로 데일리 브리핑 페이지(index.html)를 생성합니다.
- 날씨: Open-Meteo (무료, API 키 불필요)
- 뉴스: 구글 뉴스 RSS (한국)
표준 라이브러리만 사용하므로 별도 설치가 필요 없습니다.
"""

import html
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ── 설정 ──────────────────────────────────────────────
LAT, LON = 37.5644, 127.0294          # 상왕십리역 좌표
PLACE = "서울 성동구 상왕십리역"
TZ = timezone(timedelta(hours=9))      # KST
NEWS_FEEDS = [
    ("주요", "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko", 4),
    ("경제", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko", 3),
    ("세계", "https://news.google.com/rss/headlines/section/topic/WORLD?hl=ko&gl=KR&ceid=KR:ko", 2),
]
UA = {"User-Agent": "Mozilla/5.0 (compatible; DailyBriefingBot/1.0)"}

WMO = {
    0: ("맑음", "☀️"), 1: ("대체로 맑음", "🌤️"), 2: ("구름 조금", "⛅"), 3: ("흐림", "☁️"),
    45: ("안개", "🌫️"), 48: ("서리 안개", "🌫️"),
    51: ("약한 이슬비", "🌦️"), 53: ("이슬비", "🌦️"), 55: ("강한 이슬비", "🌧️"),
    61: ("약한 비", "🌦️"), 63: ("비", "🌧️"), 65: ("강한 비", "🌧️"),
    66: ("얼어붙는 비", "🌨️"), 67: ("강한 어는 비", "🌨️"),
    71: ("약한 눈", "🌨️"), 73: ("눈", "🌨️"), 75: ("많은 눈", "❄️"), 77: ("싸락눈", "🌨️"),
    80: ("소나기", "🌦️"), 81: ("소나기", "🌧️"), 82: ("강한 소나기", "⛈️"),
    85: ("소낙눈", "🌨️"), 86: ("강한 소낙눈", "❄️"),
    95: ("천둥번개", "⛈️"), 96: ("우박 동반 뇌우", "⛈️"), 99: ("강한 우박 뇌우", "⛈️"),
}


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_weather():
    """Open-Meteo에서 3일치 예보를 가져옵니다. 실패 시 None."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_sum,precipitation_probability_max"
        "&current=temperature_2m,weather_code"
        "&timezone=Asia%2FSeoul&forecast_days=3"
    )
    try:
        data = json.loads(fetch(url))
    except Exception as e:
        print(f"[weather] 실패: {e}")
        return None

    d = data["daily"]
    days = []
    for i in range(len(d["time"])):
        code = d["weather_code"][i]
        desc, icon = WMO.get(code, ("정보 없음", "🌡️"))
        days.append({
            "date": d["time"][i],
            "desc": desc,
            "icon": icon,
            "tmax": d["temperature_2m_max"][i],
            "tmin": d["temperature_2m_min"][i],
            "rain": d["precipitation_sum"][i],
            "pop": d["precipitation_probability_max"][i],
        })
    cur = data.get("current", {})
    return {
        "days": days,
        "now_temp": cur.get("temperature_2m"),
        "now_desc": WMO.get(cur.get("weather_code"), ("정보 없음", "🌡️"))[0],
    }


def get_news():
    """구글 뉴스 RSS에서 카테고리별 헤드라인을 모읍니다."""
    items, seen = [], set()
    for label, url, limit in NEWS_FEEDS:
        try:
            root = ET.fromstring(fetch(url))
        except Exception as e:
            print(f"[news:{label}] 실패: {e}")
            continue
        count = 0
        for item in root.iter("item"):
            if count >= limit:
                break
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            source = item.findtext("{*}source") or item.findtext("source") or ""
            if not title or title in seen:
                continue
            seen.add(title)
            # 구글 뉴스 제목은 "기사제목 - 언론사" 형태
            if " - " in title and not source:
                title, source = title.rsplit(" - ", 1)
            items.append({
                "cat": label,
                "title": title.strip(),
                "link": link,
                "source": (source or "").strip(),
            })
            count += 1
    return items


def build_html(weather, news, now):
    e = html.escape
    date_ko = f"{now.year}년 {now.month}월 {now.day}일"
    weekday = "월화수목금토일"[now.weekday()] + "요일"

    # 날씨 블록
    if weather and weather["days"]:
        today = weather["days"][0]
        now_temp = weather["now_temp"]
        temp_line = f"{now_temp:.0f}°" if now_temp is not None else f"{today['tmin']:.0f}~{today['tmax']:.0f}°"
        cond = f"{today['icon']} {e(weather['now_desc'] if now_temp is not None else today['desc'])}"
        cells = [
            f"<div><span>오늘 최저/최고</span>{today['tmin']:.0f}° / {today['tmax']:.0f}°</div>",
            f"<div><span>강수 확률</span>{today['pop'] if today['pop'] is not None else '-'}%</div>",
            f"<div><span>예상 강수량</span>{today['rain']:.1f}mm</div>",
        ]
        for nxt, lbl in zip(weather["days"][1:], ("내일", "모레")):
            cells.append(
                f"<div><span>{lbl} ({nxt['date'][5:].replace('-', '/')})</span>"
                f"{nxt['icon']} {e(nxt['desc'])} · {nxt['tmin']:.0f}~{nxt['tmax']:.0f}°</div>"
            )
        alert = ""
        if today["pop"] and today["pop"] >= 60:
            alert = '<div class="w-alert">☔ 비 올 확률이 높습니다. 우산을 챙기세요.</div>'
        elif today["tmax"] >= 33:
            alert = '<div class="w-alert">🔥 매우 덥습니다. 수분 섭취와 야외활동에 유의하세요.</div>'
        elif today["tmin"] <= -5:
            alert = '<div class="w-alert">🧊 강추위입니다. 따뜻하게 입고 나가세요.</div>'
        weather_block = f"""
      <div class="w-now">
        <div class="w-temp">{temp_line}</div>
        <div class="w-cond">{cond}</div>
      </div>
      <div class="w-grid">{''.join(cells)}</div>
      {alert}"""
    else:
        weather_block = '<div class="w-now"><div class="w-cond">날씨 정보를 가져오지 못했습니다.</div></div>'

    # 뉴스 블록
    if news:
        cards = []
        for n in news:
            src = f'<div class="src">{e(n["source"])}</div>' if n["source"] else ""
            link = (f'<a href="{e(n["link"])}" target="_blank" rel="noopener">기사 보기 →</a>'
                    if n["link"] else "")
            cls = {"경제": " econ", "세계": " world"}.get(n["cat"], "")
            cards.append(f"""
    <div class="news-item">
      <span class="tag{cls}">{e(n['cat'])}</span>
      <h3>{e(n['title'])}</h3>
      {src}
      {link}
    </div>""")
        news_block = "".join(cards)
    else:
        news_block = '<div class="news-item"><h3>뉴스를 가져오지 못했습니다.</h3></div>'

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>데일리 브리핑 · {date_ko} ({weekday[0]})</title>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=IBM+Plex+Sans+KR:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root{{
    --ink:#1c2733; --slate:#46586b; --mist:#eef2f5; --paper:#fbfcfd;
    --rain:#3d7ea6; --rain-deep:#2b5d7d; --line:#d7dfe6;
  }}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:'IBM Plex Sans KR',-apple-system,sans-serif;
    background:var(--mist);color:var(--ink);line-height:1.7;}}
  .wrap{{max-width:760px;margin:0 auto;padding:0 20px 80px;}}
  header{{padding:56px 0 32px;border-bottom:2px solid var(--ink);}}
  .kicker{{font-size:13px;letter-spacing:.22em;color:var(--rain-deep);
    font-weight:600;text-transform:uppercase;margin-bottom:14px;}}
  h1{{font-family:'Gowun Batang',serif;font-size:clamp(30px,6vw,44px);
    font-weight:700;line-height:1.25;}}
  .meta{{margin-top:16px;font-size:15px;color:var(--slate);}}
  .meta strong{{color:var(--ink);font-weight:600;}}
  section{{margin-top:48px;}}
  .sec-label{{display:flex;align-items:baseline;gap:12px;margin-bottom:20px;}}
  .sec-label h2{{font-family:'Gowun Batang',serif;font-size:22px;font-weight:700;}}
  .sec-label .en{{font-size:12px;letter-spacing:.18em;color:var(--slate);}}
  .weather{{background:linear-gradient(160deg,#31536b,#22394c);color:#f2f6f9;
    border-radius:14px;padding:28px;position:relative;overflow:hidden;}}
  .weather::after{{content:"";position:absolute;inset:0;pointer-events:none;
    background-image:repeating-linear-gradient(105deg,transparent 0 26px,rgba(255,255,255,.06) 26px 27px);}}
  .w-now{{display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap;}}
  .w-temp{{font-size:56px;font-weight:300;line-height:1;}}
  .w-cond{{font-size:17px;font-weight:500;padding-bottom:8px;}}
  .w-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:10px 20px;margin-top:22px;font-size:14px;}}
  .w-grid div{{border-top:1px solid rgba(255,255,255,.25);padding-top:8px;}}
  .w-grid span{{display:block;font-size:12px;opacity:.75;margin-bottom:2px;}}
  .w-alert{{margin-top:20px;background:rgba(255,255,255,.12);
    border-left:3px solid #ffce7a;border-radius:0 8px 8px 0;padding:12px 16px;font-size:14px;}}
  .news-item{{background:var(--paper);border:1px solid var(--line);
    border-radius:12px;padding:20px 24px;margin-bottom:14px;}}
  .tag{{display:inline-block;font-size:11.5px;font-weight:600;letter-spacing:.08em;
    color:var(--rain-deep);background:#e3edf4;border-radius:4px;padding:3px 9px;margin-bottom:10px;}}
  .tag.world{{color:#7a4a2b;background:#f3e9df;}}
  .tag.econ{{color:#3d6b46;background:#e5f0e7;}}
  .news-item h3{{font-family:'Gowun Batang',serif;font-size:17.5px;
    font-weight:700;line-height:1.45;}}
  .news-item .src{{font-size:13px;color:var(--slate);margin-top:6px;}}
  .news-item a{{display:inline-block;margin-top:10px;font-size:13px;color:var(--rain);
    text-decoration:none;font-weight:500;border-bottom:1px solid currentColor;}}
  footer{{margin-top:60px;padding-top:20px;border-top:1px solid var(--line);
    font-size:12.5px;color:var(--slate);}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="kicker">Daily Briefing · 데일리 브리핑</div>
    <h1>{date_ko}<br>{weekday}의 브리핑</h1>
    <div class="meta">기준 지역 · <strong>{e(PLACE)}</strong> 일대</div>
  </header>

  <section>
    <div class="sec-label"><h2>오늘의 날씨</h2><span class="en">WEATHER</span></div>
    <div class="weather">{weather_block}
    </div>
  </section>

  <section>
    <div class="sec-label"><h2>주요 뉴스</h2><span class="en">TOP NEWS</span></div>
    {news_block}
  </section>

  <footer>
    이 페이지는 매일 자동으로 갱신됩니다 · 최종 갱신 {now.strftime('%Y-%m-%d %H:%M')} KST<br>
    출처: Open-Meteo (날씨) · Google News (뉴스)
  </footer>
</div>
</body>
</html>
"""


def main():
    now = datetime.now(TZ)
    weather = get_weather()
    news = get_news()
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(build_html(weather, news, now))
    print(f"생성 완료: index.html ({now:%Y-%m-%d %H:%M} KST, 뉴스 {len(news)}건)")


if __name__ == "__main__":
    main()
