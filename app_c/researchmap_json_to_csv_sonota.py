#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
researchmap JSON -> 機構IR様式（CSV）: その他 [common.py 利用版]

Usage:
  python researchmap_json_to_csv_sonota_common.py --input-file cm3.json --output-dir out

Output:
  out/cm3-その他.csv  （入力ファイル名 stem を使用）

Notes:
- 本スクリプトは同ディレクトリの common.py を import します。
  本回答で添付した common_v7.py を common.py として配置してから実行してください。
- 変換は rules.md / 変換案Excel の指示に従い、独自の推定は行いません。
  （例: 種別は各レスポンスの type フィールドおよび役割フィールドから機械的に決定）
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from common import (
    as_list,
    build_project_index,
    extract_project_numbers_and_titles,
    get_endpoint_ja_label,
    get_lang_fallback,
    get_profile_fields,
    get_researchmap_data,
    load_json,
    normalize_date_yyyymmdd,
    sonota_type_from_academic_contribution_type,
    sonota_type_from_books_role,
    sonota_type_from_media_coverage_type,
    sonota_type_from_social,
    sonota_type_from_work_type,
    sonota_type_other,
    unwrap_items,
)

HEADERS: List[str] = ['No.', '入力者名', 'e-Rad研究者番号', '共同研究番号', '科研費課題番号', '種別', '概要', '年月(日)', 'メモ']


def get_source_label(kind: str) -> str:
    """データソースのメモ用ラベルを取得（CSVから日本語ラベルを参照）"""
    # エンドポイント名の揺れを吸収
    endpoint_map = {
        "social_contribution": "social_contribution_activities",
        "media_coverage": "media_coverage",
        "academic_contribution": "academic_contribution_activities",
        "other": "others",
    }
    endpoint = endpoint_map.get(kind, kind)
    ja_label = get_endpoint_ja_label(endpoint)
    return f"{ja_label}レスポンスから取得"

# 「その他」へ回す books_etc は、担当区分が others / 未選択のみ。
# それ以外（単著/共著/編著/分担執筆/翻訳等）は別CSVで扱うため除外する。
BOOK_ROLES_EXCLUDE = {
    "contributor",          # 分担執筆
    "single_work",          # 単著
    "joint_work",           # 共著
    "editor",               # 編者
    "joint_editor",         # 共編
    "supervisor",           # 監修
    "compilation",          # 編纂
    "single_translation",   # MISC
    "joint_translation",    # MISC
    "editing_translation",  # MISC
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="researchmap JSON から『その他』CSVを生成します（common.py 利用版）。")
    p.add_argument("--input-file", required=True, help="researchmap export JSON file (e.g., cm3.json)")
    p.add_argument("--output-dir", required=True, help="output directory")
    return p.parse_args()


def is_current_marker(v: Any) -> bool:
    """to=9999 を「現在」とする判定。"""
    if v is None:
        return False
    if isinstance(v, int):
        return v == 9999
    s = str(v).strip()
    return s.startswith("9999")


def format_date_range(from_v: Any, to_v: Any) -> str:
    """from/to の組を、ルール表の表記に寄せて 1 セルにする。"""
    from_s = normalize_date_yyyymmdd(from_v)
    if is_current_marker(to_v):
        to_s = "現在"
    else:
        to_s = normalize_date_yyyymmdd(to_v)

    if from_s and to_s:
        return f"{from_s}-{to_s}"
    if from_s:
        return from_s
    if to_s:
        return to_s
    return ""


def combine_title_and_desc(title: Any, desc: Any) -> str:
    """概要セル用: タイトル + 内容（description）を 1 セルにまとめる。"""
    t = get_lang_fallback(title, ("ja", "en"))
    d_ja = get_lang_fallback(desc, ("ja",))
    d_en = get_lang_fallback(desc, ("en",))
    d = d_ja or d_en

    if t and d:
        return f"{t} / {d}"
    return t or d


def get_first_present_collection(rm_data: Dict[str, Any], candidates: List[str]) -> Any:
    """researchmap のキー揺れ対策（単数/複数）: 先に見つかったコレクションを返す。"""
    for k in candidates:
        if k in rm_data:
            return rm_data.get(k)
    return None


def make_row(
    item: Dict[str, Any],
    inputter_name: str,
    erad_id: str,
    project_index: Dict[str, Dict[str, Any]],
    kind: str,
) -> Dict[str, str]:
    joint_numbers, kaken_numbers, _titles = extract_project_numbers_and_titles(item, project_index)

    joint_cell = "; ".join(joint_numbers)

    if kind == "books_etc":
        type_cell = sonota_type_from_books_role(item.get("book_owner_role"))
        overview = combine_title_and_desc(item.get("book_title"), item.get("description"))
        ymd = normalize_date_yyyymmdd(item.get("publication_date"))

    elif kind == "works":
        type_cell = sonota_type_from_work_type(item.get("work_type"))
        overview = combine_title_and_desc(item.get("work_title"), item.get("description"))
        ymd = format_date_range(item.get("from_date"), item.get("to_date"))

    elif kind == "social_contribution":
        type_cell = sonota_type_from_social(item.get("social_contribution_roles"), item.get("social_contribution_type"))
        overview = combine_title_and_desc(item.get("social_contribution_title"), item.get("description"))
        ymd = format_date_range(item.get("from_event_date"), item.get("to_event_date"))

    elif kind == "media_coverage":
        type_cell = sonota_type_from_media_coverage_type(item.get("media_coverage_type"))
        overview = combine_title_and_desc(item.get("media_coverage_title"), item.get("description"))
        ymd = normalize_date_yyyymmdd(item.get("publication_date"))

    elif kind == "academic_contribution":
        type_cell = sonota_type_from_academic_contribution_type(item.get("academic_contribution_type"))
        overview = combine_title_and_desc(item.get("academic_contribution_title"), item.get("description"))
        ymd = format_date_range(item.get("from_date"), item.get("to_date"))

    elif kind == "other":
        type_cell = sonota_type_other(item.get("other_type"))
        overview = combine_title_and_desc(item.get("other_title"), item.get("description"))
        ymd = format_date_range(item.get("from_date"), item.get("to_date"))

    else:
        # 想定外の種類は「その他」として受け止める（勝手に詳細分類はしない）
        type_cell = "99:その他"
        overview = combine_title_and_desc(item.get("title"), item.get("description"))
        ymd = normalize_date_yyyymmdd(item.get("publication_date"))

    # データソースのラベルをメモ欄に記載
    memo = get_source_label(kind)

    row = {
        "No.": "",  # 自動採番（CSVでは空欄）
        "入力者名": inputter_name,
        "e-Rad研究者番号": erad_id,
        "共同研究番号": joint_cell,
        "科研費課題番号": "; ".join(kaken_numbers),
        "種別": type_cell,
        "概要": overview,
        "年月(日)": ymd,
        "メモ": memo,
    }
    return {h: row.get(h, "") for h in HEADERS}


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    args = parse_args()
    in_path = Path(args.input_file)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    root = load_json(in_path)
    rm_data = get_researchmap_data(root)

    inputter_name, erad_id = get_profile_fields(rm_data.get("profile"))
    project_index = build_project_index(rm_data)

    rows: List[Dict[str, str]] = []

    # 書籍等出版物（books_etc）: book_owner_role が others/未選択 のものを「その他」へ
    for it in unwrap_items(rm_data.get("books_etc")):
        role = it.get("book_owner_role")
        role_s = str(role).strip() if role is not None else ""
        if role_s in BOOK_ROLES_EXCLUDE:
            continue
        if role_s in ("others", ""):
            rows.append(make_row(it, inputter_name, erad_id, project_index, kind="books_etc"))

    # Works（作品等）
    for it in unwrap_items(rm_data.get("works")):
        rows.append(make_row(it, inputter_name, erad_id, project_index, kind="works"))

    # social_contribution（単数/複数キー揺れ対策）
    sc = get_first_present_collection(rm_data, ["social_contribution", "social_contributions"])
    for it in unwrap_items(sc):
        rows.append(make_row(it, inputter_name, erad_id, project_index, kind="social_contribution"))

    # media_coverage（単数/複数キー揺れ対策）
    mc = get_first_present_collection(rm_data, ["media_coverage", "media_coverages"])
    for it in unwrap_items(mc):
        rows.append(make_row(it, inputter_name, erad_id, project_index, kind="media_coverage"))

    # academic_contribution（単数/複数キー揺れ対策）
    ac = get_first_present_collection(rm_data, ["academic_contribution", "academic_contributions"])
    for it in unwrap_items(ac):
        rows.append(make_row(it, inputter_name, erad_id, project_index, kind="academic_contribution"))

    # other（単数/複数キー揺れ対策）
    oth = get_first_present_collection(rm_data, ["other", "others"])
    for it in unwrap_items(oth):
        rows.append(make_row(it, inputter_name, erad_id, project_index, kind="other"))

    out_path = out_dir / f"{in_path.stem}-その他.csv"
    write_csv(out_path, rows)

    print(f"Wrote: {out_path} (rows={len(rows)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
