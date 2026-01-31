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

## VPS でのサブパス運用

nginx のリバースプロキシ配下で、サブパス（`/nihu-rm-a/`, `/nihu-rm-c/`）でアプリを公開する場合の設定例です。

### ディレクトリ構成（推奨）

```
/opt/nihu-rm/                  # アプリケーション
├── venv/
├── app_a/
├── app_c/
├── static/
└── requirements.txt

/var/lib/nihu-rm/              # データ（永続化）
├── researchers.db
├── json/
├── csv/
└── xlsx/

# シンボリックリンクで接続
/opt/nihu-rm/data -> /var/lib/nihu-rm
```

### セットアップ

```bash
# アプリケーションを配置
sudo mkdir -p /opt/nihu-rm
sudo chown $USER:$USER /opt/nihu-rm
cd /opt/nihu-rm
git clone https://github.com/cm3/nihu-rm.git .

# データディレクトリを作成
sudo mkdir -p /var/lib/nihu-rm/{json,csv,xlsx}
sudo chown -R $USER:$USER /var/lib/nihu-rm

# シンボリックリンクを作成
ln -s /var/lib/nihu-rm data

# 設定ファイルをコピー
cp /path/to/lang.csv data/
cp /path/to/researchmap_endpoint_labels.csv data/

# 仮想環境を作成
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r app_c/requirements.txt

# データをダウンロード・セットアップ
python app_a/download_data.py --csv /path/to/researchers.csv
python app_a/setup_db.py
```

### systemd ユニットファイル

#### `/etc/systemd/system/nihu-rm-a.service`

```ini
[Unit]
Description=NIHU Researcher Search (app_a)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/nihu-rm
Environment="PATH=/opt/nihu-rm/venv/bin"
Environment="NIHU_RM_ROOT_PATH=/nihu-rm-a"
ExecStart=/opt/nihu-rm/venv/bin/uvicorn app_a.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips="127.0.0.1"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### `/etc/systemd/system/nihu-rm-c.service`

```ini
[Unit]
Description=NIHU Excel Converter (app_c)
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/nihu-rm
Environment="PATH=/opt/nihu-rm/venv/bin"
Environment="NIHU_RM_ROOT_PATH=/nihu-rm-c"
ExecStart=/opt/nihu-rm/venv/bin/uvicorn app_c.main:app \
    --host 127.0.0.1 \
    --port 8001 \
    --proxy-headers \
    --forwarded-allow-ips="127.0.0.1"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### サービスの有効化

```bash
sudo systemctl daemon-reload
sudo systemctl enable nihu-rm-a nihu-rm-c
sudo systemctl start nihu-rm-a nihu-rm-c
sudo systemctl status nihu-rm-a nihu-rm-c
```

### nginx 設定例

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    # SSL 設定（省略）

    # app_a: 研究者検索
    location /nihu-rm-a/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Prefix /nihu-rm-a;
    }

    # app_c: Excel 変換
    location /nihu-rm-c/ {
        proxy_pass http://127.0.0.1:8001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Prefix /nihu-rm-c;
    }
}
```

**ポイント:**
- `proxy_pass` の末尾に `/` を付けることで、nginx がプレフィックスを剥がして upstream に渡す
- アプリ側の `NIHU_RM_ROOT_PATH` で URL 生成時にプレフィックスを補完

### 動作確認（VPS）

```bash
# ヘルスチェック
curl https://example.com/nihu-rm-a/health
curl https://example.com/nihu-rm-c/api/allowed-ids

# Swagger UI
curl -I https://example.com/nihu-rm-a/docs
curl -I https://example.com/nihu-rm-c/docs

# OpenAPI JSON
curl https://example.com/nihu-rm-a/openapi.json | head
curl https://example.com/nihu-rm-c/openapi.json | head

# API エンドポイント
curl "https://example.com/nihu-rm-a/api/organizations"
curl "https://example.com/nihu-rm-a/api/researchers?page=1&page_size=5"
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
| GET | `/api/initial-counts` | イニシャル別件数 |

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
- 本番環境では CORS 設定を適切に制限してください
- 認証機能は未実装です

### researchmap API

- レート制限: 同時 3 接続、研究者ごと 0.5 秒スリープ
- researchmap の利用規約を確認してください

---

## ライセンス

このプロジェクトは人間文化研究機構のために作成されました。
