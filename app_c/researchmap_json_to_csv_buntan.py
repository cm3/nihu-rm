#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
researchmap JSON (researchmap_data.*) -> 機構IR様式: 「分担執筆」CSV 生成（common.py 利用版）

対象:
- researchmap_data.books_etc.items のうち book_owner_role == "contributor"（分担執筆）

出力:
- <output-dir>/<input-stem>-分担執筆.csv

Usage:
  python researchmap_json_to_csv_buntan.py --input-file cm3.json --output-dir out

Notes:
- 本スクリプトは同ディレクトリの common.py を import します。
- Excel 入力規則と整合するため、選択肢セルは "1" のようなコード単体ではなく
  "01 : 単行本（学術書）" のような「コード : ラベル」表記を出力します（common.py の mapper を利用）。
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List

from common import (
    as_list,
    bool_to_choice_012,
    book_type_choice,
    build_project_index,
    convert_languages,
    extract_project_numbers_and_titles,
    find_see_also_url,
    get_lang_fallback,
    get_profile_fields,
    get_researchmap_data,
    publisher_location_choice_from_publisher,
    join_names,
    load_json,
    normalize_date_yyyymmdd,
    referee_to_choice,
)


CSV_COLUMNS: List[str] = [
    "No.",
    "入力者名",
    "e-Rad研究者番号",
    "共同研究番号",
    "科研費課題番号",
    "著者氏名（共著者含）　＞　原文",
    "著者氏名（共著者含）　＞　英訳",
    "著者氏名（共著者含）　＞　下線",
    "担当部分　＞　原文",
    "担当部分　＞　英訳",
    "著書名　＞　原文",
    "著書名　＞　英訳",
    "記述言語",
    "著書種別",
    "出版機関名　＞　原文",
    "出版機関名　＞　英訳",
    "出版機関の所在地",
    "発行年月(日)",
    "査読",
    "ISBN",
    "ISSN",
    "DOI",
    "編者名",
    "担当ページ",
    "担当部分のページ数",
    "担当部分の共著区分",
    "担当部分の共著範囲",
    "国際共著",
    "URL",
    "ASIN",
    "Amazon　URL",
    "概要　＞　原文",
    "概要　＞　英訳",
    "メモ",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input-file", required=True, help="researchmap export JSON file (e.g., cm3.json)")
    p.add_argument("--output-dir", required=True, help="output directory")
    return p.parse_args()




def first_scalar(value: Any) -> str:
    """
    identifiers などの値を 1セル向けに正規化する。
    - str: そのまま
    - list: 先頭要素を str 化
    - dict: 多言語フィールドとして ja/en 優先で取得
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    if isinstance(value, dict):
        return get_lang_fallback(value, ("ja", "en"))
    return str(value).strip()


def build_buntan_rows(rm_data: Dict[str, Any]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    profile = rm_data.get("profile") or {}
    inputter_name, erad = get_profile_fields(profile)

    project_index = build_project_index(rm_data)

    for it in as_list((rm_data.get("books_etc") or {}).get("items")):
        if not isinstance(it, dict):
            continue

        if str(it.get("book_owner_role", "")).strip() != "contributor":
            continue

        identifiers = it.get("identifiers") if isinstance(it.get("identifiers"), dict) else {}

        # 共同研究番号/科研費課題番号（rules.md に従い、英字始まり判定のみ）
        joint_nums, kaken_nums, _titles = extract_project_numbers_and_titles(it, project_index)

        authors_ja = join_names((it.get("authors") or {}).get("ja"))
        authors_en = join_names((it.get("authors") or {}).get("en"))
        authors_orig = authors_ja or authors_en

        owner_range_orig = get_lang_fallback(it.get("book_owner_range"), ("ja", "en"))
        owner_range_en = get_lang_fallback(it.get("book_owner_range"), ("en",))

        book_title_orig = get_lang_fallback(it.get("book_title"), ("ja", "en"))
        book_title_en = get_lang_fallback(it.get("book_title"), ("en",))

        langs = convert_languages(it.get("languages"))
        book_type = book_type_choice(it.get("book_type"))

        publisher_ja = get_lang_fallback(it.get("publisher"), ("ja",))
        publisher_en = get_lang_fallback(it.get("publisher"), ("en",))

        # 出版機関の所在地:
        # - books_etc には is_international_journal が無い前提のため、指示書に従い publisher から国内/海外を推定（common.py 側の関数を使用）
        publisher_location = publisher_location_choice_from_publisher(it.get("publisher"))
        publication_date = normalize_date_yyyymmdd(it.get("publication_date"))

        referee = referee_to_choice(it.get("referee"))

        isbn = ""
        issn = ""
        doi = ""
        asin = ""
        if isinstance(identifiers, dict):
            isbn = first_scalar(identifiers.get("isbn"))
            issn = first_scalar(identifiers.get("issn"))
            doi = first_scalar(identifiers.get("doi"))
            asin = first_scalar(identifiers.get("asin"))

        rep_page = str(it.get("rep_page", "") or "").strip()

        # rules.md: see_also の label == 'url' の @id を採用
        url = find_see_also_url(it.get("see_also"), label="url")

        desc_ja = get_lang_fallback(it.get("description"), ("ja",))
        desc_en = get_lang_fallback(it.get("description"), ("en",))

        row: Dict[str, str] = {c: "" for c in CSV_COLUMNS}
        row["No."] = ""  # 自動採番（CSVでは空欄）
        row["入力者名"] = inputter_name
        row["e-Rad研究者番号"] = erad
        row["共同研究番号"] = "; ".join(joint_nums)
        row["科研費課題番号"] = "; ".join(kaken_nums)

        row["著者氏名（共著者含）　＞　原文"] = authors_orig
        row["著者氏名（共著者含）　＞　英訳"] = authors_en
        row["著者氏名（共著者含）　＞　下線"] = ""

        row["担当部分　＞　原文"] = owner_range_orig
        row["担当部分　＞　英訳"] = owner_range_en

        row["著書名　＞　原文"] = book_title_orig
        row["著書名　＞　英訳"] = book_title_en

        row["記述言語"] = langs
        row["著書種別"] = book_type

        row["出版機関名　＞　原文"] = publisher_ja
        row["出版機関名　＞　英訳"] = publisher_en
        row["出版機関の所在地"] = publisher_location

        row["発行年月(日)"] = publication_date
        row["査読"] = referee

        row["ISBN"] = isbn
        row["ISSN"] = issn
        row["DOI"] = doi

        # rules.md: authors と書籍自体の著者の区別がないため、編者名は空
        row["編者名"] = ""

        row["担当ページ"] = rep_page
        row["担当部分のページ数"] = ""
        row["担当部分の共著区分"] = ""
        row["担当部分の共著範囲"] = ""

        # 国際共著（null/False/True -> 0/2/1）
        row["国際共著"] = bool_to_choice_012(it.get("is_international_collaboration"))

        row["URL"] = url
        row["ASIN"] = asin
        row["Amazon　URL"] = ""

        row["概要　＞　原文"] = desc_ja
        row["概要　＞　英訳"] = desc_en
        row["メモ"] = ""

        rows.append(row)

    return rows


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> None:
    args = parse_args()
    in_path = Path(args.input_file)
    out_dir = Path(args.output_dir)

    root = load_json(in_path)
    rm_data = get_researchmap_data(root)

    rows = build_buntan_rows(rm_data)

    out_path = out_dir / f"{in_path.stem}-分担執筆.csv"
    write_csv(out_path, rows)
    print(f"Wrote: {out_path} (rows={len(rows)})")


if __name__ == "__main__":
    main()
