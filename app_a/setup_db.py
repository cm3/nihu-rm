#!/usr/bin/env python3
"""
SQLiteデータベースの初期化スクリプト

JSONデータをSQLiteデータベースにインポートします。
業績データは個別のレコードとして保存し、URLと紐づけます。
"""

import json
import sqlite3
from pathlib import Path

# セクション名のマッピング（researchmap API → 内部名）
SECTION_MAP = {
    'published_papers': 'papers',
    'books_etc': 'books',
    'presentations': 'presentations',
    'awards': 'awards',
    'research_interests': 'research_interests',
    'research_areas': 'research_areas',
    'research_projects': 'research_projects',
    'misc': 'misc',
    'works': 'works',
    'research_experience': 'research_experience',
    'education': 'education',
    'committee_memberships': 'committee_memberships',
    'teaching_experience': 'teaching_experience',
    'association_memberships': 'association_memberships',
}

# タイトル抽出に使うフィールド（優先順位順）
TITLE_FIELDS = [
    'paper_title', 'title', 'award_title', 'presentation_title',
    'research_project_title', 'name', 'work_title', 'research_field',
    'subject', 'committee_name', 'association_name', 'organization_name',
    'course_title', 'field',
]


def create_database(db_path: Path):
    """データベースとテーブルを作成"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 既存のテーブルを削除（クリーンな再構築のため）
    cursor.execute('DROP TABLE IF EXISTS researchers')
    cursor.execute('DROP TABLE IF EXISTS researchers_fts')
    cursor.execute('DROP TABLE IF EXISTS achievements')
    cursor.execute('DROP TABLE IF EXISTS achievements_fts')

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 業績テーブル（個別エントリ）
    cursor.execute('''
        CREATE TABLE achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            researcher_id TEXT NOT NULL,
            section TEXT NOT NULL,
            title_ja TEXT,
            title_en TEXT,
            text_content TEXT NOT NULL,
            url TEXT,
            FOREIGN KEY (researcher_id) REFERENCES researchers(id)
        )
    ''')

    # 研究者の基本情報用FTS5（名前・所属での検索用）
    cursor.execute('''
        CREATE VIRTUAL TABLE researchers_fts USING fts5(
            id UNINDEXED,
            name_ja,
            name_en,
            org1,
            org2,
            position,
            tokenize='trigram'
        )
    ''')

    # 業績用FTS5（業績テキストの全文検索用）
    cursor.execute('''
        CREATE VIRTUAL TABLE achievements_fts USING fts5(
            id UNINDEXED,
            researcher_id UNINDEXED,
            section UNINDEXED,
            text_content,
            tokenize='trigram'
        )
    ''')

    # インデックス作成
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_org1 ON researchers(org1)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_org2 ON researchers(org2)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_achievements_researcher ON achievements(researcher_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_achievements_section ON achievements(section)')

    conn.commit()
    conn.close()
    print(f"Database created: {db_path}")


def extract_title(item: dict) -> tuple:
    """アイテムからタイトル（日本語・英語）を抽出"""
    title_ja = ''
    title_en = ''

    for field in TITLE_FIELDS:
        if field in item:
            title_obj = item[field]
            if isinstance(title_obj, dict):
                title_ja = title_obj.get('ja', '') or ''
                title_en = title_obj.get('en', '') or ''
                if title_ja or title_en:
                    break
            elif isinstance(title_obj, str):
                title_ja = title_obj
                break

    return title_ja[:500], title_en[:500]


def extract_text_content(item: dict) -> str:
    """アイテムから検索用テキストを抽出"""
    parts = []

    # タイトル
    title_ja, title_en = extract_title(item)
    if title_ja:
        parts.append(title_ja)
    if title_en:
        parts.append(title_en)

    # 著者名
    if 'authors' in item and isinstance(item['authors'], dict):
        for lang in ['ja', 'en']:
            if lang in item['authors'] and isinstance(item['authors'][lang], list):
                authors = []
                for author in item['authors'][lang]:
                    if isinstance(author, dict) and 'name' in author:
                        authors.append(str(author['name']))
                if authors:
                    parts.append(' '.join(authors[:5]))
                    break

    # 出版物名・機関名
    for pub_key in ['publication_name', 'publisher', 'affiliation', 'organization']:
        if pub_key in item:
            pub_obj = item[pub_key]
            if isinstance(pub_obj, dict):
                for lang in ['ja', 'en']:
                    if lang in pub_obj and pub_obj[lang]:
                        parts.append(str(pub_obj[lang]))
                        break
            elif isinstance(pub_obj, str) and pub_obj:
                parts.append(pub_obj)

    # 説明・要約
    for desc_key in ['summary', 'description', 'content', 'outline']:
        if desc_key in item:
            desc_obj = item[desc_key]
            desc_text = ''
            if isinstance(desc_obj, dict):
                desc_text = desc_obj.get('ja', '') or desc_obj.get('en', '')
            elif isinstance(desc_obj, str):
                desc_text = desc_obj
            if desc_text:
                parts.append(desc_text[:300])
                break

    # 年度
    for date_key in ['publication_date', 'year', 'start_year', 'award_date']:
        if date_key in item and item[date_key]:
            parts.append(str(item[date_key]))
            break

    return ' / '.join(parts) if parts else ''


def extract_url(item: dict) -> str:
    """アイテムからURLを抽出"""
    api_url = item.get('@id', '')
    if api_url:
        return api_url.replace('api.researchmap.jp', 'researchmap.jp')
    return ''


def extract_achievements(researchmap_data: dict, researcher_id: str) -> list:
    """ResearchMapデータから業績リストを抽出"""
    achievements = []

    if not researchmap_data:
        return achievements

    for api_section, internal_section in SECTION_MAP.items():
        section_data = researchmap_data.get(api_section, {})
        items = section_data.get('items', [])

        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            text_content = extract_text_content(item)
            if not text_content:
                continue

            title_ja, title_en = extract_title(item)
            url = extract_url(item)

            achievements.append({
                'researcher_id': researcher_id,
                'section': internal_section,
                'title_ja': title_ja,
                'title_en': title_en,
                'text_content': text_content,
                'url': url,
            })

    return achievements


def import_json_data(db_path: Path, json_dir: Path):
    """JSONデータをデータベースにインポート"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    json_files = list(json_dir.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")

    total_achievements = 0

    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        researcher_id = data['id']
        researchmap_data = data.get('researchmap_data')

        # 研究者基本情報をINSERT
        cursor.execute('''
            INSERT OR REPLACE INTO researchers
            (id, name_ja, name_en, avatar_url, org1, org2, position, researchmap_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            researcher_id,
            data['name_ja'],
            data['name_en'],
            data.get('avatar_url', ''),
            data.get('org1', ''),
            data.get('org2', ''),
            data['position'],
            data['researchmap_url'],
        ))

        # 研究者FTSにINSERT
        cursor.execute('''
            INSERT INTO researchers_fts(id, name_ja, name_en, org1, org2, position)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            researcher_id,
            data['name_ja'],
            data['name_en'],
            data.get('org1', ''),
            data.get('org2', ''),
            data['position'],
        ))

        # 業績を抽出してINSERT
        achievements = extract_achievements(researchmap_data, researcher_id)
        for ach in achievements:
            cursor.execute('''
                INSERT INTO achievements
                (researcher_id, section, title_ja, title_en, text_content, url)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                ach['researcher_id'],
                ach['section'],
                ach['title_ja'],
                ach['title_en'],
                ach['text_content'],
                ach['url'],
            ))

            # 業績FTSにINSERT
            achievement_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO achievements_fts(id, researcher_id, section, text_content)
                VALUES (?, ?, ?, ?)
            ''', (
                achievement_id,
                ach['researcher_id'],
                ach['section'],
                ach['text_content'],
            ))

        total_achievements += len(achievements)

    conn.commit()
    conn.close()
    print(f"Imported {len(json_files)} researchers with {total_achievements} achievements")


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
