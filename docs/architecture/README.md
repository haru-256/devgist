# Architecture — 現行方針

このディレクトリは、DevGist の **今の設計方針**を領域ごとにまとめた正本です。
実装や変更に着手する前に、対象領域のファイルを読んでください。

## ADR との役割分担

| | 何を持つか | 読むとき |
|---|---|---|
| `docs/architecture/` | **今こうする**。断定形の現行ルールと、その根拠 ADR へのリンク | 実装・変更の直前。「今の前提は何か」を知りたいとき |
| `docs/adr/` | **なぜそうしたか**。判断時点の記録。`Superseded` も削除せず残す | 方針を変えたいとき。過去の却下理由を確認したいとき |

ADR は追記のみで運用します（[ADR 運用ガイド](../adr/README.md)）。
そのため ADR 群だけを読んでも「今どうなっているか」は分かりません。
ADR が部分的に打ち消し合った結果を畳んで断定形にするのが、このディレクトリの役割です。

**根拠を知りたくなったら ADR を読む。今のルールを知りたいだけならここで止まる。**

## 一覧

| ファイル | 扱う範囲 | 畳んである ADR |
|---|---|---|
| [gcp-projects.md](gcp-projects.md) | GCP プロジェクトの分割と責務、環境分離 | INFRA 001, 004 |
| [terraform.md](terraform.md) | root module の切り方、state、cross-project 参照、tfvars、静的 CI | INFRA 002, 005, 006, 011 |
| [iam.md](iam.md) | Service Account 命名、WIF、guest IAM の置き場 | INFRA 007, 008, 009, 013, 014, 015, 016 |
| [cicd.md](cicd.md) | GitHub Actions の plan / apply / image push、Artifact Registry 運用 | INFRA 011, 016, 017, 018, 019, 020, 021 |
| [crawler-runtime.md](crawler-runtime.md) | Cloud Run Job の管理責務と実行粒度、crawler 実装の前提 | INFRA 003, 010, 012 / CRAWLER 001, 002 |

この対応表は棚卸しの出発点です。**新しい ADR を書いたら、この表にも行を足すか、既存の行に番号を追加してください。**
どの行にも現れない ADR があれば、それは畳み忘れです。

## 維持のルール

**ADR を追加・変更したら、同じ PR で対応する `docs/architecture/*.md` を更新する。**
これを守らないと、ここが古くなって ADR 群と同じ問題が再発します。

新しい ADR が既存の方針を部分的にしか置き換えない場合（よくあります）、
ADR 側には「何を捨て、何を維持するか」を書き、
ここには**畳んだ結果だけ**を書いてください。経緯はここに書きません。

定期的な棚卸しの手順は [`.agents/skills/adr-workflow/SKILL.md`](../../.agents/skills/adr-workflow/SKILL.md) の
「Architecture Doc の棚卸し」にあります。

## 前提

- 稼働している環境は **dev のみ**です。prod は器（命名規則と `ci_scope` の条件）だけ用意してあります
- 記述は 2026-09-02 時点の INFRA-ADR-001〜021 / CRAWLER-ADR-001〜002 を畳んだものです
