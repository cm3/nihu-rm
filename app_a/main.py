"""
FastAPIアプリケーション

サブパス配下での運用:
  NIHU_RM_ROOT_PATH=/nihu-rm-a uvicorn app_a.main:app --port 8000
"""

import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from .routers import researchers

# root_path を環境変数から取得（nginx でサブパス配下に配置する場合に設定）
ROOT_PATH = os.environ.get("NIHU_RM_ROOT_PATH", "")

# CORS設定を読み込み
BASE_DIR = Path(__file__).parent.parent
CORS_FILE = BASE_DIR / "data" / "cors.txt"

def load_cors_origins():
    """cors.txtからCORS許可オリジンを読み込み"""
    if CORS_FILE.exists():
        with open(CORS_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    return []

CORS_ORIGINS = load_cors_origins()

# FastAPIアプリケーション作成
app = FastAPI(
    title="NIHU Researcher Search",
    description="人間文化研究機構 研究者検索システム API\n\n"
                f"🔗 [検索画面を開く]({ROOT_PATH}/)" if ROOT_PATH else
                "人間文化研究機構 研究者検索システム API",
    version="1.0.0",
    root_path=ROOT_PATH,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS設定
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

# 静的ファイルとテンプレート設定
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ルーター登録
app.include_router(researchers.router, prefix="/api", tags=["researchers"])


@app.get("/")
async def index(request: Request):
    """
    トップページ
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """
    ヘルスチェック
    """
    return {"status": "ok", "root_path": ROOT_PATH}


if __name__ == "__main__":
    import uvicorn
    # 開発時は直接実行可能
    uvicorn.run(
        "app_a.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        root_path=ROOT_PATH,
    )
