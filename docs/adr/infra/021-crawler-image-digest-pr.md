# INFRA-ADR-021 crawler image digest の置換 PR を crawler-deploy が作成する

## Conclusion (結論)

- crawler-deploy が Artifact Registry へ push したあと、`GITHUB_TOKEN` で `crawler_image` digest を書き換える infra PR を作る。Cloud Run の更新は既存の terraform-apply.yml に任せる。
- GitHub App / PAT は使わない。後続 CI は `workflow_dispatch` しない。人が digest PR 上で Approve workflows to run してから merge する。
- ブランチは `ci/crawler-image-digest` に固定し、毎回 `origin/main` から作り直す。自動 merge しない。
- git / gh / tfvars 置換は `workflows/crawler/scripts/open-crawler-image-digest-pr.sh` が行う。workflow は env を渡して呼ぶ。

## Status (ステータス)

Accepted (承認済み) - 2026-08-31

[INFRA-ADR-019](./019-github-actions-terraform-plan-apply.md) が決めた 2 PR 運用のうち、digest PR の自動作成だけを埋める。019 は supersede しない。

## Context (背景・課題)

### 背景

crawler image の更新は「crawler-deploy が main で push → digest を tfvars に書く infra PR → merge で apply」である（019）。PR 作成は人手のままだった。

### 要件と制約

1. 019 の 2 PR と apply 分離を維持する
2. CI に GitHub App PEM / PAT を置かない（019 / 020）
3. crawler-push-dev の AR writer と GitHub write を同じ job に載せない
4. `actions: write` で任意 workflow を dispatch しない
5. build-push と同じく、仕事は `workflows/crawler/scripts/` に置く

### 比較した選択肢

| 選択肢 | 向いている用途 | メリット | デメリット | 今回の評価 |
|---|---|---|---|---|
| Option A: crawler-deploy 末尾 job + `GITHUB_TOKEN` + crawler script。CI は人が Approve | digest PR を自動化し、秘密を増やさない場合 | 新しい credential が無い。build-push と同じ置き場 | 人が Approve workflows する | 採用 |
| Option B: 同じ job から terraform-ci / python-ci を `workflow_dispatch` | required checks を自動で緑にしたい場合 | 承認クリックが減る | `actions: write` が terraform-apply.yml の dispatch まで届く | 非採用 |
| Option C: GitHub App / PAT で PR を作り、`pull_request` CI を自動起動 | 承認なしで checks を走らせたい場合 | 通常の PR と同じ | 019 / 020 が却下した長寿命 GitHub 秘密を戻す | 非採用 |

## Considered Options

### Option A: `GITHUB_TOKEN` で PR を作り、CI は人が承認する [採用]

digest PR はもともと人が merge する。approval-required の workflow run をその人が起こす。実装は `open-crawler-image-digest-pr.sh`。

### Option B: `workflow_dispatch` で required CI を起こす [却下]

`actions: write` の blast radius が digest PR 用 CI より広い。

### Option C: GitHub App / PAT [却下]

019 Option D と同じ理由。

## Decision (決定事項)

crawler-deploy に `create-digest-pr` job を足す。`contents: write` と `pull-requests: write` だけを持つ。`id-token` も `environment` も付けない。実作業は `workflows/crawler/scripts/open-crawler-image-digest-pr.sh`。

### 採用方針

- tfvars の `crawler_image` だけを変える
- 固定ブランチ `ci/crawler-image-digest` を毎回 `origin/main` から作り直す
- auto-merge しない
- issue #60 をこの PR で close しない

### 初期構成

- workflow: `.github/workflows/crawler-deploy.yaml`
- script: `workflows/crawler/scripts/open-crawler-image-digest-pr.sh`
- PR 本文: `workflows/crawler/scripts/crawler-image-digest-pr.md`
- 対象ファイル: `infra/terraform/environments/devgist-app/dev/terraform.tfvars`
- 後続: 人が Approve workflows → merge → terraform-apply.yml

### 再検討条件

- GitHub App を 019 の却下理由を再評価したうえで導入するとき
- digest PR の人間レビューをやめて auto-merge したくなったとき
- crawler-deploy から apply したくなったとき（010 / 019 の変更になる）

## Consequences (結果・影響)

### Positive (メリット)

- image push のあとに digest 更新が忘れにくい
- Cloud Run 更新はレビュー可能な tfvars diff を通る
- crawler-deploy の YAML は build-push と同じ薄さになる

### Negative (デメリット)

- crawler 変更の反映に PR がもう 1 本要る（019 が受け入れ済み）
- digest PR の CI は Approve workflows が必要

### Risks / Future Review (将来の課題)

- ruleset の `require_extra_approval_for_unattributed_changes` が bot commit に承認を足す可能性。初回の実 PR で確認する
- Python PR の required check 名が `Lint and Test (workflows/crawler)` になる既存ずれは本 ADR の対象外

## Next Steps

1. `open-crawler-image-digest-pr.sh` と薄い `create-digest-pr` job を実装する
2. crawler README の手元 apply 手順をこのフローに直す
3. merge 後、最初の crawler-deploy で PR 作成を確認する

## Related Documents

- [[INFRA-ADR-019] GitHub Actions から terraform plan / apply する](./019-github-actions-terraform-plan-apply.md)
- [[INFRA-ADR-016] GitHub Actions から crawler image を Artifact Registry へ push する](./016-github-actions-wif-and-crawler-image-push.md)
- [[INFRA-ADR-020] Terraform CI/CD と Secret Management 方針](./020-terraform-cicd-secret-management.md)
- [Crawler Deploy workflow](../../../.github/workflows/crawler-deploy.yaml)
- [open-crawler-image-digest-pr.sh](../../../workflows/crawler/scripts/open-crawler-image-digest-pr.sh)
- [issue #60](https://github.com/haru-256/devgist/issues/60)
- [Triggering a workflow (GITHUB_TOKEN)](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
