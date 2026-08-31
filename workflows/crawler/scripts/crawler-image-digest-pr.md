## 概要
crawler-deploy が push した image digest を `crawler_image` に反映する。

## Why
Cloud Run Job は Terraform 管理の digest pin（INFRA-ADR-010 / 019）。この PR を merge すると terraform-apply.yml が Job の image を更新する。

## 関連 Issue
Follow-up to #60 / INFRA-ADR-019。この PR では close しない。

## 変更内容
- `infra/terraform/environments/devgist-app/dev/terraform.tfvars` の `crawler_image` を更新

## 影響範囲
merge 後、terraform-apply が `devgist-app/dev` の Cloud Run Job image を変える。crawler コード自体は変わらない。

## 確認方法
1. この PR で **Approve workflows to run** を押す（GITHUB_TOKEN 作成 PR は承認待ちになる）。
2. Terraform format check / Terraform security scan が通ることを見る。Lint and Test は skip でよい（infra-only）。
3. diff が `crawler_image` 1 行であることを見る。

## レビュー観点
image_ref が crawler-deploy の出力と一致しているか。

## 補足
- image_ref: `{{IMAGE_REF}}`
- source SHA: `{{SOURCE_SHA}}`
- crawler-deploy run: {{RUN_URL}}
