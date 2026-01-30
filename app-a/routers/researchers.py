"""
研究者検索APIエンドポイント
"""

from typing import Optional
from fastapi import APIRouter, Query
from app.database import Database
from app.models import ResearcherListResponse, Researcher

router = APIRouter()
db = Database()


@router.get("/researchers", response_model=ResearcherListResponse)
async def search_researchers(
    query: Optional[str] = Query(None, description="検索クエリ（名前、役職、業績など）"),
    org1: Optional[str] = Query(None, description="機関1でフィルター"),
    org2: Optional[str] = Query(None, description="機関2でフィルター"),
    initial: Optional[str] = Query(None, description="イニシャルでフィルター（A-Z）"),
    page: int = Query(1, ge=1, description="ページ番号"),
    page_size: int = Query(50, ge=1, le=100, description="ページサイズ")
):
    """
    研究者を検索

    - query: 全文検索クエリ
    - org1: 機関1（機構本部、歴博、国文研、国語研、日文研、地球研、民博）
    - org2: 機関2
    - initial: イニシャル（A-Z、一文字）
    - page: ページ番号
    - page_size: 1ページあたりの件数
    """
    offset = (page - 1) * page_size

    # 研究者を検索
    researchers = db.search_researchers(
        query=query,
        org1=org1,
        org2=org2,
        initial=initial,
        limit=page_size,
        offset=offset
    )

    # 総件数を取得
    total = db.count_researchers(
        query=query,
        org1=org1,
        org2=org2,
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


@router.get("/initial-counts")
async def get_initial_counts(
    query: Optional[str] = Query(None, description="検索クエリ"),
    org1: Optional[str] = Query(None, description="機関1でフィルター"),
    org2: Optional[str] = Query(None, description="機関2でフィルター")
):
    """
    各イニシャルの研究者数を取得
    """
    counts = db.count_by_initial(query=query, org1=org1, org2=org2)
    return counts
