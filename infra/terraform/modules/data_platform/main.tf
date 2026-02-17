# crawlerのデータの一時保存先となるGCSバケット
resource "google_storage_bucket" "datalake" {
  name                        = "${var.gcp_project_id}-datalake"
  project                     = var.gcp_project_id
  location                    = var.datalake_bucket_location
  force_destroy               = false
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true

  # Versioning disabled - raw data is immutable after ingestion
  versioning {
    enabled = false
  }

  # Autoclass for automatic storage class transitions based on access patterns
  # Automatically transitions to NEARLINE (30+ days), COLDLINE (90+ days), ARCHIVE (terminal_storage_class)
  autoclass {
    enabled                = true
    terminal_storage_class = "ARCHIVE"
  }

  lifecycle {
    prevent_destroy = true
  }
}
