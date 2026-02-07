"""
データベース接続とクエリ処理

新しいテーブル構造:
- researchers: 研究者基本情報
- achievements: 業績（個別エントリ、URLと紐づけ）
- researchers_fts: 研究者名・所属の全文検索
- achievements_fts: 業績の全文検索
"""

import re
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any


# セクション名の日本語ラベル
SECTION_LABELS = {
    'papers': '論文',
    'books': '書籍',
    'presentations': '発表',
    'awards': '受賞',
    'research_interests': '研究興味',
    'research_areas': '研究分野',
    'research_projects': '研究プロジェクト',
    'misc': 'その他業績',
    'works': '作品',
    'research_experience': '研究経験',
    'education': '学歴',
    'committee_memberships': '委員会活動',
    'teaching_experience': '教育経験',
    'association_memberships': '学会活動',
}

# trigram tokenizer の最小文字数
MIN_FTS_QUERY_LENGTH = 3


def generate_snippet(text: str, query: str, context_chars: int = 50) -> str:
    """テキストからクエリを含むスニペットを生成"""
    if not text or not query:
        return text[:100] if text else ''

    # クエリの各単語で検索
    terms = query.split()
    pos = -1
    matched_term = query

    for term in terms:
        pos = text.lower().find(term.lower())
        if pos != -1:
            matched_term = term
            break

    if pos == -1:
        return text[:100] + ('...' if len(text) > 100 else '')

    start = max(0, pos - context_chars)
    end = min(len(text), pos + len(matched_term) + context_chars)
    snippet = text[start:end]

    if start > 0:
        snippet = '...' + snippet
    if end < len(text):
        snippet = snippet + '...'

    # マッチした部分をハイライト
    pattern = re.compile(re.escape(matched_term), re.IGNORECASE)
    return pattern.sub(lambda m: f'<mark>{m.group()}</mark>', snippet)


def _convert_org_fields(researcher: dict) -> dict:
    """org1/org2をorgに変換（カンマ区切り）"""
    org1 = researcher.pop('org1', None)
    org2 = researcher.pop('org2', None)
    orgs = [o for o in [org1, org2] if o]
    researcher['org'] = ','.join(orgs) if orgs else None
    return researcher


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

    def _add_org_filter(self, sql: str, params: list, org: str, prefix: str = 'r') -> tuple:
        """org フィルターを追加"""
        if org:
            org_list = [o.strip() for o in org.split(',') if o.strip()]
            if org_list:
                placeholders = ','.join(['?' for _ in org_list])
                sql += f" AND ({prefix}.org1 IN ({placeholders}) OR {prefix}.org2 IN ({placeholders}))"
                params.extend(org_list * 2)
        return sql, params

    def _add_initial_filter(self, sql: str, params: list, initial: str, prefix: str = 'r') -> tuple:
        """initial フィルターを追加"""
        if initial:
            sql += f" AND {prefix}.name_en LIKE ?"
            params.append(f"{initial}%")
        return sql, params

    def search_researchers(
        self,
        query: Optional[str] = None,
        org: Optional[str] = None,
        initial: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """研究者を検索（業績スニペット付き）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if query:
            # 業績テキストで検索し、マッチした研究者を取得
            if not self._is_short_query(query):
                fts_query = self._build_fts_query(query)
                # FTS5で業績を検索
                sql = """
                    SELECT DISTINCT a.researcher_id
                    FROM achievements_fts af
                    JOIN achievements a ON a.id = af.id
                    JOIN researchers r ON r.id = a.researcher_id
                    WHERE achievements_fts MATCH ?
                """
                params = [fts_query]
            else:
                # LIKE検索にフォールバック
                like_pattern = f"%{query}%"
                sql = """
                    SELECT DISTINCT a.researcher_id
                    FROM achievements a
                    JOIN researchers r ON r.id = a.researcher_id
                    WHERE a.text_content LIKE ?
                """
                params = [like_pattern]

            sql, params = self._add_org_filter(sql, params, org)
            sql, params = self._add_initial_filter(sql, params, initial)
            sql += " ORDER BY r.name_en ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(sql, params)
            researcher_ids = [row['researcher_id'] for row in cursor.fetchall()]

            if not researcher_ids:
                conn.close()
                return []

            # 研究者情報を取得
            placeholders = ','.join(['?' for _ in researcher_ids])
            cursor.execute(f"""
                SELECT * FROM researchers WHERE id IN ({placeholders})
                ORDER BY name_en ASC
            """, researcher_ids)
            researchers = [_convert_org_fields(dict(row)) for row in cursor.fetchall()]

            # 各研究者のマッチした業績を取得（スニペット付き）
            for researcher in researchers:
                researcher['snippets'] = self._get_matching_achievements(
                    cursor, researcher['id'], query, limit=5
                )

        else:
            # クエリなし：基本検索
            sql = "SELECT * FROM researchers r WHERE 1=1"
            params = []
            sql, params = self._add_org_filter(sql, params, org, prefix='r')
            sql, params = self._add_initial_filter(sql, params, initial, prefix='r')
            sql += " ORDER BY name_en ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(sql, params)
            researchers = [_convert_org_fields(dict(row)) for row in cursor.fetchall()]

            # クエリなしの場合はスニペットなし
            for researcher in researchers:
                researcher['snippets'] = []

        conn.close()
        return researchers

    def _get_matching_achievements(
        self,
        cursor,
        researcher_id: str,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """研究者のマッチした業績を取得"""
        if not self._is_short_query(query):
            fts_query = self._build_fts_query(query)
            cursor.execute("""
                SELECT a.id, a.section, a.title_ja, a.title_en, a.text_content, a.url,
                       snippet(achievements_fts, 3, '<mark>', '</mark>', '...', 64) as snippet_text
                FROM achievements_fts af
                JOIN achievements a ON a.id = af.id
                WHERE af.researcher_id = ? AND achievements_fts MATCH ?
                LIMIT ?
            """, [researcher_id, fts_query, limit])
        else:
            like_pattern = f"%{query}%"
            cursor.execute("""
                SELECT id, section, title_ja, title_en, text_content, url
                FROM achievements
                WHERE researcher_id = ? AND text_content LIKE ?
                LIMIT ?
            """, [researcher_id, like_pattern, limit])

        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            section = row_dict['section']

            # スニペットテキストを生成
            if 'snippet_text' in row_dict and row_dict['snippet_text']:
                snippet_text = row_dict['snippet_text']
            else:
                snippet_text = generate_snippet(row_dict['text_content'], query)

            results.append({
                'section': section,
                'label': SECTION_LABELS.get(section, section),
                'text': snippet_text,
                'url': row_dict['url'] or None,
                'title_ja': row_dict['title_ja'],
                'title_en': row_dict['title_en'],
            })

        return results

    def count_researchers(
        self,
        query: Optional[str] = None,
        org: Optional[str] = None,
        initial: Optional[str] = None
    ) -> int:
        """検索条件に一致する研究者数をカウント"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if query:
            if not self._is_short_query(query):
                fts_query = self._build_fts_query(query)
                sql = """
                    SELECT COUNT(DISTINCT a.researcher_id) as count
                    FROM achievements_fts af
                    JOIN achievements a ON a.id = af.id
                    JOIN researchers r ON r.id = a.researcher_id
                    WHERE achievements_fts MATCH ?
                """
                params = [fts_query]
            else:
                like_pattern = f"%{query}%"
                sql = """
                    SELECT COUNT(DISTINCT a.researcher_id) as count
                    FROM achievements a
                    JOIN researchers r ON r.id = a.researcher_id
                    WHERE a.text_content LIKE ?
                """
                params = [like_pattern]

            sql, params = self._add_org_filter(sql, params, org)
            sql, params = self._add_initial_filter(sql, params, initial)
        else:
            sql = "SELECT COUNT(*) as count FROM researchers r WHERE 1=1"
            params = []
            sql, params = self._add_org_filter(sql, params, org, prefix='r')
            sql, params = self._add_initial_filter(sql, params, initial, prefix='r')

        cursor.execute(sql, params)
        result = cursor.fetchone()
        conn.close()
        return result['count']

    def count_by_initial(
        self,
        query: Optional[str] = None
    ) -> Dict[str, int]:
        """各イニシャルごとの研究者数を取得"""
        counts = {}
        for initial in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            counts[initial] = self.count_researchers(query=query, initial=initial)
        return counts

    def count_by_org(
        self,
        query: Optional[str] = None
    ) -> Dict[str, int]:
        """各機関ごとの研究者数を取得"""
        org_list = ['歴博', '国文研', '国語研', '日文研', '地球研', '民博', '機構本部']
        counts = {}
        for org_name in org_list:
            counts[org_name] = self.count_researchers(query=query, org=org_name)
        return counts

    def get_facet_counts(
        self,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """イニシャル別・機関別の件数を取得"""
        return {
            "initials": self.count_by_initial(query=query),
            "orgs": self.count_by_org(query=query)
        }

    def get_researcher_by_id(self, researcher_id: str) -> Optional[Dict[str, Any]]:
        """IDで研究者を取得"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM researchers WHERE id = ?", (researcher_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return _convert_org_fields(dict(row))
        return None
