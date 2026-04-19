"""Google Cloud Storage への論文データ保存実装。

このモジュールは、処理済みの論文データをバッチ単位で Google Cloud Storage
に非同期で保存する実装を提供します。ファイル名にはタイムスタンプと UUID
を含めることで、同時実行時のファイル名衝突を回避します。
"""

import asyncio
import uuid
from datetime import datetime, timezone

from google.cloud import storage
from loguru import logger

from crawler.domain.models.paper import Paper
from crawler.domain.repositories.repository import SaveResult


class GCSDatalake:
    """Google Cloud Storage への論文データ保存を行うデータレイククラス。

    論文データを指定バッチサイズで分割し、JSONL 形式でエンコードした後、
    Google Cloud Storage に並列アップロードします。各バッチファイルには
    タイムスタンプと UUID サフィックスを含めることで、ファイル名の一意性を保証します。

    Attributes:
        storage_client: GCS との通信に使用する google.cloud.storage.Client。
        bucket: アップロード先の GCS Bucket オブジェクト。
        prefix_path: GCS オブジェクトのディレクトリプレフィックス。
        batch_size: 単一ファイルに含める最大論文数。
    """

    DEFAULT_CONCURRENCY = 5

    def __init__(
        self,
        storage_client: storage.Client,
        bucket_name: str,
        prefix_path: str = "papers",
        batch_size: int = 100,
    ) -> None:
        """GCSDatalake インスタンスを初期化します。

        Args:
            storage_client: GCS との通信に使用する認証済み Storage Client インスタンス。
            bucket_name: 論文データを保存する GCS バケット名。
            prefix_path: GCS オブジェクトキーの共通プレフィックス。
                デフォルトは "papers"。例えば "data/papers" のような階層構造を指定可能。
            batch_size: 1 つの JSONL ファイルに書き込む論文数の上限。
                デフォルトは 100。大きすぎるとメモリ消費が増加。

        Raises:
            google.api_core.exceptions.GoogleAPIError: バケットへのアクセス失敗時に発生する場合があります。
        """
        self.storage_client = storage_client
        self.bucket = self.storage_client.bucket(bucket_name)
        self.prefix_path = prefix_path
        self.batch_size = batch_size
        self.semaphore = asyncio.Semaphore(self.DEFAULT_CONCURRENCY)

    async def save_papers(self, papers: list[Paper], papers_rep_name: str) -> list[SaveResult]:
        """論文データをバッチ分割して GCS に並列保存します。

        入力された論文リストを ``batch_size`` 単位で分割し、各バッチを
        JSONL 形式で独立したファイルに書き込みます。ファイル名にはタイムスタンプと
        UUID を含め、複数実行での名前衝突を回避します。セマフォにより並列アップロード数を制限。

        Args:
            papers: 保存対象の論文オブジェクトのリスト。空リストの場合も正常に処理。
            papers_rep_name: ファイル名のプレフィックスに使用するリポジトリ名。
                例: "recsys", "nips", "arxiv"。ファイル名は
                ``{papers_rep_name}_{timestamp}_{uuid_suffix}.jsonl`` となります。

        Returns:
            各バッチの保存結果を表す SaveResult オブジェクトのリスト。
            リスト長は ``ceil(len(papers) / batch_size)`` に等しい（空の場合は空リスト）。
            各要素は成功/失敗、保存先 Blob 名、エラーメッセージを含みます。
        """
        tasks = []
        async with asyncio.TaskGroup() as tg:
            for i in range(0, len(papers), self.batch_size):
                batch = papers[i : i + self.batch_size]
                data = "\n".join(paper.model_dump_json(ensure_ascii=False) for paper in batch)
                now = datetime.now(tz=timezone.utc)
                timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
                uuid_suffix = uuid.uuid4().hex[:8]  # UUIDの先頭8文字を使用
                fname = f"{papers_rep_name}_{timestamp}_{uuid_suffix}.jsonl"
                tasks.append(
                    tg.create_task(
                        self._save_content(self.bucket.blob(f"{self.prefix_path}/{fname}"), data)
                    )
                )
        results = [task.result() for task in tasks]
        failed_batches = [res for res in results if not res.success]
        if failed_batches:
            logger.error(f"Failed to save {len(failed_batches)} batches to GCS.")
            # エラー処理。リトライ？
        else:
            logger.debug(f"Successfully saved all batches to GCS: {len(results)} batches")
        return results

    async def _save_content(self, blob: storage.Blob, content: str) -> SaveResult:
        """単一バッチのデータを GCS Blob に非同期でアップロードします。

        セマフォを使用して並列制御を行い、指定された文字列コンテンツを
        GCS Blob にアップロードします。アップロードは ``asyncio.to_thread()`` を
        使用してスレッドプールで実行され、他の非同期タスクをブロックしません。

        Args:
            blob: 書き込み先の GCS Blob オブジェクト。ファイル名（Blob 名）は
                既に ``blob.name`` に設定されている必要があります。
            content: 保存する文字列データ。通常は JSONL 形式（改行区切りの JSON）。

        Returns:
            保存結果を表す SaveResult オブジェクト。
            成功時は ``success=True`` および ``blob_name=blob.name`` を含みます。
            失敗時は ``success=False`` および ``error_message`` に例外メッセージを含みます。
            失敗時でも ``blob_name`` が記録されます。
        """
        try:
            async with self.semaphore:
                await asyncio.to_thread(
                    blob.upload_from_string, content, content_type="application/x-ndjson"
                )
            return SaveResult(success=True, blob_name=blob.name)
        except Exception as e:
            logger.error(f"Failed to save content to GCS: {e}, blob: {blob.name}")
            return SaveResult(success=False, blob_name=blob.name, error_message=str(e))
