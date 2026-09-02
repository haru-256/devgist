# GCP プロジェクト構成

## プロジェクトと責務

| project | 種別 | 置くもの | 置かないもの |
|---|---|---|---|
| `haru256-devgist-tf` | 管理 | 全 root の Terraform state bucket | state 以外の常設リソース |
| `haru256-devgist-ops` | 運用基盤（環境非依存） | Artifact Registry、WIF pool / provider、ops が書く guest IAM | 環境固有の compute / data |
| `haru256-devgist-data-dev` | stateful | GCS datalake（将来 Cloud SQL / BigQuery） | consumer の principal（guest IAM） |
| `haru256-devgist-app-dev` | stateless | Cloud Run Job、crawler Service Account（将来 API / frontend） | Terraform state、image store |

根拠: [INFRA-ADR-001](../adr/infra/001-gcp-project-structure.md)（data / app 分離）、
[INFRA-ADR-004](../adr/infra/004-separate-tf-and-ops-projects.md)（tf と ops の分離）

## 環境

- 稼働しているのは **dev のみ**。prod project は未作成
- prod は命名規則（`haru256-devgist-{data,app}-prod`）と CI 側の条件だけ用意してある（[INFRA-ADR-019](../adr/infra/019-github-actions-terraform-plan-apply.md)）
- `ops` と `tf` は環境を持たない。prod と dev で共有する（[INFRA-ADR-016](../adr/infra/016-github-actions-wif-and-crawler-image-push.md)）
- 環境の識別は **project ID** で行う。Service Account 名やリソース名に `dev` / `prod` を含めない（[INFRA-ADR-008](../adr/infra/008-service-account-naming.md)）

## Terraform state bucket

すべて `haru256-devgist-tf` project に置き、`<project-id>-tfstate` で命名する。

```
haru256-devgist-tf
├── haru256-devgist-tf-tfstate
├── haru256-devgist-ops-tfstate
├── haru256-devgist-data-dev-tfstate
├── haru256-devgist-app-dev-tfstate
└── haru256-devgist-github-tfstate   # GitHub リソース用。GCP project は存在しない
```

`haru256-devgist-github` は state の名前空間としてのみ使う。実体の GCP project は無い。

## 判断基準

新しいリソースの置き場に迷ったら、この順で判断する。

1. **Terraform state か** → `tf`
2. **環境をまたいで共有する運用基盤か**（image store、CI の identity） → `ops`
3. **消えたら困るデータか**（bucket、DB、warehouse） → `data-{env}`
4. **消しても作り直せる compute か** → `app-{env}`

`ops` に「共通だから」と何でも集めない。`ops` の責務は配布基盤と CI identity に限る
（[INFRA-ADR-004](../adr/infra/004-separate-tf-and-ops-projects.md) の Risks を参照）。

## 再検討の条件

- チームが分かれ、frontend と backend で app project を割りたくなったとき（[INFRA-ADR-001](../adr/infra/001-gcp-project-structure.md)）
- `ops` の責務が肥大し、配布基盤と CI identity で割りたくなったとき（[INFRA-ADR-004](../adr/infra/004-separate-tf-and-ops-projects.md)）
