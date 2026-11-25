# 読むDB

どのDBの、どの列を読むか。判断ではなく、この環境での記録の取り決め。
**列名の正は `scripts/read_notion.py`。** この文書は説明で、変えるときはスクリプトとNotion側を同時に直す（notion-cli-generic-logic-skill のスキーマの変更の判断）。

DBのURLは起動フォルダの `.env` の `DIET_DB_<KEY>_URL` にある。

| キー | DB | 書いているもの | 読む列 |
|---|---|---|---|
| `MEASUREMENT` | 体重記録 | collect-renpho-records-app-skill（それ以前は手入力） | `対象日時`・`体重(kg)`・`体脂肪率(%)`・`除脂肪体重(kg)`・`骨格筋量(kg)` |
| `OURA_SLEEP` | Oura 睡眠区間 | collect-oura-records-app-skill | `対象日時`・`種別`・`開始時刻`・`終了時刻` |
| `OURA_DAILY` | Oura 日次サマリー | collect-oura-records-app-skill | `対象日時`・`歩数` |
| `ROUTINE` | Routine | 対象者 | `Executed time`（開始と終了）・`Name`・`Status`（使うのは `Name` が「睡眠時間」で `Status` が `Succeed` の行だけ） |

- Oura の列名は collect-oura-records-app-skill の `COLUMNS` と同じ。体重記録の列名は collect-renpho-records-app-skill の `VALUE_COLUMNS` と同じ。**列を変えたら、同期のアプリとこのスキルの両方を直す。**
- Oura の記録の読み方（夜の主睡眠だけを採る・寝始めた日と目覚めた日）は、oura-api-generic-logic-skill の睡眠区間の判断に従い、`read_notion.py` が行う。
