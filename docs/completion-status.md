# Completion status

最終更新: 2026-05-31

## 判定

`global-job-aggregator-mvp` は、2026-05-31 時点で最新の `Collect jobs` workflow が `Collect jobs` ステップで失敗していたため、仕掛かり中として扱いました。

## 完了させた内容

- `app/core.py` を、公開APIの一時障害があってもsource別にエラーを記録して処理全体は完走する実装へ整理
- SQLite `data/jobs.db` を必ず初期化するよう修正
- `data/collection-summary.json` を必ず出力するCLIオプションを追加
- GitHub Actions artifact `jobs-sqlite-db` にDBとsummaryを保存
- CIで構文チェックとpytestを実行
- 既存READMEのSafety-first方針を維持

## 本番実行に必要なもの

必須Secretはありません。任意でRepository Variablesに以下を設定できます。

| Name | 用途 |
|---|---|
| `CONTACT_EMAIL` | 公開APIへ送るUser-Agent内の連絡先 |
| `JOB_KEYWORDS` | 収集キーワードのカンマ区切り |
| `MAX_PER_SOURCE` | 各ソースの最大取得件数 |

## 実行方法

```bash
pip install -r requirements.txt
python scripts/collect_once.py --force --summary-path data/collection-summary.json
uvicorn app.main:app --reload
```
