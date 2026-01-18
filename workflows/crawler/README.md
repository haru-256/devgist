# Crawler

外部サイトからテックブログや論文などを収集するクローラー。

- 以下のトップカンファレンスのpaperのタイトルとpdfのリンク、Abstractを収集する
  - RecSys
  - KDD
  - WSDM
  - WWWW
  - SIGIR
  - CIKM

以下の段階を踏む

1. https://dblp.org から各カンファレンスにアクセプトされた論文のタイトルを収集する
1. 論文タイトルをarxivで検索をかけ、Abstractを収集する。dl.acm.orgはbotアクセスできないようになっている可能性があるため、このような方法を取る
