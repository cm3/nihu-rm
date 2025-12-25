# NIHU Researcher Search

人間文化研究機構（NIHU）の研究者検索システム。researchmapと連携し、研究者情報の検索・閲覧ができます。

## 特徴

- NIHUウェブサイトのデザインを踏襲したUI
- researchmapからの研究者データ取得
- SQLiteベースの軽量データベース
- 全文検索機能（FTS5、日本語対応のtrigramトークナイザー）
- 機関別・イニシャル別フィルタリング
- 差分ダウンロード機能（CSV更新時に新規研究者のみ取得）
- レスポンシブデザイン

## プロジェクト構成

```
researcher-search/
├── app/                    # アプリケーションコード
│   ├── main.py            # FastAPIメインアプリ
│   ├── database.py        # データベース処理
│   ├── models.py          # Pydanticモデル
│   ├── routers/           # APIルーター
│   │   └── researchers.py
│   └── templates/         # HTMLテンプレート
│       └── index.html
├── static/                # 静的ファイル
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
├── scripts/               # ユーティリティスクリプト
│   ├── download_data.py  # researchmapからデータダウンロード
│   └── setup_db.py       # データベースセットアップ
├── data/                  # データディレクトリ
│   ├── researchers.db    # SQLiteデータベース
│   ├── json/             # 研究者JSONデータ
│   └── tool-a-1225-converted.csv  # CSVソースデータ
└── requirements.txt       # Python依存関係
```

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. データの準備

#### 2.1 CSVファイルの配置

`data/tool-a-1225-converted.csv` が存在することを確認してください。

#### 2.2 researchmapからデータをダウンロード

**初回または全件ダウンロード:**
```bash
python scripts/download_data.py --csv data/tool-a-1225-converted.csv
```

**差分ダウンロード（CSV更新時、既存研究者をスキップ）:**
```bash
python scripts/download_data.py --csv data/tool-a-1225-converted.csv --incremental
# または短縮形
python scripts/download_data.py --csv data/tool-a-1225-converted.csv -i
```

**その他のオプション:**
```bash
# ヘルプ表示
python scripts/download_data.py --help

# カスタムパス指定
python scripts/download_data.py --csv /path/to/data.csv --output /path/to/output
```

**注意**:
- researchmapのAPIエンドポイントは実際のAPIに合わせて修正が必要な場合があります
- researchmapの利用規約を確認し、適切なレート制限を設定してください
- 差分ダウンロードは既存のJSONファイルをチェックして、新規研究者のみダウンロードします

#### 2.3 データベースのセットアップ

```bash
python scripts/setup_db.py
```

このスクリプトは以下を実行します：
- 既存のテーブルを削除（クリーンな再構築）
- SQLiteデータベースの作成
- テーブルとFTS5インデックスの作成（trigramトークナイザー使用）
- JSONデータのインポート
- 20以上のフィールドを全文検索対象として登録

### 3. アプリケーションの起動

```bash
uvicorn app.main:app --reload
```

ブラウザで http://localhost:8000 にアクセスしてください。

## API エンドポイント

### 研究者検索

```
GET /api/researchers
```

クエリパラメータ:
- `query`: 検索クエリ（名前、役職、業績など）
- `org1`: 機関1でフィルター
- `org2`: 機関2でフィルター
- `initial`: イニシャルフィルター（A-Z、一文字）
- `page`: ページ番号（デフォルト: 1）
- `page_size`: ページサイズ（デフォルト: 50）

### 研究者詳細

```
GET /api/researchers/{researcher_id}
```

### 機関一覧

```
GET /api/organizations
```

## 開発

### データベーススキーマ

**researchers テーブル**:
- `id`: researchmap ID（主キー）
- `name_ja`: 日本語名
- `name_en`: 英語名
- `avatar_url`: アバター画像URL
- `org1`: 機関1
- `org2`: 機関2
- `position`: 役職
- `researchmap_url`: researchmap URL
- `researchmap_data`: researchmapデータ（JSON）
- `created_at`: 作成日時

**researchers_fts テーブル**:
- FTS5仮想テーブル（全文検索用、trigramトークナイザー使用）
- 検索対象: 名前、所属、役職、論文、書籍、発表、受賞、研究分野、研究プロジェクトなど20以上のフィールド

### 検索機能の拡張

業績などの情報で検索する場合は、以下を修正してください：

1. `scripts/setup_db.py`: FTS5テーブルに検索対象フィールドを追加
2. `app/database.py`: 検索クエリを拡張
3. `static/js/main.js`: UIに検索オプションを追加

## データ更新ワークフロー

CSVファイルが更新された場合の推奨手順：

1. **差分ダウンロード**: 新規研究者のみダウンロード
   ```bash
   python scripts/download_data.py --csv data/tool-a-1225-converted.csv --incremental
   ```

2. **データベース再構築**: 全データで再構築
   ```bash
   python scripts/setup_db.py
   ```

3. **動作確認**: 新規研究者が検索できることを確認
   ```bash
   uvicorn app.main:app --reload
   ```

## 注意事項

### researchmap API

現在、researchmapからのデータ取得は仮実装です。実際に使用する際は：

1. researchmapの公式APIドキュメントを確認
2. 必要に応じてAPI認証を実装
3. レート制限を遵守（現在: 同時3接続、研究者ごと0.5秒スリープ）
4. 利用規約に従ってデータを使用

### データベース

- SQLiteは軽量ですが、大規模データ（数万件以上）の場合はPostgreSQLなどへの移行を検討してください
- FTS5のtrigramトークナイザーで日本語検索に対応していますが、より高度な検索にはElasticsearchなどの使用を検討してください
- データベース再構築時は既存のテーブルが削除されるため、必要に応じてバックアップを取得してください

## ライセンス

このプロジェクトは人間文化研究機構のために作成されました。
