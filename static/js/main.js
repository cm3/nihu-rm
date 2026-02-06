// 状態管理
const state = {
    query: '',
    orgs: [],  // 複数機関を配列で管理（OR条件）
    initial: '',
    page: 1,
    pageSize: 50,
    organizations: [],
    initialCounts: {},
    orgCounts: {}
};

// 初期化
document.addEventListener('DOMContentLoaded', async () => {
    loadStateFromUrl(); // URLパラメータから状態を復元（最初に実行）
    await loadOrganizations(); // 機関リストを読み込み、state.orgsに基づいてチェック状態を設定
    setupEventListeners();
    await loadFacetCounts(); // イニシャル別・機関別件数を読み込み
    await performSearch();
});

// URLパラメータから状態を読み込み
function loadStateFromUrl() {
    const params = new URLSearchParams(window.location.search);

    if (params.has('query')) state.query = params.get('query');
    if (params.has('org')) {
        const orgValue = params.get('org');
        if (orgValue === 'none') {
            // 全部外し状態
            state.orgs = ['none'];
        } else {
            // カンマ区切りの機関を配列に変換
            state.orgs = orgValue.split(',').filter(o => o.trim());
        }
    }
    if (params.has('initial')) state.initial = params.get('initial');
    if (params.has('page')) state.page = parseInt(params.get('page')) || 1;
}

// 状態をURLに反映
function updateUrl() {
    const params = new URLSearchParams();

    if (state.query) params.set('query', state.query);
    if (state.orgs.length > 0) params.set('org', state.orgs.join(','));
    if (state.initial) params.set('initial', state.initial);
    if (state.page > 1) params.set('page', state.page);

    const url = params.toString() ? `?${params.toString()}` : window.location.pathname;
    window.history.pushState({}, '', url);
}

// 機関リストを読み込み
async function loadOrganizations() {
    try {
        const response = await fetch('api/organizations');
        state.organizations = await response.json();
        renderOrganizationFilters();
    } catch (error) {
        console.error('Failed to load organizations:', error);
    }
}

// イニシャル別・機関別件数を読み込み
async function loadFacetCounts() {
    try {
        const params = new URLSearchParams();
        if (state.query) params.append('query', state.query);

        const response = await fetch(`api/facet-counts?${params}`);
        const data = await response.json();
        state.initialCounts = data.initials;
        state.orgCounts = data.orgs;
        updateInitialButtons();
        updateOrgCheckboxes();
    } catch (error) {
        console.error('Failed to load facet counts:', error);
    }
}

// イニシャルボタンの状態を更新
function updateInitialButtons() {
    document.querySelectorAll('.filter-initial').forEach(button => {
        const initial = button.dataset.initial;
        if (initial === '') {
            // "全て"ボタンは常に有効
            button.disabled = false;
            button.classList.remove('is_disabled');
        } else {
            const count = state.initialCounts[initial] || 0;
            if (count === 0) {
                button.disabled = true;
                button.classList.add('is_disabled');
            } else {
                button.disabled = false;
                button.classList.remove('is_disabled');
            }
        }
    });
}

// 機関チェックボックスの状態を更新（件数0はグレーアウト、チェック状態は維持）
function updateOrgCheckboxes() {
    document.querySelectorAll('#orgFilters input[type="checkbox"]').forEach(checkbox => {
        const orgId = checkbox.value;
        const count = state.orgCounts[orgId] || 0;
        const container = checkbox.closest('.kikan-check');

        if (count === 0) {
            checkbox.disabled = true;
            container.classList.add('is_disabled');
            // チェック状態は維持（外さない）
        } else {
            checkbox.disabled = false;
            container.classList.remove('is_disabled');
        }
    });
}

// 機関フィルターをレンダリング
function renderOrganizationFilters() {
    const container = document.getElementById('orgFilters');

    // state.orgs の状態に応じてチェック状態を決定
    // - [] (空配列): 全選択
    // - ['none']: 全部外し
    // - その他: 指定された機関のみ
    const isAllSelected = state.orgs.length === 0;
    const isNoneSelected = state.orgs.length === 1 && state.orgs[0] === 'none';

    container.innerHTML = state.organizations.map(org => {
        let isChecked;
        if (isNoneSelected) {
            isChecked = false;  // 全部外し
        } else if (isAllSelected) {
            isChecked = true;   // 全選択
        } else {
            isChecked = state.orgs.includes(org.id);  // 一部選択
        }
        return `
            <div class="kikan-check">
                <input type="checkbox" id="org_${org.id}" value="${org.id}" data-org="${org.id}" ${isChecked ? 'checked' : ''}>
                <label for="org_${org.id}">${org.name}</label>
            </div>
        `;
    }).join('');

    // チェックボックスのイベントリスナー
    container.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', handleOrgFilterChange);
    });
}

// イベントリスナーの設定
function setupEventListeners() {
    // 検索ボックスの値を復元
    const searchInput = document.getElementById('searchQuery');
    if (state.query) {
        searchInput.value = state.query;
    }

    // イニシャルフィルターボタンの状態を復元
    document.querySelectorAll('.filter-initial').forEach(button => {
        const buttonInitial = button.dataset.initial;
        if (buttonInitial === state.initial) {
            button.classList.add('is_active');
        } else {
            button.classList.remove('is_active');
        }
    });

    // 検索ボタン
    document.getElementById('searchButton').addEventListener('click', handleSearch);

    // Enterキーで検索
    searchInput.addEventListener('keypress', (e) => {
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
async function handleSearch() {
    state.query = document.getElementById('searchQuery').value;
    state.page = 1;
    updateUrl();
    await loadFacetCounts(); // イニシャル件数を更新
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
    updateUrl();
    performSearch();
}

// 機関フィルター（クライアントサイドでフィルタリング）
function handleOrgFilterChange() {
    // チェックされている機関を取得（disabledは除外）
    const checkedInputs = document.querySelectorAll('#orgFilters input[type="checkbox"]:checked');
    const enabledInputs = document.querySelectorAll('#orgFilters input[type="checkbox"]:not(:disabled)');

    if (checkedInputs.length === 0) {
        // 全部外し → 'none' をセット
        state.orgs = ['none'];
    } else if (checkedInputs.length === enabledInputs.length && enabledInputs.length > 0) {
        // 全選択 → 空配列（URLパラメータなし）
        state.orgs = [];
    } else {
        // 一部選択
        state.orgs = Array.from(checkedInputs).map(input => input.value);
    }
    updateUrl();

    // クライアントサイドで表示/非表示を切り替え（APIリクエスト不要）
    applyOrgFilter();
}

// 表示件数を更新
function updateVisibleCount(visibleCount) {
    document.getElementById('resultCount').textContent = `${visibleCount}件の研究者が見つかりました`;
}

// リセット
async function handleReset() {
    state.query = '';
    state.orgs = [];
    state.initial = '';
    state.page = 1;

    document.getElementById('searchQuery').value = '';

    // イニシャルフィルターをリセット
    document.querySelectorAll('.filter-initial').forEach(btn => {
        btn.classList.remove('is_active');
    });
    document.querySelector('.filter-initial[data-initial=""]').classList.add('is_active');

    // 機関チェックボックスを全てチェック（デフォルト状態に戻す）
    document.querySelectorAll('#orgFilters input[type="checkbox"]').forEach(input => {
        input.checked = true;
    });

    updateUrl();
    await loadFacetCounts(); // イニシャル件数を更新
    performSearch();
}

// 検索実行
async function performSearch() {
    const params = new URLSearchParams();

    if (state.query) params.append('query', state.query);
    // org はクライアントサイドでフィルタするためAPIには送らない
    if (state.initial) params.append('initial', state.initial);
    params.append('page', state.page);
    params.append('page_size', state.pageSize);

    try {
        showLoading();
        const response = await fetch(`api/researchers?${params}`);
        const data = await response.json();

        renderResults(data);
        renderPagination(data);

        // 検索結果表示後にクライアントサイドで機関フィルタを適用
        applyOrgFilter();
    } catch (error) {
        showError('検索中にエラーが発生しました');
        console.error('Search error:', error);
    }
}

// 機関フィルタを適用（表示/非表示の切り替え）
function applyOrgFilter() {
    // disabledでない（有効な）チェックボックスのみを対象にする
    const enabledInputs = document.querySelectorAll('#orgFilters input[type="checkbox"]:not(:disabled)');
    const checkedInputs = document.querySelectorAll('#orgFilters input[type="checkbox"]:checked');
    const selectedOrgs = Array.from(checkedInputs).map(input => input.value);

    // 有効なチェックボックスが全てチェックされているか
    const isAllSelected = checkedInputs.length === enabledInputs.length && enabledInputs.length > 0;
    // state.orgs が ['none'] または checkedInputs が 0 の場合は全非表示
    const isNoneSelected = (state.orgs.length === 1 && state.orgs[0] === 'none') || checkedInputs.length === 0;

    let visibleCount = 0;
    document.querySelectorAll('.bl_articleList_item').forEach(item => {
        const itemOrgs = (item.dataset.org || '').split(',').filter(o => o);
        let isVisible;
        if (isNoneSelected) {
            isVisible = false;  // 全て未チェックなら全非表示
        } else if (isAllSelected) {
            isVisible = true;   // 全てチェックなら全表示
        } else {
            isVisible = itemOrgs.some(org => selectedOrgs.includes(org));
        }
        item.classList.toggle('is_hidden', !isVisible);
        if (isVisible) visibleCount++;
    });

    updateVisibleCount(visibleCount);
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
        // スニペットはAPIから直接取得（URLも含まれている）
        const snippets = researcher.snippets || [];

        // data-org: org1とorg2をカンマ区切りで結合（クライアントサイドフィルタ用）
        const orgs = [researcher.org1, researcher.org2].filter(o => o).join(',');

        return `
            <div class="bl_articleList_item"
                 data-name="${researcher.name_en}"
                 data-org="${orgs}"
                 data-initial="${getInitial(researcher.name_en)}">
                <div class="bl_researcher_main">
                    <div class="bl_researcher_left">
                        <div class="bl_researcher_avatar_wrapper">
                            ${researcher.avatar_url
                                ? `<img src="${researcher.avatar_url}" alt="${researcher.name_ja}" class="bl_researcher_avatar" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"><div class="bl_researcher_avatar_placeholder" style="display:none"></div>`
                                : '<div class="bl_researcher_avatar_placeholder"></div>'}
                        </div>
                        <div class="bl_researcher_nameBlock">
                            <div class="bl_researcher_name">${researcher.name_ja}</div>
                            <div class="bl_researcher_nameEn">${researcher.name_en}</div>
                            ${renderOrgTags(researcher.org1, researcher.org2)}
                        </div>
                    </div>
                    <div class="bl_researcher_right">
                        <div class="bl_researcher_position">${researcher.position.replace(/／/g, '<br>')}</div>
                        <div class="bl_researcher_link">
                            <a href="${researcher.researchmap_url}" target="_blank" rel="noopener">
                                詳細プロフィール（researchmap）
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:-1px;margin-left:4px;">
                                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                                    <polyline points="15 3 21 3 21 9"></polyline>
                                    <line x1="10" y1="14" x2="21" y2="3"></line>
                                </svg>
                            </a>
                        </div>
                    </div>
                </div>
                ${snippets.length > 0
                    ? `<div class="bl_researcher_snippets">
                        ${snippets.map(s => `
                            <div class="bl_snippet">
                                <span class="bl_snippet_label">${s.label}:</span>
                                ${s.url
                                    ? `<a href="${s.url}" target="_blank" rel="noopener" class="bl_snippet_link">
                                        <span class="bl_snippet_text">${s.text}</span>
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px;margin-left:4px;">
                                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                                            <polyline points="15 3 21 3 21 9"></polyline>
                                            <line x1="10" y1="14" x2="21" y2="3"></line>
                                        </svg>
                                    </a>`
                                    : `<span class="bl_snippet_text">${s.text}</span>`
                                }
                            </div>
                        `).join('')}
                    </div>`
                    : ''}
            </div>
        `;
    }).join('');
}

// イニシャルを取得
function getInitial(name) {
    if (!name) return '';
    return name.charAt(0).toUpperCase();
}

// 機関タグのマッピング
function getOrgTagClass(orgName) {
    const orgMap = {
        '機構本部': 'honbu',
        '歴博': 'rekihaku',
        '国文研': 'kokubun',
        '国語研': 'kokugo',
        '日文研': 'nichibun',
        '地球研': 'chikyu',
        '民博': 'minpaku'
    };
    return orgMap[orgName] || '';
}

// 機関タグを生成
function renderOrgTags(org1, org2) {
    const tags = [];
    if (org1) {
        const className = getOrgTagClass(org1);
        if (className) {
            tags.push(`<span class="bl_orgTag bl_orgTag_${className}">${org1}</span>`);
        }
    }
    if (org2) {
        const className = getOrgTagClass(org2);
        if (className) {
            tags.push(`<span class="bl_orgTag bl_orgTag_${className}">${org2}</span>`);
        }
    }
    return tags.length > 0 ? `<div class="bl_researcher_tags">${tags.join('')}</div>` : '';
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
    updateUrl();
    performSearch();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}
