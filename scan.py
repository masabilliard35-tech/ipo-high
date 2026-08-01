"""上場来高値スクリーナーの実行本体（全市場・毎日方式）。
必須条件:
  1. 上場から5か月〜3年
  2. 上場後の最初の2か月を除外した「上場来高値」を更新中（当日が高値圏）
  3. 毎日、当日に上場来高値を更新した銘柄を検知して通知

業績(ROE等)は使わない。株価の一括取得だけで完結するためレート制限に強い。

使い方:
  python scan.py            … 毎日処理（GitHub Actions想定）
出力: data/rows.json（画面用）, data/universe.json
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from universe import fetch_universe
from notify import send

HERE = Path(__file__).parent
DATA = HERE / "data"
DATA.mkdir(exist_ok=True)

MIN_AGE_D = 150      # 上場から5か月（約150日）
MAX_AGE_D = 1095     # 上場から3年（約1095日）
SKIP_D = 61          # 最初の約2か月を除外
NEAR = 60            # 表に載せる「高値からの経過日」の上限


def load_json(name, default):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def download_all(syms, period="4y", chunk=150):
    """全銘柄の株価をまとめて取得（レート制限に備え小分け＋リトライ）。
    新規上場銘柄は履歴が短いので、40本以上あれば残す。"""
    frames = {}
    for i in range(0, len(syms), chunk):
        part = syms[i:i + chunk]
        for attempt in range(3):
            try:
                h = yf.download(part, period=period, progress=False,
                                group_by="ticker", threads=True, auto_adjust=True)
            except Exception:
                h = None
            got = 0
            if h is not None:
                for s in part:
                    try:
                        d = h[s].dropna(subset=["Close", "Volume"])
                        if len(d) >= 40:
                            frames[s] = d
                            got += 1
                    except Exception:
                        pass
            if got >= max(1, len(part) // 3):
                break
            time.sleep(5 * (attempt + 1))
        print(f"\r株価 {min(i + chunk, len(syms))}/{len(syms)}  取得 {len(frames)}", end="")
    print()
    return frames


def analyze(d):
    """1銘柄の指標を返す。条件外なら None。"""
    first = d.index[0]
    last_dt = d.index[-1]
    age = (last_dt - first).days
    if age < MIN_AGE_D or age > MAX_AGE_D:      # 上場5か月〜3年
        return None

    w = d[d.index > first + pd.Timedelta(days=SKIP_D)]   # 最初の2か月を除外
    if len(w) < 20:
        return None
    close = w["Close"].to_numpy(dtype=float)
    vol = w["Volume"].to_numpy(dtype=float)
    if float(np.max(close[1:] / close[:-1])) > 1.6:       # 分割未調整等の異常
        return None

    hi = float(close.max())
    since = (len(close) - 1) - int(np.argmax(close))       # 上場来高値からの経過日
    last = float(close[-1])
    v50 = float(np.mean(vol[-50:])) if len(vol) >= 50 else float(np.mean(vol))
    v5 = float(np.max(vol[-5:]))
    ma25 = float(np.mean(close[-25:])) if len(close) >= 25 else None
    return {
        "since": since,
        "price": round(last),
        "unit": round(last * 100),
        "high": round(hi),
        "fromHigh": round((last / hi - 1) * 100, 1),
        "vol": round(v5 / v50, 1) if v50 else None,
        "ma25": round((last / ma25 - 1) * 100, 1) if ma25 else None,
        "listed": str(first.date()),
        "ageM": round(age / 30.4, 1),
    }


def run_daily():
    print("universe取得...")
    uni = fetch_universe()
    if uni:
        (DATA / "universe.json").write_text(json.dumps(uni, ensure_ascii=False), encoding="utf-8")
    else:
        uni = load_json("universe.json", {})
    syms = sorted(uni)
    print(f"全 {len(syms)} 銘柄の株価取得...")
    frames = download_all(syms)

    rows, alerts, latest = [], [], ""
    for s, d in frames.items():
        m = analyze(d)
        if m is None or m["since"] > NEAR:
            continue
        row = {"sym": s, "name": uni.get(s, {}).get("name", s),
               "sec": uni.get(s, {}).get("sector", ""),
               "cap": round((uni.get(s, {}).get("cap") or 0) / 1e8), **m}
        rows.append(row)
        latest = max(latest, str(d.index[-1].date()))
        if m["since"] == 0:
            alerts.append(row)

    out = {"date": latest, "universe": len(syms), "qualified": len(rows), "rows": rows}
    (DATA / "rows.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"rows.json 保存: {len(rows)} 銘柄 / 最新 {latest} / 当日上場来高値更新 {len(alerts)}")

    notify_alerts(alerts, latest)


def notify_alerts(rows, date):
    if not rows:
        send(f"【上場来高値】{date}\n"
             f"本日、上場5か月〜3年で上場来高値を更新した銘柄はありませんでした。")
        return
    rows = sorted(rows, key=lambda r: -(r["cap"] or 0))
    lines = [f"【上場来高値】{date}",
             f"本日、上場来高値を更新（上場5か月〜3年）: {len(rows)}銘柄", ""]
    for r in rows[:25]:
        vol = f"{r['vol']}x" if r["vol"] is not None else "—"
        lines.append(f"{r['sym']} {r['name'][:14]}  {r['price']:,}円  "
                     f"出来高{vol}  上場{r['ageM']}ヶ月  時価総額{r['cap']}億")
    if len(rows) > 25:
        lines.append(f"…ほか {len(rows) - 25} 銘柄")
    send("\n".join(lines))


if __name__ == "__main__":
    run_daily()
