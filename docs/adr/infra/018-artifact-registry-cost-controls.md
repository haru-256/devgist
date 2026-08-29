# INFRA-ADR-018 Artifact Registry の vulnerability scanning と image retention

## Conclusion (結論)

- Artifact Registry repository は vulnerability scanning を **明示的に `DISABLED`** にする。`INHERITED` にしない。
- 古い image は cleanup policy で消す。パッケージごとに **直近 5 世代を KEEP** し、**30 日より古い version を DELETE** する（KEEP が勝つ）。
- 実装は `infra/terraform/modules/artifact_registry` に置く。ops の crawler リポジトリを含む、このモジュール経由の全 Docker repository に適用する。

## Status (ステータス)

Accepted (2026-08-29)

## Context (背景・課題)

### 背景

crawler image は Artifact Registry（`devgist-ops`）に置き、Cloud Run Job は digest で参照する（[INFRA-ADR-007](./007-artifact-registry-and-sa-strategy.md)、[INFRA-ADR-010](./010-cloud-run-job-management.md)、[INFRA-ADR-016](./016-github-actions-wif-and-crawler-image-push.md)）。

[INFRA-ADR-010](./010-cloud-run-job-management.md) と [INFRA-ADR-016](./016-github-actions-wif-and-crawler-image-push.md) は retention を未決のまま残していた。Crawler Deploy は `GITHUB_SHA` で毎回 push するため、cleanup が無いと storage 課金が増え続ける。

Terraform の `google_artifact_registry_repository` で `vulnerability_scanning_config` を省略すると `INHERITED` 相当になる。プロジェクトで Container Scanning API を有効にすると、リポジトリ単位で拒否していない限りスキャン課金が発生し得る。

### 要件と制約

1. **課金抑制**
   - vulnerability scanning 課金を避ける
   - 使わない古い image の storage を抑える
2. **rollback 余地**
   - Cloud Run は digest pin なので、直近数世代は残す
3. **明示性**
   - 「API が無いから実質 off」ではなく、リポジトリ設定で OFF を宣言する
4. **運用シンプルさ**
   - 初期フェーズでは複雑なタグ規則や環境別 retention は避ける

### 比較した選択肢

#### Vulnerability scanning

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: 省略（INHERITED） | プロジェクト方針に追従したい場合 | 記述が短い | API 有効化で意図せずスキャンが走る | 非採用 |
| Option B: `DISABLED` を明示 | スキャン課金をリポジトリ単位で止めたい場合 | 意図が Terraform に残る。API を後から有効にしても除外される | セキュリティスキャンは別経路が必要 | 採用 |

#### Retention

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: 無制限保持 | 監査で全履歴が要る場合 | 失うものがない | storage が単調増加 | 非採用 |
| Option B: KEEP 直近 N のみ（DELETE 無し） | 試験中 | 設定が単純 | DELETE が無いと何も消えない | 非採用 |
| Option C: KEEP 直近 5 + DELETE 30 日超 | 個人開発で rollback と課金のバランスを取る場合 | 直近は残る。古いものは消える。KEEP が DELETE に勝つ | 30 日以内に 5 を超えると古い方は残る | 採用 |
| Option D: KEEP 直近 5 + DELETE 即時（年齢ほぼ 0） | storage を最小にしたい場合 | 世代数が厳密に 5 付近になる | 誤削除リスクが高い | 非採用 |

### 選定観点

- 課金を抑える明示的な設定か
- digest pin の rollback に足りる世代があるか
- Terraform module 1 箇所で全 app repository に適用できるか

## Considered Options

### Option A: scanning を省略し、retention も後回し [却下]

現状維持。ADR-010 / 016 の「未決」を残す。

却下理由: push のたびに storage が増え、scanning も `INHERITED` のまま意図が曖昧。

### Option B: scanning `DISABLED` + KEEP 5 / DELETE 30d [採用]

module で両方を宣言する。

採用理由:

- Container Scanning API を後から有効にしても、この repository はスキャン対象外になる
- KEEP が DELETE に勝つので、直近 5 世代は 30 日を超えても残る
- 30 日以内に 5 を超えた分は、年齢条件に入るまで残る（過剰削除を避ける）

## Decision (決定事項)

Artifact Registry の Docker repository は vulnerability scanning を `DISABLED` にし、cleanup policy で直近 5 世代を KEEP・30 日より古い version を DELETE する。

### 採用方針

- `vulnerability_scanning_config.enablement_config = "DISABLED"`
- cleanup policy:
  - `keep-minimum-versions` (`KEEP`, `most_recent_versions.keep_count = 5`)
  - `delete-older-than` (`DELETE`, `tag_state = ANY`, `older_than = 30d`)
- `cleanup_policy_dry_run` の初期値は `false`（実際に削除する）
- keep / older_than は module 変数で上書きできるが、デフォルトは上記

### 初期構成

- 適用対象: `artifact_registry` module で作る全 repository（現状 `crawler`）
- Container Scanning API は ops の `required_services` に入れない（現状維持）
- Cloud Run / GKE とのリージョン揃えは [INFRA-ADR-007](./007-artifact-registry-and-sa-strategy.md) と既存 `gcp_default_region` のまま

### 再検討条件

- コンプライアンスで脆弱性スキャン必須になった場合（別経路のスキャン含む）
- rollback に 5 世代では足りない、または 30 日では storage が厚い場合
- prod 専用 retention（より長く残す）が必要になった場合

## Consequences (結果・影響)

### Positive (メリット)

- scanning 課金をリポジトリ単位で明示的に止められる
- 古い image の storage 増加を抑えられる
- digest pin の直近 rollback 用に 5 世代残る

### Negative (デメリット)

- 30 日を超え、かつ直近 5 世代に入らない digest は消える。長い間 apply していない Cloud Run の旧 digest 参照は pull できなくなる
- Artifact Registry の cleanup はバックグラウンドジョブなので、反映まで最大おおよそ 1 日かかることがある

### Risks / Future Review (将来の課題)

- apply 直後に dry-run へ一時切替して監査ログを見る運用が必要なら、`cleanup_policy_dry_run` を true にして再 apply する
- untagged digest だけの掃除が必要なら、DELETE 条件を足す

## Next Steps

1. `artifact_registry` module に scanning `DISABLED` と cleanup policy を入れる
2. `devgist-ops` を手元で `terraform plan` / `apply` する（Cloud Agent からは AR 権限が無い）
3. apply 後、Console または権限のあるアカウントで scanning が Disabled・cleanup が有効であることを確認する

## Related Documents

- [[INFRA-ADR-007] Artifact Registry リポジトリ戦略とワークロード用 Service Account 設計](./007-artifact-registry-and-sa-strategy.md)
- [[INFRA-ADR-010] Cloud Run Job の管理責務を Terraform に集約する](./010-cloud-run-job-management.md)
- [[INFRA-ADR-016] GitHub Actions から crawler image を Artifact Registry へ push する](./016-github-actions-wif-and-crawler-image-push.md)
- [artifact_registry module](../../../infra/terraform/modules/artifact_registry/README.md)
- [Artifact Registry cleanup policies](https://docs.cloud.google.com/artifact-registry/docs/repositories/cleanup-policy)
- [Control scanning settings for a repository](https://docs.cloud.google.com/artifact-analysis/docs/enable-automatic-scanning)
