# テスト

研究者検索APIのテストスイートです。

## ファイル構成

```
tests/
├── README.md              # このファイル
├── generate_fixtures.py   # フィクスチャ生成スクリプト
├── test_api.py            # pytestテストファイル
└── fixtures/
    └── api_fixtures.json  # 生成されたフィクスチャ
```

## セットアップ

```bash
pip install pytest
```

## テストの実行

### 基本的なテスト実行

```bash
pytest tests/test_api.py -v
```

### 特定のテストクラスのみ実行

```bash
pytest tests/test_api.py::TestSearchResearchers -v
pytest tests/test_api.py::TestFacetCounts -v
pytest tests/test_api.py::TestSnippets -v
```

### 特定のテストのみ実行

```bash
pytest tests/test_api.py::TestSearchResearchers::test_query_gender -v
```

## フィクスチャの生成

データベースの内容が変更された場合、期待値を更新するためにフィクスチャを再生成できます。

```bash
python -m tests.generate_fixtures
```

これにより `tests/fixtures/api_fixtures.json` が生成されます。

## テストケース

ISSUES.md に基づくテストケースです：

| ID | クエリ/条件 | 期待件数 | 説明 |
|----|-------------|----------|------|
| all | なし | 224 | 全件の確認 |
| query_jouhou | 情報 | 143 | 全研究所にいる、ページングの確認 |
| query_gender | ジェンダー | 22 | 全研究所にいる、ページングのない場合 |
| query_indonesia | インドネシア | 22 | 機構本部だけの人間もひっかかるか |
| org_chikyuken | org=地球研 | 22 | 機関の基本クエリ |
| initial_k | initial=K | 31 | イニシャルの基本クエリ |
| gender_initial_a | ジェンダー, initial=A | 1 | 朝日先生のみ、researchmap上の重複データの確認 |
| query_muromachi | 室町 | 12 | 地球研と民博にはいない |
| query_seishichou | 誓詞帳 | 1 | 未知語になりやすい語 |
| query_lawrencium | ローレンシウム | 0 | 0件の確認 |

## テストの追加

新しいテストケースを追加する場合：

1. `generate_fixtures.py` の `TEST_CASES` にケースを追加
2. `test_api.py` に対応するテストメソッドを追加
3. `python -m tests.generate_fixtures` でフィクスチャを更新
