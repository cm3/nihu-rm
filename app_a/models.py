"""
Pydanticモデル定義
"""

from typing import Optional, Any
from pydantic import BaseModel


class Snippet(BaseModel):
    """業績スニペットモデル"""
    section: str
    label: str
    text: str
    url: Optional[str] = None
    title_ja: Optional[str] = None
    title_en: Optional[str] = None


class Researcher(BaseModel):
    """研究者モデル"""
    id: str
    name_ja: str
    name_en: str
    avatar_url: Optional[str] = None
    org: Optional[str] = None  # カンマ区切りで複数機関を格納
    position: str
    researchmap_url: str
    snippets: Optional[list[Snippet]] = None


class ResearcherListResponse(BaseModel):
    """研究者リストレスポンス"""
    total: int
    page: int
    page_size: int
    researchers: list[Researcher]


class SearchQuery(BaseModel):
    """検索クエリ"""
    query: Optional[str] = None
    org: Optional[str] = None
    initial: Optional[str] = None
    page: int = 1
    page_size: int = 50
