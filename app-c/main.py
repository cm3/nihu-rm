#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
researchmap JSON → Excel 変換 Web アプリ

Usage:
  uvicorn main:app --reload --port 8000

アクセス:
  http://localhost:8000/
"""

import re
import shutil
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# app-a のパスを追加（download_data.py の参照用）
import sys
APP_A_DIR = Path(__file__).parent.parent / "app-a"
sys.path.insert(0, str(APP_A_DIR))

# 変換スクリプトのディレクトリ（このディレクトリ自身）
SCRIPT_DIR = Path(__file__).parent

from common import (
    get_researchmap_data,
    get_profile_fields,
)
from download_data import fetch_researcher_data

app = FastAPI(title="researchmap → Excel 変換")

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


def load_allowed_ids() -> set[str]:
    """CSV ファイルから許可された permalink を読み込む"""
    allowed = set()

    # tool-a-1225-converted.csv から permalink を抽出
    csv_path = DATA_DIR / "tool-a-1225-converted.csv"
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8-sig") as f:
            for line in f:
                # https://researchmap.jp/{permalink} からpermalinkを抽出
                match = re.search(r"https://researchmap\.jp/([^/,\s\"]+)", line)
                if match:
                    permalink = match.group(1)
                    # avatar などを除外
                    if not permalink.endswith((".jpg", ".png", ".gif")):
                        allowed.add(permalink)

    # test_ids.txt からも読み込み
    ids_path = DATA_DIR / "test_ids.txt"
    if ids_path.exists():
        with ids_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    allowed.add(line)

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


def convert_csvs_to_excel(csv_dir: Path, output_dir: Path, researcher_id: str) -> Path:
    """CSV を Excel に変換（create_researcher_excel 関数を直接呼び出し）"""
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
        csv_to_excel.create_researcher_excel(researcher_id, category_files, xlsx_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel 変換エラー: {e}")

    xlsx_path = xlsx_dir / f"{researcher_id}.xlsx"
    if not xlsx_path.exists():
        raise HTTPException(status_code=500, detail=f"Excel ファイルが生成されませんでした")

    return xlsx_path


def cleanup_old_files(max_age_hours: int = 24):
    """古い一時ファイルを削除"""
    import time
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
async def convert(researcher_id: str = Form(...), background_tasks: BackgroundTasks = None):
    """研究者 ID から Excel を生成"""
    # バリデーション
    researcher_id = validate_researcher_id(researcher_id)

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

        # 3. CSV → Excel 変換
        xlsx_path = convert_csvs_to_excel(csv_dir, work_path, researcher_id)

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
            "download_url": f"/api/download/{work_id}/{researcher_id}.xlsx",
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
