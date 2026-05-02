# INFRA-ADR-XXX Terraform monorepo における CI 対象検出と検証方針

## Conclusion (結論)

Terraform monorepo の CI では、Terraform root を自動検出し、検出結果を GitHub Actions の matrix に渡して `terraform validate`, `terraform test`, `tflint` を実行する。

Terraform root の検出ロジックは GitHub Actions の YAML に複雑な Bash として直書きせず、`.github/scripts/find_terraform_roots.py` に Python script として切り出す。

CI では `terraform init -backend=false` を使用し、PR CI では remote state backend へ接続せずに静的検証・mock ベースのテストを行う。実際の `terraform plan` は、必要になった段階で認証・backend 接続を伴う別 workflow として設計する。

## Status (ステータス)

Accepted (承認済み) - 2026-05-02

## Context (背景・課題)

### 背景

DevGist は、論文・技術ブログ・キャリア情報を収集・構造化し、検索と推薦を提供する MLE/FDE 向けのインテリジェンス・プラットフォームである。

このプロダクトでは、データ収集、構造化、RAG、推薦、UI など複数のレイヤーを段階的に実装する。そのため、GCP project、environment、reusable module を Terraform monorepo 内で管理する。

Terraform ディレクトリは、概ね以下の2種類に分かれる。

1. `infra/terraform/environments/**`

   * 実際の GCP environment を表す Terraform root
   * 例: app, data, ops, tfstate 管理用 project
2. `infra/terraform/modules/**`

   * reusable module
   * 例: Artifact Registry, service accounts, data platform, tfstate bucket

Terraform CI では、これらに対して以下を実行したい。

* `terraform validate`
* `terraform test`
* `tflint`

ただし、environment と module はディレクトリの深さが異なる。また、module が更新された場合、その module を利用する environment 側の壊れも検出したい。

### 要件と制約

1. **保守性**

   * Terraform root が増えたときに GitHub Actions の matrix 更新漏れを防ぎたい。
   * CI 対象の検出ロジックはレビューしやすくしたい。

2. **可読性**

   * GitHub Actions YAML に長い Bash pipeline を直書きし続けると、意図が読み取りにくくなる。
   * `find`, `sed`, `while`, `python3 -c` が混在すると、CI の失敗調査コストが上がる。

3. **過剰な汎用化の回避**

   * module と environment の依存関係を完全に解析する仕組みは、現時点では複雑さに見合わない。
   * 初期段階では、Terraform 関連ファイルが変わったら広めに検査する方針を優先する。

4. **PR CI の安全性**

   * PR CI では GCS backend や本物の tfstate に接続しない。
   * GCP 認証や state lock に依存せず、コードとして壊れていないことを早期検知する。

5. **将来拡張**

   * `terraform plan` を追加する余地は残す。
   * ただし、`plan` は backend 接続・GCP 認証・権限設計が必要なため、validate/test/lint とは分離する。

### 比較した選択肢

| 選択肢                               | 向いている用途                   | メリット                                | デメリット                                    | 今回の評価 |
| --------------------------------- | ------------------------- | ----------------------------------- | ---------------------------------------- | ----- |
| 手書き matrix                        | root 数が少なく、変更頻度も低い場合      | 最も単純で読みやすい                          | root 追加時の更新漏れが起きる                        | 却下    |
| 手書き matrix + 漏れ検知                 | 明示性と安全性を両立したい場合           | CI 対象が明示的で、更新漏れも検知できる               | 定義ファイルと検出ロジックが必要                         | 将来候補  |
| Bash で root 自動検出                  | 小規模な自動検出                  | すぐ実装できる                             | script が長くなると可読性が急速に落ちる                  | 却下    |
| `actions/github-script` inline JS | GitHub API を使う処理          | GitHub context や Octokit と相性がよい     | 今回は GitHub API 不要。YAML 内 script が長い問題も残る | 却下    |
| repo 内 Node.js script             | JS/TS 中心 repo の補助script   | JSON処理やGitHub連携が得意                  | 再帰探索が標準APIだけだとやや冗長。今回の処理にはやや過剰           | 却下    |
| repo 内 Python script              | path 操作・JSON生成・CI補助処理     | `pathlib` と標準 `json` で簡潔。ローカル実行しやすい | GitHub API 連携には Node より不向き               | 採用    |
| Composite Action                  | 複数 workflow で同じ処理を再利用する場合 | 再利用性が高い                             | 現時点では抽象化が早い                              | 却下    |

### 選定観点

* Terraform root 追加時の CI 漏れを防ぐ
* GitHub Actions YAML を薄く保つ
* ローカルでも検出ロジックを実行できる
* 初期段階では依存解析を避ける
* `validate/test/lint` と `plan/apply` の責務を分離する
* DevGist の既存技術文脈と整合させる

## Considered Options

### Option A: 手書き matrix [却下]

GitHub Actions の `strategy.matrix.root` に Terraform root を手書きで列挙する方式。

```yaml
strategy:
  matrix:
    root:
      - infra/terraform/environments/devgist-app/dev
      - infra/terraform/environments/devgist-data/dev
      - infra/terraform/modules/service_accounts
```

採用しない理由:

* 初期実装としては最も単純。
* ただし、Terraform root が追加されたときに matrix の更新漏れが起きやすい。
* module が増えるたびに GitHub Actions YAML を編集する必要がある。
* DevGist は今後 infra component が増える見込みがあるため、長期的には保守性が弱い。

### Option B: module と environment の依存関係を解析して差分実行する [却下]

変更された module を検出し、その module を参照している environment だけを CI 対象にする方式。

採用しない理由:

* 理論上は効率がよい。

* しかし、以下の処理が必要になる。

  * `module.source` の解析
  * 相対パスの解決
  * module から module への依存の再帰的解決
  * rename / move への対応
  * 差分ファイルから影響範囲を計算する仕組み

* 現時点の DevGist 規模では、CI 実行時間の削減よりも実装・運用の複雑さの方が大きい。

* 初期段階では、Terraform 関連変更時に広めに CI を回す方が安全である。

### Option C: Bash script を GitHub Actions YAML に直書きする [却下]

`find`, `sed`, `sort`, `python3 -c` などを組み合わせて、Terraform root を検出する方式。

```bash
find infra/terraform/environments -maxdepth 5 -name providers.tf -print |
sed 's#/providers.tf$##' |
sort |
python3 -c 'import json, sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))'
```

採用しない理由:

* 短い間は問題ない。
* しかし、environment root と module test root の両方を検出し、count も出力する段階で script が複雑化した。
* YAML 内に長い Bash を書くと syntax highlight や lint が弱く、レビューしにくい。
* ローカルで同じ処理を実行・テストしにくい。
* 今回のように JSON 処理を含む場合、Bash より通常の script 言語に寄せる方がよい。

### Option D: `actions/github-script@v7` で JavaScript 化する [却下]

`actions/github-script` を使い、GitHub Actions 内で JavaScript を実行する方式。

採用しない理由:

* JavaScript として syntax highlight が効きやすくなる。
* GitHub API や PR コメント、label 操作、check annotation などを扱う場合には有効。
* しかし、今回の処理は GitHub API を使わない。
* ファイルシステム走査と JSON 生成だけであれば、`github-script` を使う必然性が低い。
* inline script にすると、YAML 内 script が長い問題は残る。
* 外部 JS ファイル化するなら、`actions/github-script` ではなく通常の `node` 実行で十分である。

### Option E: repo 内 Node.js script に切り出す [却下]

`.github/scripts/find-terraform-roots.mjs` のような Node.js script を作り、workflow から `node` で実行する方式。

採用しない理由:

* Node.js でも実装可能。
* JSON 生成や GitHub Actions output 書き込みも問題ない。
* ただし、標準 library だけで再帰探索を書くと Python よりやや冗長になりやすい。
* `glob` などを使うと依存が増える。
* 今回の処理は GitHub API 連携ではなく path 操作が中心であるため、Python の方が自然である。

### Option F: repo 内 Python script に切り出す [採用]

`.github/scripts/find_terraform_roots.py` を作り、workflow から `python` で実行する方式。

採用理由:

* `pathlib` により path 操作を読みやすく書ける。
* `json` 標準 library だけで matrix 用 JSON を生成できる。
* 外部依存が不要。
* ローカル実行しやすい。
* 将来、必要になれば `pytest` で検出ロジックを unit test 化できる。
* DevGist はデータ収集・構造化・RAG・推薦など Python と親和性の高い処理を含むため、repo の技術文脈とも整合する。

### Option G: Composite Action 化する [却下]

`.github/actions/find-terraform-roots/action.yml` のように Composite Action として切り出す方式。

採用しない理由:

* 複数 workflow から同じ root 検出処理を再利用する段階では有効。
* しかし、現時点では Terraform CI 内の一処理であり、Composite Action にするほどではない。
* まずは script 化し、`terraform-plan.yml`, `terraform-docs.yml`, `security-scan.yml` など複数 workflow で再利用する必要が出たら再検討する。

## Decision (決定事項)

Terraform CI では、Terraform root の検出ロジックを `.github/scripts/find_terraform_roots.py` に Python script として切り出し、GitHub Actions ではその出力を `fromJSON` で matrix に渡して各 root に対して検証を実行する。

### 採用方針

1. Terraform root は CI 内で自動検出する。
2. environment root は `infra/terraform/environments/**/providers.tf` を持つディレクトリとして検出する。
3. module test root は `infra/terraform/modules/**.tftest.hcl` を持つディレクトリから検出する。
4. `.terraform` ディレクトリ配下は検出対象から除外する。
5. `tests/*.tftest.hcl` にある場合は、`tests` の親ディレクトリを Terraform root とみなす。
6. 検出結果は JSON 配列として GitHub Actions output に出力する。
7. 後続 job は `fromJSON(needs.find_terraform_roots.outputs.<name>)` により matrix を生成する。
8. PR CI では `terraform init -backend=false` を使い、remote backend へ接続しない。
9. `terraform plan` はこの ADR の対象外とし、必要になった段階で別 workflow として設計する。

### 初期構成

```text
.github/
  workflows/
    terraform-ci.yml
  scripts/
    find_terraform_roots.py
```

`find_terraform_roots.py` は以下の output を出す。

```text
environment_roots
environment_roots_count
module_test_roots
module_test_roots_count
```

GitHub Actions 側では以下のように job output として公開する。

```yaml
jobs:
  find_terraform_roots:
    runs-on: ubuntu-latest
    outputs:
      environment_roots: ${{ steps.find-roots.outputs.environment_roots }}
      environment_roots_count: ${{ steps.find-roots.outputs.environment_roots_count }}
      module_test_roots: ${{ steps.find-roots.outputs.module_test_roots }}
      module_test_roots_count: ${{ steps.find-roots.outputs.module_test_roots_count }}

    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version: "3.13"

      - name: Find Terraform roots
        id: find-roots
        run: python .github/scripts/find_terraform_roots.py --terraform-dir infra/terraform
```

environment root 用の CI job では以下のように matrix を生成する。

```yaml
strategy:
  fail-fast: false
  matrix:
    root: ${{ fromJSON(needs.find_terraform_roots.outputs.environment_roots) }}
```

module test root 用の CI job では以下のように matrix を生成する。

```yaml
strategy:
  fail-fast: false
  matrix:
    root: ${{ fromJSON(needs.find_terraform_roots.outputs.module_test_roots) }}
```

各 root では以下を実行する。

```bash
terraform init -backend=false -input=false
terraform validate -no-color
terraform test -no-color
tflint --config "$GITHUB_WORKSPACE/.tflint.hcl" -f compact
```

`tflint` の config は repo root の `.tflint.hcl` を基本とする。`terraform-linters/setup-tflint` の `tflint_config_path` は cache key 用であり、実行時に使う config は `tflint --config` で明示する。

### 再検討条件

以下の条件を満たした場合は、設計を見直す。

1. Terraform root 数が増え、全 root CI の実行時間が明確に問題になった場合

   * module と environment の依存関係に基づく差分実行を検討する。

2. `terraform plan` を PR または main branch で実行したくなった場合

   * GCP 認証、GCS backend 接続、state lock、権限境界を含めた別 ADR を作成する。

3. 複数 workflow で Terraform root 検出を再利用するようになった場合

   * Python script を Composite Action に昇格する。

4. GitHub API を使った PR コメントや check annotation が必要になった場合

   * `actions/github-script` または GitHub CLI / API の利用を再検討する。

## Consequences (結果・影響)

### Positive (メリット)

1. **matrix 更新漏れを防げる**

   Terraform root を自動検出するため、新しい environment や module test root を追加したときに GitHub Actions の matrix を手で更新する必要がない。

2. **GitHub Actions YAML が薄くなる**

   複雑な `find`, `sed`, `while`, `python3 -c` の組み合わせを YAML から追い出せる。workflow は「scriptを実行する」「matrixに渡す」「検証する」という責務に集中できる。

3. **検出ロジックを通常のコードとしてレビューできる**

   Python script になっているため、関数分割、コメント、unit test を追加しやすい。

4. **PR CI が安全になる**

   `terraform init -backend=false` を使うことで、GCS backend や tfstate に接続せずに `validate/test/lint` を実行できる。

5. **DevGist の技術文脈と整合する**

   DevGist はデータ収集・構造化・RAG・推薦など、Python と親和性の高い処理を含む。CI補助scriptをPythonで書くことは、repo内の技術的整合性を保ちやすい。

### Negative (デメリット)

1. **CI対象がやや暗黙的になる**

   手書き matrix と比べると、workflow YAML を見ただけでは具体的な CI 対象一覧が分からない。

2. **検出ルールへの依存が生まれる**

   environment root は `providers.tf` を持つこと、module test root は `.tftest.hcl` を持つこと、という規約に依存する。

3. **全 root 実行によりCI時間が増える可能性がある**

   module 変更時に依存 environment だけを実行するのではなく、広めに検証するため、root 数が増えると実行時間が伸びる。

4. **`terraform plan` 相当の保証はない**

   `init -backend=false`, `validate`, `test`, `tflint` では、実際の state との差分、GCP API 権限、既存 resource との衝突は検出できない。

### Risks / Future Review (将来の課題)

1. **検出漏れリスク**

   `providers.tf` を持たない environment root が作られると、CI対象から漏れる可能性がある。Terraform root には `providers.tf` を置くという規約を明示する。

2. **テスト設計の複雑化**

   `terraform test` で `command = plan` を使う場合、`data.terraform_remote_state` や provider data source は mock / override が必要になる。実cloud resourceに依存するテストは、PR CI では避ける。

3. **plan workflow の追加**

   apply可能性を検証したくなった場合、backend 接続ありの `terraform plan` workflow を別途設計する必要がある。

4. **CI時間の増大**

   Terraform root が増えた場合、差分ベース実行や module dependency 解析を検討する。ただし、その導入はCI時間が実際に問題化してから行う。

## Next Steps

1. `.github/scripts/find_terraform_roots.py` を追加する。
2. `terraform-ci.yml` の root 検出処理を Python script 呼び出しに置き換える。
3. `actions/setup-python` で Python version を明示する。
4. `find_terraform_roots` job の output を整理する。

   * `environment_roots`
   * `environment_roots_count`
   * `module_test_roots`
   * `module_test_roots_count`
5. 後続 job の matrix を `fromJSON(needs.find_terraform_roots.outputs.<output>)` で生成する。
6. 各 Terraform root で以下を実行する。

   * `terraform init -backend=false -input=false`
   * `terraform validate -no-color`
   * `terraform test -no-color`
   * `tflint --config "$GITHUB_WORKSPACE/.tflint.hcl" -f compact`
7. root 検出結果が空の場合は CI を fail させる。
8. 将来必要になったら、Python script に unit test を追加する。

## Related Documents
