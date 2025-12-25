// 状態管理
const state = {
    query: '',
    org1: '',
    org2: '',
    initial: '',
    page: 1,
    pageSize: 50,
    organizations: []
};

// 初期化
document.addEventListener('DOMContentLoaded', async () => {
    await loadOrganizations();
    setupEventListeners();
    await performSearch();
});

// 機関リストを読み込み
async function loadOrganizations() {
    try {
        const response = await fetch('/api/organizations');
        state.organizations = await response.json();
        renderOrganizationFilters();
    } catch (error) {
        console.error('Failed to load organizations:', error);
    }
}

// 機関フィルターをレンダリング
function renderOrganizationFilters() {
    const container = document.getElementById('orgFilters');
    container.innerHTML = state.organizations.map(org => `
        <div class="kikan-check">
            <input type="checkbox" id="org_${org.id}" value="${org.id}" data-org="${org.id}">
            <label for="org_${org.id}">${org.name}</label>
        </div>
    `).join('');

    // チェックボックスのイベントリスナー
    container.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', handleOrgFilterChange);
    });
}

// イベントリスナーの設定
function setupEventListeners() {
    // 検索ボタン
    document.getElementById('searchButton').addEventListener('click', handleSearch);

    // Enterキーで検索
    document.getElementById('searchQuery').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleSearch();
        }
    });

    // イニシャルフィルター
    document.querySelectorAll('.filter-initial').forEach(button => {
        button.addEventListener('click', handleInitialFilter);
    });

    // リセットボタン
    document.getElementById('resetFilterButton').addEventListener('click', handleReset);
}

// 検索実行
function handleSearch() {
    state.query = document.getElementById('searchQuery').value;
    state.page = 1;
    performSearch();
}

// イニシャルフィルター
function handleInitialFilter(e) {
    const initial = e.target.dataset.initial;

    // ボタンのアクティブ状態を更新
    document.querySelectorAll('.filter-initial').forEach(btn => {
        btn.classList.remove('is_active');
    });
    e.target.classList.add('is_active');

    state.initial = initial;
    state.page = 1;
    performSearch();
}

// 機関フィルター
function handleOrgFilterChange() {
    // チェックされている機関を取得
    const checkedOrgs = Array.from(document.querySelectorAll('#orgFilters input:checked'))
        .map(input => input.value);

    // org1を使用（複数選択可能だが、APIは単一のみサポート）
    state.org1 = checkedOrgs.length > 0 ? checkedOrgs[0] : '';
    state.page = 1;
    performSearch();
}

// リセット
function handleReset() {
    state.query = '';
    state.org1 = '';
    state.org2 = '';
    state.initial = '';
    state.page = 1;

    document.getElementById('searchQuery').value = '';

    // イニシャルフィルターをリセット
    document.querySelectorAll('.filter-initial').forEach(btn => {
        btn.classList.remove('is_active');
    });
    document.querySelector('.filter-initial[data-initial=""]').classList.add('is_active');

    // 機関チェックボックスをリセット
    document.querySelectorAll('#orgFilters input:checked').forEach(input => {
        input.checked = false;
    });

    performSearch();
}

// 検索実行
async function performSearch() {
    const params = new URLSearchParams();

    if (state.query) params.append('query', state.query);
    if (state.org1) params.append('org1', state.org1);
    if (state.org2) params.append('org2', state.org2);
    if (state.initial) params.append('initial', state.initial);
    params.append('page', state.page);
    params.append('page_size', state.pageSize);

    try {
        showLoading();
        const response = await fetch(`/api/researchers?${params}`);
        const data = await response.json();

        renderResults(data);
        renderPagination(data);
    } catch (error) {
        showError('検索中にエラーが発生しました');
        console.error('Search error:', error);
    }
}

// ローディング表示
function showLoading() {
    document.getElementById('researcherList').innerHTML = '<div class="bl_loading">読み込み中...</div>';
    document.getElementById('resultCount').textContent = '読み込み中...';
}

// エラー表示
function showError(message) {
    document.getElementById('researcherList').innerHTML = `<div class="bl_error">${message}</div>`;
}

// 検索結果をレンダリング
function renderResults(data) {
    const { total, researchers } = data;

    // 結果件数
    document.getElementById('resultCount').textContent = `${total}件の研究者が見つかりました`;

    // 研究者リスト
    const container = document.getElementById('researcherList');

    if (researchers.length === 0) {
        container.innerHTML = '<div class="bl_articleList_item"><p>該当する研究者が見つかりませんでした。</p></div>';
        return;
    }

    container.innerHTML = researchers.map(researcher => {
        // スニペットを取得
        const snippets = [];
        if (state.query) {
            const snippetFields = [
                { field: 'papers_snippet', label: '論文' },
                { field: 'books_snippet', label: '書籍' },
                { field: 'presentations_snippet', label: '発表' },
                { field: 'awards_snippet', label: '受賞' },
                { field: 'research_interests_snippet', label: '研究興味' },
                { field: 'research_areas_snippet', label: '研究分野' },
                { field: 'research_projects_snippet', label: '研究プロジェクト' },
                { field: 'misc_snippet', label: 'その他業績' },
                { field: 'works_snippet', label: '作品' },
                { field: 'research_experience_snippet', label: '研究経験' },
                { field: 'education_snippet', label: '学歴' },
                { field: 'committee_memberships_snippet', label: '委員会活動' },
                { field: 'teaching_experience_snippet', label: '教育経験' },
                { field: 'association_memberships_snippet', label: '学会活動' }
            ];

            snippetFields.forEach(({ field, label }) => {
                const snippetText = researcher[field];
                if (snippetText && snippetText.includes('<mark>')) {
                    // 区切り文字で分割して個別の業績として表示（最大3件）
                    const items = snippetText.split('\n---\n')
                        .filter(item => item.includes('<mark>'))
                        .slice(0, 3);

                    items.forEach(item => {
                        snippets.push({ label, text: item.trim() });
                    });
                }
            });
        }

        return `
            <div class="bl_articleList_item"
                 data-name="${researcher.name_en}"
                 data-kikan1="${researcher.org1 || ''}"
                 data-kikan2="${researcher.org2 || ''}"
                 data-initial="${getInitial(researcher.name_en)}">
                <div>
                    ${researcher.avatar_url
                        ? `<img src="${researcher.avatar_url}" alt="${researcher.name_ja}" class="bl_researcher_avatar" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="bl_researcher_avatar_placeholder" style="display:none"></div>`
                        : '<div class="bl_researcher_avatar_placeholder"></div>'}
                </div>
                <div class="bl_researcher_info">
                    <div class="bl_researcher_name">${researcher.name_ja}</div>
                    <div class="bl_researcher_nameEn">${researcher.name_en}</div>
                    ${researcher.org1 || researcher.org2
                        ? `<div class="bl_researcher_org">${[researcher.org1, researcher.org2].filter(Boolean).join(' / ')}</div>`
                        : ''}
                    <div class="bl_researcher_position">${researcher.position}</div>
                    ${snippets.length > 0
                        ? `<div class="bl_researcher_snippets">
                            ${snippets.map(s => `
                                <div class="bl_snippet">
                                    <span class="bl_snippet_label">${s.label}:</span>
                                    <span class="bl_snippet_text">${s.text}</span>
                                </div>
                            `).join('')}
                        </div>`
                        : ''}
                    <div class="bl_researcher_link">
                        <a href="${researcher.researchmap_url}" target="_blank" rel="noopener">researchmapで見る →</a>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// イニシャルを取得
function getInitial(name) {
    if (!name) return '';
    return name.charAt(0).toUpperCase();
}

// ページネーションをレンダリング
function renderPagination(data) {
    const { total, page, page_size } = data;
    const totalPages = Math.ceil(total / page_size);

    if (totalPages <= 1) {
        document.getElementById('pagination').innerHTML = '';
        return;
    }

    const container = document.getElementById('pagination');
    let html = '';

    // 前へボタン
    html += `<button class="bl_pagination_button" ${page === 1 ? 'disabled' : ''} onclick="changePage(${page - 1})">← 前へ</button>`;

    // ページ番号
    const startPage = Math.max(1, page - 2);
    const endPage = Math.min(totalPages, page + 2);

    if (startPage > 1) {
        html += `<button class="bl_pagination_button" onclick="changePage(1)">1</button>`;
        if (startPage > 2) {
            html += '<span class="bl_pagination_info">...</span>';
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="bl_pagination_button ${i === page ? 'active' : ''}" onclick="changePage(${i})">${i}</button>`;
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            html += '<span class="bl_pagination_info">...</span>';
        }
        html += `<button class="bl_pagination_button" onclick="changePage(${totalPages})">${totalPages}</button>`;
    }

    // 次へボタン
    html += `<button class="bl_pagination_button" ${page === totalPages ? 'disabled' : ''} onclick="changePage(${page + 1})">次へ →</button>`;

    container.innerHTML = html;
}

// ページ変更
function changePage(newPage) {
    state.page = newPage;
    performSearch();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}
