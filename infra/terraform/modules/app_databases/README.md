# app_databases

`app_databases` は、DevGist アプリケーションが **即座に使用するトランザクション処理用データベース（OLTP）** を管理する専用モジュールです。  
Cloud SQL（PostgreSQL + pgvector）と Redis を作成し、アプリケーション層からの接続を想定した設定を提供します。

## このモジュールが格納・管理するもの（責務）

このモジュールは、**アプリケーション用の OLTP データベース基盤のみ** を管理します。

- **Cloud SQL（PostgreSQL）**
  - pgvector 拡張（ベクトル埋め込み対応）
  - Public IP + IAM Auth Proxy による接続
  - 自動バックアップ・ポイント・イン・タイム・リカバリ（PITR）設定

- **Redis（Cloud Memorystore）**
  - セッション管理・キャッシング用
  - Private IP 接続（VPC 内から）

- **Secret Manager**
  - DB 認証情報（パスワード）の安全な保管

> 分析用 DB（BigQuery）や大規模ストレージ（GCS）は作成しません。  
> それらは `data_platform` モジュールの責務です。

## 何を作るモジュールか（What it creates）

このモジュールが作成するリソース:

- `google_sql_database_instance`  
  Cloud SQL インスタンス（PostgreSQL 15）

- `google_sql_database`  
  Cloud SQL 内のデータベース

- `google_sql_user`  
  Cloud SQL のユーザー（認証用）

- `google_redis_instance`  
  Cloud Memorystore for Redis インスタンス

- `google_secret_manager_secret` / `google_secret_manager_secret_version`  
  DB パスワード、Redis 接続文字列などの機密情報

- `google_sql_ssl_cert`  
  SSL/TLS 証明書（接続暗号化用）

## 想定される使用シーン（Usage Pattern）

### App Project での DB 構築

```hcl
# envs/dev/app/main.tf

module "app_databases" {
  source = "../../../modules/app_databases"

  project_id = var.gcp_project_id  # haru256-devgist-app-dev
  region     = var.region

  # Cloud SQL 設定
  database_instance_name = "devgist-postgres-dev"
  database_version       = "POSTGRES_15"
  database_tier          = "db-f1-micro"  # 開発環境用
  
  # Database & User
  databases = [
    {
      name = "devgist"
    }
  ]

  users = [
    {
      name     = "devgist_user"
      password = random_password.db_password.result
    }
  ]

  # pgvector 拡張を有効化
  database_flags = [
    {
      name  = "cloudsql_iam_authentication"
      value = "on"
    }
  ]

  # バックアップ設定
  backup_configuration = {
    enabled                        = true
    start_time                     = "02:00"
    binary_log_enabled             = true
    transaction_log_retention_days = 7
    location                       = "us"
  }

  # Redis 設定
  redis_instance_name = "devgist-redis-dev"
  redis_tier          = "basic"
  redis_size_gb       = 1
  redis_region        = var.region

  # Secret Manager への保存
  create_secrets = true
}

output "cloudsql_connection_name" {
  description = "Cloud SQL 接続名（Auth Proxy 用）"
  value       = module.app_databases.cloudsql_connection_name
}

output "cloudsql_private_ip" {
  description = "Cloud SQL のプライベート IP"
  value       = module.app_databases.cloudsql_private_ip
}

output "redis_host" {
  description = "Redis ホスト名"
  value       = module.app_databases.redis_host
}

output "redis_port" {
  description = "Redis ポート"
  value       = module.app_databases.redis_port
}
```

## 接続方式（Connection Strategy）

### Plan A（推奨: Public IP + IAM Auth Proxy）

```
┌─────────────────┐
│  Cloud Run      │
│  (アプリ)       │
└────────┬────────┘
         │
         │ インターネット経由
         │
┌────────▼──────────────────┐
│ Cloud SQL Auth Proxy      │
│ (IAM 認証)                 │
└────────┬───────────────────┘
         │
┌────────▼──────────────────┐
│ Cloud SQL                 │
│ (Public IP)               │
└───────────────────────────┘
```

**特徴:**
- VPC Peering 不要
- セキュリティは IAM 認証で担保
- 構成がシンプル

## 入出力（Inputs / Outputs）

### 想定される Inputs

| 名前 | 説明 | 型 | 必須 |
|------|------|------|------|
| `project_id` | リソースを作成する GCP Project ID | `string` | ○ |
| `region` | リージョン | `string` | ○ |
| `database_instance_name` | Cloud SQL インスタンス名 | `string` | ○ |
| `database_version` | PostgreSQL バージョン | `string` | ○ |
| `database_tier` | マシンタイプ（`db-f1-micro` など） | `string` | ○ |
| `databases` | 作成するデータベース定義リスト | `list(object(...))` | ○ |
| `users` | 作成するユーザー定義リスト | `list(object(...))` | ○ |
| `database_flags` | PostgreSQL フラグ | `list(object(...))` | ✗ |
| `backup_configuration` | バックアップ設定 | `object(...)` | ✗ |
| `redis_instance_name` | Redis インスタンス名 | `string` | ○ |
| `redis_tier` | Redis ティア（`basic` / `standard`） | `string` | ○ |
| `redis_size_gb` | Redis メモリサイズ | `number` | ○ |
| `create_secrets` | Secret Manager に認証情報を保存するか | `bool` | ✗ |

### 想定される Outputs

| 名前 | 説明 |
|------|------|
| `cloudsql_instance_name` | Cloud SQL インスタンス名 |
| `cloudsql_connection_name` | Cloud SQL 接続名（`project:region:instance` 形式） |
| `cloudsql_private_ip` | Cloud SQL のプライベート IP |
| `cloudsql_public_ip` | Cloud SQL のパブリック IP |
| `cloudsql_database_names` | 作成されたデータベース名のリスト |
| `redis_host` | Redis ホスト名 |
| `redis_port` | Redis ポート（通常 6379） |
| `redis_connection_string` | Redis 接続文字列 |

## セキュリティ設定（Security Configuration）

### Cloud SQL のセキュリティ

- **IAM 認証**: `cloudsql_iam_authentication = on`
  - Service Account 認証が可能
  - パスワード認証より安全

- **SSL/TLS**: 接続の暗号化
  - `require_ssl = true` 推奨

- **バックアップ**: 自動化と保持期間設定
  - 日次バックアップ + PITR

- **IP ホワイトリスト**: Cloud Run から App VPC のリソースのみ許可

### Redis のセキュリティ

- **AUTH**: Redis パスワード認証
  - Secret Manager で管理

- **Private IP Only**: インターネット経由アクセス禁止

- **ネットワーク分離**: VPC 内 Cloud Run のみ接続可能

## 運用上のポイント

### Cloud SQL

- インスタンス削除時にバックアップを自動作成
- バージョンアップは事前検証が必須
- ストレージ自動スケーリング設定を推奨
- リードレプリカは将来の高可用性構成で検討

### Redis

- 再起動時はインメモリデータ全消失
- セッションデータのみ保存（永続化は不要）
- メモリ使用率監視を有効化

## 関連モジュールとの依存関係

```
network_base（このモジュールが依存）
    ↑
    │
app_databases（このモジュール）
    ↑ 被依存
    │
    ├─ backend_api（このモジュールの出力を参照）
    └─ collector（Redis へアクセス）
```

`app_databases` が作成する接続情報（Connection Name、IP、ポート）は、後続の `backend_api` / `collector` モジュールで参照されます。

## 初期化スクリプト例（Database Schema）

```sql
-- devgist データベースの初期化
CREATE EXTENSION IF NOT EXISTS pgvector;

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS embeddings (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  content TEXT,
  embedding vector(1536),  -- OpenAI embedding 次元数
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 環境別設定例

### 開発環境（dev）

```hcl
database_tier = "db-f1-micro"
redis_size_gb = 1
backup_configuration = {
  enabled    = true
  start_time = "02:00"
}
```

### 本番環境（prod）

```hcl
database_tier = "db-n1-standard-2"  # または以上
redis_size_gb = 5  # または以上
backup_configuration = {
  enabled                        = true
  start_time                     = "02:00"
  binary_log_enabled             = true
  transaction_log_retention_days = 30
}
```

## 参考リンク

- [Cloud SQL - PostgreSQL](https://cloud.google.com/sql/docs/postgres)
- [pgvector 拡張](https://cloud.google.com/sql/docs/postgres/pgvector-intro)
- [Cloud Memorystore for Redis](https://cloud.google.com/memorystore/docs/redis)
- [Cloud SQL Auth Proxy](https://cloud.google.com/sql/docs/postgres/sql-proxy)