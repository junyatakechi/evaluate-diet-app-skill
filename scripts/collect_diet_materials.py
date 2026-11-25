#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""evaluate-diet-app-skill: ダイエットの判断に要る材料を集め、1つのJSONにまとめて出力する。

Usage:
  uv run collect_diet_materials.py --days 30 --weight-days 120
      --sleep-sources スマートリング,メモアプリ
      [--end YYYY-MM-DD] [--calendar-json events1.json ...]

**計算も判断もしない。** 取得と、ロジックスキルが受け取れる形への変換だけを行う。
出力のキーと形は diet-process-jayt-core-logic-skill の各判断の「求める材料」に合わせてある。
記録ごとに間食か・外食かを決めず、記録と記録の語彙をそのまま渡す。

  - 体重と睡眠は --weight-days 日ぶん(体重の増減の「使用するデータ期間」)、食事と歩数は --days 日ぶんを読む。
  - 歩数は、値が確定していない今日の分を渡さない(oura-api-generic-logic-skill のデータが確定する時期の判断)。
  - 睡眠は --sleep-sources の順(起床・就寝時刻の選び方の答え)に、目覚めた日ごとに先の出所に記録があれば
    それだけを使う。順そのものはここで決めない。
  - 記録の語彙は、このスキルの conventions/meal-words.json から読む(導入先の取り決め)。
  - 目標体重は、起動フォルダの diet-goal-weights.json から読む(導入先のデータ)。
  - 読むDBのURLは、起動フォルダの .env から読む(同じキーの環境変数があればそちら)。
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_notion import (  # noqa: E402
    JST,
    NotionError,
    get_measurements,
    get_nights,
    get_daily_steps,
    get_routine_sleeps,
)

# 記録の語彙(導入先の取り決め。conventions/data-sources.md)。キーは材料のキーと同じ。
WORDS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "conventions", "meal-words.json")
WORD_KEYS = ("間食の表現", "過食の表現", "外食の表現", "外食を否定する表現", "中食の表現", "内食の表現")

# 目標体重(導入先のデータ。conventions/data-sources.md)。起動フォルダに置く
GOALS_FILE = "diet-goal-weights.json"

# 睡眠の記録の出所(この導入先。conventions/data-sources.md)。出所の名前は起床・就寝時刻の選び方の値。
SLEEP_SOURCES = {
    "スマートリング": {"出所": "スマートリング"},
    "メモアプリ": {"出所": "メモアプリ", "記録": "Routine DB の睡眠時間", "性質": "主観"},
}

# カレンダーの食事の記録の書き方(対象者のカレンダーの規約。conventions/data-sources.md)。
# `食事(内食, カレー, 目玉焼き*2)! at 店名` のように、接頭辞と括弧で始まる予定だけを食事の記録にする。
# 「食事会: …」のような食べた記録でない予定は、括弧が続かないので入らない。
MEAL_RECORD = re.compile(r"^(食事|おやつ|デザート)\s*[(（]")

BODY_KEYS = ("体脂肪率", "除脂肪体重", "骨格筋量")


def read_json(path, what):
    """JSONファイルを読む。無ければ None。壊れていたら止まる(黙って空で渡さない)。"""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"Error: {what}の {path} がJSONとして読めない: {e}")


def word_lists():
    """記録の語彙。無いキーは材料から外し、警告を出す(ロジックスキルが見ない項目を返す)。"""
    data = read_json(WORDS_FILE, "記録の語彙") or {}
    out = {}
    for material in WORD_KEYS:
        words = data.get(material)
        if isinstance(words, list) and all(isinstance(w, str) for w in words) and any(w.strip() for w in words):
            out[material] = [w for w in words if w.strip()]
        else:
            print(f"Warning: {WORDS_FILE} に「{material}」の語の並びが無いので、材料から外す", file=sys.stderr)
    return out


def iso(s):
    """ISO日時の書き方をそろえる(ミリ秒を落とし、JSTの +09:00 にする)。"""
    if not s or "T" not in s:
        return s  # 日付だけの記録(手入力の体重など)は、そのまま渡す
    return datetime.fromisoformat(s).astimezone(JST).isoformat()


# --- 睡眠 -------------------------------------------------------------------

def nights_by_order(order, since, until):
    """目覚めた日ごとに、order の先の出所に記録があればその出所の夜をすべて使う。"""
    readers = {"スマートリング": get_nights, "メモアプリ": get_routine_sleeps}
    # `since` の当日に目覚める睡眠は前日に始まっていることがあるので、1日手前から読み、目覚めた日で絞る。
    read_from = (date.fromisoformat(since) - timedelta(days=1)).isoformat()
    by_source = {s: [n for n in readers[s](read_from, until) if n["起床日"] and since <= n["起床日"] <= until]
                 for s in order}
    taken, out = set(), []
    for source in order:
        days = {n["起床日"] for n in by_source[source]} - taken
        out += [{"日付": n["対象日時"], "開始": iso(n["開始時刻"]), "終了": iso(n["終了時刻"]), "出所": source}
                for n in by_source[source] if n["起床日"] in days]
        taken |= days
    return sorted(out, key=lambda n: n["開始"])


# --- カレンダー -------------------------------------------------------------

def load_meal_events(paths, since, until):
    """カレンダーMCPの list_events 結果から、食事の記録の予定だけを取り出す。"""
    out = []
    for path in paths or []:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for ev in (data.get("events") if isinstance(data, dict) else data) or []:
            title = (ev.get("summary") or "").strip()
            if not MEAL_RECORD.match(title):
                continue
            start, end = ev.get("start", {}), ev.get("end", {})
            s = start.get("dateTime") or start.get("date") or ""
            day = s[:10]
            if since <= day <= until:
                out.append({
                    "日付": day,
                    "時刻": s[11:16] if start.get("dateTime") else "終日",
                    "終了": (end.get("dateTime") or "")[11:16] or None,
                    "記録": title,
                })
    return sorted(out, key=lambda m: (m["日付"], m["時刻"]))


# --- 目標 -------------------------------------------------------------------

def goal_weights():
    """目標体重 `{名前: kg}`。起動フォルダの diet-goal-weights.json(`{"マイルストーン1": 70, "マイルストーン2": 65}`)から読む。"""
    path = os.path.join(os.getcwd(), GOALS_FILE)
    data = read_json(path, "目標体重")
    if data is None:
        print(f"Warning: {path} が無いので、材料の「目標体重」を外す", file=sys.stderr)
        return {}
    if not isinstance(data, dict) or not data or not all(
            isinstance(k, str) and k.strip() and isinstance(v, (int, float)) and not isinstance(v, bool)
            for k, v in data.items()):
        sys.exit(f'Error: {path} は {{"名前": kg, ...}} の形で書く(kgは数): {data}')
    return {k.strip(): float(v) for k, v in data.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, required=True, help="評価の期間(食事を読む日数)")
    ap.add_argument("--weight-days", type=int, required=True,
                    help="体重と睡眠を読む日数(体重の増減の「使用するデータ期間」)")
    ap.add_argument("--sleep-sources", required=True,
                    help="睡眠の記録の出所の順(起床・就寝時刻の選び方の答え)。カンマ区切り")
    ap.add_argument("--end", help="期間の終わり YYYY-MM-DD(既定は今日/JST)")
    ap.add_argument("--calendar-json", nargs="*", default=[],
                    help="カレンダーMCPのlist_events結果JSONファイル(ページ送り分すべて)")
    args = ap.parse_args()

    end = date.fromisoformat(args.end) if args.end else datetime.now(JST).date()
    until = end.isoformat()
    since = (end - timedelta(days=args.days - 1)).isoformat()
    weight_since = (end - timedelta(days=args.weight_days - 1)).isoformat()
    order = [s.strip() for s in args.sleep_sources.split(",") if s.strip()]
    unknown = [s for s in order if s not in SLEEP_SOURCES]
    if not order or unknown:
        sys.exit(f"Error: --sleep-sources に、この導入先に無い出所がある: {unknown}"
                 f"(使えるのは {', '.join(SLEEP_SOURCES)})")
    words = word_lists()

    materials = {
        "期間": {"評価": {"開始": since, "終了": until}, "体重と睡眠": {"開始": weight_since, "終了": until}},
        "体重の記録": [
            {"日時": iso(r["対象日時"]), "体重": r["体重"]} | {k: r.get(k) for k in BODY_KEYS}
            for r in get_measurements(weight_since, until)
            if r.get("対象日時") and r.get("体重") is not None
        ],
        "睡眠の記録の出所": [SLEEP_SOURCES[s] for s in order],
        "夜間睡眠": nights_by_order(order, weight_since, until),
        "食事": load_meal_events(args.calendar_json, since, until),
        "歩数": get_daily_steps(since, min(until, (datetime.now(JST).date() - timedelta(days=1)).isoformat())),
        **words,
    }
    goals = goal_weights()
    if goals:
        materials["目標体重"] = goals

    json.dump(materials, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    try:
        main()
    except NotionError as e:
        sys.exit(f"Error: {e}")
