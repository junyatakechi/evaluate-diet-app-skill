"""evaluate-diet-app-skill: 材料に要る記録を、Notionから読む(取得と変換だけ)。

**計算も判断もしない。** Notionへの通信は notion-cli-generic-logic-skill の道具を、
Ouraの記録の読み方(夜の主睡眠だけを採る・寝始めた日と目覚めた日)は
oura-api-generic-logic-skill の道具を使う。どちらも写さずimportする。

このモジュールが持つのは、導入先の取り決め(読むDBと列名)だけ。DBのURLは
起動フォルダの .env(環境変数が優先)の DIET_DB_<KEY>_URL にある。
列名の説明は conventions/notion-db.md。列名を変えたら、Notion側と同時にここを直す
(notion-cli-generic-logic-skill のスキーマの変更の判断)。
"""
import os
import sys

_SKILLS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(_SKILLS, "notion-cli-generic-logic-skill", "scripts"))
sys.path.insert(0, os.path.join(_SKILLS, "oura-api-generic-logic-skill", "scripts"))
from notion_client import EnvDataSources, NotionError, query_data_source  # noqa: E402,F401
import oura_records  # noqa: E402

JST = oura_records.JST
DS = EnvDataSources("DIET", (
    "measurement",  # 体重記録
    "oura_sleep",   # Oura 睡眠区間
    "routine",      # Routine(睡眠時間の自己申告)
    "oura_daily",   # Oura 日次サマリー
))

# 期間で絞る列
DATE_COLUMN = {"measurement": "対象日時", "oura_sleep": "対象日時", "routine": "Executed time",
               "oura_daily": "対象日時"}

# Routine DB で、睡眠の区間を自己申告している行の名前と、実行した記録の Status(対象者の Routine DB の運用)。
ROUTINE_SLEEP_NAME = "睡眠時間"
ROUTINE_DONE = "Succeed"


# ---------------------------------------------------------------- 列の値

def prop(props, key):
    """Notionプロパティ1つを素のPython値にする。"""
    v = props.get(key)
    if not v:
        return None
    t = v["type"]
    if t == "number":
        return v["number"]
    if t == "date":
        return (v["date"] or {}).get("start")
    if t in ("select", "status"):
        return (v[t] or {}).get("name")
    if t in ("title", "rich_text"):
        return "".join(x["plain_text"] for x in v[t]) or None
    if t == "checkbox":
        return v["checkbox"]
    if t == "multi_select":
        return [x["name"] for x in v[t]]
    return None


def date_range(props, key):
    """date型プロパティを(start, end)で取り出す。"""
    v = props.get(key)
    if not v or v["type"] != "date":
        return None, None
    d = v["date"] or {}
    return d.get("start"), d.get("end")


def _fetch(entity, since=None, until=None):
    col = DATE_COLUMN[entity]
    conds = []
    if since:
        conds.append({"property": col, "date": {"on_or_after": since}})
    if until:
        conds.append({"property": col, "date": {"on_or_before": until}})
    body = {"sorts": [{"property": col, "direction": "ascending"}]}
    if conds:
        body["filter"] = conds[0] if len(conds) == 1 else {"and": conds}
    return query_data_source(DS[entity], body)


# ---------------------------------------------------------------- 体重

def get_measurements(since, until=None):
    """体重・体組成。体組成計の導入より前は体重だけの手入力なので、体組成はNoneになる。"""
    out = []
    for page in _fetch("measurement", since, until):
        p = page["properties"]
        out.append({
            "対象日時": prop(p, "対象日時"),
            "体重": prop(p, "体重(kg)"),
            "体脂肪率": prop(p, "体脂肪率(%)"),
            "除脂肪体重": prop(p, "除脂肪体重(kg)"),
            "骨格筋量": prop(p, "骨格筋量(kg)"),
        })
    return out


# ---------------------------------------------------------------- 睡眠

def get_nights(since, until=None):
    """Ouraの夜の主睡眠を、すべて寝始めた実日付の昇順で返す。

    昼寝は含めない。`対象日時` はOuraの日付で寝始めた日とは限らないので、
    寝始めた実日付で返し直す(oura-api-generic-logic-skill の睡眠区間の判断)。
    同じ日に目覚めた主睡眠が複数あっても、選ばずにすべて返す。
    """
    out = []
    for page in _fetch("oura_sleep", since, until):
        p = page["properties"]
        if prop(p, "種別") != oura_records.NIGHT_SLEEP_TYPE:
            continue
        start, end = prop(p, "開始時刻"), prop(p, "終了時刻")
        out.append({
            "対象日時": oura_records.jst_date(start) or (prop(p, "対象日時") or "")[:10],
            "起床日": oura_records.jst_date(end),
            "開始時刻": start,
            "終了時刻": end,
        })
    out.sort(key=lambda r: r["開始時刻"] or r["対象日時"])
    return out


# ---------------------------------------------------------------- 歩数

def get_daily_steps(since, until=None):
    """Ouraの日次の歩数を、Ouraがつけた日付の昇順で返す。歩数が空の日は返さない。"""
    out = []
    for page in _fetch("oura_daily", since, until):
        p = page["properties"]
        if prop(p, "歩数") is None:
            continue
        out.append({"日付": (prop(p, "対象日時") or "")[:10], "歩数": prop(p, "歩数")})
    return out


def get_routine_sleeps(since, until=None):
    """Routine DB の睡眠時間の行(自己申告)を、Ouraの夜と同じ形で返す。実行した行だけ。"""
    out = []
    for page in _fetch("routine", since, until):
        p = page["properties"]
        if (prop(p, "Name") or "").strip() != ROUTINE_SLEEP_NAME or prop(p, "Status") != ROUTINE_DONE:
            continue
        start, end = date_range(p, "Executed time")
        if not (start and end):
            continue
        out.append({
            "対象日時": oura_records.jst_date(start),
            "起床日": oura_records.jst_date(end),
            "開始時刻": start,
            "終了時刻": end,
        })
    out.sort(key=lambda r: r["開始時刻"])
    return out
