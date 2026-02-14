#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shared/api_client.py — researchmap API クライアントの共通モジュール

app_a と app_c の両方から参照される API 取得関数を提供する。
"""

from __future__ import annotations

import asyncio

import httpx

from .endpoint_config import get_endpoint_list


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
