# APIs

マイクロサービス間やフロントエンドとの通信に使用するAPIスキーマ定義を管理するディレクトリです。

## 役割

- **スキーマの唯一の信頼源 (Single Source of Truth)** として機能します。
- Protocol Buffers (gRPC) や OpenAPI (Swagger) の定義ファイルを配置します。
- ここで定義されたスキーマから、各言語（Go, TypeScriptなど）のクライアント/サーバーコードを自動生成します。
