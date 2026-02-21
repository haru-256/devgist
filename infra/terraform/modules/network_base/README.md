# network_base

`network_base` は、DevGist インフラの **通信基盤層** を担当する専用モジュールです。  
VPC / Subnet / Firewall / VPC Peering など、ネットワークトポロジーの定義と管理を責務とします。

## このモジュールが格納・管理するもの（責務）

このモジュールは、**ネットワーク通信基盤のみ** を管理します。

- VPC（Virtual Private Cloud）
- Subnet（サブネット）
- Cloud Router
- Cloud NAT
- VPC Peering 設定（他 VPC との接続）
- Firewall ルール

> アプリケーション本体（Cloud Run）やデータベース（Cloud SQL）は作成しません。  
> それらは `app_databases`, `data_platform`, `collector`, `backend_api` など他モジュールの責務です。

## 何を作るモジュールか（What it creates）

このモジュールが作成するリソース:

- `google_compute_network`  
  VPC ネットワーク
- `google_compute_subnetwork`  
  サブネット（複数可能）
- `google_compute_router`  
  Cloud Router（NAT アウトバウンド用）
- `google_compute_router_nat`  
  Cloud NAT（Subnet 内リソースのアウトバウンド IP 統一）
- `google_compute_firewall`  
  Firewall ルール（Ingress/Egress）
- `google_compute_network_peering`  
  VPC Peering（他プロジェクト VPC との接続）

## 想定される使用シーン（Usage Pattern）

### シーン 1: Data Project での VPC 構築

```hcl
# envs/dev/data/main.tf

module "data_network" {
  source = "../../../modules/network_base"

  project_id = var.gcp_project_id
  region     = var.region

  # Data 専用 VPC
  network_name = "data-vpc"
  network_cidr = "10.1.0.0/16"

  # Subnet
  subnets = [
    {
      name          = "data-subnet-1"
      ip_cidr_range = "10.1.1.0/24"
      region        = "us-central1"
    }
  ]

  # Firewall: Cloud SQL への接続を許可
  firewall_rules = [
    {
      name      = "allow-cloud-sql"
      direction = "INGRESS"
      source_ranges = ["10.0.0.0/16"]  # App VPC から接続許可
      allow = [
        { protocol = "tcp", ports = ["3306"] }
      ]
    }
  ]
}

output "data_vpc_id" {
  value = module.data_network.network_id
}

output "data_subnet_id" {
  value = module.data_network.subnet_ids[0]
}
```

### シーン 2: App Project での VPC 構築

```hcl
# envs/dev/app/main.tf

module "app_network" {
  source = "../../../modules/network_base"

  project_id = var.gcp_project_id
  region     = var.region

  # App 専用 VPC
  network_name = "app-vpc"
  network_cidr = "10.0.0.0/16"

  subnets = [
    {
      name          = "app-subnet-1"
      ip_cidr_range = "10.0.1.0/24"
      region        = "us-central1"
    }
  ]

  firewall_rules = [
    {
      name      = "allow-cloud-run"
      direction = "INGRESS"
      source_ranges = ["0.0.0.0/0"]
      allow = [
        { protocol = "tcp", ports = ["80", "443"] }
      ]
    }
  ]
}

output "app_vpc_id" {
  value = module.app_network.network_id
}
```

### シーン 3: VPC Peering の設定

```hcl
# Data VPC と App VPC をピアリング
module "data_app_peering" {
  source = "../../../modules/network_base"

  # ... VPC Peering の設定 ...

  peering_configs = [
    {
      name      = "data-app-peering"
      peer_project = var.app_project_id
      peer_network = "app-vpc"
    }
  ]
}
```

## 入出力（Inputs / Outputs）

### 想定される Inputs

| 名前 | 説明 | 型 | 必須 |
|------|------|------|------|
| `project_id` | リソースを作成する GCP Project ID | `string` | ○ |
| `region` | デフォルトリージョン | `string` | ○ |
| `network_name` | VPC の名前 | `string` | ○ |
| `network_cidr` | VPC の CIDR ブロック | `string` | ○ |
| `subnets` | Subnet の定義リスト | `list(object(...))` | ○ |
| `firewall_rules` | Firewall ルールのリスト | `list(object(...))` | ○ |
| `peering_configs` | VPC Peering の設定リスト | `list(object(...))` | ✗ |

### 想定される Outputs

| 名前 | 説明 |
|------|------|
| `network_id` | 作成された VPC の ID |
| `network_self_link` | VPC の self_link（参照用） |
| `subnet_ids` | 作成された Subnet の ID リスト |
| `router_id` | Cloud Router の ID |
| `nat_ip` | Cloud NAT に割り当てられた外部 IP |

## ネットワーク設計方針（Design Guidelines）

### CIDR 割り当て（Hard Mode 推奨）

- **App VPC**: `10.0.0.0/16`
- **Data VPC**: `10.1.0.0/16`

これにより、将来的に VPC Peering や Cloud Interconnect 導入時に CIDR 重複の問題を回避できます。

### Firewall 設計の基本

- **Default**: すべてのトラフィック拒否
- **明示的許可のみ**: 必要な通信パスだけを許可ルールで開く
- **最小権限の原則**: ソース IP 範囲やプロトコト・ポートを明確に制限

### Cloud NAT の役割

- Subnet 内の GCE / Cloud Run が外部 API へアクセスする際の送信元 IP を固定
- 外部パートナー API がホワイトリスト管理する場合に重要

## 運用上のポイント

- 一度作成した VPC/Subnet を削除すると、他リソース（VM、Cloud SQL）への影響が大きいため注意
- VPC Peering は双方向設定が必要（このモジュール呼び出し時は一方向のみ定義し、相手側でも同様に定義）
- Firewall ルールは `name` でユニークにしておき、後での検索・更新が容易にする

## 関連モジュールとの依存関係

```
network_base（このモジュール）
    ↑ 被依存（以下が依存）
    │
    ├─ app_databases
    ├─ data_platform
    ├─ collector
    └─ backend_api
```

`app_databases` / `data_platform` など他モジュール実装時に、このモジュールの出力（VPC ID、Subnet ID）を参照する必要があります。