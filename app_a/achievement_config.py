"""
業績サマリー抽出の設定

achievements_summary に何を含めるかをここで調整可能。
FTS検索テキストとは独立しているため、検索結果には影響しない。
"""

# 対象セクション
SECTIONS = [
    'published_papers',
    'books_etc',
    'misc',
    'presentations',
    'awards',
    'research_projects',
    'works',
    'research_experience',
    'education',
    'committee_memberships',
    'teaching_experience',
    'association_memberships',
    'research_interests',
    'research_areas',
]

# タイトル抽出に使うフィールド（優先順位順）
TITLE_FIELDS = [
    'paper_title',
    'title',
    'award_title',
    'presentation_title',
    'name',
    'work_title',
    'research_field',
    'subject',
    'committee_name',
    'association_name',
]

# 保持するフィールド（True: 保持, False: 除外）
KEEP_FIELDS = {
    'title_ja': True,           # 日本語タイトル
    'title_en': True,           # 英語タイトル
    'authors': False,           # 著者名
    'publication_name': False,  # 出版物名
    'publication_date': False,  # 出版日
    'url': True,                # researchmap URL
}

# テキスト長制限
MAX_TITLE_LENGTH = 200


def extract_achievements_summary(researchmap_data: dict) -> list:
    """
    researchmap_data から軽量な業績サマリーを抽出

    Returns:
        [{"s": "section", "ja": "日本語タイトル", "en": "English title", "u": "URL"}, ...]
    """
    if not researchmap_data:
        return []

    achievements = []

    for section in SECTIONS:
        section_data = researchmap_data.get(section, {})
        items = section_data.get('items', [])

        for item in items:
            entry = {'s': section}

            # タイトル抽出
            for field in TITLE_FIELDS:
                if field in item:
                    title_obj = item[field]
                    if isinstance(title_obj, dict):
                        if KEEP_FIELDS['title_ja']:
                            ja = title_obj.get('ja', '')
                            if ja:
                                entry['ja'] = ja[:MAX_TITLE_LENGTH]
                        if KEEP_FIELDS['title_en']:
                            en = title_obj.get('en', '')
                            if en:
                                entry['en'] = en[:MAX_TITLE_LENGTH]
                    elif isinstance(title_obj, str):
                        if KEEP_FIELDS['title_ja']:
                            entry['ja'] = title_obj[:MAX_TITLE_LENGTH]
                    break

            # URL
            if KEEP_FIELDS['url']:
                api_url = item.get('@id', '')
                if api_url:
                    entry['u'] = api_url.replace('api.researchmap.jp', 'researchmap.jp')

            # タイトルかURLがあれば追加
            if entry.get('ja') or entry.get('en') or entry.get('u'):
                achievements.append(entry)

    return achievements
