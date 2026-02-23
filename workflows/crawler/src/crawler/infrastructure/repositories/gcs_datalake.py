import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from google.cloud import storage
from loguru import logger

from crawler.domain.models.paper import Paper


class GCSDatalake:
    def __init__(
        self,
        storage_client: storage.Client,
        bucket_name: str,
        prefix_path: str = "papers",
        batch_size: int = 100,
    ) -> None:
        # GCSクライアントの初期化
        self.storage_client = storage_client
        self.bucket = self.storage_client.bucket(bucket_name)
        self.prefix_path = prefix_path
        self.batch_size = batch_size

    async def save_papers(
        self, papers: list[Paper], semaphore: asyncio.Semaphore, papers_rep_name: str
    ) -> list["SaveResult"]:
        """論文データをGCSに保存します。"""

        tasks = []
        async with asyncio.TaskGroup() as tg:
            for i in range(0, len(papers), self.batch_size):
                batch = papers[i : i + self.batch_size]
                data = "\n".join(
                    paper.model_dump_json(ensure_ascii=False, indent=4) for paper in batch
                )
                now = datetime.now(tz=timezone.utc)
                timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
                uuid_suffix = uuid.uuid4().hex[:8]  # UUIDの先頭8文字を使用
                fname = f"{papers_rep_name}_{timestamp}_{uuid_suffix}.jsonl"
                tasks.append(
                    tg.create_task(
                        self._save_content(
                            self.bucket.blob(f"{self.prefix_path}/{fname}"), data, semaphore
                        )
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

    async def _save_content(
        self, blob: storage.Blob, content: str, semaphore: asyncio.Semaphore
    ) -> "SaveResult":
        """バッチデータをGCSに保存します。

        Args:
            blob: 保存先のGCS Blobオブジェクト
            content: 保存するデータ（JSONL形式の文字列）
            semaphore: 並列実行数を制限するセマフォ
        """
        try:
            async with semaphore:
                await asyncio.to_thread(
                    blob.upload_from_string, content, content_type="application/x-ndjson"
                )
            return SaveResult(success=True, blob_name=blob.name)
        except Exception as e:
            logger.error(f"Failed to save content to GCS: {e}, blob: {blob.name}")
            return SaveResult(success=False, blob_name=blob.name, error_message=str(e))


@dataclass(frozen=True)
class SaveResult:
    success: bool
    blob_name: str | None = None
    error_message: str | None = None
