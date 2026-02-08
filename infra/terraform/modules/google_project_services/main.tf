# 必要なAPIをすべて有効化するリソース
resource "google_project_service" "api_services" {
  # リストをセットに変換して for_each でループ
  for_each = toset(var.required_services)

  project = var.project_id
  service = each.value

  # terraform destroy 時にサービスを無効化しない
  disable_on_destroy = false
}

// APIが有効化された後、伝播するまで待機するリソース
resource "time_sleep" "wait_for_api_propagation" {
  for_each        = google_project_service.api_services
  create_duration = "${var.wait_seconds}s"
  triggers = {
    gce_api_id = each.value.id
  }
}
