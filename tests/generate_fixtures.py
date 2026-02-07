#!/usr/bin/env python3
"""
テスト用フィクスチャ（期待値）を生成するスクリプト

APIを実行して返り値をJSONファイルに保存します。
保存された値はtest_api.pyでリグレッションテストに使用されます。

使用方法:
    python -m tests.generate_fixtures
"""

import json
from pathlib import Path
from app_a.database import Database

# テストケース定義
# ISSUES.mdに基づく
TEST_CASES = [
    {
        "id": "all",
        "description": "全件の確認",
        "params": {},
        "expected_total": 224,
    },
    {
        "id": "query_jouhou",
        "description": "情報: 全研究所にいる、ページングの確認",
        "params": {"query": "情報"},
        "expected_total": 143,
    },
    {
        "id": "query_gender",
        "description": "ジェンダー: 全研究所にいる、ページングのない場合の確認",
        "params": {"query": "ジェンダー"},
        "expected_total": 22,
    },
    {
        "id": "query_indonesia",
        "description": "インドネシア: 機構本部だけの人間もひっかかるか",
        "params": {"query": "インドネシア"},
        "expected_total": 22,
    },
    {
        "id": "org_chikyuken",
        "description": "地球研のみ: 機関の基本クエリ",
        "params": {"org": "地球研"},
        "expected_total": 22,
    },
    {
        "id": "initial_k",
        "description": "イニシャルK: イニシャルの基本クエリ",
        "params": {"initial": "K"},
        "expected_total": 31,
    },
    {
        "id": "gender_initial_a",
        "description": "ジェンダー+イニシャルA: 朝日先生のみ、researchmap上の重複データの確認",
        "params": {"query": "ジェンダー", "initial": "A"},
        "expected_total": 1,
    },
    {
        "id": "query_muromachi",
        "description": "室町: 地球研と民博にはいない、機関グレーアウトの確認",
        "params": {"query": "室町"},
        "expected_total": 12,
    },
    {
        "id": "query_seishichou",
        "description": "誓詞帳: 未知語になりやすい語の確認",
        "params": {"query": "誓詞帳"},
        "expected_total": 1,
    },
    {
        "id": "query_lawrencium",
        "description": "ローレンシウム: 0件の確認",
        "params": {"query": "ローレンシウム"},
        "expected_total": 0,
    },
]


def generate_fixtures():
    """フィクスチャを生成してJSONに保存"""
    db = Database()
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    results = []

    for case in TEST_CASES:
        print(f"Testing: {case['id']} - {case['description']}")

        # 件数を取得
        total = db.count_researchers(**case["params"])

        # 研究者リストを取得（最大50件）
        researchers = db.search_researchers(**case["params"], limit=50)

        # 結果を保存
        fixture = {
            "id": case["id"],
            "description": case["description"],
            "params": case["params"],
            "expected_total": case["expected_total"],
            "actual_total": total,
            "researcher_ids": [r["id"] for r in researchers],
            "match": total == case["expected_total"],
        }

        results.append(fixture)

        status = "✓" if fixture["match"] else "✗"
        print(f"  {status} Expected: {case['expected_total']}, Actual: {total}")

    # 全結果をJSONに保存
    output_file = fixtures_dir / "api_fixtures.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nFixtures saved to: {output_file}")

    # サマリー
    passed = sum(1 for r in results if r["match"])
    print(f"\nSummary: {passed}/{len(results)} tests match expected values")

    return results


if __name__ == "__main__":
    generate_fixtures()
