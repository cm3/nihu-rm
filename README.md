# NIHU Researcher Tools

人間文化研究機構（NIHU）の研究者データ管理ツール群。researchmap と連携し、研究者情報の検索・閲覧、および機構 IR 様式の Excel 出力に対応します。

## アプリケーション構成

本リポジトリには 2 つの FastAPI アプリケーションが含まれています。

| アプリ | 説明 | デフォルトポート | サブパス例 |
|--------|------|------------------|------------|
| **app_a** | 研究者検索システム（全文検索対応） | 8000 | `/nihu-rm-a/` |
| **app_c** | researchmap → Excel 変換 Web アプリ | 8001 | `/nihu-rm-c/` |

## プロジェクト構成

```
researcher-search/
├── app_a/                     # 研究者検索システム
│   ├── main.py               # FastAPI メインアプリ
│   ├── database.py           # データベース処理
│   ├── models.py             # Pydantic モデル
│   ├── routers/              # API ルーター
│   ├── templates/            # HTML テンプレート
│   ├── download_data.py      # researchmap データ取得（共有）
│   └── setup_db.py           # DB セットアップ
│
├── app_c/                     # Excel 変換 Web アプリ
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
├── deploy.sh                  # VPS 初回デプロイスクリプト
├── update.sh                  # コード更新スクリプト
└── requirements.txt           # Python 依存関係
```

---

## ローカル開発

### 1. セットアップ

```bash
# リポジトリをクローン
git clone https://github.com/cm3/nihu-rm.git
cd nihu-rm

# 仮想環境を作成
python3 -m venv venv
source venv/bin/activate

# 依存関係をインストール
pip install -r requirements.txt
pip install -r app_c/requirements.txt
```

### 2. データの準備

```bash
# 研究者リスト CSV を data/ に配置（gitignore 対象）
cp /path/to/your-researchers.csv data/

# researchmap からデータをダウンロード
python app_a/download_data.py --csv data/your-researchers.csv --incremental

# データベースをセットアップ（app_a 用）
python app_a/setup_db.py
```

### 3. 起動

```bash
# app_a: 研究者検索（ポート 8000）
uvicorn app_a.main:app --reload --port 8000

# app_c: Excel 変換（ポート 8001）- 別ターミナルで
uvicorn app_c.main:app --reload --port 8001
```

### 4. 動作確認

```bash
# app_a
curl http://localhost:8000/health
curl http://localhost:8000/docs

# app_c
curl http://localhost:8001/api/allowed-ids
curl http://localhost:8001/docs
```

---

## VPS へのデプロイ

nginx のリバースプロキシ配下で、サブパス（`/nihu-rm-a/`, `/nihu-rm-c/`）でアプリを公開します。

### 自動デプロイ（推奨）

`deploy.sh` を使用すると、以下を自動で行います：
- OS パッケージのインストール（nginx, certbot, python3-venv）
- ディレクトリ作成とリポジトリのクローン
- Python 仮想環境と依存関係のセットアップ
- systemd ユーザーサービスの作成・起動
- nginx 設定ファイルの生成（SSL 対応）

```bash
# リポジトリをクローン（一時的な場所）
git clone https://github.com/cm3/nihu-rm.git /tmp/nihu-rm
cd /tmp/nihu-rm

# 環境変数でカスタマイズ可能（デフォルト値あり）
export DOMAIN="your-domain.example.com"  # デフォルト: ik1-421-42635.vs.sakura.ne.jp

# デプロイ実行
bash deploy.sh
```

#### deploy.sh の設定変数

| 変数 | デフォルト値 | 説明 |
|------|-------------|------|
| `DOMAIN` | `ik1-421-42635.vs.sakura.ne.jp` | サーバーのドメイン名 |
| `APP_ROOT` | `/srv/projects/nihu-rm` | アプリケーションルート |
| `DATA_PERSIST_DIR` | `/var/lib/nihu-rm` | 永続データディレクトリ |
| `PREFIX_A` | `/nihu-rm-a` | app_a のサブパス |
| `PREFIX_C` | `/nihu-rm-c` | app_c のサブパス |
| `PORT_A` | `8000` | app_a のポート |
| `PORT_C` | `8001` | app_c のポート |

### コードの更新

GitHub の最新コードに追従するには `update.sh` を使用します：

```bash
cd /srv/projects/nihu-rm/repo
bash update.sh
```

`update.sh` は以下を行います：
- `git pull --ff-only` で最新コードを取得
- pip 依存関係を更新
- systemd サービスを再起動

```bash
# ダーティな作業ツリーを許可する場合
ALLOW_DIRTY=1 bash update.sh
```

### ディレクトリ構成

デプロイ後の構成：

```
/srv/projects/nihu-rm/         # APP_ROOT
├── repo/                      # git リポジトリ
│   ├── app_a/
│   ├── app_c/
│   ├── static/
│   └── data/                  # 実ディレクトリ
│       ├── json -> /var/lib/nihu-rm/json
│       ├── csv -> /var/lib/nihu-rm/csv
│       ├── xlsx -> /var/lib/nihu-rm/xlsx
│       └── researchers.db -> /var/lib/nihu-rm/researchers.db
└── venv/                      # Python 仮想環境

/var/lib/nihu-rm/              # DATA_PERSIST_DIR（永続データ）
├── researchers.db
├── json/
├── csv/
└── xlsx/

~/.config/systemd/user/        # ユーザー systemd サービス
├── nihu-rm-a.service
└── nihu-rm-c.service
```

### データの準備

デプロイ後、研究者データを準備します：

```bash
cd /srv/projects/nihu-rm/repo

# 研究者リスト CSV を配置
cp /path/to/researchers.csv data/

# researchmap からデータをダウンロード
../venv/bin/python app_a/download_data.py --csv data/researchers.csv --incremental

# データベースをセットアップ
../venv/bin/python app_a/setup_db.py
```

### 動作確認

```bash
# ヘルスチェック
curl https://your-domain.example.com/nihu-rm-a/health
curl https://your-domain.example.com/nihu-rm-c/api/allowed-ids

# Swagger UI
curl -I https://your-domain.example.com/nihu-rm-a/docs
curl -I https://your-domain.example.com/nihu-rm-c/docs
```

### サービス管理

```bash
# ステータス確認
systemctl --user status nihu-rm-a nihu-rm-c

# 再起動
systemctl --user restart nihu-rm-a nihu-rm-c

# ログ確認
journalctl --user -u nihu-rm-a -f
journalctl --user -u nihu-rm-c -f
```

### SSL 証明書（Let's Encrypt）

`deploy.sh` は既存の証明書を検出して HTTPS 設定を生成します。
証明書がない場合は HTTP のみで設定され、後から追加できます：

```bash
sudo certbot --nginx -d your-domain.example.com
```

---

## 環境変数

| 変数名 | 説明 | デフォルト |
|--------|------|------------|
| `NIHU_RM_ROOT_PATH` | サブパスプレフィックス（例: `/nihu-rm-a`） | `""` (空文字) |

---

## 共有コンポーネント

### download_data.py

`app_a/download_data.py` は両アプリで共有されています。

- **app_a**: バッチダウンロード用として直接実行
- **app_c**: `fetch_researcher_data()` 関数を import して使用

```
app_a/download_data.py   ← 正本
    ↓ import
app_c/main.py            ← Web API から呼び出し
```

### データファイル

| ファイル | 用途 | 編集 |
|----------|------|------|
| `data/researchmap_endpoint_labels.csv` | API エンドポイント定義 | 可 |
| `data/lang.csv` | 言語コード変換（jpn→日本語） | 可 |

### ローカルファイル（.gitignore 対象）

以下のファイルは .gitignore 対象のため、ローカル環境で用意する必要があります。

| ファイル | 生成スクリプト | 使用スクリプト | 説明 |
|----------|----------------|----------------|------|
| `data/cors.txt` | - | `app_a/main.py` | CORS 許可オリジン |
| `data/researchers.db` | `app_a/setup_db.py` | `app_a/database.py` | SQLite データベース |
| `data/json/` | `app_a/download_data.py` | `app_a/setup_db.py` | 研究者 JSON データ |
| `data/csv/` | `app_c/main.py` | `app_c/csv_to_excel.py` | CSV 出力 |
| `data/xlsx/` | `app_c/csv_to_excel.py` | - | Excel 出力 |
| `data/test_ids.txt` | - | `app_a/download_data.py` | app_c テスト用 ID 一覧 |
| `app_c/work/` | `app_c/main.py` | `app_c/main.py` | 作業ディレクトリ |

生成スクリプトが「-」のものは外部から与える必要があります。

---

## API エンドポイント

### app_a: 研究者検索

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/` | トップページ |
| GET | `/health` | ヘルスチェック |
| GET | `/docs` | Swagger UI |
| GET | `/openapi.json` | OpenAPI スキーマ |
| GET | `/api/researchers` | 研究者検索 |
| GET | `/api/researchers/{id}` | 研究者詳細 |
| GET | `/api/organizations` | 機関一覧 |
| GET | `/api/facet-counts` | イニシャル別・機関別件数 |

### app_c: Excel 変換

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/` | トップページ |
| GET | `/docs` | Swagger UI |
| GET | `/openapi.json` | OpenAPI スキーマ |
| GET | `/api/allowed-ids` | 許可 ID 一覧 |
| POST | `/api/convert` | 変換実行 |
| GET | `/api/download/{work_id}/{filename}` | ファイルダウンロード |

---

## 変更履歴（サブパス対応）

### v2.0.0（サブパス対応版）

**ディレクトリ名変更:**
- `app-a/` → `app_a/`（Python パッケージ規約準拠）
- `app-c/` → `app_c/`

**root_path 対応:**
- 環境変数 `NIHU_RM_ROOT_PATH` でサブパスを設定可能
- `/docs`, `/openapi.json` がサブパス配下で正常動作
- Swagger UI 内のリクエスト送信が正しく動作

**import 修正:**
- `from app.xxx` → `from .xxx`（相対インポート）
- パッケージとして `uvicorn app_a.main:app` で起動可能

**フロントエンド:**
- 静的ファイル参照・API リクエストを相対パスに変更
- サーバー側の root_path 注入が不要になり、コードがシンプルに

---

## 注意事項

### セキュリティ

- 個人データを含むファイルは gitignore 対象です
- 認証機能は未実装です
- 外部ドメインから API を呼ぶ場合は nginx で CORS ヘッダーを設定してください

### researchmap API

- レート制限: 同時 3 接続、研究者ごと 0.5 秒スリープ
- researchmap の利用規約を確認してください

---

## ライセンス

MIT License

Copyright (c) 2026 National Institutes for the Humanities

詳細は [LICENSE](LICENSE) を参照してください。

## 貢献者

このプロジェクトへの貢献者については [CONTRIBUTORS.md](CONTRIBUTORS.md) を参照してください。
