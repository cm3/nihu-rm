#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
researchmap JSON -> 機構IR様式（CSV）: MISC [common.py 利用版・著者区切り修正版]

Usage:
  python researchmap_json_to_csv_misc_common.py --input-file cm3.json --output-dir out

Output:
  out/cm3-MISC.csv  （入力ファイル名 stem を使用）

Notes:
- 本スクリプトは同ディレクトリの common.py を import します。
- 著者氏名の区切りは common.join_names() の仕様に従い、常に「, 」へ統制されます。
  （Surname, First 形式は First Surname へ並べ替え）
  本回答で添付した common_v6.py を common.py として配置してから実行してください。
- 変換は rules.md / 変換案Excel の指示に従い、独自の推定は行いません。
  （例: 掲載種別は misc_type / 翻訳担当区分から "code : label" を出力）
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Dict, List

from common import (
    as_list,
    convert_languages,
    request_choice_misc,
    build_project_index,
    extract_project_numbers_and_titles,
    find_see_also_url,
    get_lang_fallback,
    get_profile_fields,
    get_researchmap_data,
    join_names,
    load_json,
    misc_type_choice,
    normalize_date_yyyymmdd,
    publisher_location_choice_from_is_international_journal,
    referee_to_choice,
    translation_role_to_misc_type_choice,
    unwrap_items,
)

HEADERS: List[str] = ['No.', '入力者名', 'e-Rad研究者番号', '共同研究番号', '科研費課題番号', '著者氏名（共著者含）\u3000＞\u3000原文', '著者氏名（共著者含）\u3000＞\u3000英訳', '著者氏名（共著者含）\u3000＞\u3000下線', '題目\u3000＞\u3000原文', '題目\u3000＞\u3000英訳', '記述言語', '掲載種別', '掲載誌名\u3000＞\u3000原文', '掲載誌名\u3000＞\u3000英訳', '掲載誌(巻・号・頁)\u3000＞\u3000巻', '掲載誌(巻・号・頁)\u3000＞\u3000号', '掲載誌(巻・号・頁)\u3000＞\u3000開始頁', '掲載誌(巻・号・頁)\u3000＞\u3000終了頁', '掲載誌\u3000発行年月(日)', '出版機関名\u3000＞\u3000原文', '出版機関名\u3000＞\u3000英訳', '出版機関の所在地', '査読', '依頼の有無', 'ISBN', 'ISSN', 'DOI', 'CiNiiのID', '共著区分', '共著範囲', '担当部分', 'リンクURL\u3000＞\u3000Permalink', 'リンクURL\u3000＞\u3000URL', 'Web of ScienceのID', 'PubMedのID', 'ScopusのID', 'JGlobalのID', 'arXivのID', 'ORCIDのPut Code', 'DBLPのID', 'OpenDepoのID', '概要\u3000＞\u3000原文', '概要\u3000＞\u3000英訳', 'メモ']

# books_etc のうち、MISC（翻訳業績）として取り込む担当区分
TRANSLATION_BOOK_ROLES = {"single_translation", "joint_translation", "editing_translation"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="researchmap JSON から『MISC』CSVを生成します（common.py 利用版）。")
    p.add_argument("--input-file", required=True, help="researchmap export JSON file (e.g., cm3.json)")
    p.add_argument("--output-dir", required=True, help="output directory")
    return p.parse_args()


def join_values(value: Any, sep: str = "; ") -> str:
    """list/str/None を sep で連結（ID類向け）。"""
    if value is None:
        return ""
    if isinstance(value, list):
        return sep.join([str(x).strip() for x in value if x is not None and str(x).strip()])
    return str(value).strip()


def make_row(
    item: Dict[str, Any],
    inputter_name: str,
    erad_id: str,
    project_index: Dict[str, Dict[str, Any]],
    kind: str
) -> Dict[str, str]:
    joint_numbers, kaken_numbers, _titles = extract_project_numbers_and_titles(item, project_index)

    joint_cell = "; ".join(joint_numbers)

    # 著者
    authors = item.get("authors") or {}
    authors_ja = authors_en = ""
    if isinstance(authors, dict):
        authors_ja = join_names(authors.get("ja")) or join_names(authors.get("en"))
        authors_en = join_names(authors.get("en"))

    # 題目 / 掲載誌名（kind により参照フィールドが異なる）
    title_ja = title_en = ""
    pubname_ja = pubname_en = ""
    type_cell = ""

    if kind == "misc":
        paper_title = item.get("paper_title") or {}
        title_ja = get_lang_fallback(paper_title, ("ja", "en"))
        title_en = get_lang_fallback(paper_title, ("en",))

        publication_name = item.get("publication_name") or {}
        pubname_ja = get_lang_fallback(publication_name, ("ja", "en"))
        pubname_en = get_lang_fallback(publication_name, ("en",))

        type_cell = misc_type_choice(item.get("misc_type"))

    elif kind == "translation_books":
        # rules.md（MISC セクション）に従い、掲載誌名に books_etc の book_title を充当
        book_title = item.get("book_title") or {}
        pubname_ja = get_lang_fallback(book_title, ("ja", "en"))
        pubname_en = get_lang_fallback(book_title, ("en",))

        type_cell = translation_role_to_misc_type_choice(item.get("book_owner_role"))

    # 記述言語
    lang_str = convert_languages(item.get("languages"))

    # 出版者・発行元
    publisher = item.get("publisher") or {}
    pub_ja = get_lang_fallback(publisher, ("ja",))
    pub_en = get_lang_fallback(publisher, ("en",))

    # 出版機関の所在地（is_international_journal: null/False/True → 0/1/2）
    pub_loc = publisher_location_choice_from_is_international_journal(item.get("is_international_journal"))

    # 巻号頁
    volume = str(item.get("volume", "") or "").strip()
    number = str(item.get("number", "") or "").strip()
    sp = str(item.get("starting_page", "") or "").strip()
    ep = str(item.get("ending_page", "") or "").strip()

    # 日付
    pub_date = normalize_date_yyyymmdd(item.get("publication_date"))

    # 査読 / 依頼（招待）
    referee = referee_to_choice(item.get("referee"))
    invited = request_choice_misc(item.get("invited"))

    # 研究者番号類
    identifiers = item.get("identifiers") or {}
    isbn = issn = doi = cinii = wos_id = pm_id = scopus_id = jg = arxiv = orcid_put = dblp = open_depo = ""
    if isinstance(identifiers, dict):
        isbn = join_values(as_list(identifiers.get("isbn")))
        issn = join_values(as_list(identifiers.get("issn")))
        doi = join_values(as_list(identifiers.get("doi")))
        cinii = join_values(as_list(identifiers.get("cinii_cr_id")))
        wos_id = join_values(as_list(identifiers.get("wos_id")))
        pm_id = join_values(as_list(identifiers.get("pm_id")))
        scopus_id = join_values(as_list(identifiers.get("scopus_id")))
        jg = join_values(as_list(identifiers.get("j_global_id")))
        arxiv = join_values(as_list(identifiers.get("arxiv_id")))
        orcid_put = join_values(as_list(identifiers.get("orcid_put_cd")))
        dblp = join_values(as_list(identifiers.get("dblp_id")))
        open_depo = join_values(as_list(identifiers.get("opendepo_id")))

    # URL
    url = find_see_also_url(item.get("see_also"), "url")

    # 概要
    desc = item.get("description") or {}
    desc_ja = get_lang_fallback(desc, ("ja",))
    desc_en = get_lang_fallback(desc, ("en",))

    row: Dict[str, str] = {
        "No.": "",
        "入力者名": inputter_name,
        "e-Rad研究者番号": erad_id,
        "共同研究番号": joint_cell,
        "科研費課題番号": "; ".join(kaken_numbers),

        "著者氏名（共著者含）　＞　原文": authors_ja,
        "著者氏名（共著者含）　＞　英訳": authors_en,
        "著者氏名（共著者含）　＞　下線": "",

        "題目　＞　原文": title_ja,
        "題目　＞　英訳": title_en,
        "記述言語": lang_str,

        "掲載種別": type_cell,

        "掲載誌名　＞　原文": pubname_ja,
        "掲載誌名　＞　英訳": pubname_en,

        "掲載誌(巻・号・頁)　＞　巻": volume,
        "掲載誌(巻・号・頁)　＞　号": number,
        "掲載誌(巻・号・頁)　＞　開始頁": sp,
        "掲載誌(巻・号・頁)　＞　終了頁": ep,

        "掲載誌　発行年月(日)": pub_date,

        "出版機関名　＞　原文": pub_ja,
        "出版機関名　＞　英訳": pub_en,
        "出版機関の所在地": pub_loc,

        "査読": referee,
        "依頼の有無": invited,

        "ISBN": isbn,
        "ISSN": issn,
        "DOI": doi,
        "CiNiiのID": cinii,

        "共著区分": "",
        "共著範囲": "",
        "担当部分": "",

        "リンクURL　＞　Permalink": "",
        "リンクURL　＞　URL": url,

        "Web of ScienceのID": wos_id,
        "PubMedのID": pm_id,
        "ScopusのID": scopus_id,
        "JGlobalのID": jg,
        "arXivのID": arxiv,
        "ORCIDのPut Code": orcid_put,
        "DBLPのID": dblp,
        "OpenDepoのID": open_depo,

        "概要　＞　原文": desc_ja,
        "概要　＞　英訳": desc_en,
        "メモ": "",
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

    # 通常の MISC（misc）
    for it in unwrap_items(rm_data.get("misc")):
        rows.append(make_row(it, inputter_name, erad_id, project_index, kind="misc"))

    # 翻訳業績（books_etc の一部を MISC として取り込む）
    for it in unwrap_items(rm_data.get("books_etc")):
        role = str(it.get("book_owner_role", "")).strip()
        if role not in TRANSLATION_BOOK_ROLES:
            continue
        rows.append(make_row(it, inputter_name, erad_id, project_index, kind="translation_books"))

    out_path = out_dir / f"{in_path.stem}-MISC.csv"
    write_csv(out_path, rows)

    print(f"Wrote: {out_path} (rows={len(rows)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
