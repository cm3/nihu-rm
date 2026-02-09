#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
researchmap JSON -> 機構IR様式（CSV）: 口頭発表 [common.py 利用版・レビュー反映]

Usage:
  python researchmap_json_to_csv_kotohappyo_common_v2.py --input-file cm3.json --output-dir out

Output:
  out/<input-stem>-口頭発表.csv  （例: cm3-口頭発表.csv）

Notes:
- 本スクリプトは同ディレクトリの common.py を import します。
- 変換は rules.md の指示に従い、独自の推定は行いません。
- レビュー反映:
  - 会議区分列の追加（is_international_presentation: False/True -> J/I）
  - 招待の有無のラベル変更（2 : 招待無し / 1 : 招待有り）
  - OpenDepoのID 列追加
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Dict, List

from common import (
    as_list,
    build_project_index,
    conference_class_choice_kotohappyo,
    convert_country_code,
    convert_languages,
    extract_project_numbers_and_titles,
    find_see_also_url,
    get_lang_fallback,
    get_profile_fields,
    get_researchmap_data,
    invited_choice_kotohappyo,
    join_names,
    load_json,
    normalize_date_yyyymmdd,
    presentation_type_choice,
    unwrap_items,
)

HEADERS_KOTOHAPPYO: List[str] = [
    "No.",
    "入力者名",
    "e-Rad研究者番号",
    "共同研究番号",
    "科研費課題番号",
    "発表者名（共同発表者含）　＞　原文",
    "発表者名（共同発表者含）　＞　英訳",
    "発表者名（共同発表者含））　＞　下線",
    "題目又はセッション名　＞　原文",
    "題目又はセッション名　＞　英訳",
    "会議区分",
    "会議名称　＞　原文",
    "会議名称　＞　英訳",
    "主催者名称 　＞　原文",
    "主催者名称 　＞　英訳",
    "開催場所　＞　原文",
    "開催場所　＞　英訳",
    "開催場所　＞　開催国",
    "発表年月(日) 　＞　（自）",
    "発表年月(日) 　＞　（至）",
    "発表形態",
    "発表(記述)言語",
    "招待の有無",
    "査読",
    "共同作業範囲",
    "担当部分",
    "URL",
    "CiNiiのID",
    "OpenDepoのID",
    "DOI",
    "概要　＞　原文",
    "概要　＞　英訳",
    "メモ",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="researchmap JSON から『口頭発表』CSVを生成します（common.py 利用版）。")
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




def extract_presenters(presenters_obj: Any, lang: str, fallback_lang: str = "") -> str:
    """
    presenters: {"ja":[{"name":...}], "en":[...]} を想定し、name を連結。
    """
    if not isinstance(presenters_obj, dict):
        return ""
    out = join_names(presenters_obj.get(lang), delim=" / ")
    if out:
        return out
    if fallback_lang:
        return join_names(presenters_obj.get(fallback_lang), delim=" / ")
    return ""


def pick_from_date(item: Dict[str, Any]) -> str:
    """
    発表年月(日) ＞（自）:
      - publication_date を優先
      - 無ければ from_event_date
    """
    pub = str(item.get("publication_date", "") or "").strip()
    if pub:
        return pub
    return str(item.get("from_event_date", "") or "").strip()


def make_row_kotohappyo(
    item: Dict[str, Any],
    inputter_name: str,
    erad_id: str,
    project_index: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    # 研究課題
    joint_numbers, kaken_numbers, _titles = extract_project_numbers_and_titles(item, project_index)
    joint_cell = "; ".join(joint_numbers)

    # 発表者
    presenters = item.get("presenters") or {}
    presenters_ja = extract_presenters(presenters, "ja", fallback_lang="en")
    presenters_en = extract_presenters(presenters, "en")

    # 題目/セッション
    ptitle = item.get("presentation_title") or {}
    title_ja = get_lang_fallback(ptitle, ("ja", "en"))
    title_en = get_lang_fallback(ptitle, ("en",))

    # 会議区分（レビュー指摘: 未選択->空、False->J : 国内会議、True->I : 国際会議）
    conference_class = conference_class_choice_kotohappyo(item.get("is_international_presentation"))

    # 会議名
    event = item.get("event") or {}
    event_ja = get_lang_fallback(event, ("ja", "en"))
    event_en = get_lang_fallback(event, ("en",))

    # 主催者
    promoter = item.get("promoter") or {}
    promoter_ja = get_lang_fallback(promoter, ("ja", "en"))
    promoter_en = get_lang_fallback(promoter, ("en",))

    # 開催地
    location = item.get("location") or {}
    location_ja = get_lang_fallback(location, ("ja", "en"))
    location_en = get_lang_fallback(location, ("en",))

    # 国・地域（コードから日本語名に変換）
    address_country = convert_country_code(str(item.get("address_country", "") or "").strip())

    # 日付（発表年月日は publication_date 優先）
    from_date = normalize_date_yyyymmdd(pick_from_date(item))
    to_date = normalize_date_yyyymmdd(item.get("to_event_date"))

    # 発表形態（Excelルールに従いコード値のみ）
    ptype = presentation_type_choice(item.get("presentation_type"))

    # 記述言語
    lang_str = convert_languages(item.get("languages"))

    # 招待の有無（レビュー指摘: 2 : 招待無し / 1 : 招待有り）
    invited = invited_choice_kotohappyo(item.get("invited"))

    # URL
    url = find_see_also_url(item.get("see_also"), "url")

    # 識別子
    identifiers = item.get("identifiers") or {}
    cinii = open_depo = doi = ""
    if isinstance(identifiers, dict):
        cinii = join_values(as_list(identifiers.get("cinii_cr_id")))
        open_depo = join_values(as_list(identifiers.get("opendepo_id")))
        doi = join_values(as_list(identifiers.get("doi")))

    # 概要
    desc = item.get("description") or {}
    desc_ja = get_lang_fallback(desc, ("ja",))
    desc_en = get_lang_fallback(desc, ("en",))

    row = {
        "No.": "",
        "入力者名": inputter_name,
        "e-Rad研究者番号": erad_id,
        "共同研究番号": joint_cell,
        "科研費課題番号": "; ".join(kaken_numbers),
        "発表者名（共同発表者含）　＞　原文": presenters_ja,
        "発表者名（共同発表者含）　＞　英訳": presenters_en,
        "発表者名（共同発表者含））　＞　下線": "",
        "題目又はセッション名　＞　原文": title_ja,
        "題目又はセッション名　＞　英訳": title_en,
        "会議区分": conference_class,
        "会議名称　＞　原文": event_ja,
        "会議名称　＞　英訳": event_en,
        "主催者名称 　＞　原文": promoter_ja,
        "主催者名称 　＞　英訳": promoter_en,
        "開催場所　＞　原文": location_ja,
        "開催場所　＞　英訳": location_en,
        "開催場所　＞　開催国": address_country,
        "発表年月(日) 　＞　（自）": from_date,
        "発表年月(日) 　＞　（至）": to_date,
        "発表形態": ptype,
        "発表(記述)言語": lang_str,
        "招待の有無": invited,
        "査読": "",
        "共同作業範囲": "",
        "担当部分": "",
        "URL": url,
        "CiNiiのID": cinii,
        "OpenDepoのID": open_depo,
        "DOI": doi,
        "概要　＞　原文": desc_ja,
        "概要　＞　英訳": desc_en,
        "メモ": "",
    }

    return {h: row.get(h, "") for h in HEADERS_KOTOHAPPYO}


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS_KOTOHAPPYO, extrasaction="ignore")
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
    for it in unwrap_items(rm_data.get("presentations")):
        rows.append(make_row_kotohappyo(it, inputter_name, erad_id, project_index))

    out_path = out_dir / f"{in_path.stem}-口頭発表.csv"
    write_csv(out_path, rows)

    print(f"Wrote: {out_path} (rows={len(rows)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
