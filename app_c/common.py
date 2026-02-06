#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
common.py — researchmap JSON → 機構IR様式CSV 変換スクリプト群の共通ユーティリティ

重要:
- 人間可読な Excel 入力規則と連携しているため、選択肢項目は
  "4" のような単独コードではなく "4 : 論文（国際会議録）" のような「コード : ラベル」表記を
  CSV に出力できる必要がある（該当する場合は common 側の mapper を用いる）。
- 変換ロジックは、原則として rules.md（指示書）の記述に従う。
  rules.md に無い独自の自動判別・推定は、カテゴリ側でも common 側でも行わない。
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


# =========================
# Endpoint labels (from CSV)
# =========================

# データディレクトリ（app-c/ から見て ../data/）
_DATA_DIR = Path(__file__).parent.parent / "data"
_ENDPOINT_LABELS_CSV = _DATA_DIR / "researchmap_endpoint_labels.csv"

# キャッシュ
_endpoint_labels_cache: Dict[str, Dict[str, str]] | None = None


def load_endpoint_labels() -> Dict[str, Dict[str, str]]:
    """
    researchmap_endpoint_labels.csv を読み込み、エンドポイント名をキーとした辞書を返す。

    Returns:
        {
            "published_papers": {"ja": "論文", "en": "Published Papers", "description": "..."},
            ...
        }
    """
    global _endpoint_labels_cache
    if _endpoint_labels_cache is not None:
        return _endpoint_labels_cache

    result: Dict[str, Dict[str, str]] = {}
    if _ENDPOINT_LABELS_CSV.exists():
        with _ENDPOINT_LABELS_CSV.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                endpoint = row.get("endpoint", "").strip()
                if endpoint:
                    result[endpoint] = {
                        "ja": row.get("ja", "").strip(),
                        "en": row.get("en", "").strip(),
                        "description": row.get("description", "").strip(),
                    }
    _endpoint_labels_cache = result
    return result


def get_endpoint_list() -> List[str]:
    """API から取得するエンドポイント名のリストを返す（profile は空文字）"""
    labels = load_endpoint_labels()
    # profile は空文字として扱う、それ以外はそのまま
    endpoints = []
    for ep in labels.keys():
        if ep == "profile":
            endpoints.append("")
        else:
            endpoints.append(ep)
    return endpoints


def get_endpoint_ja_label(endpoint: str) -> str:
    """エンドポイント名から日本語ラベルを取得"""
    labels = load_endpoint_labels()
    return labels.get(endpoint, {}).get("ja", endpoint)


# =========================
# Basic helpers
# =========================

def as_list(x: Any) -> List[Any]:
    """None / scalar / list を list に正規化。"""
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def uniq_preserve(xs: Iterable[str]) -> List[str]:
    """順序を保って重複除去。"""
    seen = set()
    out: List[str] = []
    for x in xs:
        s = str(x).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def unwrap_items(container: Any) -> List[Dict[str, Any]]:
    """
    researchmap のコレクションが
      - list[dict]
      - {"total_items":..., "items":[dict,...]}
    のどちらでも items を取り出して返す。
    """
    if container is None:
        return []
    if isinstance(container, list):
        return [x for x in container if isinstance(x, dict)]
    if isinstance(container, dict):
        items = container.get("items")
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    return []


def get_lang_fallback(d: Any, prefer: Tuple[str, ...] = ("ja", "en")) -> str:
    """
    多言語フィールド（例: {"ja": "...", "en": "..."}）から prefer 順に値を取得。
    d が str の場合はそのまま返す。
    """
    if d is None:
        return ""
    if isinstance(d, str):
        return d.strip()
    if isinstance(d, dict):
        for lang in prefer:
            v = d.get(lang)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def join_names(maybe_people: Any, delim: str = ",") -> str:
    """
    list[{"name":...}] / list[str] / str を 1セル用に連結（人名用）。

    仕様（ユーザー指定）:
    - 著者・発表者等の人名リスト区切りは常に「,」(前後スペースなし) に統制する。
    - 個別人名が "Surname, First" 形式（英語圏でよくある表記）の場合は
      区切りカンマとの混乱を避けるため "First Surname" に並べ替える。
      例: "Doe, John" -> "John Doe" / "Doe, John, Jr." -> "John Doe Jr."
    - 日本語（CJK）人名で姓名の間に空白がある場合は「全角スペース(　)」に統一する。
      例: "亀田 章弘" -> "亀田　章弘"
      ※空白が無い（例: "亀田章弘"）場合は安全に分割できないため変更しない。
    - 呼び出し側が delim を渡しても無視し、出力は必ず「,」になる。
    """
    canonical = ","

    # 文字列入力を「複数人名の並び」とみなす場合の区切り（カンマは人名内にあり得るため使わない）
    split_pat = re.compile(r"\s*(?:/|／|;|；)\s*")

    cjk_pat = re.compile(r"[一-龯々〆〤ぁ-ゖァ-ヺｦ-ﾟ\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\u3400-\u4dbf\uac00-\ud7af]")

    def _is_mostly_cjk(s: str) -> bool:
        if not s:
            return False
        has_cjk = bool(cjk_pat.search(s))
        has_latin = bool(re.search(r"[A-Za-z0-9]", s))
        return has_cjk and not has_latin

    def _normalize_japanese_space(s: str) -> str:
        parts = [p for p in re.split(r"\s+", s.strip()) if p]
        if len(parts) == 2 and _is_mostly_cjk(s):
            return f"{parts[0]}　{parts[1]}"
        return s

    def _normalize_person_name(s: str) -> str:
        s = s.strip()
        if not s:
            return ""

        # "Surname, First[, suffix...]" -> "First Surname suffix..."
        if "," in s:
            parts = [p.strip() for p in s.split(",") if p.strip()]
            if len(parts) >= 2:
                surname = parts[0]
                given = parts[1]
                suffix = " ".join(parts[2:]) if len(parts) >= 3 else ""
                out = f"{given} {surname}".strip()
                if suffix:
                    out = f"{out} {suffix}".strip()
                out = re.sub(r"\s+", " ", out).strip()
                return out
            s = s.replace(",", " ")
            s = re.sub(r"\s+", " ", s).strip()

        # 日本語姓名の空白を全角へ
        s = _normalize_japanese_space(s)

        s = s.strip(" ,;/／；")
        return s

    def _emit(tokens: List[str]) -> str:
        normed = [_normalize_person_name(t) for t in tokens]
        normed = [x for x in normed if x]
        return canonical.join(normed)

    if maybe_people is None:
        return ""

    if isinstance(maybe_people, str):
        s = maybe_people.strip()
        if not s:
            return ""
        tokens = [t for t in split_pat.split(s) if t and t.strip()]
        if len(tokens) >= 2:
            return _emit(tokens)
        return _normalize_person_name(s)

    if isinstance(maybe_people, list):
        tokens: List[str] = []
        for p in maybe_people:
            if p is None:
                continue
            if isinstance(p, str):
                t = p.strip()
                if t:
                    tokens.append(t)
                continue
            if isinstance(p, dict):
                name = p.get("name")
                if name is None:
                    continue
                t = str(name).strip()
                if t:
                    tokens.append(t)
        return _emit(tokens)

    return ""


# =========================
# Choice (code : label) helpers
# =========================

def choice(code: Any, label: Any, sep: str = " : ") -> str:
    """
    Excel 入力規則選択肢セルに入れるための "code : label" を生成。
    code/label のどちらかが空なら空文字（未回答）を返す。

    sep のデフォルトは " : "（スペースあり）。
    「その他」シートのみ ":" （スペースなし）を使用。
    """
    c = str(code).strip() if code is not None else ""
    l = str(label).strip() if label is not None else ""
    if not c or not l:
        return ""
    return f"{c}{sep}{l}"


def map_choice(value: Any, mapping: Mapping[str, Tuple[str, str]], *, default: str = "", sep: str = " : ") -> str:
    """
    researchmap 側の列挙値（value）を、Excel 側の "code : label" に変換する汎用 mapper。

    mapping は:
      { "researchmap_value": ("code", "label"), ... }

    sep のデフォルトは " : "（スペースあり）。
    「その他」シートのみ ":" （スペースなし）を使用。
    """
    if value is None:
        return default
    key = str(value).strip()
    if not key:
        return default
    pair = mapping.get(key)
    if not pair:
        return default
    return choice(pair[0], pair[1], sep=sep)


# =========================
# Date helpers
# =========================

_DATE_YMD = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DATE_YM = re.compile(r"^(\d{4})-(\d{2})$")
_DATE_Y = re.compile(r"^(\d{4})$")


def normalize_date_yyyymmdd(date_str: Any) -> str:
    """
    yyyy-MM-dd → yyyyMMdd
    yyyy-MM    → yyyyMM00
    yyyy       → yyyy0000
    想定外はそのまま（空なら空）
    """
    if date_str is None:
        return ""
    s = str(date_str).strip()
    if not s:
        return ""
    m = _DATE_YMD.fullmatch(s)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    m = _DATE_YM.fullmatch(s)
    if m:
        return f"{m.group(1)}{m.group(2)}00"
    m = _DATE_Y.fullmatch(s)
    if m:
        return f"{m.group(1)}0000"
    return s


# =========================
# Boolean / coded helpers
# =========================

def bool_to_12(v: Any) -> str:
    """null/False -> '2', True -> '1'（例: 査読）"""
    return "1" if v is True else "2"


def bool_to_012(v: Any) -> str:
    """null -> '0', False -> '2', True -> '1'（例: 招待/国際共著）"""
    if v is True:
        return "1"
    if v is False:
        return "2"
    return "0"


# 0:無回答 / 2:いいえ / 1:はい
BOOL_YN_012 = {
    "0": ("0", "無回答"),
    "1": ("1", "はい"),
    "2": ("2", "いいえ"),
}

def bool_to_choice_012(v: Any) -> str:
    """null->'0:無回答', False->'2:いいえ', True->'1:はい'"""
    return map_choice(bool_to_012(v), BOOL_YN_012)


# 1:査読有り / 2:査読無し
REFEREE_12 = {
    "1": ("1", "査読有り"),
    "2": ("2", "査読無し"),
}

def referee_to_choice(v: Any) -> str:
    """referee: null/False->'2:査読無し', True->'1:査読有り'"""
    return map_choice(bool_to_12(v), REFEREE_12)


# 0:無回答 / 1:国内 / 2:海外（所在地系）
DOMESTIC_OVERSEAS_012 = {
    "0": ("0", "無回答"),
    "1": ("1", "国内"),
    "2": ("2", "海外"),
}

def code_to_domestic_overseas_choice(code: Any) -> str:
    """'0'/'1'/'2' を '0:無回答' / '1:国内' / '2:海外' にする。"""
    if code is None:
        return ""
    return map_choice(str(code).strip(), DOMESTIC_OVERSEAS_012)


def publisher_fields_to_domestic_overseas_choice(publisher_ja: str, publisher_en: str) -> str:
    """
    rules.md に「出版機関の所在地」が明示フィールドではなく、
    publisher.ja / publisher.en から振り分ける、と書かれているカテゴリ向け。

      - publisher.ja が入力されている → 1:国内
      - publisher.en が入力されている → 2:海外
      - 両方無し → 0:無回答
    """
    if (publisher_ja or "").strip():
        return code_to_domestic_overseas_choice("1")
    if (publisher_en or "").strip():
        return code_to_domestic_overseas_choice("2")
    return code_to_domestic_overseas_choice("0")


def international_domestic_journal_choice(v: Any) -> str:
    """
    is_international_journal の指示（rules.md）に従うカテゴリ向け。

      - null: 未設定（default）→ 0:無回答
      - FALSE: 国内誌           → 1:国内
      - TRUE : 国際誌           → 2:海外
    """
    if v is True:
        return code_to_domestic_overseas_choice("2")
    if v is False:
        return code_to_domestic_overseas_choice("1")
    return code_to_domestic_overseas_choice("0")


# =========================
# Publisher location helpers (explicit strategy; no "auto")
# =========================

def publisher_location_choice_from_is_international_journal(v: Any) -> str:
    """
    論文向け（rules.md の指示: is_international_journal で振り分け）
      - null -> 0:無回答
      - False -> 1:国内
      - True  -> 2:海外
    """
    return international_domestic_journal_choice(v)


def publisher_location_choice_from_publisher(publisher: Any) -> str:
    """
    著書向け（rules.md の指示: publisher.ja / publisher.en で振り分け）
      - publisher.ja が入力 -> 1:国内
      - publisher.en が入力 -> 2:海外
      - 両方なし -> 0:無回答

    注意:
      - これは「推測」ではなく、指示書に記載されたルールに従う“機械的”な振り分け。
      - publisher が dict（多言語）でも、文字列でも受け付ける（文字列の場合は ja 扱い）。
    """
    if publisher is None:
        return code_to_domestic_overseas_choice("0")
    if isinstance(publisher, str):
        # dict でない場合、情報が ja/en に分解されていないので ja 扱い（入力あり）とみなす
        return code_to_domestic_overseas_choice("1") if publisher.strip() else code_to_domestic_overseas_choice("0")

    pub_ja = get_lang_fallback(publisher, ("ja",))
    pub_en = get_lang_fallback(publisher, ("en",))
    return publisher_fields_to_domestic_overseas_choice(pub_ja, pub_en)


# =========================
# URL / project helpers
# =========================

def find_see_also_url(see_also: Any, label: str = "url") -> str:
    """see_also[] のうち label が一致する要素の @id を返す。"""
    for it in as_list(see_also):
        if not isinstance(it, dict):
            continue
        if str(it.get("label", "")).strip() == label:
            return str(it.get("@id", "")).strip()
    return ""


def parse_project_id_from_iri(iri: str) -> str:
    """.../research_projects/{id} の {id} を取り出す。"""
    iri = (iri or "").strip()
    if not iri:
        return ""
    m = re.search(r"/research_projects/([^/?#]+)", iri)
    return m.group(1) if m else ""


def build_project_index(rm_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """research_projects の items を rm:id（文字列）で引ける辞書を作る。"""
    idx: Dict[str, Dict[str, Any]] = {}
    for p in unwrap_items(rm_data.get("research_projects")):
        pid = str(p.get("rm:id", "")).strip()
        if pid:
            idx[pid] = p
    return idx


def _is_kaken_grant_number(grant_number: str) -> bool:
    """
    grant_number のパターンから科研費かどうかを推定する。
    system_name が空の場合のフォールバック用（精度約98.6%）。

    科研費の grant_number パターン:
    - 数字2桁 + K + (数字 or K/F/J + 数字): 23K01047, 19KK0106, 22KF0370
    - 数字2桁 + H/J/F/A/B/C/S + 数字: 16H01941, 03J03656
    - 5-8桁の数字のみ（旧形式）: 24251017
    """
    gn = grant_number.strip()
    if not gn:
        return False

    # パターン1: 数字2桁 + K + (数字 or K/F/J + 数字)
    if re.match(r'^\d{2}K[KFJ]?\d+$', gn):
        return True
    # パターン2: 数字2桁 + H/J/F/A/B/C/S + 数字（単一英字のみ）
    if re.match(r'^\d{2}[HJFABCS]\d+$', gn):
        return True
    # パターン3: 5-8桁の数字のみ（旧形式）
    if re.match(r'^\d{5,8}$', gn):
        return True

    return False


def _is_kaken_project(proj: Dict[str, Any]) -> bool:
    """
    研究課題が科研費（KAKEN）かどうかを判定する。

    判定順序:
    1. system_name に科研費キーワードが含まれていれば科研費
    2. system_name が空の場合、grant_number のパターンから推定（精度約98.6%）
    """
    system_name = proj.get("system_name")

    kaken_keywords_ja = ("科学研究費助成事業", "科学研究費補助金")
    kaken_keywords_en = ("Grants-in-Aid for Scientific Research", "Grant-in-Aid for Scientific Research")

    if system_name:
        # 日本語チェック
        name_ja = get_lang_fallback(system_name, ("ja",))
        for kw in kaken_keywords_ja:
            if kw in name_ja:
                return True

        # 英語チェック
        name_en = get_lang_fallback(system_name, ("en",))
        for kw in kaken_keywords_en:
            if kw in name_en:
                return True

        # system_name があるが科研費キーワードを含まない → 非科研費
        return False

    # system_name が空の場合、grant_number から推定
    identifiers = proj.get("identifiers") or {}
    if isinstance(identifiers, dict):
        for gn in as_list(identifiers.get("grant_number")):
            if _is_kaken_grant_number(str(gn)):
                return True

    return False


def extract_project_numbers_and_titles(
    item: Dict[str, Any],
    project_index: Dict[str, Dict[str, Any]],
    see_also_labels: Sequence[str] = ("rm:research_projects", "rm:research_project_id"),
) -> Tuple[List[str], List[str], List[str]]:
    """
    item から研究課題情報を抽出する。

    戻り値:
      (共同研究番号, 科研費課題番号, 競争的資金タイトル)

    仕様:
    - see_also から /research_projects/{id} を辿り、research_projects から情報を抽出:
      - 科研費の場合（system_name に「科学研究費助成事業」等を含む）:
        → grant_number を科研費課題番号に追加
      - 科研費以外の場合:
        → "研究課題名（system_name）" を共同研究番号に追加
        → system_name がない場合は "研究課題名" のみ
    """
    joint_numbers: List[str] = []
    kaken_numbers: List[str] = []
    titles: List[str] = []

    # see_also からプロジェクトIDを収集
    project_ids_from_see_also: List[str] = []
    for sa in as_list(item.get("see_also")):
        if not isinstance(sa, dict):
            continue
        label = str(sa.get("label", "")).strip()
        if label not in set(see_also_labels):
            continue
        pid = parse_project_id_from_iri(str(sa.get("@id", "")))
        if pid:
            project_ids_from_see_also.append(pid)

    # 各プロジェクトを処理
    for pid in project_ids_from_see_also:
        proj = project_index.get(pid)
        if not proj:
            continue

        title = get_lang_fallback(proj.get("research_project_title"), ("ja", "en"))

        if _is_kaken_project(proj):
            # 科研費の場合: grant_number を科研費課題番号に追加
            p_ident = proj.get("identifiers") or {}
            if isinstance(p_ident, dict):
                for gn in as_list(p_ident.get("grant_number")):
                    s = str(gn).strip()
                    if not s:
                        continue
                    kaken_numbers.append(s)
        else:
            # 科研費以外の場合: "研究課題名（system_name）" を共同研究番号に追加
            if title:
                system_name = get_lang_fallback(proj.get("system_name"), ("ja", "en"))
                if system_name:
                    joint_entry = f"{title}（{system_name}）"
                else:
                    joint_entry = title
                joint_numbers.append(joint_entry)

        # titles は互換性のため残す（使用箇所があれば）
        if title:
            titles.append(title)

    return (uniq_preserve(joint_numbers), uniq_preserve(kaken_numbers), uniq_preserve(titles))


# =========================
# JSON root helpers
# =========================

def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_researchmap_data(root: Dict[str, Any]) -> Dict[str, Any]:
    """root に researchmap_data がある場合はそれを返し、無ければ root を返す。"""
    if isinstance(root.get("researchmap_data"), dict):
        return root["researchmap_data"]
    return root


def get_profile_fields(profile: Any) -> Tuple[str, str]:
    """入力者名 / e-Rad研究者番号 を返す。"""
    if not isinstance(profile, dict):
        return ("", "")

    family = get_lang_fallback(profile.get("family_name"), ("ja", "en"))
    given = get_lang_fallback(profile.get("given_name"), ("ja", "en"))
    inputter_name = f"{family}　{given}".strip("　").strip()

    identifiers = profile.get("identifiers") or {}
    erad = ""
    if isinstance(identifiers, dict):
        erad = "; ".join([str(x).strip() for x in as_list(identifiers.get("erad_id")) if str(x).strip()])
    return (inputter_name, erad)


# =========================
# Category-specific choice mappings
# =========================

# 論文: 掲載種別（published_paper_type）
PUBLISHED_PAPER_TYPE_CHOICES: Dict[str, Tuple[str, str]] = {
    "scientific_journal": ("1", "論文（学術雑誌）"),
    "research_institution": ("2", "論文（大学，研究機関紀要）"),
    "international_conference_proceedings": ("4", "論文（国際会議録）"),
    # symposium / research_society / in_book / master_thesis / doctoral_thesis / others -> 5
    "symposium": ("5", "論文（その他学術刊行物等）"),
    "research_society": ("5", "論文（その他学術刊行物等）"),
    "in_book": ("5", "論文（その他学術刊行物等）"),
    "master_thesis": ("5", "論文（その他学術刊行物等）"),
    "doctoral_thesis": ("5", "論文（その他学術刊行物等）"),
    "others": ("5", "論文（その他学術刊行物等）"),
    # 3/6/7 は選択肢になし（rules.md の注記）
}

def map_published_paper_type(value: Any) -> str:
    """papers.published_paper_type → 'code : label'"""
    return map_choice(value, PUBLISHED_PAPER_TYPE_CHOICES)


# 論文: 参加形態（担当区分） published_paper_owner_roles
# 未選択→00:無回答、lead→01、last→02、corresponding→03
PUBLISHED_PAPER_OWNER_ROLE_CHOICES: Dict[str, Tuple[str, str]] = {
    "lead": ("01", "筆頭著者"),
    "last": ("02", "最終著者"),
    "corresponding": ("03", "責任著者"),
}
PUBLISHED_PAPER_OWNER_ROLE_UNSELECTED = ("00", "無回答")

def map_published_paper_owner_roles(value: Any) -> str:
    """
    published_paper_owner_roles → 'code : label'
    - list の場合は ' / ' で連結（順序維持・重複除去）
    - 未選択（None/空/空配列）は '00:無回答'
    """
    if value is None:
        return choice(*PUBLISHED_PAPER_OWNER_ROLE_UNSELECTED)

    if isinstance(value, list):
        if not value:
            return choice(*PUBLISHED_PAPER_OWNER_ROLE_UNSELECTED)
        mapped = []
        for v in value:
            s = str(v).strip()
            if not s:
                continue
            c = map_choice(s, PUBLISHED_PAPER_OWNER_ROLE_CHOICES, default="")
            if c:
                mapped.append(c)
        mapped = uniq_preserve(mapped)
        return " / ".join(mapped) if mapped else choice(*PUBLISHED_PAPER_OWNER_ROLE_UNSELECTED)

    s = str(value).strip()
    if not s:
        return choice(*PUBLISHED_PAPER_OWNER_ROLE_UNSELECTED)

    return map_choice(s, PUBLISHED_PAPER_OWNER_ROLE_CHOICES, default=choice(*PUBLISHED_PAPER_OWNER_ROLE_UNSELECTED))


# 著書: 著書種別（book_type）
BOOK_TYPE_CHOICES: Dict[str, Tuple[str, str]] = {
    "scholarly_book": ("01", "単行本（学術書）"),
    "general_book": ("02", "単行本（一般書）"),
    "dictionary_or_encycropedia": ("03", "事典・辞書"),
    "textbook": ("04", "教科書"),
    "report": ("05", "調査報告書"),
}
BOOK_TYPE_OTHER = ("99", "その他")

def book_type_choice(value: Any) -> str:
    """
    books_etc.book_type → 'code : label'
    - None/空: 空文字（未入力）
    - 既知: 対応する 'code : label'
    - 未知: 99:その他
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    return map_choice(s, BOOK_TYPE_CHOICES, default=choice(*BOOK_TYPE_OTHER))


# 著書（共著・編著）: 著書形態（book_owner_role）
# rules.md:
#   共著→1 : 共著（編著以外）
#   編者（編著者）→2 : 単編
#   共編者（共編著者）→3 : 共編
#   監修・編纂→9 : その他
BOOK_OWNER_ROLE_SHAPE_CHOICES: Dict[str, Tuple[str, str]] = {
    "joint_work": ("1", "共著（編著以外）"),
    "editor": ("2", "単編"),
    "joint_editor": ("3", "共編"),
    "supervisor": ("9", "その他"),
    "compilation": ("9", "その他"),
}

def book_owner_role_shape_choice(value: Any) -> str:
    """
    books_etc.book_owner_role（共著・編著向け）→ 'code : label'
    - None/空: 空文字
    - 未知: 空文字（勝手にその他にしない）
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    return map_choice(s, BOOK_OWNER_ROLE_SHAPE_CHOICES, default="")


# 口頭発表: 発表形態（presentation_type）
# rules.xlsx「口頭発表」シートの会議種別の指定に従う（code : label）
PRESENTATION_TYPE_CHOICES: Dict[str, Tuple[str, str]] = {
    "oral_presentation": ("1", "口頭（一般）"),
    "invited_oral_presentation": ("2", "口頭（招待・特別）"),
    "keynote_oral_presentation": ("3", "口頭（基調）"),
    "poster_presentation": ("4", "ポスター（デモ発表含む）"),
    "public_symposium": ("5", "シンポジウム・研究ワークショップ パネル（公募）"),
    "nominated_symposium": ("6", "シンポジウム・研究ワークショップ パネル（指名）"),
    "public_discourse": ("7", "公開講演，セミナー，チュートリアル，講習，講義等"),
    "media_report": ("8", "メディア報道等"),
    "others": ("9", "その他"),
}

def presentation_type_choice(value: Any) -> str:
    """presentations.presentation_type → 'code : label'（未設定/未知は空文字）"""
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    return map_choice(s, PRESENTATION_TYPE_CHOICES, default="")


# =========================
# MISC mappings
# =========================

# MISC: 掲載種別（misc_type）
# rules.md「MISC」シートに従い、"code : label" で出力する。
_MISCTYPE: Dict[str, Tuple[str, str]] = {
    # 07 : 速報，短報
    "report_scientific_journal": ("07", "速報，短報"),
    "report_research_institution": ("07", "速報，短報"),
    # 08 : 研究発表要旨
    "summary_international_conference": ("08", "研究発表要旨"),
    "summary_national_conference": ("08", "研究発表要旨"),
    # 09 : 機関テクニカルレポート，プレプリント等
    "technical_report": ("09", "機関テクニカルレポート，プレプリント等"),
    # 05 : 総説・解説
    "introduction_scientific_journal": ("05", "総説・解説"),
    "introduction_international_proceedings": ("05", "総説・解説"),
    "introduction_research_institution": ("05", "総説・解説"),
    "introduction_other": ("05", "総説・解説"),
    # 01 : 新聞・雑誌等での執筆
    "introduction_commerce_magazine": ("01", "新聞・雑誌等での執筆"),
    # 10 : 講演資料等
    "lecture_materials": ("10", "講演資料等"),
    # 11 : 書評，文献紹介等
    "book_review": ("11", "書評，文献紹介等"),
    # 12 : 会議報告等
    "meeting_report": ("12", "会議報告等"),
    # 99:その他記事
    "others": ("99", "その他記事"),
}

def misc_type_choice(value: Any) -> str:
    """
    misc.misc_type → 'code : label'
    - None/空: 空文字
    - 未知: 空文字（勝手にその他等へ寄せない）
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    return map_choice(s, _MISCTYPE, default="")


# MISC: books_etc の翻訳担当区分（book_owner_role）を、MISC の掲載種別へ写像
# rules.md:
#   single_translation -> 03 : 翻訳業績（単著）
#   joint_translation / editing_translation -> 04 : 翻訳業績（共著・編著）
_TRANSLATION_ROLE_TO_MISC: Dict[str, Tuple[str, str]] = {
    "single_translation": ("03", "翻訳業績（単著）"),
    "joint_translation": ("04", "翻訳業績（共著・編著）"),
    "editing_translation": ("04", "翻訳業績（共著・編著）"),
}

def translation_role_to_misc_type_choice(value: Any) -> str:
    """
    books_etc.book_owner_role（翻訳）→ MISC 掲載種別 'code : label'
    - None/空: 空文字
    - 未知: 空文字
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    return map_choice(s, _TRANSLATION_ROLE_TO_MISC, default="")


# =========================
# その他（Sonota）: 種別 mappings
# =========================

# 書籍等出版物（books_etc）: 担当区分 others / 未選択 → 99:その他
SONOTA_BOOK_ROLE_CHOICES: Dict[str, Tuple[str, str]] = {
    "others": ("99", "その他"),
    # 未選択は map せず default で 99 を出す（＝未選択→99:その他）
}

def sonota_type_from_books_role(value: Any) -> str:
    """
    books_etc.book_owner_role → 'code:label'（「その他」シート用、スペースなし）
    仕様:
      - others / 未選択(空/None) → 99:その他
      - それ以外は空文字（その他CSVに入れる対象外のため）
    """
    if value is None:
        return "99:その他"
    s = str(value).strip()
    if not s or s == "others":
        return "99:その他"
    return ""


# Works（作品等）: work_type
SONOTA_WORK_TYPE_CHOICES: Dict[str, Tuple[str, str]] = {
    "artistic_activity": ("21", "芸術作品"),
    "architectural_works": ("22", "建築作品"),
    "software": ("12", "コンピュータソフト（主に教育・研究用）"),
    "database": ("11", "データベース"),
    "educational_materials": ("13", "教材"),
    # web_service / others は 99:その他（Excel指示）
    "web_service": ("99", "その他"),
    "others": ("99", "その他"),
}

def sonota_type_from_work_type(value: Any) -> str:
    """works.work_type → 'code:label'（未知/未設定は 99:その他）"""
    if value is None:
        return "99:その他"
    s = str(value).strip()
    if not s:
        return "99:その他"
    return map_choice(s, SONOTA_WORK_TYPE_CHOICES, default="99:その他", sep=":")


# メディア報道: media_coverage_type
SONOTA_MEDIA_COVERAGE_TYPE_CHOICES: Dict[str, Tuple[str, str]] = {
    "media_report": ("41", "メディア出演（テレビ・ラジオ番組）"),
    # paper/internet/pr/others は 99:その他（Excel指示）
    "paper": ("99", "その他"),
    "internet": ("99", "その他"),
    "pr": ("99", "その他"),
    "others": ("99", "その他"),
}

def sonota_type_from_media_coverage_type(value: Any) -> str:
    """media_coverage.media_coverage_type → 'code:label'（未知/未設定は 99:その他）"""
    if value is None:
        return "99:その他"
    s = str(value).strip()
    if not s:
        return "99:その他"
    return map_choice(s, SONOTA_MEDIA_COVERAGE_TYPE_CHOICES, default="99:その他", sep=":")


# 学術貢献活動: academic_contribution_type
SONOTA_ACADEMIC_CONTRIBUTION_TYPE_CHOICES: Dict[str, Tuple[str, str]] = {
    "academic_society_etc": ("51", "学術貢献活動（学会・大会・研究会・シンポジウムの企画運営等）"),
    "competition_etc": ("51", "学術貢献活動（学会・大会・研究会・シンポジウムの企画運営等）"),
    "exhibition": ("52", "学術貢献活動（展覧会）"),
    "review": ("53", "学術貢献活動（審査・学術的助言）"),
    "academic_research": ("54", "学術貢献活動（学術調査報告等）"),
    "peer_review_etc": ("55", "学術貢献活動（査読等）"),
    "cultural_property_protection": ("56", "学術貢献活動（文化財保護）"),
    "others": ("99", "その他"),
}

def sonota_type_from_academic_contribution_type(value: Any) -> str:
    """academic_contribution.academic_contribution_type → 'code:label'（未知/未設定は 99:その他）"""
    if value is None:
        return "99:その他"
    s = str(value).strip()
    if not s:
        return "99:その他"
    return map_choice(s, SONOTA_ACADEMIC_CONTRIBUTION_TYPE_CHOICES, default="99:その他", sep=":")


# 社会貢献活動: social_contribution_roles + social_contribution_type
def sonota_type_from_social(roles: Any, social_contribution_type: Any) -> str:
    """
    social_contribution_roles（役割）と social_contribution_type（種別）を組み合わせて 'code:label' を返す。
    （「その他」シート用、スペースなし）

    Excel指示:
      - lecturer → 31:社会貢献（出前授業）
      - advisor / informant → 32:社会貢献（助言・指導・情報提供）
      - planner / organizing_member → 33:社会貢献（運営参加・支援）
      - 上記以外（出演・取材協力・寄稿等）は social_contribution_type で追加判断:
          - media_report → 41:メディア出演（テレビ・ラジオ番組）
          - それ以外 → 99:その他
    """
    role_set = {str(r).strip() for r in as_list(roles) if r is not None and str(r).strip()}

    if "lecturer" in role_set:
        return "31:社会貢献（出前授業）"
    if role_set.intersection({"advisor", "informant"}):
        return "32:社会貢献（助言・指導・情報提供）"
    if role_set.intersection({"planner", "organizing_member"}):
        return "33:社会貢献（運営参加・支援）"

    sct = "" if social_contribution_type is None else str(social_contribution_type).strip()
    if sct == "media_report":
        return "41:メディア出演（テレビ・ラジオ番組）"
    return "99:その他"


def sonota_type_other(_: Any) -> str:
    """その他レスポンス → 99:その他"""
    return "99:その他"



# =========================
# Category-specific coded choices (レビュー対応)
# =========================

def conference_class_choice_kotohappyo(v: Any) -> str:
    """
    口頭発表: 会議区分（is_international_presentation）
      - 未選択(None/空) → ""（空欄）
      - False → "J:国内会議"
      - True  → "I:国際会議"
    """
    if v is None:
        return ""
    if isinstance(v, str) and not v.strip():
        return ""
    if v is True:
        return "I:国際会議"
    if v is False:
        return "J:国内会議"
    # 想定外は空欄（勝手な推定をしない）
    return ""


def invited_choice_kotohappyo(v: Any) -> str:
    """
    口頭発表: 招待の有無（invited）
      - null/未設定 → "0:無回答"
      - False → "2:招待無し"
      - True  → "1:招待有り"
    """
    if v is None:
        return "0:無回答"
    if isinstance(v, str) and not v.strip():
        return "0:無回答"
    if v is True:
        return "1:招待有り"
    if v is False:
        return "2:招待無し"
    return "0:無回答"


def request_choice_misc(v: Any) -> str:
    """
    MISC: 依頼の有無（invited を依頼として扱う）
      - null/未設定 → "0:無回答"
      - False → "2:依頼無し"
      - True  → "1:依頼有り"
    """
    if v is None:
        return "0:無回答"
    if isinstance(v, str) and not v.strip():
        return "0:無回答"
    if v is True:
        return "1:依頼有り"
    if v is False:
        return "2:依頼無し"
    return "0:無回答"


# =========================
# Language code conversion
# =========================

_LANG_MAP: Dict[str, str] = {}


def _load_lang_map() -> None:
    """data/lang.csv から言語コード→日本語ラベルのマッピングを読み込む。"""
    global _LANG_MAP
    if _LANG_MAP:
        return

    import csv
    lang_csv = _DATA_DIR / "lang.csv"
    if not lang_csv.exists():
        return

    with lang_csv.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("コード", "").strip()
            label_ja = row.get("言語(日)", "").strip()
            if code and label_ja:
                _LANG_MAP[code] = label_ja


def convert_language_code(code: str) -> str:
    """
    言語コード（例: jpn, eng）を日本語ラベル（例: 日本語, 英語）に変換する。
    該当する値がなければ元のコードをそのまま返す。
    """
    _load_lang_map()
    code = code.strip()
    return _LANG_MAP.get(code, code)


def convert_languages(langs: Any) -> str:
    """
    言語コードのリストまたは文字列を日本語ラベルに変換し、セミコロン区切りで返す。

    例:
      ["jpn", "eng"] → "日本語; 英語"
      "jpn" → "日本語"
    """
    if langs is None:
        return ""

    if isinstance(langs, list):
        converted = [convert_language_code(str(x).strip()) for x in langs if x is not None and str(x).strip()]
        return "; ".join(converted)

    return convert_language_code(str(langs).strip())
