# INFRA-ADR-012 Cloud Run Job の実行粒度と実行時パラメータ設計

## Conclusion (結論)

- カンファレンス論文クロールは**単一の汎用 Cloud Run Job** で運用し、実行時に `CONFERENCE_NAMES` と `YEARS` を上書きする。
- カンファレンス名や年度は**インフラの識別子ではなく実行時パラメータ**として扱う。
- 日次・定期フィード（arXiv や技術ブログなど）は将来導入する際に **Cloud Scheduler** で制御する。
- 大規模化時には `CLOUD_RUN_TASK_INDEX` を使った並列実行・シャード分割を検討する。

## Status (ステータス)

Accepted (承認済み) - 2026-05-08

## Context (背景・課題)

### 背景

DevGist の crawler は `CONFERENCE_NAMES` と `YEARS` を環境変数で受け取り、DBLP などのソースから論文メタデータを収集するバッチワークロードである。
これまでの ADR（INFRA-ADR-003, INFRA-ADR-010）では、Cloud Run Jobs を実行基盤とし、Terraform で完全管理する方針を決定してきた。INFRA-ADR-003 で想定した `Cloud Scheduler + Cloud Run Jobs + Artifact Registry` は、arXiv 新着論文フィードや技術ブログ RSS のような**日次・定期クロール**に対しては、今も適切な構成である。
ただし、これらの ADR は**カンファレンス論文のバックフィル・イベント駆動クロール**と**日次フィードクロール**を明確に区別していなかった。INFRA-ADR-003 の Cloud Scheduler 想定は、定期実行を前提としており、カンファレンス論文クロールのような「手動・イベント駆動・パラメータ可変」な運用までは含意していない。
本 ADR は、カンファレンス論文クロールという**特定の例外運用**に対して、Scheduler 前提を絞り込み・精緻化する。カンファレンス論文クロールは手動実行やイベント駆動を主とし、実行時に `CONFERENCE_NAMES` と `YEARS` をオーバーライドして運用する。これは以前の ADR の方針を否定するものではないが、カンファレンス論文クロールの運用想定を明確に変更・特化させるものである。

### 要件と制約

1. **実行頻度の違い**
   - カンファレンス論文クロール（RecSys / KDD / WSDM / WWW / SIGIR / CIKM など）は**イベント駆動・手動実行・バックフィル中心**であり、日次定期実行ではない。
   - 新着論文・記事フィード（arXiv や技術ブログなど）は**日次・周期実行**が自然であり、将来的に Cloud Scheduler で制御したい。

2. **パラメータの性質**
   - `CONFERENCE_NAMES` や `YEARS` は「インフラの core identity」ではなく「実行時に変わる運用パラメータ」である。
   - 年度が変わるたびにインフラ定義（Terraform）を変更すべきではない。

3. **運用のシンプルさ**
   - 初期フェーズでは、Cloud Console や gcloud からの手動実行が主要な運用パスである。
   - 実行のたびに Terraform apply せずに、実行時パラメータを差し替えられる必要がある。

4. **将来の拡張性**
   - カンファレンス数や年度が増えた場合、1 回の実行で大量の組み合わせを処理する必要が出る可能性がある。
   - Cloud Run Jobs の task 並列・シャード分割を将来活用できる余地を残す。

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: 単一汎用 Job + 実行時オーバーライド | 手動・イベント駆動のバッチ。パラメータが頻繁に変わる場合 | Job リソースの重複を避けられる。Terraform 定義がシンプル。運用パラメータとインフラが分離できる | 1 つの Job ログに複数カンファレンスの実行が混在する。Cloud Console からの実行時に毎回 env を指定する必要がある | **採用（初期デフォルト）** |
| Option B: カンファレンス別 Cloud Run Job | 運用で「Cloud Console のワンクリック選択」や「ログの完全分離」を強く重視する場合 | Console 上で Job 名で選択できる。ログ・履歴がカンファレンス単位で分離される | パラメータ違いだけで Job リソースが増え、Terraform が冗長になる。年度変更時にも Job 定義を更新する必要がある（または実行時上書きが結局必要） | 受け入れ可能な代替案だが**初期デフォルトではない** |
| Option C: task 並列 / カンファレンス×年度シャード | 1 回の execution で数十〜数百の組み合わせを並列処理する場合 | スケール時の処理時間を短縮できる。Cloud Run Jobs の task 数で水平分散できる | 実装・運用・デバッグが複雑になる。現時点の規模では過剰 | **将来の選択肢** |
| Option D: Cloud Scheduler による定期実行 | 日次・週次の定常フィード（arXiv RSS など） | 定期実行をマネージドに扱える。ジョブ定義とスケジュールを分離できる | カンファレンス論文クロールのような「イベント駆動・手動実行」には向かない。Scheduler は Job 定義ではなく実行トリガーである | **日次フィード導入時に検討** |

### 選定観点

- インフラ定義と運用パラメータを分離する
- 初期フェーズの手動実行運用を優先し、Terraform 変更なしで実行時パラメータを変えられること
- Job リソースの重複を最小化する
- 将来の並列化・定期化への移行可能性を残す

## Considered Options

### Option A: 単一汎用 Job + 実行時オーバーライド [採用（初期デフォルト）]

Terraform 上では 1 つの汎用 Cloud Run Job（例: `crawler-job`）を定義し、`CONFERENCE_NAMES` や `YEARS` などの実行パラメータは**実行時に上書き**する。

具体的な実行方法:

- **Cloud Console**: 「Execute with overrides」で環境変数を上書き
- **gcloud CLI**:
  ```bash
  # 実行時に環境変数を上書き（Job 定義自体は変更しない）
  # 値にカンマを含む場合は、gcloud のリスト構文と衝突するため代替区切り文字を使う
  # カスタム区切り文字（例: @）はキーや値に含まれてはならない。含まれる場合は別の文字を選ぶ
  gcloud run jobs execute crawler-job \
    --update-env-vars='^@^CONFERENCE_NAMES=recsys,kdd@YEARS=2024,2025' \
    --region=asia-northeast1
  ```
- **Cloud Run Jobs API**: `overrides` フィールドで環境変数を指定

採用理由:

- `CONFERENCE_NAMES` や `YEARS` はインフラの identity ではなく、実行ごとに変わる運用パラメータである。
- 年度が変わるたびに Terraform を修正するのは過剰である。
- Job リソースが 1 つで済み、Terraform 定義・IAM・Scheduler 設定がシンプルになる。
- INFRA-ADR-010「Terraform で完全管理」の方針と整合する。Job の基本定義（image、memory、CPU、timeout、service account など）は Terraform で管理し、**実行時パラメータのみ execution 側で上書き**する。

注意点・トレードオフ:

- Cloud Run の execution ID はユーザーが Console から意味のある名前を付けられないため、複数カンファレンスを並行実行した際に「どの実行がどのカンファレンスか」を ID だけで判別しにくい。
- これは**実行時オーバーライド**（`gcloud run jobs execute --update-env-vars`）であり、**Job 定義の更新**（`gcloud run jobs update --update-env-vars`）とは異なる。後者は Job そのものの desired state を変更するため、INFRA-ADR-010 に反する。

この観測性の課題に対しては以下で緩和する:

- アプリケーション側で **INFO レベルのログに実行コンテキスト**（カンファレンス名、年度、task index など）を含める。
- GCS 出力パスやメタデータにカンファレンス名・年度を含める（例: `gs://bucket/recsys/2025/...`）。
- 必要に応じて `CRAWL_RUN_ID` や `RUN_LABEL` 環境変数を実行時に渡し、ログ・出力パス・メタデータに反映する。

### Option B: カンファレンス別 Cloud Run Job [受け入れ可能な代替案 / 初期デフォルトではない]

Terraform 上で `crawler-recsys-job`、`crawler-kdd-job` など、カンファレンスごとに Cloud Run Job を定義する。
年度については各 Job でも実行時上書きが必要となる。

却下理由（初期デフォルトとして）:

- パラメータ違い（カンファレンス名）だけで Job リソースが増え、Terraform が冗長になる。
- 年度は依然として実行時に上書きする必要があるため、「完全にワンクリック実行」にはならない。
- 新しいカンファレンス追加時に Terraform 変更が必要になる。
- INFRA-ADR-010 の「Terraform で完全管理」の方針は維持できるが、Job 数の増加により管理・監視・IAM のオーバーヘッドが増える。

ただし、以下の場合は Option B への移行や併用を検討できる:

- 運用チームが Cloud Console 上で「Job 名を選んでワンクリック実行」を強く重視する場合
- ログ・監査・コスト配分をカンファレンス単位で厳密に分離したい場合
- カンファレンスごとに異なる resource 設定（memory、timeout、task count）が必要になった場合

### Option C: task 並列 / カンファレンス×年度シャード [将来の選択肢]

1 回の execution で複数の Cloud Run task を起動し、`CLOUD_RUN_TASK_INDEX` 環境変数に基づいて各 task が担当するカンファレンス・年度の組み合わせを決定する。

例:

```python
# 擬似的なシャード割り当て例
shards = [
    ("recsys", 2024), ("recsys", 2025),
    ("kdd", 2024),    ("kdd", 2025),
    ...
]
task_index = int(os.getenv("CLOUD_RUN_TASK_INDEX", 0))
conference, year = shards[task_index]
```

非採用（現時点）:

- 現時点のカンファレンス数・年度数では、単一 task 実行で十分な処理時間であり、シャード分割のメリットが小さい。
- シャード設計、失敗時の部分再実行、task 間の依存制御などが複雑になる。
- 実行時パラメータ（どの組み合わせを処理するか）がコード内の shard テーブルに埋もれやすく、運用の柔軟性が下がる。

再検討条件:

- 1 回の execution で処理すべきカンファレンス・年度の組み合わせが数十を超え、実行時間が許容範囲を超えた場合
- 各カンファレンス・年度の処理を並列化することで、全体の wall-clock time を短縮する必要が生じた場合
- 各 task の処理が独立であり、task 間でデータ共有が不要な場合

### Option D: Cloud Scheduler による定期実行 [日次フィード導入時に検討]

Cloud Scheduler から Cloud Run Job を定期起動する。Scheduler 側で環境変数を指定する場合、Cloud Run Jobs API の `jobs:run` への認証済み HTTP 呼び出しを行い、リクエストボディに `overrides` を含める。これは Scheduler 固有の「ネイティブ機能」ではなく、Scheduler が Cloud Run Jobs API を呼び出す仕組みである。

非採用（カンファレンス論文クロールのデフォルトとして）:

- カンファレンス論文クロールは「毎日決まったカンファレンス・年度を回す」という性質ではない。
- バックフィル、新規カンファレンス追加、年度更新など、実行タイミングとパラメータが不定である。
- Scheduler は「トリガー」の役割であり、パラメータを固定して定期実行する用途に適している。

ただし、以下のワークロードでは Option D を採用する:

- arXiv 新着論文フィード
- 技術ブログ RSS の定期巡回
- その他「毎日決まった処理を回す」定常バッチ

## Decision (決定事項)

カンファレンス論文クロールは**単一の汎用 Cloud Run Job** で運用し、`CONFERENCE_NAMES` と `YEARS` は**実行時に上書き**する。

### 採用方針

- Terraform 上では 1 つの Cloud Run Job を定義する。Job 名は環境や目的で分離してよいが、カンファレンス名で分離しない。
- `CONFERENCE_NAMES`、`YEARS`、および必要に応じて `CRAWL_RUN_ID` / `RUN_LABEL` は**実行時パラメータ**として扱う。
- 実行時上書きは `gcloud run jobs execute --update-env-vars` または Cloud Console「Execute with overrides」を使う。
- **Job 定義の更新**（`gcloud run jobs update --update-env-vars`）は行わない。環境変数の恒常的な変更が必要な場合は Terraform 変更に回す。
- 環境変数を上書きする際は、`CONFERENCE_NAMES` と `YEARS` を必ずセットで渡すことを推奨する。片方だけを上書きすると、Job 定義のデフォルト値やアプリケーションのデフォルト値と意図せず組み合わさるリスクがある。
- 日次・定期フィード（arXiv など）は別の Cloud Run Job（または同一 Job を別用途で使い回す場合は別スケジュール）として、Cloud Scheduler から起動する。
- 将来、シャード並列が必要になった場合は `CLOUD_RUN_TASK_INDEX` を使った task 分割を検討する。

### 初期構成

- **Job Runtime**: 1 つの汎用 Cloud Run Job（例: `crawler-job`）
- **実行時パラメータ**:
  - `CONFERENCE_NAMES`（カンマ区切り）
  - `YEARS`（カンマ区切り）
  - 任意: `CRAWL_RUN_ID` / `RUN_LABEL`
- **実行方法**:
  - Cloud Console「Execute with overrides」
  - `gcloud run jobs execute --update-env-vars ...`
  - Cloud Run Jobs API `overrides`
- **観測性**:
  - アプリケーションログにカンファレンス名・年度・run label を含める
  - GCS 出力パスにカンファレンス名・年度を含める
- **定期フィード（将来）**: Cloud Scheduler + 別途検討

### 実行例

```bash
# 単一カンファレンス・単一年度の手動実行
# （実行時に env を上書きする。Job 定義自体は変更しない）
gcloud run jobs execute crawler-job \
  --update-env-vars=CONFERENCE_NAMES=recsys,YEARS=2025 \
  --region=asia-northeast1

# 複数カンファレンス・複数年度の一括実行
# 値にカンマを含む場合、gcloud の comma-separated flag 構文と衝突するため
# 先頭に ^@^ を付けて @ を区切り文字にする
# カスタム区切り文字はキーや値に含まれてはならない。含まれる場合は別の文字を選ぶ
gcloud run jobs execute crawler-job \
  --update-env-vars='^@^CONFERENCE_NAMES=recsys,kdd,wsdm@YEARS=2024,2025@RUN_LABEL=backfill-2024-2025' \
  --region=asia-northeast1
```

### 再検討条件

- 運用で「Cloud Console から Job 名で選んでワンクリック実行」を強く要望された場合 → Option B（カンファレンス別 Job）を検討
- 1 回の execution で処理する組み合わせが数十を超え、実行時間や並列度が不足した場合 → Option C（task シャード並列）を検討
- 日次・週次の定常フィード（arXiv など）が導入された場合 → Option D（Cloud Scheduler）を検討
- カンファレンスごとに異なる memory、timeout、task count が必要になった場合 → Option B への移行または Terraform 変数化を検討

## Consequences (結果・影響)

### Positive (メリット)

- **Terraform 定義がシンプルに保たれる**
  - Job リソースが 1 つで済み、カンファレンス追加・年度変更で Terraform 変更が不要になる。
- **運用パラメータとインフラが分離される**
  - 実行時に自由にカンファレンス・年度を組み合わせられる。
- **INFRA-ADR-010 と整合する**
  - Job の基本定義は Terraform で管理し、実行時パラメータのみ execution 側で上書きする。
  - `gcloud run jobs update` による Job 定義の直接変更を避けられる。
- **将来の拡張性が残る**
  - task シャード並列（Option C）や Cloud Scheduler 連携（Option D）への移行が、Job 定義を大きく変えずに検討できる。

### Negative (デメリット)

- **Cloud Run execution ID から実行内容が判別しにくい**
  - Console やログ上では execution ID（例: `crawler-job-abcde`）だけでは「どのカンファレンス・年度を処理したか」が分からない。
  - これはアプリケーション側のログ・GCS パス・メタデータで補完する。
- **実行時に毎回パラメータを指定する必要がある**
  - Cloud Console から実行する場合、「Execute with overrides」で環境変数を入力する手間が生じる。
  - よく使う組み合わせについては、運用ドキュメントやスクリプトで補完する。
- **1 つの Job ログに複数カンファレンスの実行が混在する**
  - フィルタリングはログクエリ（`jsonPayload.conference_name` など）で行う前提となる。

### Risks / Future Review (将来の課題)

- 実行時パラメータの入力ミス（カンファレンス名の typo、年度の範囲誤り）による誤実行リスク。
- 複数の手動実行が同時に走った場合のリソース競合や、GCS 出力の上書き・重複の有無を確認する必要がある。
- `CRAWL_RUN_ID` や `RUN_LABEL` の運用ルール（必須か任意か、命名規則など）を別途定める必要がある。
- 日次フィード導入時に、カンファレンス用 Job とフィード用 Job を分離するか、同一 Job を使い回すかの判断が必要。

## Next Steps

1. Terraform の Cloud Run Job 定義を単一汎用 Job に整理する（カンファレンス別 Job が既に存在する場合は統合または移行計画を立てる）
2. 実行時パラメータ（`CONFERENCE_NAMES`、`YEARS`、`CRAWL_RUN_ID` / `RUN_LABEL`）の運用手順を README・runbook に記載する
3. アプリケーション側で実行コンテキスト（カンファレンス名・年度・run label）を INFO ログに出力する実装を確認・追加する
4. GCS 出力パス・メタデータにカンファレンス名・年度を含める設計を確認する
5. 日次フィード（arXiv など）の導入時に、Cloud Scheduler + 別 Job 構成を別途 ADR または設計ドキュメントで検討する
6. 大規模化時の task シャード並列（Option C）の設計を必要に応じて別途検討する
7. 手動実行の際のパラメータ入力ミスを防ぐため、推奨実行パターンをスクリプト化またはドキュメント化する

## Related Documents

- [INFRA-ADR-003 Crawler実行基盤として Cloud Run Jobs を採用する](./003-crawler-execution-platform.md)
- [INFRA-ADR-010 Cloud Run Job の管理責務を Terraform に集約する](./010-cloud-run-job-management.md)
- [CRAWLER-ADR-001 論文収集クローラーの実装言語としてPythonを採用](../crawler/001-language-selection.md)
- [CRAWLER-ADR-002 XMLパースにdefusedxmlを採用](../crawler/002-xml-parsing-security.md)
- [Crawler README](../../../workflows/crawler/README.md)
- [ADR運用ガイド](../README.md)
- [ADRテンプレート](../_template.md)
