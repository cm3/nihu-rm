#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
researchmap JSON (researchmap_data.*) -> 機構IR様式: 「論文」CSV 生成（common.py 利用版）

Usage:
  python researchmap_json_to_csv_papers.py --input-file cm3.json --output-dir out

Output:
  out/cm3-論文.csv  （入力ファイル名 stem を使用）

Notes:
- 本スクリプトは同ディレクトリの common.py を import します。
- Excel 入力規則と整合するため、コード値は "4" ではなく "4 : 論文（国際会議録）" のような
  「コード : ラベル」表記を出力します（common.py の mapper を利用）。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Dict, List

from common import (
    as_list,
    bool_to_choice_012,
    build_project_index,
    convert_languages,
    extract_project_numbers_and_titles,
    find_see_also_url,
    get_lang_fallback,
    get_profile_fields,
    get_researchmap_data,
    join_names,
    international_domestic_journal_choice,
    load_json,
    map_published_paper_owner_roles,
    map_published_paper_type,
    normalize_date_yyyymmdd,
    referee_to_choice,
    unwrap_items,
)

# ルールに基づく列順（markdown「論文」表の「機構IR様式項目」を踏襲）
CSV_COLUMNS: List[str] = [
    "No.",
    "入力者名",
    "e-Rad研究者番号",
    "共同研究番号",
    "科研費課題番号",
    "著者氏名（共著者含）　＞　原文",
    "著者氏名（共著者含）　＞　英訳",
    "著者氏名（共著者含）　＞　下線",
    "論文題目名　＞　原文",
    "論文題目名　＞　英訳",
    "記述言語",
    "掲載種別",
    "査読",
    "招待論文",
    "国際共著",
    "掲載誌名　＞　原文",
    "掲載誌名　＞　英訳",
    "掲載誌(巻・号・頁)　＞　巻",
    "掲載誌(巻・号・頁)　＞　号",
    "掲載誌(巻・号・頁)　＞　開始頁",
    "掲載誌(巻・号・頁)　＞　終了頁",
    "掲載誌　発行年月(日)",
    "出版機関名　＞　原文",
    "出版機関名　＞　英訳",
    "出版機関の所在地",
    "ISBN",
    "ISSN",
    "DOI",
    "CiNiiのID",
    "共著区分",
    "共著範囲",
    "参加形態",
    "担当部分",
    "リンクURL　＞　Permalink",
    "リンクURL　＞　URL",
    "Web of ScienceのID",
    "PubMedのID",
    "ScopusのID",
    "JGlobalのID",
    "arXivのID",
    "ORCIDのPut Code",
    "DBLPのID",
    "OpenDepoのID",
    "概要　＞　原文",
    "概要　＞　英訳",
    "メモ",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="researchmap JSON から『論文』CSVを生成します（common.py 利用版）。")
    p.add_argument("--input-file", required=True, help="researchmap export JSON file (e.g., cm3.json)")
    p.add_argument("--output-dir", required=True, help="output directory")
    return p.parse_args()


def first_str(value: Any) -> str:
    """value が list[str] / str / None のいずれでも、代表値（文字列）を返す。"""
    if value is None:
        return ""
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    return str(value).strip()




def extract_authors(authors_obj: Any, lang: str) -> str:
    """
    authors: { "ja": [{"name": ...}, ...], "en": ... } を想定し、name を連結。
    common.join_names を利用（区切りは '; '）。
    """
    if not isinstance(authors_obj, dict):
        return ""
    return join_names(authors_obj.get(lang), delim="; ")


def build_papers_rows(rm_data: Dict[str, Any]) -> List[Dict[str, str]]:
    project_index = build_project_index(rm_data)
    inputter_name, erad_id = get_profile_fields(rm_data.get("profile"))

    rows: List[Dict[str, str]] = []
    for it in unwrap_items(rm_data.get("published_papers")):
        # 研究課題情報
        joint_numbers, kaken_numbers, _titles = extract_project_numbers_and_titles(it, project_index)

        joint_cell = "; ".join(joint_numbers)

        # 著者
        authors_ja = extract_authors(it.get("authors"), "ja")
        authors_en = extract_authors(it.get("authors"), "en")
        authors_orig = authors_ja or authors_en

        # タイトル
        title_orig = get_lang_fallback(it.get("paper_title"), ("ja", "en"))
        title_en = get_lang_fallback(it.get("paper_title"), ("en",))

        # 誌名
        journal_orig = get_lang_fallback(it.get("publication_name"), ("ja", "en"))
        journal_en = get_lang_fallback(it.get("publication_name"), ("en",))

        # 出版者
        publisher_ja = get_lang_fallback(it.get("publisher"), ("ja",))
        publisher_en = get_lang_fallback(it.get("publisher"), ("en",))

        # 記述言語
        langs = convert_languages(it.get("languages"))

        # リンクURL（label=='url' の @id）
        url = find_see_also_url(it.get("see_also"), "url")

        # IDs
        identifiers = it.get("identifiers") if isinstance(it.get("identifiers"), dict) else {}
        isbn = first_str(identifiers.get("isbn"))
        issn = first_str(identifiers.get("issn")) or first_str(identifiers.get("e_issn"))
        doi = first_str(identifiers.get("doi"))
        cinii = first_str(identifiers.get("cinii_cr_id"))
        wos = first_str(identifiers.get("wos_id"))
        pm = first_str(identifiers.get("pm_id"))
        scopus = first_str(identifiers.get("scopus_id"))
        jglobal = first_str(identifiers.get("j_global_id"))
        arxiv = first_str(identifiers.get("arxiv_id"))
        orcid_put = first_str(identifiers.get("orcid_put_cd"))
        dblp = first_str(identifiers.get("dblp_id"))

        # 概要
        desc_ja = get_lang_fallback(it.get("description"), ("ja",))
        desc_en = get_lang_fallback(it.get("description"), ("en",))

        row: Dict[str, str] = {c: "" for c in CSV_COLUMNS}

        # ルール：No. は空欄（システム側で自動付与）
        row["No."] = ""

        row["入力者名"] = inputter_name
        row["e-Rad研究者番号"] = erad_id

        row["共同研究番号"] = joint_cell
        row["科研費課題番号"] = "; ".join(kaken_numbers)

        row["著者氏名（共著者含）　＞　原文"] = authors_orig
        row["著者氏名（共著者含）　＞　英訳"] = authors_en
        row["著者氏名（共著者含）　＞　下線"] = ""

        row["論文題目名　＞　原文"] = title_orig
        row["論文題目名　＞　英訳"] = title_en

        row["記述言語"] = langs
        row["掲載種別"] = map_published_paper_type(it.get("published_paper_type"))
        row["査読"] = referee_to_choice(it.get("referee"))
        row["招待論文"] = bool_to_choice_012(it.get("invited"))
        row["国際共著"] = bool_to_choice_012(it.get("is_international_collaboration"))

        row["掲載誌名　＞　原文"] = journal_orig
        row["掲載誌名　＞　英訳"] = journal_en

        row["掲載誌(巻・号・頁)　＞　巻"] = first_str(it.get("volume"))
        row["掲載誌(巻・号・頁)　＞　号"] = first_str(it.get("number"))
        row["掲載誌(巻・号・頁)　＞　開始頁"] = first_str(it.get("starting_page"))
        row["掲載誌(巻・号・頁)　＞　終了頁"] = first_str(it.get("ending_page"))

        row["掲載誌　発行年月(日)"] = normalize_date_yyyymmdd(it.get("publication_date"))

        row["出版機関名　＞　原文"] = publisher_ja
        row["出版機関名　＞　英訳"] = publisher_en
        row["出版機関の所在地"] = international_domestic_journal_choice(it.get("is_international_journal"))

        row["ISBN"] = isbn
        row["ISSN"] = issn
        row["DOI"] = doi
        row["CiNiiのID"] = cinii

        # ルール表に具体変換が無い場合は空欄のまま
        row["共著区分"] = ""
        row["共著範囲"] = ""

        row["参加形態"] = map_published_paper_owner_roles(it.get("published_paper_owner_roles"))
        row["担当部分"] = ""

        row["リンクURL　＞　Permalink"] = ""
        row["リンクURL　＞　URL"] = url

        row["Web of ScienceのID"] = wos
        row["PubMedのID"] = pm
        row["ScopusのID"] = scopus
        row["JGlobalのID"] = jglobal
        row["arXivのID"] = arxiv
        row["ORCIDのPut Code"] = orcid_put
        row["DBLPのID"] = dblp
        row["OpenDepoのID"] = ""

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


def main() -> int:
    args = parse_args()
    in_path = Path(args.input_file)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    root = load_json(in_path)
    rm_data = get_researchmap_data(root)
    rows = build_papers_rows(rm_data)

    out_path = out_dir / f"{in_path.stem}-論文.csv"
    write_csv(out_path, rows)

    print(f"Wrote: {out_path} (rows={len(rows)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
