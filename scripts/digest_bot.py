import os
import requests
from datetime import datetime

CMC_API_KEY = os.environ["CMC_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

REQUEST_TIMEOUT = 20
LIMIT = 200
TOP_N = 20

MIN_VOLUME_24H = 10_000_000
MIN_PRICE_CHANGE_FOR_HOT = 2.0
MIN_FLOW_RATIO = 0.05

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
        n = float(value)
        return f"{n:+.1f}%"
    except:
        return "N/A"


def fmt_money(value):
    try:
        n = float(value)
    except:
        return "N/A"

    if n >= 1_000_000_000:
        return f"${n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"${n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"${n / 1_000:.2f}K"
    return f"${n:.2f}"


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

    data = r.json()
    if "data" not in data:
        raise Exception(f"CMC response không hợp lệ: {data}")

    return data["data"]


def score_coin(coin):
    q = coin.get("quote", {}).get("USD", {})

    volume_change = float(q.get("volume_change_24h") or 0)
    price_change = float(q.get("percent_change_24h") or 0)
    volume_24h = float(q.get("volume_24h") or 0)
    market_cap = float(q.get("market_cap") or 0)
    price = float(q.get("price") or 0)

    if volume_24h < MIN_VOLUME_24H:
        return None

    flow_ratio = (volume_24h / market_cap) if market_cap > 0 else 0

    # Sniper score: ưu tiên volume, xác nhận bằng giá, thêm flow ratio
    trend_score = (
        volume_change * 0.50
        + max(price_change, 0) * 0.25
        + (flow_ratio * 100) * 0.25
    )

    return {
        "name": coin.get("name", "Unknown"),
        "symbol": coin.get("symbol", "???"),
        "slug": coin.get("slug", ""),
        "price": price,
        "price_change_24h": price_change,
        "volume_change_24h": volume_change,
        "volume_24h": volume_24h,
        "market_cap": market_cap,
        "flow_ratio": flow_ratio,
        "trend_score": trend_score,
    }


def quality_badge(c):
    if c["price_change_24h"] >= 5 and c["volume_change_24h"] >= 75:
        return "🔥"
    if c["price_change_24h"] >= 2 and c["volume_change_24h"] >= 50:
        return "⚡"
    return "👀"


def build_pretty_line(rank, c):
    badge = quality_badge(c)
    return (
        f"`#{rank}` {badge} **{c['symbol']}**  "
        f"• {fmt_price(c['price'])}  "
        f"• 24h {fmt_pct(c['price_change_24h'])}  "
        f"• Vol {fmt_pct(c['volume_change_24h'])}"
    )


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
        if scored:
            ranked.append(scored)

    ranked.sort(key=lambda x: x["trend_score"], reverse=True)
    top = ranked[:TOP_N]

    if not top:
        send_embeds([
            {
                "title": "📊 CoinTrend V3 Sniper Digest",
                "description": "Không có dữ liệu phù hợp để hiển thị.",
                "color": 8421504,
                "footer": {"text": "CoinTrend V3 • 08:00 / 20:00 VN"},
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        ])
        return

    hot_picks = top[:4]
    momentum = top[4:8]
    watchlist = top[8:20]

    hot_text = "\n".join(
        build_pretty_line(i, c) for i, c in enumerate(hot_picks, start=1)
    ) or "Không có dữ liệu"

    momentum_text = "\n".join(
        build_pretty_line(i, c) for i, c in enumerate(momentum, start=5)
    ) or "Không có dữ liệu"

    watchlist_text = " • ".join(c["symbol"] for c in watchlist) or "Không có dữ liệu"

    avg_vol_change = sum(c["volume_change_24h"] for c in top[:10]) / min(len(top[:10]), 10)
    avg_price_change = sum(c["price_change_24h"] for c in top[:10]) / min(len(top[:10]), 10)
    strongest = top[0]["symbol"]
    total_candidates = len(ranked)

    timestamp = datetime.utcnow().isoformat() + "Z"

    embed_main = {
        "title": "📊 CoinTrend V3 Sniper Digest",
        "description": "Sàng lọc theo **volume momentum + price confirmation + flow ratio**",
        "color": 3447003,
        "fields": [
            {
                "name": "📎 Market Snapshot",
                "value": (
                    f"**Strongest:** {strongest}\n"
                    f"**Avg Vol 24h:** {fmt_pct(avg_vol_change)}\n"
                    f"**Avg Price 24h:** {fmt_pct(avg_price_change)}\n"
                    f"**Candidates:** {total_candidates}"
                ),
                "inline": False
            },
            {
                "name": "🔥 Hot Picks",
                "value": hot_text,
                "inline": False
            },
            {
                "name": "⚡ Momentum",
                "value": momentum_text,
                "inline": False
            },
            {
                "name": "👀 Watchlist",
                "value": watchlist_text,
                "inline": False
            }
        ],
        "footer": {
            "text": "CoinTrend V3 • 08:00 / 20:00 VN"
        },
        "timestamp": timestamp
    }

    embed_note = {
        "title": "🧭 Cách đọc nhanh",
        "description": (
            "🔥 **Hot Picks** = tín hiệu đẹp nhất\n"
            "⚡ **Momentum** = đang có lực, cần theo dõi thêm\n"
            "👀 **Watchlist** = nằm trong radar nhưng chưa phải ưu tiên số 1"
        ),
        "color": 10181046,
        "footer": {
            "text": "Sniper mode prefers quality over noise"
        },
        "timestamp": timestamp
    }

    send_embeds([embed_main, embed_note])


if __name__ == "__main__":
    main()
