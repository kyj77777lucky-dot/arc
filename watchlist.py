"""관심종목 시세판

watchlist.txt 에 적힌 미국주식 종목들의 현재가, 전일 대비 등락률,
52주 최고가/최저가를 한 화면에 표로 보여줍니다.

실행 방법:
    python watchlist.py            # watchlist.txt 의 종목 조회
    python watchlist.py AAPL MSFT  # 원하는 종목만 바로 조회
    python watchlist.py --demo     # 인터넷 없이 예시 데이터로 연습
"""

import argparse
import os
import sys
import unicodedata
from pathlib import Path

WATCHLIST_FILE = Path(__file__).parent / "watchlist.txt"

# 한국식 색상: 오르면 빨강, 내리면 파랑
RED = "\033[91m"
BLUE = "\033[94m"
GRAY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_tickers(path=WATCHLIST_FILE):
    """watchlist.txt 에서 종목 코드(티커)를 읽어옵니다. '#' 뒤는 메모로 무시합니다."""
    tickers = []
    for line in path.read_text(encoding="utf-8").splitlines():
        ticker = line.split("#")[0].strip().upper()
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    return tickers


def summarize(ticker, closes):
    """1년치 종가 목록으로 시세판 한 줄에 필요한 숫자를 계산합니다."""
    closes = [c for c in closes if c == c]  # 비어 있는 값(NaN) 제거
    if len(closes) < 2:
        return None
    price = closes[-1]
    prev = closes[-2]
    high = max(closes)
    low = min(closes)
    return {
        "ticker": ticker,
        "price": price,
        "change": price - prev,
        "change_pct": (price - prev) / prev * 100,
        "high_52w": high,
        "low_52w": low,
        # 52주 범위에서 지금 가격이 어디쯤인지 (0% = 최저가, 100% = 최고가)
        "position": (price - low) / (high - low) * 100 if high > low else 100.0,
        "from_high_pct": (price - high) / high * 100,
    }


def fetch_rows(tickers):
    """야후 파이낸스에서 최근 1년 주가를 받아 종목별로 요약합니다."""
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("yfinance 가 설치되어 있지 않습니다. 먼저 'pip install -r requirements.txt' 를 실행하세요.")

    data = yf.download(tickers, period="1y", auto_adjust=False,
                       progress=False, group_by="ticker", threads=True)
    rows, failed = [], []
    for ticker in tickers:
        try:
            if ticker in data.columns.get_level_values(0):
                closes = data[ticker]["Close"].tolist()
            else:  # 종목이 하나뿐일 때 표 모양이 다른 버전 대비
                closes = data["Close"].squeeze().tolist()
        except (KeyError, AttributeError):
            closes = []
        row = summarize(ticker, closes)
        if row:
            rows.append(row)
        else:
            failed.append(ticker)
    return rows, failed


def demo_rows(tickers):
    """인터넷 없이 연습할 수 있도록 그럴듯한 가짜 주가를 만듭니다. (실제 시세 아님)"""
    import random
    rows = []
    for ticker in tickers:
        rng = random.Random(ticker)  # 같은 종목은 항상 같은 결과
        price = rng.uniform(30, 600)
        closes = []
        for _ in range(252):  # 1년 = 약 252 거래일
            price *= 1 + rng.gauss(0.0005, 0.02)
            closes.append(price)
        rows.append(summarize(ticker, closes))
    return rows, []


def pad(text, width, align="right"):
    """한글은 화면에서 두 칸을 차지하므로, 실제 보이는 폭에 맞춰 공백을 채웁니다."""
    shown = sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)
    space = " " * max(width - shown, 0)
    return text + space if align == "left" else space + text


def colorize(text, value):
    if value > 0:
        return f"{RED}{text}{RESET}"
    if value < 0:
        return f"{BLUE}{text}{RESET}"
    return text


def range_bar(position, width=10):
    """52주 최저~최고 사이에서 현재 위치를 ●로 표시합니다."""
    filled = round(position / 100 * (width - 1))
    return "".join("●" if i == filled else "─" for i in range(width))


def print_board(rows, failed, demo=False):
    title = "📈 관심종목 시세판"
    if demo:
        title += f" {GRAY}(예시 데이터 - 실제 시세 아님){RESET}"
    print(f"\n{BOLD}{title}{RESET}\n")

    header = " ".join([pad("종목", 6, "left"), pad("현재가($)", 10), pad("전일대비", 9),
                       pad("등락률", 8), pad("52주 최저", 11), " " + pad("52주 위치", 10, "left") + " ",
                       pad("52주 최고", 9), pad("고점대비", 8)])
    print(BOLD + header + RESET)
    print("-" * 88)

    for r in sorted(rows, key=lambda r: r["change_pct"], reverse=True):
        arrow = "▲" if r["change"] > 0 else "▼" if r["change"] < 0 else "-"
        change = colorize(f"{arrow}{abs(r['change']):>8.2f}", r["change"])
        pct = colorize(f"{r['change_pct']:>+7.2f}%", r["change_pct"])
        print(f"{r['ticker']:<6} {r['price']:>10.2f} {change} {pct}   "
              f"{r['low_52w']:>9.2f}  {range_bar(r['position'])}  {r['high_52w']:>9.2f} "
              f"{r['from_high_pct']:>+7.1f}%")

    if failed:
        print(f"\n⚠️  데이터를 가져오지 못한 종목: {', '.join(failed)} (티커 철자를 확인해 보세요)")

    print(f"\n{GRAY}· 등락률: 직전 거래일 종가 대비 / 빨강=상승, 파랑=하락")
    print("· 52주 위치: 왼쪽 끝이 1년 중 최저가, 오른쪽 끝이 최고가")
    print(f"· 고점대비: 1년 중 최고가에서 몇 % 떨어져 있는지 (종가 기준){RESET}\n")


def main():
    if os.name == "nt":
        os.system("")  # 윈도우 터미널에서 색깔 표시 켜기
    parser = argparse.ArgumentParser(description="관심종목 시세판")
    parser.add_argument("tickers", nargs="*", help="조회할 티커 (생략하면 watchlist.txt 사용)")
    parser.add_argument("--demo", action="store_true", help="인터넷 없이 예시 데이터로 실행")
    args = parser.parse_args()

    tickers = [t.upper() for t in args.tickers] or load_tickers()
    if not tickers:
        sys.exit("조회할 종목이 없습니다. watchlist.txt 에 티커를 한 줄에 하나씩 적어주세요.")

    if args.demo:
        rows, failed = demo_rows(tickers)
    else:
        print(f"{len(tickers)}개 종목 시세를 불러오는 중...")
        rows, failed = fetch_rows(tickers)
        if not rows:
            sys.exit("시세를 하나도 가져오지 못했습니다. 인터넷 연결을 확인하거나 --demo 로 실행해 보세요.")

    print_board(rows, failed, demo=args.demo)


if __name__ == "__main__":
    main()
