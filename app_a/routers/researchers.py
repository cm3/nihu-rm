"""
研究者検索APIエンドポイント
"""

from typing import Optional
from fastapi import APIRouter, Query

from ..database import Database
from ..models import ResearcherListResponse, Researcher

router = APIRouter()
db = Database()


@router.get("/researchers", response_model=ResearcherListResponse)
async def search_researchers(
    query: Optional[str] = Query(None, description="検索クエリ（名前、役職、業績など）"),
    org: Optional[str] = Query(None, description="機関でフィルター（カンマ区切りでOR条件、例: 歴博,国文研）"),
    initial: Optional[str] = Query(None, description="イニシャルでフィルター（A-Z）"),
    page: int = Query(1, ge=1, description="ページ番号"),
    page_size: int = Query(50, ge=1, le=100, description="ページサイズ")
):
    """
    研究者を検索

    - query: 全文検索クエリ
    - org: 機関フィルター（カンマ区切りでOR条件）
      - 例: org=歴博 → org1またはorg2が「歴博」の研究者
      - 例: org=歴博,国文研 → org1またはorg2が「歴博」または「国文研」の研究者
    - initial: イニシャル（A-Z、一文字）
    - page: ページ番号
    - page_size: 1ページあたりの件数
    """
    offset = (page - 1) * page_size

    # 研究者を検索
    researchers = db.search_researchers(
        query=query,
        org=org,
        initial=initial,
        limit=page_size,
        offset=offset
    )

    # 総件数を取得
    total = db.count_researchers(
        query=query,
        org=org,
        initial=initial
    )

    return ResearcherListResponse(
        total=total,
        page=page,
        page_size=page_size,
        researchers=researchers
    )


@router.get("/researchers/{researcher_id}", response_model=Researcher)
async def get_researcher(researcher_id: str):
    """
    研究者の詳細情報を取得
    """
    researcher = db.get_researcher_by_id(researcher_id)
    return researcher


@router.get("/organizations")
async def get_organizations():
    """
    機関一覧を取得
    """
    # 元のサイトに基づいた機関リスト
    organizations = [
        {"id": "歴博", "name": "国立歴史民俗博物館"},
        {"id": "国文研", "name": "国文学研究資料館"},
        {"id": "国語研", "name": "国立国語研究所"},
        {"id": "日文研", "name": "国際日本文化研究センター"},
        {"id": "地球研", "name": "総合地球環境学研究所"},
        {"id": "民博", "name": "国立民族学博物館"}
    ]
    return organizations


@router.get("/facet-counts")
async def get_facet_counts(
    query: Optional[str] = Query(None, description="検索クエリ")
):
    """
    イニシャル別・機関別の研究者数を取得

    Returns:
        {
            "initials": {"A": 10, "B": 5, ...},
            "orgs": {"歴博": 43, "国文研": 31, ...}
        }
    """
    return db.get_facet_counts(query=query)
