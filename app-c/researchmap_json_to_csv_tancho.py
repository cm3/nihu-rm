#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
researchmap JSON -> 機構IR様式（CSV）: 単著（books_etc / book_owner_role=single_work） [common.py 利用版]

Usage:
  python researchmap_json_to_csv_tancho_common.py --input-file cm3.json --output-dir out

Output:
  out/cm3-単著.csv  （入力ファイル名 stem を使用）

Notes:
- 本スクリプトは同ディレクトリの common.py を import します。
  本回答で添付した common_v3.py を common.py として配置してから実行してください。
- 選択肢項目は "code : label" を出力します（Excel 入力規則に合わせる）。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Dict, List

from common import (
    as_list,
    book_type_choice,
    build_project_index,
    convert_languages,
    extract_project_numbers_and_titles,
    find_see_also_url,
    get_lang_fallback,
    get_profile_fields,
    get_researchmap_data,
    join_names,
    load_json,
    normalize_date_yyyymmdd,
    publisher_location_choice_from_publisher,
    referee_to_choice,
    unwrap_items,
)

HEADERS_TANCHO: List[str] = ['No.', '入力者名', 'e-Rad研究者番号', '共同研究番号', '科研費課題番号', '著者氏名\u3000＞\u3000原文', '著者氏名\u3000＞\u3000英訳', '著書名\u3000＞\u3000原文', '著書名\u3000＞\u3000英訳', '記述言語', '著書種別', '出版機関名\u3000＞\u3000原文', '出版機関名\u3000＞\u3000英訳', '出版機関の所在地', '発行年月(日)', 'ISBN', 'ISSN', 'DOI', '査読', '章数', 'ページ数', 'URL', 'ASIN', 'Amazon\u3000URL', '概要\u3000＞\u3000原文', '概要\u3000＞\u3000英訳', 'メモ']


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="researchmap JSON から『単著』CSVを生成します（common.py 利用版）。")
    p.add_argument("--input-file", required=True, help="researchmap export JSON file (e.g., cm3.json)")
    p.add_argument("--output-dir", required=True, help="output directory")
    return p.parse_args()


def join_values(value: Any, sep: str = "; ") -> str:
    """list/str/None を sep で連結（ID類向け）。"""
    if value is None:
        return ""
    if isinstance(value, list):
        return sep.join([str(x).strip() for x in value if x is not None and str(x).strip()])
    s = str(value).strip()
    return s


def make_row_tancho(
    item: Dict[str, Any],
    inputter_name: str,
    erad_id: str,
    project_index: Dict[str, Dict[str, Any]],
    people_delim: str = " / ",
) -> Dict[str, str]:
    joint_numbers, kaken_numbers, _titles = extract_project_numbers_and_titles(item, project_index)

    joint_cell = "; ".join(joint_numbers)

    authors = item.get("authors") or {}
    authors_ja = authors_en = ""
    if isinstance(authors, dict):
        authors_ja = join_names(authors.get("ja"), delim=people_delim) or join_names(authors.get("en"), delim=people_delim)
        authors_en = join_names(authors.get("en"), delim=people_delim)

    book_title = item.get("book_title") or {}
    title_ja = get_lang_fallback(book_title, ("ja", "en"))
    title_en = get_lang_fallback(book_title, ("en",))

    lang_str = convert_languages(item.get("languages"))

    publisher = item.get("publisher") or {}
    pub_ja = get_lang_fallback(publisher, ("ja",))
    pub_en = get_lang_fallback(publisher, ("en",))
    pub_loc = publisher_location_choice_from_publisher(item.get("publisher"))

    identifiers = item.get("identifiers") or {}
    isbn = issn = doi = asin = ""
    if isinstance(identifiers, dict):
        isbn = join_values(as_list(identifiers.get("isbn")))
        issn = join_values(as_list(identifiers.get("issn")))
        doi = join_values(as_list(identifiers.get("doi")))
        asin = join_values(as_list(identifiers.get("asin")))

    url = find_see_also_url(item.get("see_also"), "url")
    amazon_url = find_see_also_url(item.get("see_also"), "amazon_url")

    desc = item.get("description") or {}
    desc_ja = get_lang_fallback(desc, ("ja",))
    desc_en = get_lang_fallback(desc, ("en",))

    row: Dict[str, str] = {
        "No.": "",
        "入力者名": inputter_name,
        "e-Rad研究者番号": erad_id,
        "共同研究番号": joint_cell,
        "科研費課題番号": "; ".join(kaken_numbers),
        "著者氏名　＞　原文": authors_ja,
        "著者氏名　＞　英訳": authors_en,
        "著書名　＞　原文": title_ja,
        "著書名　＞　英訳": title_en,
        "記述言語": lang_str,
        "著書種別": book_type_choice(item.get("book_type")),
        "出版機関名　＞　原文": pub_ja,
        "出版機関名　＞　英訳": pub_en,
        "出版機関の所在地": pub_loc,
        "発行年月(日)": normalize_date_yyyymmdd(item.get("publication_date")),
        "ISBN": isbn,
        "ISSN": issn,
        "DOI": doi,
        "査読": referee_to_choice(item.get("referee")),
        "章数": "",
        "ページ数": str(item.get("total_page", "") or "").strip(),
        "URL": url,
        "ASIN": asin,
        "Amazon　URL": amazon_url,
        "概要　＞　原文": desc_ja,
        "概要　＞　英訳": desc_en,
        "メモ": "",
    }

    return {h: row.get(h, "") for h in HEADERS_TANCHO}


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS_TANCHO, extrasaction="ignore")
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
    for it in unwrap_items(rm_data.get("books_etc")):
        if str(it.get("book_owner_role", "")).strip() != "single_work":
            continue
        rows.append(make_row_tancho(it, inputter_name, erad_id, project_index))

    out_path = out_dir / f"{in_path.stem}-単著.csv"
    write_csv(out_path, rows)

    print(f"Wrote: {out_path} (rows={len(rows)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
