"""
Pydanticモデル定義
"""

from typing import Optional, Any
from pydantic import BaseModel


class Researcher(BaseModel):
    """研究者モデル"""
    id: str
    name_ja: str
    name_en: str
    avatar_url: Optional[str] = None
    org1: Optional[str] = None
    org2: Optional[str] = None
    position: str
    researchmap_url: str
    researchmap_data: Optional[Any] = None
    papers_snippet: Optional[str] = None
    books_snippet: Optional[str] = None
    presentations_snippet: Optional[str] = None
    awards_snippet: Optional[str] = None
    research_interests_snippet: Optional[str] = None
    research_areas_snippet: Optional[str] = None
    research_projects_snippet: Optional[str] = None
    misc_snippet: Optional[str] = None
    works_snippet: Optional[str] = None
    research_experience_snippet: Optional[str] = None
    education_snippet: Optional[str] = None
    committee_memberships_snippet: Optional[str] = None
    teaching_experience_snippet: Optional[str] = None
    association_memberships_snippet: Optional[str] = None


class ResearcherListResponse(BaseModel):
    """研究者リストレスポンス"""
    total: int
    page: int
    page_size: int
    researchers: list[Researcher]


class SearchQuery(BaseModel):
    """検索クエリ"""
    query: Optional[str] = None
    org1: Optional[str] = None
    org2: Optional[str] = None
    initial: Optional[str] = None
    page: int = 1
    page_size: int = 50
