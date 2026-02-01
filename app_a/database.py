"""
データベース接続とクエリ処理
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional


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

        # ベースクエリ
        sql = "SELECT * FROM researchers WHERE 1=1"
        params = []

        # 機関1でフィルター
        if org1:
            sql += " AND org1 = ?"
            params.append(org1)

        # 機関2でフィルター
        if org2:
            sql += " AND org2 = ?"
            params.append(org2)

        # イニシャルでフィルター（一文字）
        if initial:
            sql += " AND name_en LIKE ?"
            params.append(f"{initial}%")

        # 全文検索（名前、機関、役職、業績など）
        if query:
            # trigram tokenizerは3文字以上必要
            # 3文字未満の検索語がある場合はLIKE検索にフォールバック
            query_terms = query.split()
            min_term_len = min(len(t) for t in query_terms) if query_terms else 0

            if min_term_len >= 3:
                # 3文字以上: FTS5で全文検索
                if len(query_terms) > 1:
                    fts_query = ' OR '.join(query_terms)
                else:
                    fts_query = query

                sql = """
                    SELECT r.*,
                        snippet(researchers_fts, 7, '<mark>', '</mark>', '...', 64) as papers_snippet,
                        snippet(researchers_fts, 8, '<mark>', '</mark>', '...', 64) as books_snippet,
                        snippet(researchers_fts, 9, '<mark>', '</mark>', '...', 64) as presentations_snippet,
                        snippet(researchers_fts, 10, '<mark>', '</mark>', '...', 64) as awards_snippet,
                        snippet(researchers_fts, 11, '<mark>', '</mark>', '...', 64) as research_interests_snippet,
                        snippet(researchers_fts, 12, '<mark>', '</mark>', '...', 64) as research_areas_snippet,
                        snippet(researchers_fts, 13, '<mark>', '</mark>', '...', 64) as research_projects_snippet,
                        snippet(researchers_fts, 14, '<mark>', '</mark>', '...', 64) as misc_snippet,
                        snippet(researchers_fts, 15, '<mark>', '</mark>', '...', 64) as works_snippet,
                        snippet(researchers_fts, 16, '<mark>', '</mark>', '...', 64) as research_experience_snippet,
                        snippet(researchers_fts, 17, '<mark>', '</mark>', '...', 64) as education_snippet,
                        snippet(researchers_fts, 18, '<mark>', '</mark>', '...', 64) as committee_memberships_snippet,
                        snippet(researchers_fts, 19, '<mark>', '</mark>', '...', 64) as teaching_experience_snippet,
                        snippet(researchers_fts, 20, '<mark>', '</mark>', '...', 64) as association_memberships_snippet
                    FROM researchers_fts
                    JOIN researchers r ON r.id = researchers_fts.id
                    WHERE researchers_fts MATCH ?
                """
                params = [fts_query]
            else:
                # 3文字未満: LIKE検索にフォールバック（スニペットなし）
                like_pattern = f"%{query}%"
                sql = """
                    SELECT r.*,
                        NULL as papers_snippet, NULL as books_snippet,
                        NULL as presentations_snippet, NULL as awards_snippet,
                        NULL as research_interests_snippet, NULL as research_areas_snippet,
                        NULL as research_projects_snippet, NULL as misc_snippet,
                        NULL as works_snippet, NULL as research_experience_snippet,
                        NULL as education_snippet, NULL as committee_memberships_snippet,
                        NULL as teaching_experience_snippet, NULL as association_memberships_snippet
                    FROM researchers_fts f
                    JOIN researchers r ON r.id = f.id
                    WHERE (
                        f.name_ja LIKE ? OR f.name_en LIKE ? OR
                        f.org1 LIKE ? OR f.org2 LIKE ? OR f.position LIKE ? OR
                        f.papers_text LIKE ? OR f.books_text LIKE ? OR
                        f.presentations_text LIKE ? OR f.misc_text LIKE ? OR
                        f.research_projects_text LIKE ?
                    )
                """
                params = [like_pattern] * 10

            # 機関とイニシャルのフィルターを追加
            if org1:
                sql += " AND r.org1 = ?"
                params.append(org1)
            if org2:
                sql += " AND r.org2 = ?"
                params.append(org2)
            if initial:
                sql += " AND r.name_en LIKE ?"
                params.append(f"{initial}%")

        # ソートとページネーション
        sql += " ORDER BY name_en ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # 結果を辞書に変換
        results = []
        for row in rows:
            result = dict(row)
            # researchmap_dataをJSONとしてパース
            if result.get('researchmap_data'):
                try:
                    result['researchmap_data'] = json.loads(result['researchmap_data'])
                except json.JSONDecodeError:
                    result['researchmap_data'] = None
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

        sql = "SELECT COUNT(*) as count FROM researchers WHERE 1=1"
        params = []

        if org1:
            sql += " AND org1 = ?"
            params.append(org1)

        if org2:
            sql += " AND org2 = ?"
            params.append(org2)

        if initial:
            sql += " AND name_en LIKE ?"
            params.append(f"{initial}%")

        if query:
            # trigram tokenizerは3文字以上必要（search_researchersと同じロジック）
            query_terms = query.split()
            min_term_len = min(len(t) for t in query_terms) if query_terms else 0

            if min_term_len >= 3:
                # 3文字以上: FTS5で全文検索
                if len(query_terms) > 1:
                    fts_query = ' OR '.join(query_terms)
                else:
                    fts_query = query

                sql = """
                    SELECT COUNT(*) as count FROM researchers_fts
                    JOIN researchers r ON r.id = researchers_fts.id
                    WHERE researchers_fts MATCH ?
                """
                params = [fts_query]
            else:
                # 3文字未満: LIKE検索にフォールバック
                like_pattern = f"%{query}%"
                sql = """
                    SELECT COUNT(*) as count FROM researchers_fts f
                    JOIN researchers r ON r.id = f.id
                    WHERE (
                        f.name_ja LIKE ? OR f.name_en LIKE ? OR
                        f.org1 LIKE ? OR f.org2 LIKE ? OR f.position LIKE ? OR
                        f.papers_text LIKE ? OR f.books_text LIKE ? OR
                        f.presentations_text LIKE ? OR f.misc_text LIKE ? OR
                        f.research_projects_text LIKE ?
                    )
                """
                params = [like_pattern] * 10

            if org1:
                sql += " AND r.org1 = ?"
                params.append(org1)
            if org2:
                sql += " AND r.org2 = ?"
                params.append(org2)
            if initial:
                sql += " AND r.name_en LIKE ?"
                params.append(f"{initial}%")

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
        conn = self.get_connection()
        cursor = conn.cursor()

        # A-Zの各イニシャルで件数をカウント
        initials = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        counts = {}

        for initial in initials:
            count = self.count_researchers(
                query=query,
                org1=org1,
                org2=org2,
                initial=initial
            )
            counts[initial] = count

        conn.close()
        return counts

    def get_researcher_by_id(self, researcher_id: str):
        """IDで研究者を取得"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM researchers WHERE id = ?", (researcher_id,))
        row = cursor.fetchone()

        if row:
            result = dict(row)
            if result.get('researchmap_data'):
                try:
                    result['researchmap_data'] = json.loads(result['researchmap_data'])
                except json.JSONDecodeError:
                    result['researchmap_data'] = None
            conn.close()
            return result

        conn.close()
        return None
