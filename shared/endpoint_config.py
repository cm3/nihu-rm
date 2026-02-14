#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared/endpoint_config.py — researchmap エンドポイント設定の共通モジュール

app_a と app_c の両方から参照されるエンドポイント関連関数を提供する。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List


# データディレクトリ（shared/ から見て ../data/）
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
