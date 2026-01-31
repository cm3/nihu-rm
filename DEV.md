# 開発者向けメモ

## サブパス配下でのホスティング対応

nginx のリバースプロキシ配下で `/nihu-rm-a/` のようなサブパスでアプリを公開する場合の設計方針。

---

### 基本方針

| レイヤー | 方針 |
|----------|------|
| **nginx** | プレフィックスを剥がして upstream に渡す |
| **FastAPI** | `root_path` を設定（OpenAPI/Swagger 用） |
| **フロントエンド** | 相対パスを使用（サーバー側の注入不要） |

---

### 1. nginx 設定

```nginx
location /nihu-rm-a/ {
    proxy_pass http://127.0.0.1:8000/;  # 末尾の / が重要
    # ...
}
```

**ポイント**: `proxy_pass` の末尾に `/` を付けることで、nginx がプレフィックス (`/nihu-rm-a`) を剥がして upstream に渡す。

```
リクエスト: GET /nihu-rm-a/api/users
upstream:   GET /api/users
```

---

### 2. FastAPI の root_path

```python
ROOT_PATH = os.environ.get("NIHU_RM_ROOT_PATH", "")

app = FastAPI(
    root_path=ROOT_PATH,
    docs_url="/docs",
    openapi_url="/openapi.json",
)
```

**root_path が必要な理由**:
- OpenAPI スキーマの `servers[].url` に反映される
- Swagger UI の「Try it out」が正しい URL にリクエストを送る
- FastAPI 内部のリダイレクト生成（trailing slash 補完など）

**root_path が不要なもの**:
- HTML テンプレート内の静的ファイル参照
- JavaScript からの API リクエスト
- レスポンスで返す URL（download_url など）

→ これらは**相対パス**で解決できる。

---

### 3. フロントエンドの URL 解決

#### NG パターン（絶対パス）

```html
<!-- 常に / から始まるため、サブパスで壊れる -->
<link rel="stylesheet" href="/static/css/style.css">
<script src="/static/js/main.js"></script>
```

```javascript
// 常にホストのルートからのパスになる
fetch('/api/users')
```

#### OK パターン（相対パス）

```html
<!-- 現在のページを基準に解決される -->
<link rel="stylesheet" href="static/css/style.css">
<script src="static/js/main.js"></script>
```

```javascript
// 現在のページを基準に解決される
fetch('api/users')
```

#### 解決の仕組み

```
ページ URL:    https://example.com/nihu-rm-a/
相対パス:      api/users
解決後:        https://example.com/nihu-rm-a/api/users ✓

ページ URL:    https://example.com/nihu-rm-a/
相対パス:      static/css/style.css
解決後:        https://example.com/nihu-rm-a/static/css/style.css ✓
```

---

### 4. サーバーが返す URL

API レスポンスに URL を含める場合も相対パスを使う。

```python
# NG: 絶対パス（サブパスで壊れる）
return {"download_url": f"/api/download/{work_id}/{filename}"}

# NG: root_path を注入（複雑になる）
return {"download_url": f"{root_path}/api/download/{work_id}/{filename}"}

# OK: 相対パス（シンプル）
return {"download_url": f"api/download/{work_id}/{filename}"}
```

フロントエンドで `<a href="${data.download_url}">` とすれば、ブラウザが現在のページを基準に解決する。

---

### 5. 避けるべきパターン

#### テンプレート変数での root_path 注入

```html
<!-- 複雑になるため避ける -->
<link rel="stylesheet" href="{{ root_path }}/static/css/style.css">
<script>window.API_BASE = "{{ root_path }}";</script>
```

```javascript
// JavaScript 側でも対応が必要になる
const API_BASE = window.API_BASE || '';
fetch(`${API_BASE}/api/users`)
```

**問題点**:
- サーバー側でテンプレートに root_path を渡す処理が必要
- JavaScript でも API_BASE を参照する必要がある
- コードが複雑になる

**解決策**: 相対パスを使えば、これらすべてが不要になる。

---

### 6. チェックリスト

サブパス対応を実装する際の確認項目：

- [ ] nginx の `proxy_pass` 末尾に `/` があるか
- [ ] FastAPI に `root_path` を設定しているか
- [ ] HTML の静的ファイル参照が相対パスか（先頭に `/` がないか）
- [ ] JavaScript の fetch が相対パスか
- [ ] API レスポンスの URL が相対パスか
- [ ] `/docs` と `/openapi.json` がサブパス配下で動作するか
- [ ] Swagger UI の「Try it out」が正しい URL にリクエストを送るか

---

### 7. 動作確認コマンド

```bash
# ローカル（root_path なし）
uvicorn app_a.main:app --port 8000
curl http://localhost:8000/api/organizations
curl http://localhost:8000/docs

# ローカル（root_path あり、nginx なし）
NIHU_RM_ROOT_PATH=/nihu-rm-a uvicorn app_a.main:app --port 8000
# この状態では /nihu-rm-a/api/... ではなく /api/... でアクセス
# root_path は OpenAPI の servers URL にのみ影響

# VPS（nginx 経由）
curl https://example.com/nihu-rm-a/health
curl https://example.com/nihu-rm-a/docs
curl https://example.com/nihu-rm-a/openapi.json
curl https://example.com/nihu-rm-a/api/organizations
```

---

### 8. まとめ

```
┌─────────────────────────────────────────────────────────────┐
│ Client                                                      │
│   GET https://example.com/nihu-rm-a/api/users               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ nginx                                                       │
│   location /nihu-rm-a/ { proxy_pass http://127.0.0.1:8000/; }│
│   → プレフィックス /nihu-rm-a を剥がす                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI (uvicorn)                                           │
│   GET /api/users                                            │
│   root_path="/nihu-rm-a" (OpenAPI/Swagger 用)               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Response                                                    │
│   {"users": [...]}                                          │
│   URLs in response: "api/download/..." (相対パス)            │
└─────────────────────────────────────────────────────────────┘
```

**シンプルに保つコツ**:
1. nginx でプレフィックスを剥がす
2. FastAPI は root_path のみ設定
3. フロントエンドは相対パスを使う
4. サーバーが返す URL も相対パスにする
