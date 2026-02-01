"""
データベース接続とクエリ処理
"""

import re
import sqlite3
import json
from pathlib import Path
from typing import Optional


# FTS5カラムインデックス（snippet関数用）
FTS_COLUMN_INDICES = {
    'papers': 7,
    'books': 8,
    'presentations': 9,
    'awards': 10,
    'research_interests': 11,
    'research_areas': 12,
    'research_projects': 13,
    'misc': 14,
    'works': 15,
    'research_experience': 16,
    'education': 17,
    'committee_memberships': 18,
    'teaching_experience': 19,
    'association_memberships': 20,
}

# LIKE検索対象カラム
LIKE_SEARCH_COLUMNS = [
    'name_ja', 'name_en', 'org1', 'org2', 'position',
    'papers_text', 'books_text', 'presentations_text', 'misc_text', 'research_projects_text'
]

# trigram tokenizer の最小文字数
MIN_FTS_QUERY_LENGTH = 3


def generate_snippet(text: str, query: str, context_chars: int = 30) -> Optional[str]:
    """テキストからクエリを含むスニペットを生成"""
    if not text or not query:
        return None

    pos = text.lower().find(query.lower())
    if pos == -1:
        return None

    start = max(0, pos - context_chars)
    end = min(len(text), pos + len(query) + context_chars)
    snippet = text[start:end]

    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f"<mark>{m.group()}</mark>", snippet)


class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "researchers.db"
        self.db_path = str(db_path)

    def get_connection(self):
        """データベース接続を取得"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _is_short_query(self, query: str) -> bool:
        """クエリがFTS5の最小文字数未満かどうか"""
        if not query:
            return False
        terms = query.split()
        return min(len(t) for t in terms) < MIN_FTS_QUERY_LENGTH if terms else True

    def _build_fts_query(self, query: str) -> str:
        """検索クエリをFTS5形式に変換"""
        terms = query.split()
        return ' OR '.join(terms) if len(terms) > 1 else query

    def _build_snippet_columns(self) -> str:
        """FTS5スニペット取得用のSELECT句を生成"""
        snippets = []
        for name, idx in FTS_COLUMN_INDICES.items():
            snippets.append(
                f"snippet(researchers_fts, {idx}, '<mark>', '</mark>', '...', 64) as {name}_snippet"
            )
        return ', '.join(snippets)

    def _build_text_columns(self) -> str:
        """LIKE検索用のテキストカラム取得SELECT句を生成"""
        return ', '.join(f"f.{name}_text" for name in FTS_COLUMN_INDICES.keys())

    def _build_like_conditions(self) -> str:
        """LIKE検索のWHERE句を生成"""
        conditions = [f"f.{col} LIKE ?" for col in LIKE_SEARCH_COLUMNS]
        return ' OR '.join(conditions)

    def _add_filters(self, sql: str, params: list, org1: str, org2: str, initial: str, prefix: str = 'r') -> tuple:
        """org1, org2, initial フィルターを追加"""
        if org1:
            sql += f" AND {prefix}.org1 = ?"
            params.append(org1)
        if org2:
            sql += f" AND {prefix}.org2 = ?"
            params.append(org2)
        if initial:
            sql += f" AND {prefix}.name_en LIKE ?"
            params.append(f"{initial}%")
        return sql, params

    def _convert_text_to_snippets(self, result: dict, query: str) -> dict:
        """テキストカラムをスニペットに変換"""
        for name in FTS_COLUMN_INDICES.keys():
            text_col = f"{name}_text"
            if text_col in result:
                text = result.pop(text_col)
                result[f"{name}_snippet"] = generate_snippet(text, query)
        return result

    def _parse_achievements_summary(self, result: dict) -> dict:
        """achievements_summary をJSONとしてパース"""
        if result.get('achievements_summary'):
            try:
                result['achievements_summary'] = json.loads(result['achievements_summary'])
            except json.JSONDecodeError:
                result['achievements_summary'] = []
        return result

    def search_researchers(
        self,
        query: Optional[str] = None,
        org1: Optional[str] = None,
        org2: Optional[str] = None,
        initial: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ):
        """研究者を検索"""
        conn = self.get_connection()
        cursor = conn.cursor()

        use_like_search = False

        if query:
            if not self._is_short_query(query):
                # FTS5で全文検索
                fts_query = self._build_fts_query(query)
                sql = f"""
                    SELECT r.*, {self._build_snippet_columns()}
                    FROM researchers_fts
                    JOIN researchers r ON r.id = researchers_fts.id
                    WHERE researchers_fts MATCH ?
                """
                params = [fts_query]
            else:
                # LIKE検索にフォールバック
                use_like_search = True
                like_pattern = f"%{query}%"
                sql = f"""
                    SELECT r.*, {self._build_text_columns()}
                    FROM researchers_fts f
                    JOIN researchers r ON r.id = f.id
                    WHERE ({self._build_like_conditions()})
                """
                params = [like_pattern] * len(LIKE_SEARCH_COLUMNS)

            sql, params = self._add_filters(sql, params, org1, org2, initial)
        else:
            # クエリなし：基本検索
            sql = "SELECT * FROM researchers WHERE 1=1"
            params = []
            sql, params = self._add_filters(sql, params, org1, org2, initial, prefix='')
            # prefixなしの場合はカラム名のみ
            sql = sql.replace('.org1', 'org1').replace('.org2', 'org2').replace('.name_en', 'name_en')

        sql += " ORDER BY name_en ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            result = dict(row)
            if query and use_like_search:
                result = self._convert_text_to_snippets(result, query)
            result = self._parse_achievements_summary(result)
            results.append(result)

        conn.close()
        return results

    def count_researchers(
        self,
        query: Optional[str] = None,
        org1: Optional[str] = None,
        org2: Optional[str] = None,
        initial: Optional[str] = None
    ):
        """検索条件に一致する研究者数をカウント"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if query:
            if not self._is_short_query(query):
                # FTS5で全文検索
                fts_query = self._build_fts_query(query)
                sql = """
                    SELECT COUNT(*) as count FROM researchers_fts
                    JOIN researchers r ON r.id = researchers_fts.id
                    WHERE researchers_fts MATCH ?
                """
                params = [fts_query]
            else:
                # LIKE検索にフォールバック
                like_pattern = f"%{query}%"
                sql = f"""
                    SELECT COUNT(*) as count FROM researchers_fts f
                    JOIN researchers r ON r.id = f.id
                    WHERE ({self._build_like_conditions()})
                """
                params = [like_pattern] * len(LIKE_SEARCH_COLUMNS)

            sql, params = self._add_filters(sql, params, org1, org2, initial)
        else:
            sql = "SELECT COUNT(*) as count FROM researchers WHERE 1=1"
            params = []
            sql, params = self._add_filters(sql, params, org1, org2, initial, prefix='')
            sql = sql.replace('.org1', 'org1').replace('.org2', 'org2').replace('.name_en', 'name_en')

        cursor.execute(sql, params)
        result = cursor.fetchone()
        conn.close()
        return result['count']

    def count_by_initial(
        self,
        query: Optional[str] = None,
        org1: Optional[str] = None,
        org2: Optional[str] = None
    ):
        """各イニシャルごとの研究者数を取得"""
        counts = {}
        for initial in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            counts[initial] = self.count_researchers(
                query=query, org1=org1, org2=org2, initial=initial
            )
        return counts

    def get_researcher_by_id(self, researcher_id: str):
        """IDで研究者を取得"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM researchers WHERE id = ?", (researcher_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return self._parse_achievements_summary(dict(row))
        return None
