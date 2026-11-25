# evaluate-diet-app-skill

ダイエットの進捗を評価するアプリケーションスキル。
体重・Oura・Googleカレンダーの記録を集め、ロジックスキルに判断を聞いて、評価をプロジェクトのフォルダの `output/` に Markdown のファイルで書き出す。

## 必要なもの

- [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) か [Codex](https://developers.openai.com/codex)
- [uv](https://docs.astral.sh/uv/)
- Notion のワークスペースと、評価に使うDB
- AIエージェントに接続した Googleカレンダーのコネクタ
- `SKILL.md` の frontmatter の `metadata.dependencies` に書いてある依存するスキル

## インストール

Claude Code では、次のようにクローンする。

```bash
git clone https://github.com/junyatakechi/evaluate-diet-app-skill.git ~/.claude/skills/evaluate-diet-app-skill
```

Codex では、`~/.claude/skills/` を `~/.agents/skills/` に替えてクローンする。

特定のプロジェクトだけで使うなら、`<プロジェクト>/.claude/skills/`（Codex は `<プロジェクト>/.agents/skills/`）の中でクローンする。

## セットアップ

1. 依存するスキルを、このスキルと同じ `skills/` フォルダに並べて置く。
2. 依存するスキルの README の「セットアップ」を、先に済ませる。
3. このスキルが読むDBに、Notion の Integration を接続する。
4. `.env.example` のキーを、プロジェクトのフォルダ直下（AIエージェントを起動するフォルダ）の `.env` に足し、値を埋める。キーの中身は `.env.example` のコメントにある。`.env` はプロジェクトのスキルで共有する。
5. `diet-goal-weights.example.json` を、プロジェクトのフォルダ直下に `diet-goal-weights.json` として写し、目標体重を書く。
6. `conventions/meal-words.json` の語を、自分がカレンダーの食事の記録に書く語に直す。

## 使い方

スキル名だけを指定して呼ぶ。指名しないと、このスキルは読み込まれない。Codex では、例の `/` を `$` に替えて指名する。

```
/evaluate-diet-app-skill
```
