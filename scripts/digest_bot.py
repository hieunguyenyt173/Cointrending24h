import os
import requests
from datetime import datetime

CMC_API_KEY = os.environ["CMC_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

REQUEST_TIMEOUT = 20
LIMIT = 200
TOP_N = 30
MIN_VOLUME_24H = 10_000_000

CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"


def fmt_price(price):
    try:
        price = float(price)
    except:
        return "N/A"

    if price >= 1000:
        return f"${price:,.2f}"
    if price >= 1:
        return f"${price:,.3f}"
    if price >= 0.01:
        return f"${price:,.4f}"
    return f"${price:,.6f}"


def fmt_pct(value):
    try:
        return f"{float(value):+.1f}%"
    except:
        return "N/A"


def fetch_coins():
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": CMC_API_KEY,
    }
    params = {
        "start": "1",
        "limit": str(LIMIT),
        "convert": "USD",
        "sort": "market_cap",
        "sort_dir": "desc",
    }
    r = requests.get(CMC_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()["data"]


def score_coin(coin):
    q = coin.get("quote", {}).get("USD", {})
    volume_change = float(q.get("volume_change_24h") or 0)
    price_change = float(q.get("percent_change_24h") or 0)
    volume_24h = float(q.get("volume_24h") or 0)
    market_cap = float(q.get("market_cap") or 0)

    if volume_24h < MIN_VOLUME_24H:
        return None

    # Sniper score
    flow_ratio = (volume_24h / market_cap) if market_cap > 0 else 0
    trend_score = (
        volume_change * 0.50
        + max(price_change, 0) * 0.25
        + flow_ratio * 100 * 0.25
    )

    return {
        "name": coin.get("name", "Unknown"),
        "symbol": coin.get("symbol", "???"),
        "slug": coin.get("slug", ""),
        "price": q.get("price") or 0,
        "price_change_24h": price_change,
        "volume_change_24h": volume_change,
        "volume_24h": volume_24h,
        "market_cap": market_cap,
        "flow_ratio": flow_ratio,
        "trend_score": trend_score,
    }


def send_embeds(embeds):
    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"embeds": embeds},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()


def main():
    coins = fetch_coins()
    ranked = []

    for coin in coins:
        scored = score_coin(coin)
        if not scored:
            continue
        ranked.append(scored)

    ranked.sort(key=lambda x: x["trend_score"], reverse=True)
    top = ranked[:TOP_N]

    top_1_10 = top[:10]
    top_11_20 = top[10:20]
    top_21_30 = top[20:30]

    def block(items, start_rank):
        lines = []
        for i, c in enumerate(items, start=start_rank):
            lines.append(
                f"**{i}. {c['symbol']}** | {fmt_price(c['price'])} | "
                f"24h {fmt_pct(c['price_change_24h'])} | "
                f"Vol {fmt_pct(c['volume_change_24h'])}"
            )
        return "\n".join(lines) or "Không có dữ liệu"

    embeds = [
        {
            "title": "📊 CoinTrend V3 Sniper Digest",
            "description": "Top coin theo volume momentum + price confirmation + flow ratio",
            "color": 3447003,
            "fields": [
                {"name": "🔥 Top 1-10", "value": block(top_1_10, 1), "inline": False},
                {"name": "📈 Top 11-20", "value": block(top_11_20, 11), "inline": False},
                {"name": "📌 Top 21-30", "value": block(top_21_30, 21), "inline": False},
            ],
            "footer": {"text": "CoinTrend V3 • 08:00 / 20:00 VN"},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    ]

    send_embeds(embeds)


if __name__ == "__main__":
    main()
