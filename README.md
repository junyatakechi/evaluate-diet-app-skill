# evaluate-diet-app-skill

ダイエットの進捗を評価するアプリケーションスキル。
体重・Oura・Googleカレンダーの記録を集め、ロジックスキルに判断を聞いて、評価をプロジェクトのフォルダの `output/` に Markdown のファイルで書き出す。

## 必要なもの

- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) と [uv](https://docs.astral.sh/uv/)
- Notion のワークスペースと、評価に使うDB
- Claude に接続した Googleカレンダーのコネクタ
- `SKILL.md` の frontmatter の `metadata.dependencies` に書いてある依存するスキル

## インストール

```bash
git clone https://github.com/junyatakechi/evaluate-diet-app-skill.git ~/.claude/skills/evaluate-diet-app-skill
```

特定のプロジェクトだけで使うなら、`<プロジェクト>/.claude/skills/` の中でクローンする。

## セットアップ

1. 依存するスキルを、このスキルと同じ `skills/` フォルダに並べて置く。
2. 依存するスキルの README の「セットアップ」を、先に済ませる。
3. このスキルが読むDBに、Notion の Integration を接続する。
4. `.env.example` のキーを、プロジェクトのフォルダ直下（Claude Code を起動するフォルダ）の `.env` に足し、値を埋める。キーの中身は `.env.example` のコメントにある。`.env` はプロジェクトのスキルで共有する。
5. `diet-goal-weights.example.json` を、プロジェクトのフォルダ直下に `diet-goal-weights.json` として写し、目標体重を書く。
6. `conventions/meal-words.json` の語を、自分がカレンダーの食事の記録に書く語に直す。

## 使い方

スキル名だけを指定して呼ぶ。指名しないと、このスキルは読み込まれない。

```
/evaluate-diet-app-skill
```
