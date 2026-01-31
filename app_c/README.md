# app_c: researchmap → Excel 変換 Web アプリ

researchmap の研究者 ID を入力すると、JSON のダウンロードから Excel 生成までを自動実行し、ダウンロードリンクを表示する Web アプリケーションです。

## セットアップ

```bash
cd app_c
pip install -r requirements.txt
```

## 起動

```bash
# 開発モード（ホットリロード有効）
uvicorn main:app --reload --port 8000

# 本番モード
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 使い方

1. ブラウザで http://localhost:8000/ にアクセス
2. 研究者 ID（researchmap のパーマリンク）を入力
3. 「取得」ボタンをクリック
4. 変換完了後、「Excel をダウンロード」リンクが表示される

**注意**: CSV ファイル（`data/tool-a-1225-converted.csv` または `data/test_ids.txt`）に登録されている ID のみ使用可能です。

## 処理フロー

```
入力: 研究者ID (例: cm3)
  ↓
1. researchmap API から JSON 取得（app_a/download_data.py を使用）
  ↓
2. JSON → CSV 変換（7種類）
   - 論文
   - 分担執筆
   - 単著
   - 共著・編著
   - 口頭発表
   - MISC
   - その他
  ↓
3. CSV → Excel 変換
  ↓
出力: {researcher_id}.xlsx
```

## app_a との関係

本アプリケーションは `app_a/download_data.py` の `fetch_researcher_data()` 関数を再利用しています。

```
app_a/download_data.py   ← 正本（バッチダウンロード用）
    ↓ import
app_c/main.py            ← Web API から呼び出し
```

`download_data.py` は以下の機能を提供します：
- researchmap API から全エンドポイントのデータを非同期取得
- 取得対象エンドポイントは `data/researchmap_endpoint_labels.csv` で定義

## API エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/` | メインページ（HTML） |
| GET | `/api/allowed-ids` | 許可された ID 一覧 |
| POST | `/api/convert` | 変換実行（researcher_id をフォーム送信） |
| GET | `/api/download/{work_id}/{filename}` | 生成ファイルのダウンロード |

## ディレクトリ構成

```
app_c/
├── main.py                              # FastAPI アプリケーション
├── common.py                            # 共通ユーティリティ
├── requirements.txt                     # 依存パッケージ
├── researchmap_json_to_csv_*.py         # JSON→CSV 変換スクリプト（7種）
├── csv_to_excel.py                      # CSV→Excel 変換
├── run_all.sh                           # バッチ処理スクリプト
├── templates/
│   └── index.html                       # フロントエンド HTML
├── static/                              # 静的ファイル
└── work/                                # 一時作業ディレクトリ（自動生成）

../app_a/
└── download_data.py                     # researchmap データ取得（共有）

../data/
├── researchmap_endpoint_labels.csv      # エンドポイント定義
├── lang.csv                             # 言語コード変換
├── test_ids.txt                         # テスト用 ID 一覧
└── json/                                # ダウンロード済み JSON
```

## 注意事項

- `work/` ディレクトリ内のファイルは 24 時間後に自動削除されます
- 大量のリクエストを処理する場合は、非同期処理の最適化が必要です
- `download_data.py` を修正する場合は app_a 側の正本を編集してください
