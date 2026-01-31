# NIHU Researcher Tools

人間文化研究機構（NIHU）の研究者データ管理ツール群。researchmap と連携し、研究者情報の検索・閲覧、および機構 IR 様式の Excel 出力に対応します。

## アプリケーション構成

本リポジトリには 2 つのアプリケーションが含まれています。

| アプリ | 説明 | ポート |
|--------|------|--------|
| **app-a** | 研究者検索システム（全文検索対応） | 8000 |
| **app-c** | researchmap → Excel 変換 Web アプリ | 8001 |

## プロジェクト構成

```
researcher-search/
├── app-a/                     # 研究者検索システム
│   ├── main.py               # FastAPI メインアプリ
│   ├── database.py           # データベース処理
│   ├── models.py             # Pydantic モデル
│   ├── routers/              # API ルーター
│   ├── templates/            # HTML テンプレート
│   ├── download_data.py      # researchmap データ取得（共有）
│   └── setup_db.py           # DB セットアップ
│
├── app-c/                     # Excel 変換 Web アプリ
│   ├── main.py               # FastAPI メインアプリ
│   ├── common.py             # 共通ユーティリティ
│   ├── researchmap_json_to_csv_*.py  # JSON→CSV 変換（7種）
│   ├── csv_to_excel.py       # CSV→Excel 変換
│   ├── run_all.sh            # バッチ処理スクリプト
│   └── templates/            # HTML テンプレート
│
├── data/                      # データディレクトリ
│   ├── researchmap_endpoint_labels.csv  # API エンドポイント定義
│   ├── lang.csv              # 言語コード変換
│   ├── json/                 # 研究者 JSON データ（※gitignore）
│   ├── csv/                  # 生成 CSV（※gitignore）
│   └── xlsx/                 # 生成 Excel（※gitignore）
│
├── static/                    # 共通静的ファイル
│   ├── css/
│   └── js/
│
└── requirements.txt           # Python 依存関係
```

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
cd app-c && pip install -r requirements.txt
```

### 2. データの準備

#### 2.1 研究者リスト CSV の配置

`data/` ディレクトリに研究者リストの CSV ファイルを配置してください（gitignore 対象）。

#### 2.2 researchmap からデータをダウンロード

```bash
# 初回または全件ダウンロード
python app-a/download_data.py --csv data/your-researchers.csv

# 差分ダウンロード（既存研究者をスキップ）
python app-a/download_data.py --csv data/your-researchers.csv --incremental

# ID ファイルで絞り込み
python app-a/download_data.py --ids-file data/test_ids.txt --incremental
```

#### 2.3 データベースのセットアップ（app-a 用）

```bash
python app-a/setup_db.py
```

## アプリケーションの起動

### app-a: 研究者検索システム

```bash
uvicorn app-a.main:app --reload --port 8000
```

http://localhost:8000 にアクセス

### app-c: Excel 変換 Web アプリ

```bash
cd app-c
uvicorn main:app --reload --port 8001
```

http://localhost:8001 にアクセス

## 共有コンポーネント

### download_data.py

`app-a/download_data.py` は両アプリで共有されています。

- **app-a**: バッチダウンロード用として直接実行
- **app-c**: `fetch_researcher_data()` 関数を import して使用

```
app-a/download_data.py   ← 正本
    ↓ import
app-c/main.py            ← Web API から呼び出し
```

### データファイル

| ファイル | 用途 | 編集 |
|----------|------|------|
| `data/researchmap_endpoint_labels.csv` | API エンドポイント定義 | 可 |
| `data/lang.csv` | 言語コード変換（jpn→日本語） | 可 |

## app-a: 研究者検索システム

### 機能

- 全文検索（FTS5、trigram トークナイザーで日本語対応）
- 機関別・イニシャル別フィルタリング
- researchmap データの閲覧

### API エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/researchers` | 研究者検索 |
| GET | `/api/researchers/{id}` | 研究者詳細 |
| GET | `/api/organizations` | 機関一覧 |

### データベーススキーマ

**researchers テーブル**: 研究者基本情報
**researchers_fts テーブル**: FTS5 仮想テーブル（20+ フィールド検索対象）

## app-c: Excel 変換 Web アプリ

### 機能

- researchmap ID から JSON をリアルタイム取得
- 7 種類の業績カテゴリを CSV/Excel に変換
  - 論文、分担執筆、単著、共著編著、口頭発表、MISC、その他

### API エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/` | メインページ |
| GET | `/api/allowed-ids` | 許可 ID 一覧 |
| POST | `/api/convert` | 変換実行 |
| GET | `/api/download/{work_id}/{filename}` | ファイルダウンロード |

### バッチ処理

```bash
cd app-c

# CSV/Excel 変換のみ
./run_all.sh

# ダウンロード + 変換
./run_all.sh --download
```

## 注意事項

### researchmap API

- レート制限: 同時 3 接続、研究者ごと 0.5 秒スリープ
- researchmap の利用規約を確認してください

### セキュリティ

- 個人データを含むファイルは gitignore 対象です
- 本番環境では CORS 設定を適切に制限してください
- 認証機能は未実装です

## ライセンス

このプロジェクトは人間文化研究機構のために作成されました。
