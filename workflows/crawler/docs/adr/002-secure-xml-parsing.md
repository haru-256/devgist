# ADR-002: XMLパースにdefusedxmlを採用

## Status (ステータス)

Accepted (承認済み) - 2026-01-24

## Context (背景・課題)

### 課題

arXiv APIからのレスポンスはXML形式であるが、標準ライブラリの `xml.etree.ElementTree` は、**Billion Laughs攻撃**（エンティティ展開によるDoS攻撃）や **Quadratic Blowup攻撃** などの悪意あるXMLデータに対して脆弱である。

信頼できる `arxiv.org` からのデータであっても、中間者攻撃のリスクや、将来的に他のXMLソースを追加する可能性を考慮すると、アンセキュアなパーサーを使用し続けることは潜在的な脆弱性となる。

### 制約

1. **標準ライブラリ互換性**: 既存の実装を大きく変更せずに導入できることが望ましい
2. **パフォーマンス**: クロール処理に大きなオーバーヘッドを与えないこと

## Decision (決定事項)

**XMLデータのパースには、標準ライブラリの脆弱性を修正した `defusedxml` ライブラリを使用する。**

具体的には、`xml.etree.ElementTree` の代わりに `defusedxml.ElementTree` をインポートして使用する。

```python
# Before
import xml.etree.ElementTree as ET

# After
import defusedxml.ElementTree as ET
```

## Consequences (結果・影響)

### Positive (メリット)

1. **セキュリティ向上**: Billion Laughs攻撃、Quadratic Blowup攻撃などのXML脆弱性からアプリケーションを保護できる。
2. **容易な移行**: APIが標準ライブラリと互換性があるため、インポート文の変更のみで対応可能。

### Negative (デメリット)

1. **依存関係の増加**: 新たに `defusedxml` パッケージへの依存が発生する。
    - ただし、軽量なピュアPythonライブラリであり、リスクは低い。

## 参照

- [Python公式ドキュメント: xml.etree.ElementTreeの脆弱性](https://docs.python.org/3/library/xml.etree.elementtree.html#xml-vulnerabilities)
- [defusedxml PyPI](https://pypi.org/project/defusedxml/)
