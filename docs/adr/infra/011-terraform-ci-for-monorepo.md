# INFRA-ADR-011 Terraform monorepo CI パイプライン設計

## Conclusion (結論)

- Terraform root の検出ロジックを `.github/scripts/find_terraform_roots.py` に切り出し、GitHub Actions matrix を動的生成する。手書き matrix の更新漏れを防ぐ。
- 検証ステップ（init / validate / test / tflint）を Composite Action (`.github/actions/terraform-check`) に集約し、environment CI と module test CI で共通利用する。
- PR CI では `terraform init -backend=false` と `mock_provider` / `override_data` を用い、GCP 認証・backend 接続なしに静的検証を行う。

## Status

Accepted (承認済み) - 2026-05-02

## Context

### 背景

DevGist は GCP project、environment、reusable module を Terraform monorepo で管理する。
`infra/terraform/environments/` 配下は実際の GCP environment を表す Terraform root（例: devgist-app/dev）、
`infra/terraform/modules/` 配下は再利用可能なモジュールを置く。

Terraform CI では、これらに対して `terraform validate`, `terraform test`, `tflint` を実行したい。

### 課題

1. **matrix の手動管理**: Terraform root を GitHub Actions YAML に列挙する方式では、root 追加時に matrix の更新漏れが起きやすい。
2. **検証手順の重複**: environment root 向けと module test root 向けで validate / test / tflint の手順が重複し、変更時に複数箇所の修正が必要になる。
3. **PR CI のバックエンド依存**: `terraform plan` は GCS backend 接続と GCP 認証を要求するため、PR ごとに実行するには権限設計が複雑になる。コードとして壊れていないかの早期検知と、apply 可能性の検証は分離すべきである。

### 要件と制約

1. **保守性**: Terraform root が増えても CI の更新漏れが起きないこと。
2. **可読性**: CI の制御フロー（何を対象に何を実行するか）が読みやすいこと。
3. **PR CI の安全性**: PR CI は GCP 認証・state lock・backend 接続に依存しないこと。
4. **過剰な汎用化の回避**: module と environment の依存解析など、現規模では複雑さに見合わない仕組みは持ち込まない。
5. **将来拡張**: `terraform plan` を後から追加できる設計にする。

## Considered Options

### Decision 1: Terraform root 検出方式

#### Option A: 手書き matrix [却下]

`strategy.matrix.root` に Terraform root を列挙する方式。

却下理由: root 追加・削除のたびに YAML を手で更新する必要があり、更新漏れが起きやすい。DevGist は今後 environment が増える見込みがあり、長期的な保守性が弱い。

#### Option B: module と environment の依存関係を解析して差分実行する [却下]

変更された module を検出し、それを参照する environment だけを CI 対象にする方式。

却下理由: 理論上は効率的だが、`module.source` の解析・相対パス解決・再帰的な依存解決・差分ファイルからの影響範囲計算が必要になる。現時点の規模では実装・運用の複雑さが実行時間短縮のメリットを上回る。Terraform 変更時は広めに CI を回す方が安全。

#### Option C: Bash script を YAML に直書きする [却下]

`find`, `sed`, `sort`, `python3 -c` を組み合わせて root を検出する方式。

却下理由: 短期的には書けるが、environment root と module test root の両方を検出し count も JSON 出力する段階で複雑化した。YAML 内の長い Bash は syntax highlight・lint が弱く、ローカルで実行・テストしにくい。

#### Option D: repo 内 Node.js script [却下]

`.github/scripts/find-terraform-roots.mjs` を Node.js で作成する方式。

却下理由: 実装は可能だが、標準 library だけで再帰的な path 探索を書くと Python より冗長になりやすい。本処理は GitHub API 連携ではなく path 操作が中心であるため、Python の方が自然である。

#### Option E: repo 内 Python script [採用]

`.github/scripts/find_terraform_roots.py` を作成し、workflow から `python` で呼び出す方式。

採用理由:
- `pathlib` により path 操作を簡潔に書ける。
- `json` 標準 library だけで matrix 用 JSON を生成できる。外部依存が不要。
- pytest で unit test を書ける。ローカル実行・デバッグもしやすい。
- DevGist は Python 中心のリポジトリであり、CI 補助 script を Python で書くことは技術的整合性が高い。

---

### Decision 2: 検証ステップの共通化

Terraform CI には environment 向けと module test 向けの 2 種類のジョブがある。両方で init / test / tflint を実行し、environment は加えて validate も実行する。

#### Option A: 各 job でステップを直書きする [却下]

`terraform-environment-ci` と `terraform-module-test` それぞれの job に同じステップを記述する方式。

却下理由: 手順の追加・変更時に複数箇所の修正が必要になり、差異が生じやすい。

#### Option B: Composite Action として共通化する [採用]

`.github/actions/terraform-check/action.yml` に検証手順をまとめ、各 job から呼び出す方式。

採用理由:
- 変更が 1 箇所に集まり、environment/module 間で手順の乖離が起きない。
- `skip-validate` などの入力で environment と module の差異を吸収できる。
- Composite Action はリポジトリ内で完結し、外部公開を必要としない。

---

### Decision 3: PR CI の静的検証方針

#### Option A: GCP 認証ありの `terraform plan` を PR CI で実行する [将来候補]

Workload Identity Federation などを使い、PR CI でも plan を実行する方式。

採用しない理由（現時点）: GCS backend 接続・GCP 認証・state lock・権限設計が必要となり、PR CI として設定・管理するコストが高い。現時点の規模では、コードとして壊れていないかの早期検知を優先する。

#### Option B: `terraform init -backend=false` + mock / override [採用]

backend を無効化した init を使い、`mock_provider` と `override_data` で外部依存を除いてテストを実行する方式。

採用理由:
- GCP 認証や state lock なしに validate / test / tflint を実行できる。
- `mock_provider "google" {}` で provider-managed リソースをモックできる。
- `terraform_remote_state` などのバックエンド依存は `override_data` でモックする。
- PR ごとに認証を扱う複雑さを排除でき、CI のセットアップが単純になる。

## Decision

### 採用方針

1. **root 自動検出**: environment root は `environments/**/providers.tf` を持つディレクトリ、module test root は `modules/**/*.tftest.hcl` を持つディレクトリとして検出する。
2. **動的 matrix**: 検出結果を JSON 配列として `$GITHUB_OUTPUT` に出力し、後続 job が `fromJSON()` で matrix を生成する。
3. **Composite Action**: init / validate（environment のみ）/ test / tflint を `terraform-check` action にまとめ、両 job で共通利用する。
4. **PR CI の安全性**: `terraform init -backend=false` を使い、`terraform_remote_state` などの外部依存は `override_data` でモックする。
5. **job 分離**: スクリプトテスト・フォーマットチェック・root 検出・環境検証・モジュールテスト・セキュリティスキャンを独立した job として実行する。これにより各 job の失敗原因を切り分けやすくなる。
6. **`terraform plan` は対象外**: plan は GCP 認証と backend 接続を伴う別 workflow として、必要になった段階で別 ADR で設計する。

### 再検討条件

- Terraform root 数が増え、全 root CI の実行時間が問題になった場合 → module dependency 解析に基づく差分実行を検討する。
- `terraform plan` を PR または main branch で実行したくなった場合 → GCP 認証・backend 接続・権限境界を含めた別 ADR を作成する。
- 複数 workflow で root 検出処理を再利用するようになった場合 → Python script の Composite Action 昇格を検討する。

## Consequences

### Positive

- **matrix 更新漏れを防げる**: root の追加・削除が自動検出に反映され、YAML の手動更新が不要になる。
- **GitHub Actions YAML が薄くなる**: 複雑な Bash を YAML から排除し、workflow は「何をするか」の記述に集中できる。
- **検証ロジックをコードとして管理できる**: Python script に関数分割・unit test・ローカル実行の環境を整えられる。
- **PR CI が GCP 認証不要**: セットアップが単純で、コードとして壊れていないことを早期に検知できる。

### Negative

- **CI 対象が暗黙的になる**: workflow YAML だけでは具体的な CI 対象一覧が分からない。root 検出スクリプトと `providers.tf` の配置規約をあわせて把握する必要がある。
- **静的検証にとどまる**: validate / test / tflint は構文・型・ルール違反を検出できるが、実際の state との差分・GCP API 権限・リソースの衝突は検出できない。
- **検出規約への依存**: environment root は `providers.tf` を持つこと、module test は `.tftest.hcl` を配置することが規約となる。この規約が守られない場合、CI 対象から漏れる。

### Risks / Future Review

- `providers.tf` を持たない environment root が作られると CI 対象から漏れる。Terraform root には必ず `providers.tf` を置く規約を維持する。
- `terraform test` で新たな `terraform_remote_state` や data source を追加する場合、対応する `override_data` を test ファイルに追加する必要がある。
- Terraform root が増えた場合、広めに CI を実行する設計ゆえ実行時間が増える。その場合は module dependency 解析と差分実行を検討する。

## Next Steps

- `terraform plan` が必要になった場合は、Workload Identity Federation・GCS backend 接続・state lock・権限境界を含めた別 ADR を作成する。

## Related Documents

- [INFRA-ADR-002] Terraform 構成: ドメイン駆動モジュールとマルチプロジェクト戦略の採用
- [INFRA-ADR-005] Terraform environments は GCP project ごとに分割する
