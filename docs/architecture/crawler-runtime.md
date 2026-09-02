# Crawler の実行基盤と実装

## 実行基盤は Cloud Run Jobs

crawler は HTTP 駆動の常駐サービスではなく、定期実行・手動再実行・リトライを伴う batch workload として扱う（[INFRA-ADR-003](../adr/infra/003-crawler-execution-platform.md)）。

| 用途 | 使うもの |
|---|---|
| Job runtime | Cloud Run Jobs（`haru256-devgist-app-dev`） |
| image | Artifact Registry（`haru256-devgist-ops`） |
| 収集データ | GCS datalake（`haru256-devgist-data-dev`） |
| 定期起動 | Cloud Scheduler（**日次フィード導入時**。現在は未使用） |
| ログ / メトリクス | Cloud Logging / Cloud Monitoring |

`Cloud Batch` は初期フェーズには過剰。大規模分散、VM レベルの制御、複雑なジョブ依存が必要になったら再検討する。

## Job の定義は Terraform に集約する

**`gcloud run jobs deploy` と `gcloud run jobs update` は使わない**（[INFRA-ADR-010](../adr/infra/010-cloud-run-job-management.md)）。

| | Terraform | CI/CD |
|---|---|---|
| Cloud Run Job の作成・更新 | ✅ | ❌ |
| image 参照（digest） | ✅ | ❌（digest を tfvars 経由で渡す） |
| memory / CPU / timeout / retry / task count / parallelism | ✅ | ❌ |
| env / secret reference / service account | ✅ | ❌ |
| Cloud Scheduler / IAM / Artifact Registry | ✅ | ❌ |
| image の build と push | ❌ | ✅ |

image 参照は **digest 形式が必須**。tag は可読性のために付けてよいが、参照には使わない。
image 更新の 2 PR 運用は [cicd.md](cicd.md) を参照。

緊急対応を除き、Cloud Console からの直接変更もしない。

## 実行粒度は単一の汎用 Job

カンファレンス論文クロールは **1 つの汎用 Job**（`crawler`、region `us-central1`）で運用し、対象は実行時に上書きする（[INFRA-ADR-012](../adr/infra/012-crawler-execution-parameters.md)）。

**カンファレンス名や年度はインフラの識別子ではなく実行時パラメータ。**
カンファレンスや年度が増えても Terraform を変更しない。Job をカンファレンス別に分けない。

実行時パラメータ:

| 変数 | 内容 |
|---|---|
| `CONFERENCE_NAMES` | カンマ区切り（`recsys,kdd`） |
| `YEARS` | カンマ区切り（`2024,2025`） |

`CRAWL_RUN_ID` / `RUN_LABEL` は [INFRA-ADR-012](../adr/infra/012-crawler-execution-parameters.md) の Next Steps のまま未実装。crawler は読まない。

```bash
# 単一カンファレンス・単一年度
gcloud run jobs execute crawler \
  --update-env-vars=CONFERENCE_NAMES=recsys,YEARS=2025 \
  --region=us-central1

# 値にカンマを含むので、先頭に ^@^ を付けて @ を区切り文字にする
gcloud run jobs execute crawler \
  --update-env-vars='^@^CONFERENCE_NAMES=recsys,kdd,wsdm@YEARS=2024,2025' \
  --region=us-central1
```

注意点:

- 使うのは `jobs execute --update-env-vars`（**実行時オーバーライド**）。`jobs update --update-env-vars`（Job 定義の変更）は Terraform の責務なので使わない
- `CONFERENCE_NAMES` と `YEARS` は必ずセットで渡す。片方だけだと Job 定義のデフォルトと意図せず組み合わさる
- execution ID から実行内容は判別できない。アプリ側のログ・GCS 出力パス（`gs://bucket/recsys/2025/...`）・メタデータで補う

日次・定期フィード（arXiv、技術ブログ RSS）を導入するときは Cloud Scheduler を使う。
これはカンファレンス論文クロールとは別の運用として扱う。

## アプリケーション側の責務

実行基盤は再開性やクロール品質を担保しない。crawler 側で設計する（[INFRA-ADR-003](../adr/infra/003-crawler-execution-platform.md)、[INFRA-ADR-010](../adr/infra/010-cloud-run-job-management.md)）。

- 冪等性（再実行しても重複登録しない）
- 再開性・checkpoint
- レート制御
- 重複排除
- 実行コンテキスト（カンファレンス名・年度・task index）を INFO ログに出す

状態は Job の外（GCS / Cloud SQL / Firestore）に置く。

## 実装の前提

- 言語は **Python**、型定義とバリデーションは **Pydantic**（[CRAWLER-ADR-001](../adr/crawler/001-language-selection.md)）
  - DBLP / Semantic Scholar など不定形なレスポンスを低コストで吸収するため
  - Go への移行は、監視 URL 10 万件超・同時接続 1,000 超・単一プロセス 4GB 超などの閾値に達したら再検討
- XML パースは **`defusedxml`**。`xml.etree.ElementTree` を直接使わない（[CRAWLER-ADR-002](../adr/crawler/002-xml-parsing-security.md)）

  ```python
  import defusedxml.ElementTree as ET  # not: import xml.etree.ElementTree as ET
  ```

## 再検討の条件

- 1 execution の組み合わせが数十を超えて実行時間が足りない → `CLOUD_RUN_TASK_INDEX` による task シャード並列（[INFRA-ADR-012](../adr/infra/012-crawler-execution-parameters.md) Option C）
- カンファレンスごとに異なる memory / timeout / task count が必要 → カンファレンス別 Job（同 Option B）
- image 更新の頻度が上がり Terraform apply がボトルネックになった → image のみ CI/CD 管理（[INFRA-ADR-010](../adr/infra/010-cloud-run-job-management.md) Option B）
- 大規模分散や VM レベルの制御、GPU が必要 → Cloud Batch（[INFRA-ADR-003](../adr/infra/003-crawler-execution-platform.md)）
