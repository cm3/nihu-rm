#!/usr/bin/env python3
"""
API リグレッションテスト

generate_fixtures.py で生成したフィクスチャを使用して
APIの動作を検証します。

使用方法:
    pytest tests/test_api.py -v
"""

import json
from pathlib import Path

import pytest

from app_a.database import Database


# フィクスチャファイルを読み込み
FIXTURES_FILE = Path(__file__).parent / "fixtures" / "api_fixtures.json"


def load_fixtures():
    """フィクスチャを読み込む"""
    if not FIXTURES_FILE.exists():
        pytest.skip(f"Fixtures file not found: {FIXTURES_FILE}\nRun 'python -m tests.generate_fixtures' first.")
    with open(FIXTURES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db():
    """データベース接続"""
    return Database()


@pytest.fixture(scope="module")
def fixtures():
    """テストフィクスチャ"""
    return load_fixtures()


class TestSearchResearchers:
    """研究者検索APIのテスト"""

    def test_all_researchers(self, db):
        """全件検索"""
        total = db.count_researchers()
        assert total == 224, f"全研究者数が期待値と異なります: {total}"

    def test_query_jouhou(self, db):
        """クエリ「情報」の検索"""
        total = db.count_researchers(query="情報")
        assert total == 143, f"「情報」の検索結果が期待値と異なります: {total}"

    def test_query_gender(self, db):
        """クエリ「ジェンダー」の検索"""
        total = db.count_researchers(query="ジェンダー")
        assert total == 22, f"「ジェンダー」の検索結果が期待値と異なります: {total}"

    def test_query_indonesia(self, db):
        """クエリ「インドネシア」の検索（機構本部の研究者を含む）"""
        total = db.count_researchers(query="インドネシア")
        researchers = db.search_researchers(query="インドネシア", limit=50)
        researcher_ids = [r["id"] for r in researchers]

        assert total == 22, f"「インドネシア」の検索結果が期待値と異なります: {total}"
        assert "cm3" in researcher_ids, "機構本部の研究者(cm3)が検索結果に含まれていません"

    def test_org_chikyuken(self, db):
        """機関フィルター「地球研」"""
        total = db.count_researchers(org="地球研")
        assert total == 22, f"地球研の研究者数が期待値と異なります: {total}"

    def test_initial_k(self, db):
        """イニシャルフィルター「K」"""
        total = db.count_researchers(initial="K")
        assert total == 31, f"イニシャルKの研究者数が期待値と異なります: {total}"

    def test_gender_initial_a(self, db):
        """ジェンダー + イニシャルA（朝日先生のみ）"""
        total = db.count_researchers(query="ジェンダー", initial="A")
        researchers = db.search_researchers(query="ジェンダー", initial="A", limit=10)

        assert total == 1, f"ジェンダー+イニシャルAの結果が期待値と異なります: {total}"
        if researchers:
            assert "ASAHI" in researchers[0]["name_en"].upper(), "朝日先生が結果に含まれていません"

    def test_query_muromachi(self, db):
        """クエリ「室町」（地球研と民博にはいない）"""
        total = db.count_researchers(query="室町")
        assert total == 12, f"「室町」の検索結果が期待値と異なります: {total}"

        # 地球研と民博には該当者がいないことを確認
        researchers = db.search_researchers(query="室町", limit=50)
        for r in researchers:
            orgs = [r.get("org1"), r.get("org2")]
            assert "地球研" not in orgs, "地球研の研究者が含まれています"
            assert "民博" not in orgs, "民博の研究者が含まれています"

    def test_query_seishichou(self, db):
        """クエリ「誓詞帳」（未知語）"""
        total = db.count_researchers(query="誓詞帳")
        assert total == 1, f"「誓詞帳」の検索結果が期待値と異なります: {total}"

    def test_query_lawrencium(self, db):
        """クエリ「ローレンシウム」（0件）"""
        total = db.count_researchers(query="ローレンシウム")
        assert total == 0, f"「ローレンシウム」の検索結果が0件ではありません: {total}"


class TestFacetCounts:
    """ファセットカウントのテスト"""

    def test_facet_counts_structure(self, db):
        """ファセットカウントの構造確認"""
        facets = db.get_facet_counts()

        assert "initials" in facets, "initialsが含まれていません"
        assert "orgs" in facets, "orgsが含まれていません"

        # イニシャルは A-Z
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert letter in facets["initials"], f"イニシャル{letter}が含まれていません"

        # 機関リスト
        expected_orgs = ["歴博", "国文研", "国語研", "日文研", "地球研", "民博", "機構本部"]
        for org in expected_orgs:
            assert org in facets["orgs"], f"機関{org}が含まれていません"

    def test_facet_counts_with_query(self, db):
        """クエリ付きファセットカウント"""
        facets = db.get_facet_counts(query="室町")

        # 地球研と民博は0件のはず
        assert facets["orgs"]["地球研"] == 0, "地球研が0件ではありません"
        assert facets["orgs"]["民博"] == 0, "民博が0件ではありません"


class TestSnippets:
    """スニペット機能のテスト"""

    def test_snippets_with_query(self, db):
        """クエリ時にスニペットが返される"""
        researchers = db.search_researchers(query="ジェンダー", limit=5)

        for r in researchers:
            assert "snippets" in r, "snippetsフィールドがありません"
            assert len(r["snippets"]) > 0, "スニペットが空です"
            assert len(r["snippets"]) <= 5, "スニペットが5件を超えています"

            for snippet in r["snippets"]:
                assert "section" in snippet, "sectionがありません"
                assert "label" in snippet, "labelがありません"
                assert "text" in snippet, "textがありません"
                assert "<mark>" in snippet["text"], "ハイライトがありません"

    def test_snippets_without_query(self, db):
        """クエリなしの場合はスニペットが空"""
        researchers = db.search_researchers(limit=5)

        for r in researchers:
            assert "snippets" in r, "snippetsフィールドがありません"
            assert len(r["snippets"]) == 0, "クエリなしでスニペットが返されています"

    def test_snippet_has_url(self, db):
        """スニペットにURLが含まれる"""
        researchers = db.search_researchers(query="インドネシア", limit=5)

        url_found = False
        for r in researchers:
            for snippet in r.get("snippets", []):
                if snippet.get("url"):
                    url_found = True
                    assert "researchmap.jp" in snippet["url"], "URLがresearchmapではありません"
                    break

        assert url_found, "URLを含むスニペットが見つかりませんでした"
