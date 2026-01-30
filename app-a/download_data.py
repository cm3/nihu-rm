#!/usr/bin/env python3
"""
researchmapから研究者データをダウンロードするスクリプト

CSVファイルからresearchmap IDを抽出し、各研究者のJSONデータを取得します。
"""

import argparse
import csv
import json
import re
import asyncio
import sys
from pathlib import Path
import httpx

# app-c の common.py を参照
APP_C_DIR = Path(__file__).parent.parent / "app-c"
sys.path.insert(0, str(APP_C_DIR))
from common import get_endpoint_list


def extract_researchmap_id(url: str) -> str | None:
    """researchmap URLからIDを抽出"""
    if not url:
        return None
    match = re.search(r'researchmap\.jp/([^/]+)', url)
    return match.group(1) if match else None


async def fetch_endpoint(client: httpx.AsyncClient, rm_id: str, endpoint: str = "") -> dict | None:
    """researchmap APIから単一のエンドポイントデータを取得"""
    url = f"https://api.researchmap.jp/{rm_id}"
    if endpoint:
        url += f"/{endpoint}"

    try:
        response = await client.get(url, timeout=30.0)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            # 404は正常（データが存在しない可能性）
            return None
        else:
            print(f"  Failed to fetch {endpoint or 'profile'} for {rm_id}: {response.status_code}")
            return None
    except Exception as e:
        print(f"  Error fetching {endpoint or 'profile'} for {rm_id}: {e}")
        return None


async def fetch_researcher_data(client: httpx.AsyncClient, rm_id: str) -> dict:
    """researchmapから研究者の全データを取得"""
    # 取得するエンドポイント一覧（CSVから読み込み）
    endpoints = get_endpoint_list()

    result = {}

    for endpoint in endpoints:
        data = await fetch_endpoint(client, rm_id, endpoint)
        if data is not None:
            key = endpoint if endpoint else "profile"
            result[key] = data
        # 各エンドポイント間に少し待機
        await asyncio.sleep(0.1)

    return result


def read_ids_file(ids_file: Path) -> set[str]:
    """IDファイルを読み込み、有効なIDのセットを返す"""
    ids = set()
    with ids_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().replace("\r", "")
            if line and not line.startswith("#"):
                ids.add(line)
    return ids


async def download_all_data(csv_path: Path, output_dir: Path, incremental: bool = False, ids_file: Path | None = None):
    """全研究者のデータをダウンロード

    Args:
        csv_path: CSVファイルのパス
        output_dir: 出力先ディレクトリ
        incremental: Trueの場合、既存のJSONファイルがある研究者はスキップ
        ids_file: 指定した場合、このファイルに含まれるIDのみダウンロード
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # IDファイルが指定されている場合、絞り込み用のIDセットを読み込む
    filter_ids = None
    if ids_file:
        if not ids_file.exists():
            print(f"Error: IDs file not found: {ids_file}")
            return
        filter_ids = read_ids_file(ids_file)
        print(f"Filter: {len(filter_ids)} IDs from {ids_file}")

    # CSVから研究者情報を読み込み
    researchers = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 7:
                continue

            avatar_url = row[0]
            name_ja = row[1]
            name_en = row[2]
            org1 = row[3]
            org2 = row[4]
            position = row[5]
            rm_url = row[6]

            rm_id = extract_researchmap_id(rm_url)
            if rm_id:
                # IDフィルタが指定されている場合、マッチするもののみ追加
                if filter_ids is not None and rm_id not in filter_ids:
                    continue
                researchers.append({
                    'id': rm_id,
                    'name_ja': name_ja,
                    'name_en': name_en,
                    'avatar_url': avatar_url,
                    'org1': org1,
                    'org2': org2,
                    'position': position,
                    'researchmap_url': rm_url
                })

    print(f"Found {len(researchers)} researchers in CSV" + (" (after filtering)" if filter_ids else ""))

    # 差分ダウンロードモードの場合、既存のJSONファイルをチェック
    if incremental:
        existing_ids = {f.stem for f in output_dir.glob("*.json")}
        researchers_to_download = [r for r in researchers if r['id'] not in existing_ids]
        skipped_count = len(researchers) - len(researchers_to_download)

        print(f"Incremental mode: {skipped_count} researchers already exist, {len(researchers_to_download)} to download")
        researchers = researchers_to_download
    else:
        print(f"Full download mode: downloading all {len(researchers)} researchers")

    # ダウンロードする研究者がいない場合は終了
    if not researchers:
        print("No new researchers to download.")
        return

    # 研究者データをダウンロード（並列処理）
    async with httpx.AsyncClient() as client:
        # 注: researchmapの利用規約を確認し、適切なレート制限を設定してください
        semaphore = asyncio.Semaphore(3)  # 同時接続数を制限（各研究者で複数エンドポイントを取得するため減らす）

        async def download_with_semaphore(researcher):
            async with semaphore:
                try:
                    print(f"Downloading: {researcher['name_ja']} ({researcher['id']})...")
                    rm_data = await fetch_researcher_data(client, researcher['id'])

                    # 基本情報とresearchmapデータをマージ
                    full_data = {
                        **researcher,
                        'researchmap_data': rm_data
                    }

                    # JSONファイルとして保存
                    output_path = output_dir / f"{researcher['id']}.json"
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(full_data, f, ensure_ascii=False, indent=2)

                    # データ取得状況を表示
                    data_count = len(rm_data)
                    print(f"✓ Completed: {researcher['name_ja']} ({researcher['id']}) - {data_count} endpoints")

                except Exception as e:
                    print(f"✗ Error downloading {researcher['name_ja']} ({researcher['id']}): {e}")

                finally:
                    # 必ず研究者ごとにスリープ（成功・失敗関わらず）
                    await asyncio.sleep(0.5)

        tasks = [download_with_semaphore(r) for r in researchers]
        await asyncio.gather(*tasks, return_exceptions=True)

    print(f"Download complete. Data saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='researchmapから研究者データをダウンロード',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 全てダウンロード（既存データも上書き）
  python scripts/download_data.py

  # 差分のみダウンロード（既存のJSONファイルがある研究者はスキップ）
  python scripts/download_data.py --incremental
  python scripts/download_data.py -i

  # カスタムCSVファイルとディレクトリを指定
  python scripts/download_data.py --csv box/custom.csv --output data/output

  # IDファイルで絞り込んでダウンロード
  python scripts/download_data.py --ids-file data/test_ids.txt
  python scripts/download_data.py --ids-file data/test_ids.txt --incremental
        """
    )

    parser.add_argument(
        '--csv',
        type=Path,
        default=Path(__file__).parent.parent / "box" / "tool-a-1225-converted.csv",
        help='CSVファイルのパス (デフォルト: box/tool-a-1225-converted.csv)'
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=Path(__file__).parent.parent / "data" / "json",
        help='出力先ディレクトリ (デフォルト: data/json)'
    )

    parser.add_argument(
        '-i', '--incremental',
        action='store_true',
        help='差分ダウンロードモード: 既存のJSONファイルがある研究者はスキップ'
    )

    parser.add_argument(
        '--ids-file',
        type=Path,
        default=None,
        help='IDファイル（1行1ID）で絞り込み (例: data/test_ids.txt)'
    )

    args = parser.parse_args()

    # CSVファイルの存在確認
    if not args.csv.exists():
        print(f"Error: CSV file not found: {args.csv}")
        return

    print(f"CSV file: {args.csv}")
    print(f"Output directory: {args.output}")
    print(f"Mode: {'Incremental (skip existing)' if args.incremental else 'Full (overwrite existing)'}")
    if args.ids_file:
        print(f"IDs filter: {args.ids_file}")
    print()

    asyncio.run(download_all_data(args.csv, args.output, args.incremental, args.ids_file))


if __name__ == "__main__":
    main()
