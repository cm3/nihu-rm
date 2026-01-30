#!/usr/bin/env python3
"""
SQLiteデータベースの初期化スクリプト

JSONデータをSQLiteデータベースにインポートします。
"""

import json
import sqlite3
from pathlib import Path


def create_database(db_path: Path):
    """データベースとテーブルを作成"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 既存のテーブルを削除（クリーンな再構築のため）
    cursor.execute('DROP TABLE IF EXISTS researchers')
    cursor.execute('DROP TABLE IF EXISTS researchers_fts')

    # 研究者テーブル
    cursor.execute('''
        CREATE TABLE researchers (
            id TEXT PRIMARY KEY,
            name_ja TEXT NOT NULL,
            name_en TEXT NOT NULL,
            avatar_url TEXT,
            org1 TEXT,
            org2 TEXT,
            position TEXT,
            researchmap_url TEXT NOT NULL,
            researchmap_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 全文検索用の仮想テーブル（FTS5）
    # content=''で自己完結型にする（業績データはresearchersテーブルにないため）
    # tokenize='trigram'で日本語（CJK）テキストに対応
    # trigramは3文字のn-gramで分割するため、日本語の単語検索に適している
    cursor.execute('''
        CREATE VIRTUAL TABLE researchers_fts USING fts5(
            id UNINDEXED,
            name_ja,
            name_en,
            org1,
            org2,
            position,
            keywords,
            papers_text,
            books_text,
            presentations_text,
            awards_text,
            research_interests_text,
            research_areas_text,
            research_projects_text,
            misc_text,
            works_text,
            research_experience_text,
            education_text,
            committee_memberships_text,
            teaching_experience_text,
            association_memberships_text,
            tokenize='trigram'
        )
    ''')

    # トリガーは使用しない（業績データを含むため手動で挿入）
    # import_json_data()で直接FTS5テーブルにデータを挿入する

    # インデックス作成
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_org1 ON researchers(org1)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_org2 ON researchers(org2)')

    conn.commit()
    conn.close()
    print(f"Database created: {db_path}")


def extract_text_from_list(data_list, fields):
    """リスト形式のデータからテキストを抽出"""
    if not data_list or not isinstance(data_list, list):
        return ""

    texts = []
    for item in data_list:
        if isinstance(item, dict):
            for field in fields:
                value = item.get(field, '')
                if value:
                    texts.append(str(value))

    return ' '.join(texts)


def extract_texts_from_researchmap_items(data, separator='\n---\n'):
    """ResearchMapのitems配列からテキストを抽出（一行一業績）"""
    if not data or not isinstance(data, dict):
        return ""

    items = data.get('items', [])
    if not isinstance(items, list):
        return ""

    item_texts = []
    for item in items:
        if isinstance(item, dict):
            parts = []

            # タイトル・名称フィールド
            for title_key in [
                'paper_title', 'title', 'award_title', 'presentation_title', 'name',
                'research_field', 'field', 'subject', 'organization_name', 'course_title',
                'committee_name', 'association_name', 'work_title'
            ]:
                if title_key in item:
                    title_obj = item[title_key]
                    if isinstance(title_obj, dict):
                        for lang in ['ja', 'en']:
                            if lang in title_obj:
                                parts.append(str(title_obj[lang]))
                                break  # 最初の言語のみ
                    elif isinstance(title_obj, str):
                        parts.append(title_obj)
                    if parts:  # タイトルが見つかったらbreak
                        break

            # 著者名
            if 'authors' in item and isinstance(item['authors'], dict):
                authors = []
                for lang in ['ja', 'en']:
                    if lang in item['authors'] and isinstance(item['authors'][lang], list):
                        for author in item['authors'][lang]:
                            if isinstance(author, dict) and 'name' in author:
                                authors.append(str(author['name']))
                        if authors:
                            break
                if authors:
                    parts.append(' '.join(authors[:3]))  # 最大3名まで

            # 出版物名・機関名
            for pub_key in ['publication_name', 'publisher', 'affiliation', 'organization']:
                if pub_key in item:
                    pub_obj = item[pub_key]
                    if isinstance(pub_obj, dict):
                        for lang in ['ja', 'en']:
                            if lang in pub_obj:
                                parts.append(str(pub_obj[lang]))
                                break
                    elif isinstance(pub_obj, str):
                        parts.append(pub_obj)

            # 説明・要約（短縮版）
            for desc_key in ['summary', 'description', 'content', 'outline']:
                if desc_key in item:
                    desc_obj = item[desc_key]
                    desc_text = ''
                    if isinstance(desc_obj, dict):
                        for lang in ['ja', 'en']:
                            if lang in desc_obj:
                                desc_text = str(desc_obj[lang])
                                break
                    elif isinstance(desc_obj, str):
                        desc_text = desc_obj
                    if desc_text:
                        # 要約は200文字まで
                        parts.append(desc_text[:200])
                        break

            # 年度・期間
            for date_key in ['publication_date', 'year', 'start_year', 'award_date']:
                if date_key in item and item[date_key]:
                    parts.append(str(item[date_key]))
                    break

            if parts:
                item_texts.append(' '.join(parts))

    return separator.join(item_texts)


def extract_achievement_texts(researchmap_data):
    """ResearchMapデータから業績テキストを抽出"""
    if not researchmap_data:
        return {
            'papers': '', 'books': '', 'presentations': '', 'awards': '',
            'research_interests': '', 'research_areas': '', 'research_projects': '',
            'misc': '', 'works': '', 'research_experience': '', 'education': '',
            'committee_memberships': '', 'teaching_experience': '', 'association_memberships': ''
        }

    return {
        # 論文
        'papers': extract_texts_from_researchmap_items(
            researchmap_data.get('published_papers', {}))[:10000],
        # 書籍
        'books': extract_texts_from_researchmap_items(
            researchmap_data.get('books_etc', {}))[:10000],
        # 発表
        'presentations': extract_texts_from_researchmap_items(
            researchmap_data.get('presentations', {}))[:10000],
        # 受賞
        'awards': extract_texts_from_researchmap_items(
            researchmap_data.get('awards', {}))[:5000],
        # 研究興味
        'research_interests': extract_texts_from_researchmap_items(
            researchmap_data.get('research_interests', {}))[:5000],
        # 研究分野
        'research_areas': extract_texts_from_researchmap_items(
            researchmap_data.get('research_areas', {}))[:5000],
        # 研究プロジェクト（科研費など）
        'research_projects': extract_texts_from_researchmap_items(
            researchmap_data.get('research_projects', {}))[:10000],
        # その他の業績
        'misc': extract_texts_from_researchmap_items(
            researchmap_data.get('misc', {}))[:10000],
        # 作品
        'works': extract_texts_from_researchmap_items(
            researchmap_data.get('works', {}))[:5000],
        # 研究経験
        'research_experience': extract_texts_from_researchmap_items(
            researchmap_data.get('research_experience', {}))[:5000],
        # 学歴
        'education': extract_texts_from_researchmap_items(
            researchmap_data.get('education', {}))[:5000],
        # 委員会活動
        'committee_memberships': extract_texts_from_researchmap_items(
            researchmap_data.get('committee_memberships', {}))[:5000],
        # 教育経験
        'teaching_experience': extract_texts_from_researchmap_items(
            researchmap_data.get('teaching_experience', {}))[:5000],
        # 学会活動
        'association_memberships': extract_texts_from_researchmap_items(
            researchmap_data.get('association_memberships', {}))[:5000]
    }


def import_json_data(db_path: Path, json_dir: Path):
    """JSONデータをデータベースにインポート"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    json_files = list(json_dir.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")

    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # ResearchMapデータをJSON文字列として保存
        researchmap_data = data.get('researchmap_data')
        researchmap_data_str = json.dumps(researchmap_data, ensure_ascii=False)

        # 業績テキストを抽出
        achievement_texts = extract_achievement_texts(researchmap_data)

        # 基本データをINSERT
        cursor.execute('''
            INSERT OR REPLACE INTO researchers
            (id, name_ja, name_en, avatar_url, org1, org2, position, researchmap_url, researchmap_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['id'],
            data['name_ja'],
            data['name_en'],
            data.get('avatar_url', ''),
            data.get('org1', ''),
            data.get('org2', ''),
            data['position'],
            data['researchmap_url'],
            researchmap_data_str
        ))

        # FTS5テーブルを手動で更新（業績データを含める）
        cursor.execute('''
            INSERT INTO researchers_fts(
                id, name_ja, name_en, org1, org2, position, keywords,
                papers_text, books_text, presentations_text, awards_text, research_interests_text,
                research_areas_text, research_projects_text, misc_text, works_text,
                research_experience_text, education_text, committee_memberships_text,
                teaching_experience_text, association_memberships_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['id'],
            data['name_ja'],
            data['name_en'],
            data.get('org1', ''),
            data.get('org2', ''),
            data['position'],
            '',
            achievement_texts['papers'],
            achievement_texts['books'],
            achievement_texts['presentations'],
            achievement_texts['awards'],
            achievement_texts['research_interests'],
            achievement_texts['research_areas'],
            achievement_texts['research_projects'],
            achievement_texts['misc'],
            achievement_texts['works'],
            achievement_texts['research_experience'],
            achievement_texts['education'],
            achievement_texts['committee_memberships'],
            achievement_texts['teaching_experience'],
            achievement_texts['association_memberships']
        ))

    conn.commit()
    conn.close()
    print(f"Imported {len(json_files)} researchers with achievement data")


def main():
    db_path = Path(__file__).parent.parent / "data" / "researchers.db"
    json_dir = Path(__file__).parent.parent / "data" / "json"

    # データベース作成
    create_database(db_path)

    # JSONデータがある場合はインポート
    if json_dir.exists():
        import_json_data(db_path, json_dir)
    else:
        print(f"JSON directory not found: {json_dir}")
        print("Run download_data.py first to download researcher data")


if __name__ == "__main__":
    main()
