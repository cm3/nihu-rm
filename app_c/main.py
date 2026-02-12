#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
researchmap JSON → Excel 変換 Web アプリ

Usage:
  uvicorn app_c.main:app --reload --port 8001

サブパス配下での運用:
  NIHU_RM_ROOT_PATH=/nihu-rm-c uvicorn app_c.main:app --port 8001

アクセス:
  http://localhost:8001/
"""

import os
import re
import shutil
import uuid
from pathlib import Path

from dotenv import load_dotenv
import httpx
from fastapi import FastAPI, Form, HTTPException, BackgroundTasks

# プロジェクトルートの .env を読み込み
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# 変換スクリプトのディレクトリ（このディレクトリ自身）
SCRIPT_DIR = Path(__file__).parent

# パッケージとして実行した場合に備え、ローカルディレクトリを sys.path に追加
import sys
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# app_a のパスを追加（download_data.py の参照用）
APP_A_DIR = Path(__file__).parent.parent / "app_a"
if str(APP_A_DIR) not in sys.path:
    sys.path.insert(0, str(APP_A_DIR))

from common import (
    get_researchmap_data,
    get_profile_fields,
)
from download_data import fetch_researcher_data

# root_path を環境変数から取得（nginx でサブパス配下に配置する場合に設定）
ROOT_PATH = os.environ.get("NIHU_RM_ROOT_PATH", "")

app = FastAPI(
    title="researchmap → Excel 変換",
    description="researchmap データを機構IR様式の Excel に変換する API\n\n"
                f"🔗 [変換画面を開く]({ROOT_PATH}/)" if ROOT_PATH else
                "researchmap データを機構IR様式の Excel に変換する API",
    root_path=ROOT_PATH,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# テンプレートと静的ファイル
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# 一時ファイル保存ディレクトリ
WORK_DIR = Path(__file__).parent / "work"
WORK_DIR.mkdir(exist_ok=True)

# データディレクトリ
DATA_DIR = Path(__file__).parent.parent / "data"

# researchmap API 設定
RESEARCHMAP_API_BASE = "https://api.researchmap.jp"


def _extract_permalinks_from_url_csv(csv_path: Path) -> set[str]:
    """CSV ファイルから researchmap URL を検出し permalink を抽出する"""
    permalinks = set()
    if not csv_path.exists():
        return permalinks

    with csv_path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            # https://researchmap.jp/{permalink} から permalink を抽出
            match = re.search(r"https://researchmap\.jp/([^/,\s\"]+)", line)
            if match:
                permalink = match.group(1)
                # avatar などを除外
                if not permalink.endswith((".jpg", ".png", ".gif")):
                    permalinks.add(permalink)
    return permalinks


def _extract_permalinks_from_header_tsv(tsv_path: Path, column_name: str = "rm_id") -> set[str]:
    """ヘッダー付き TSV（タブ区切り）から指定カラムの値を抽出する"""
    permalinks = set()
    if not tsv_path.exists():
        print(f"Warning: TSV file not found: {tsv_path}", file=sys.stderr)
        return permalinks

    with tsv_path.open("r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    if not lines:
        print(f"Warning: TSV file is empty: {tsv_path}", file=sys.stderr)
        return permalinks

    # ヘッダー行を解析
    header_line = lines[0].strip()
    if "\t" not in header_line:
        print(f"Warning: TSV file is not tab-delimited: {tsv_path}", file=sys.stderr)
        print(f"  Header line: {repr(header_line)}", file=sys.stderr)
        return permalinks

    headers = [h.strip() for h in header_line.split("\t")]
    if column_name not in headers:
        print(f"Warning: Column '{column_name}' not found in TSV: {tsv_path}", file=sys.stderr)
        print(f"  Available columns: {headers}", file=sys.stderr)
        return permalinks
    col_idx = headers.index(column_name)

    # データ行を処理
    for line_num, line in enumerate(lines[1:], start=2):
        fields = line.strip().split("\t")
        if col_idx < len(fields):
            value = fields[col_idx].strip()
            if value:
                permalinks.add(value)

    return permalinks


def load_allowed_ids() -> set[str]:
    """CSV ファイルから許可された permalink を読み込む

    読み込むファイル（環境変数で指定、data/ ディレクトリ内）:
      - TOOL_C_MAIN_CSV: メインリスト（URL形式）
      - TOOL_C_ADD_CSV: 追加リスト（ヘッダー付き、オプション）
      - TOOL_C_ADD_CSV_COLUMN: 追加リストのカラム名（デフォルト: rm_id）

    CSV仕様: .env-sample のコメントを参照
    """
    allowed = set()

    # メインリスト（URL形式）
    main_csv_name = os.environ.get("TOOL_C_MAIN_CSV", "").strip()
    if main_csv_name:
        main_csv = DATA_DIR / main_csv_name
        main_ids = _extract_permalinks_from_url_csv(main_csv)
        allowed.update(main_ids)
        print(f"Loaded {len(main_ids)} IDs from main CSV: {main_csv_name}", file=sys.stderr)
    else:
        print("Warning: TOOL_C_MAIN_CSV not set", file=sys.stderr)

    # 追加リスト（ヘッダー付き）
    add_csv_name = os.environ.get("TOOL_C_ADD_CSV", "").strip()
    if add_csv_name:
        add_csv = DATA_DIR / add_csv_name
        column_name = os.environ.get("TOOL_C_ADD_CSV_COLUMN", "rm_id").strip()
        add_ids = _extract_permalinks_from_header_tsv(add_csv, column_name)
        allowed.update(add_ids)
        print(f"Loaded {len(add_ids)} IDs from add CSV: {add_csv_name}", file=sys.stderr)

    print(f"Total allowed IDs: {len(allowed)}", file=sys.stderr)
    return allowed


# 許可された ID をキャッシュ
ALLOWED_IDS: set[str] = load_allowed_ids()


def validate_researcher_id(researcher_id: str) -> str:
    """研究者 ID のバリデーション"""
    researcher_id = researcher_id.strip()

    if not researcher_id:
        raise HTTPException(status_code=400, detail="研究者 ID を入力してください")

    # 許可リストにあるかチェック
    if researcher_id not in ALLOWED_IDS:
        raise HTTPException(
            status_code=400,
            detail=f"'{researcher_id}' は許可された研究者 ID ではありません。CSV に登録されている ID のみ使用できます。"
        )

    return researcher_id


async def download_researchmap_json(researcher_id: str) -> dict:
    """researchmap API から研究者データを取得（download_data.py を再利用）"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        rm_data = await fetch_researcher_data(client, researcher_id)

        if not rm_data or "profile" not in rm_data:
            raise HTTPException(
                status_code=404,
                detail=f"研究者 ID '{researcher_id}' が researchmap に見つかりません"
            )

        # researchmap_data 形式でラップ（既存スクリプトとの互換性のため）
        return {"researchmap_data": rm_data}


def convert_json_to_csvs(json_data: dict, output_dir: Path, researcher_id: str) -> list[Path]:
    """JSON を各種 CSV に変換（subprocess で各スクリプトを実行）"""
    import json
    import subprocess

    # JSON ファイルを一時保存
    json_path = output_dir / f"{researcher_id}.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    csv_dir = output_dir / "csv"
    csv_dir.mkdir(exist_ok=True)

    # 各変換スクリプトとその出力ファイル名
    converters = [
        ("researchmap_json_to_csv_papers.py", "論文"),
        ("researchmap_json_to_csv_buntan.py", "分担執筆"),
        ("researchmap_json_to_csv_tancho.py", "単著"),
        ("researchmap_json_to_csv_kyocho_hencho.py", "共著編著"),
        ("researchmap_json_to_csv_kotohappyo.py", "口頭発表"),
        ("researchmap_json_to_csv_misc.py", "MISC"),
        ("researchmap_json_to_csv_sonota.py", "その他"),
    ]

    csv_files = []
    for script_name, category in converters:
        script_path = SCRIPT_DIR / script_name
        if not script_path.exists():
            print(f"Warning: Script not found: {script_path}")
            continue

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--input-file", str(json_path),
                    "--output-dir", str(csv_dir),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(SCRIPT_DIR),  # スクリプトのディレクトリで実行
            )

            if result.returncode != 0:
                print(f"Warning: {script_name} failed: {result.stderr}")
                continue

            # 出力ファイルを確認
            out_path = csv_dir / f"{researcher_id}-{category}.csv"
            if out_path.exists():
                csv_files.append(out_path)
            else:
                print(f"Warning: Output not found: {out_path}")

        except subprocess.TimeoutExpired:
            print(f"Warning: {script_name} timed out")
        except Exception as e:
            print(f"Warning: {script_name} error: {e}")

    return csv_files


def convert_csvs_to_excel(csv_dir: Path, output_dir: Path, researcher_id: str, fiscal_year: int = None) -> Path:
    """CSV を Excel に変換（create_researcher_excel 関数を直接呼び出し）

    Args:
        csv_dir: CSVファイルのディレクトリ
        output_dir: 出力ディレクトリ
        researcher_id: 研究者ID
        fiscal_year: 年度フィルタ（例: 2023 = 2023年4月〜2024年3月）、Noneでフィルタなし
    """
    import importlib.util

    xlsx_dir = output_dir / "xlsx"
    xlsx_dir.mkdir(exist_ok=True)

    # CSVファイルを収集
    csv_files = list(csv_dir.glob(f"{researcher_id}-*.csv"))
    if not csv_files:
        raise HTTPException(status_code=500, detail="CSV ファイルが生成されませんでした")

    # カテゴリごとにファイルを整理
    category_files = {}
    for csv_file in csv_files:
        # ファイル名からカテゴリを抽出 (例: cm3-論文.csv -> 論文)
        category = csv_file.stem.replace(f"{researcher_id}-", "")
        category_files[category] = csv_file

    # csv_to_excel モジュールを動的にロード
    spec = importlib.util.spec_from_file_location("csv_to_excel", SCRIPT_DIR / "csv_to_excel.py")
    csv_to_excel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(csv_to_excel)

    # Excel 作成
    try:
        csv_to_excel.create_researcher_excel(researcher_id, category_files, xlsx_dir, fiscal_year=fiscal_year)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel 変換エラー: {e}")

    # 出力ファイルパスを決定
    if fiscal_year:
        xlsx_path = xlsx_dir / f"{researcher_id}_{fiscal_year}年度.xlsx"
    else:
        xlsx_path = xlsx_dir / f"{researcher_id}.xlsx"

    if not xlsx_path.exists():
        raise HTTPException(status_code=500, detail=f"Excel ファイルが生成されませんでした")

    return xlsx_path


def cleanup_old_files():
    """古い一時ファイルを削除"""
    import time
    max_age_hours = int(os.environ.get("TOOL_C_WORK_MAX_AGE_HOURS", "24"))
    now = time.time()
    max_age_seconds = max_age_hours * 3600

    for item in WORK_DIR.iterdir():
        if item.is_dir():
            try:
                age = now - item.stat().st_mtime
                if age > max_age_seconds:
                    shutil.rmtree(item)
            except Exception:
                pass


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """メインページ"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/allowed-ids")
async def get_allowed_ids():
    """許可された ID 一覧を返す"""
    return {"ids": sorted(ALLOWED_IDS), "count": len(ALLOWED_IDS)}


@app.post("/api/convert")
async def convert(
    researcher_id: str = Form(...),
    fiscal_year: str = Form(None),
    background_tasks: BackgroundTasks = None
):
    """研究者 ID から Excel を生成

    Args:
        researcher_id: researchmap の研究者 ID
        fiscal_year: 年度フィルタ（例: "2023" = 2023年4月〜2024年3月）、空文字または None でフィルタなし
    """
    # バリデーション
    researcher_id = validate_researcher_id(researcher_id)

    # 年度フィルタのパース
    fiscal_year_int = None
    if fiscal_year and fiscal_year.strip():
        try:
            fiscal_year_int = int(fiscal_year.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"年度の形式が不正です: {fiscal_year}")

    # 作業ディレクトリ作成
    work_id = str(uuid.uuid4())[:8]
    work_path = WORK_DIR / work_id
    work_path.mkdir(parents=True, exist_ok=True)

    try:
        # 1. JSON ダウンロード
        json_data = await download_researchmap_json(researcher_id)

        # 2. JSON → CSV 変換
        csv_dir = work_path / "csv"
        csv_files = convert_json_to_csvs(json_data, work_path, researcher_id)

        # 3. CSV → Excel 変換（年度フィルタ適用）
        xlsx_path = convert_csvs_to_excel(csv_dir, work_path, researcher_id, fiscal_year=fiscal_year_int)

        if not xlsx_path.exists():
            raise HTTPException(status_code=500, detail="Excel ファイルの生成に失敗しました")

        # プロファイル情報を取得
        rm_data = get_researchmap_data(json_data.get("researchmap_data", json_data))
        name, erad_id = get_profile_fields(rm_data.get("profile"))

        # 古いファイルのクリーンアップをバックグラウンドで実行
        if background_tasks:
            background_tasks.add_task(cleanup_old_files)

        return {
            "success": True,
            "researcher_id": researcher_id,
            "name": name,
            "erad_id": erad_id,
            "fiscal_year": fiscal_year_int,
            "download_url": f"api/download/{work_id}/{xlsx_path.name}",
            "csv_count": len(csv_files),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{work_id}/{filename}")
async def download(work_id: str, filename: str):
    """生成した Excel をダウンロード"""
    file_path = WORK_DIR / work_id / "xlsx" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


if __name__ == "__main__":
    import uvicorn
    # 開発時は直接実行可能
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        root_path=ROOT_PATH,
    )
