
        let liffId = "{{ liff_id }}";
        let apiBaseUrl = "{{ request.scheme }}://{{ request.get_host }}";
        let userAccessToken = null;
        let lineContext = null;

        // 分頁與狀態變數
        let currentTab = "my_dramas";
        let recSubTab = "pending";
        let activeCategoryFilter = "";
        let tvMainExpanded = true;
        let movieMainExpanded = true;
        let mainCategoryExpanded = true;
        let expandedDecades = { tv: new Set(), movie: new Set() };
        let expandedYears = { tv: new Set(), movie: new Set() };
        let defaultExpandedInitialized = false;

        let myDramasPage = 1;
        let myDramasPageSize = 10;
        let recsPage = 1;
        let recsPageSize = 10;
        let allDramasPage = 1;
        let allDramasPageSize = 10;

        // 全區前端資料庫 Master Lists
        let myDramasMasterList = null;
        let allDramasMasterList = null;
        let recsMasterList = null;
        let franchiseMasterList = null;

        let displayPrefs = {
            category: true,
            links: true,
            total: true,
            creator: true
        };

        // 快捷分類面板折疊狀態
        let mainCategoryCollapsed = false;
        let tvSubExpanded = false;
        let movieSubExpanded = false;
        let cachedCategoriesData = null;

        // 好友快取
        let myFriendsList = [];

        document.addEventListener("DOMContentLoaded", function() {
            loadDisplaySettings();
            initLiff();
        });

        // 規範化搜尋文字輔助函數 (忽略大小寫、空格、書名號、波浪號、冒號等所有符號)
        function normalizeSearchText(text) {
            if (!text) return "";
            return text.toString().toLowerCase().replace(/[\s《》『』~∼〜〰⁓:：!！?？\-_—–]/g, "");
        }

        // 大類面板整體折疊/展開
        function toggleMainCategorySection() {
            mainCategoryCollapsed = !mainCategoryCollapsed;
            const container = document.getElementById("main-cat-container");
            const icon = document.getElementById("main-cat-toggle-icon");
            if (mainCategoryCollapsed) {
                container.classList.add("d-none");
                icon.innerHTML = `<i class="fa-solid fa-chevron-down me-1"></i>展開面板`;
            } else {
                container.classList.remove("d-none");
                icon.innerHTML = `<i class="fa-solid fa-chevron-up me-1"></i>折疊面板`;
            }
        }

        // 判斷是否屬於 NEW 提醒類別：
        // TV：2026年7月(含)之後 + "動畫化決定"
        // 劇場版：2026年(含)之後 + "日本動畫電影製作決定"
        function isNewCategory(cat) {
            if (!cat) return false;
            if (cat === "動畫化決定" || cat === "日本動畫電影製作決定") return true;

            // TV 季番判定
            const tvMatch = cat.match(/^(\d{4})年(\d{1,2})月/);
            if (tvMatch) {
                const year = parseInt(tvMatch[1]);
                const month = parseInt(tvMatch[2]);
                if (year > 2026 || (year === 2026 && month >= 7)) {
                    return true;
                }
            }

            // 劇場版/電影判定
            const movieMatch = cat.match(/^(\d{4})年.*電影/);
            if (movieMatch) {
                const year = parseInt(movieMatch[1]);
                if (year >= 2026) {
                    return true;
                }
            }
            return false;
        }

        // 取得目前使用者的獨立已讀標籤 Storage Key
        function getReadTagsKey() {
            let uid = "universal_user";
            if (typeof userProfile !== "undefined" && userProfile && userProfile.userId) {
                uid = userProfile.userId;
            } else if (userAccessToken && userAccessToken.length > 5) {
                uid = userAccessToken.substring(0, 15);
            }
            return "drama_read_new_tags_" + uid;
        }

        function getReadTags() {
            try {
                const data = localStorage.getItem(getReadTagsKey());
                return data ? JSON.parse(data) : [];
            } catch(e) {
                return [];
            }
        }

        function markTagsAsRead(tagsArray) {
            const readList = new Set(getReadTags());
            tagsArray.forEach(t => readList.add(t));
            try {
                localStorage.setItem(getReadTagsKey(), JSON.stringify(Array.from(readList)));
            } catch(e) {}
        }


        function toggleMainCategorySection() {
            mainCategoryExpanded = !mainCategoryExpanded;
            const container = document.getElementById("main-cat-container");
            const icon = document.getElementById("main-cat-toggle-icon");
            if (mainCategoryExpanded) {
                container.classList.remove("d-none");
                icon.innerHTML = '<i class="fa-solid fa-chevron-up me-1"></i>折疊面板';
            } else {
                container.classList.add("d-none");
                icon.innerHTML = '<i class="fa-solid fa-chevron-down me-1"></i>展開面板';
            }
        }

        function toggleSectionMain(type) {
            if (type === 'tv') {
                tvMainExpanded = !tvMainExpanded;
                const label = document.getElementById("tv-toggle-label");
                const icon = document.querySelector("#toggle-tv-btn i");
                if (label) label.innerText = tvMainExpanded ? "折疊季番" : "展開季番";
                if (icon) icon.className = tvMainExpanded ? "fa-solid fa-angle-up me-1" : "fa-solid fa-angle-down me-1";
            } else {
                movieMainExpanded = !movieMainExpanded;
                const label = document.getElementById("movie-toggle-label");
                const icon = document.querySelector("#toggle-movie-btn i");
                if (label) label.innerText = movieMainExpanded ? "折疊電影" : "展開電影";
                if (icon) icon.className = movieMainExpanded ? "fa-solid fa-angle-up me-1" : "fa-solid fa-angle-down me-1";
            }
            renderVisualChips(cachedCategoriesData);
        }

        function toggleDecade(type, decade) {
            decade = parseInt(decade);
            if (expandedDecades[type].has(decade)) {
                expandedDecades[type].delete(decade);
            } else {
                expandedDecades[type].add(decade);
            }
            renderVisualChips(cachedCategoriesData);
        }

        function toggleYear(type, year) {
            year = parseInt(year);
            if (expandedYears[type].has(year)) {
                expandedYears[type].delete(year);
            } else {
                expandedYears[type].add(year);
            }
            renderVisualChips(cachedCategoriesData);
        }

        function clearCategoryFilter() {
            activeCategoryFilter = "";
            const mySelect = document.getElementById("my-dramas-cat-select");
            const allSelect = document.getElementById("all-dramas-cat-select");
            if (mySelect) mySelect.value = "";
            if (allSelect) allSelect.value = "";
            triggerMyDramasSearch();
            triggerAllDramasSearch();
            renderVisualChips(cachedCategoriesData);
        }

        function parseYearAndDecade(cat) {
            const match = cat.match(/(\d{4})/);
            if (match) {
                const year = parseInt(match[1]);
                const decade = Math.floor(year / 10) * 10;
                return { hasYear: true, year: year, decade: decade };
            }
            return { hasYear: false, year: 0, decade: 0 };
        }

        function buildCategoryTree(catList, countsObj) {
            const tree = { decades: {}, otherItems: [] };
            catList.forEach(cat => {
                const count = countsObj ? (countsObj[cat] || 0) : 0;
                const info = parseYearAndDecade(cat);
                if (!info.hasYear) {
                    tree.otherItems.push({ cat, count });
                } else {
                    const d = info.decade;
                    const y = info.year;
                    if (!tree.decades[d]) {
                        tree.decades[d] = { decade: d, totalCount: 0, years: {} };
                    }
                    tree.decades[d].totalCount += count;

                    if (!tree.decades[d].years[y]) {
                        tree.decades[d].years[y] = { year: y, totalCount: 0, items: [] };
                    }
                    tree.decades[d].years[y].totalCount += count;
                    tree.decades[d].years[y].items.push({ cat, count });
                }
            });
            return tree;
        }

        // 渲染依十年與每一年層級折疊/展開的細分 Chips
        function renderVisualChips(data) {
            if (!data) return;
            cachedCategoriesData = data;

            const tvTreeContainer = document.getElementById("tv-decade-tree-container");
            const movieTreeContainer = document.getElementById("movie-decade-tree-container");
            const activeBadge = document.getElementById("current-selected-cat-badge");
            const clearBtn = document.getElementById("clear-cat-btn");

            // 同步當前選取分類提示與重置全選按鈕
            if (activeCategoryFilter) {
                if (activeBadge) {
                    activeBadge.className = "badge bg-success text-white shadow fs-6 ms-1 active-cat-glow";
                    activeBadge.innerHTML = `<i class="fa-solid fa-check me-1"></i>${activeCategoryFilter}`;
                }
                if (clearBtn) clearBtn.classList.remove("d-none");
            } else {
                if (activeBadge) {
                    activeBadge.className = "badge bg-secondary text-light ms-1";
                    activeBadge.innerText = "🌐 全部劇集";
                }
                if (clearBtn) clearBtn.classList.add("d-none");
            }

            if (!tvTreeContainer || !movieTreeContainer) return;
            tvTreeContainer.innerHTML = "";
            movieTreeContainer.innerHTML = "";

            const catList = (currentTab === 'my_dramas' && data.my_categories) ? data.my_categories : data.categories;
            const countsObj = (currentTab === 'my_dramas') ? data.my_counts : data.all_counts;
            const readTags = new Set(getReadTags());

            const tvCats = [];
            const movieCats = [];
            catList.forEach(cat => {
                if (cat.includes("電影") || cat.includes("劇場版")) {
                    movieCats.push(cat);
                } else {
                    tvCats.push(cat);
                }
            });

            const tvTree = buildCategoryTree(tvCats, countsObj);
            const movieTree = buildCategoryTree(movieCats, countsObj);

            // 首次載入：預設展開最新年代與最新 2 個年份
            if (!defaultExpandedInitialized) {
                const tvDecades = Object.keys(tvTree.decades).map(Number).sort((a, b) => b - a);
                if (tvDecades.length > 0) {
                    expandedDecades.tv.add(tvDecades[0]);
                    const latestYears = Object.keys(tvTree.decades[tvDecades[0]].years).map(Number).sort((a, b) => b - a);
                    latestYears.slice(0, 2).forEach(y => expandedYears.tv.add(y));
                }

                const movieDecades = Object.keys(movieTree.decades).map(Number).sort((a, b) => b - a);
                if (movieDecades.length > 0) {
                    expandedDecades.movie.add(movieDecades[0]);
                    const latestMovieYears = Object.keys(movieTree.decades[movieDecades[0]].years).map(Number).sort((a, b) => b - a);
                    latestMovieYears.slice(0, 2).forEach(y => expandedYears.movie.add(y));
                }
                defaultExpandedInitialized = true;
            }

            // 若目前有高亮選取的分類，自動展開其所屬的十年與年份，確保使用者始終看得到當前選項
            if (activeCategoryFilter) {
                const activeInfo = parseYearAndDecade(activeCategoryFilter);
                if (activeInfo.hasYear) {
                    expandedDecades.tv.add(activeInfo.decade);
                    expandedYears.tv.add(activeInfo.year);
                    expandedDecades.movie.add(activeInfo.decade);
                    expandedYears.movie.add(activeInfo.year);
                }
            }

            function renderTypeTree(tree, type, container, mainExpanded) {
                if (!mainExpanded) {
                    container.innerHTML = `<div class="small text-muted p-1">（已折疊，點擊上方標題列展開）</div>`;
                    return;
                }

                if (tree.otherItems.length > 0) {
                    const otherDiv = document.createElement("div");
                    otherDiv.className = "d-flex flex-wrap gap-1 mb-2 p-1 rounded bg-secondary bg-opacity-10";
                    tree.otherItems.forEach(item => {
                        const btn = createChipButton(item.cat, item.count, type, readTags);
                        otherDiv.appendChild(btn);
                    });
                    container.appendChild(otherDiv);
                }

                const sortedDecades = Object.keys(tree.decades).map(Number).sort((a, b) => b - a);
                if (sortedDecades.length === 0 && tree.otherItems.length === 0) {
                    container.innerHTML = `<div class="small text-muted p-1">目前沒有分類選項</div>`;
                    return;
                }

                sortedDecades.forEach(dNum => {
                    const decadeObj = tree.decades[dNum];
                    const isDecadeExpanded = expandedDecades[type].has(dNum);

                    const decadeCard = document.createElement("div");
                    decadeCard.className = "decade-block d-flex flex-column gap-1";

                    const decadeHeader = document.createElement("div");
                    decadeHeader.className = "decade-header d-flex justify-content-between align-items-center";
                    decadeHeader.onclick = () => toggleDecade(type, dNum);
                    decadeHeader.innerHTML = `
                        <span class="fw-bold small text-light">
                            <i class="fa-solid fa-calendar-days text-primary me-1"></i>${dNum} 年代
                            <span class="badge bg-primary text-white ms-1">${decadeObj.totalCount} 筆</span>
                        </span>
                        <span class="small text-muted">
                            ${isDecadeExpanded ? '折疊 <i class="fa-solid fa-chevron-up ms-1"></i>' : '展開 <i class="fa-solid fa-chevron-down ms-1"></i>'}
                        </span>
                    `;
                    decadeCard.appendChild(decadeHeader);

                    if (isDecadeExpanded) {
                        const yearsContainer = document.createElement("div");
                        yearsContainer.className = "d-flex flex-column gap-1 ms-2 ps-1 border-start border-secondary border-opacity-50";

                        const sortedYears = Object.keys(decadeObj.years).map(Number).sort((a, b) => b - a);
                        sortedYears.forEach(yNum => {
                            const yearObj = decadeObj.years[yNum];
                            const isYearExpanded = expandedYears[type].has(yNum);

                            const yearBlock = document.createElement("div");
                            yearBlock.className = "year-block d-flex flex-column gap-1";

                            const yearHeader = document.createElement("div");
                            yearHeader.className = "year-header d-flex justify-content-between align-items-center";
                            yearHeader.onclick = () => toggleYear(type, yNum);
                            yearHeader.innerHTML = `
                                <span class="fw-bold small text-light text-opacity-90">
                                    <i class="fa-regular fa-calendar-check text-info me-1"></i>${yNum} 年
                                    <span class="badge bg-info text-dark ms-1" style="font-size: 0.7rem;">${yearObj.totalCount} 筆</span>
                                </span>
                                <span class="small text-muted" style="font-size: 0.72rem;">
                                    ${isYearExpanded ? '<i class="fa-solid fa-angle-up"></i>' : '<i class="fa-solid fa-angle-down"></i>'}
                                </span>
                            `;
                            yearBlock.appendChild(yearHeader);

                            if (isYearExpanded) {
                                const chipsWrap = document.createElement("div");
                                chipsWrap.className = "d-flex flex-wrap gap-1 ms-2 pt-1 pb-1";
                                yearObj.items.forEach(item => {
                                    const chipBtn = createChipButton(item.cat, item.count, type, readTags);
                                    chipsWrap.appendChild(chipBtn);
                                });
                                yearBlock.appendChild(chipsWrap);
                            }

                            yearsContainer.appendChild(yearBlock);
                        });

                        decadeCard.appendChild(yearsContainer);
                    }

                    container.appendChild(decadeCard);
                });
            }

            function createChipButton(cat, count, type, readTags) {
                const isActive = (cat === activeCategoryFilter);
                const isNew = isNewCategory(cat);
                const isUnread = isNew && !readTags.has(cat);
                const btn = document.createElement("button");

                if (isActive) {
                    btn.className = "btn btn-sm btn-success text-white fw-bold rounded-pill py-0 px-2 small position-relative shadow active-cat-glow";
                } else if (type === 'tv') {
                    btn.className = "btn btn-sm btn-outline-primary rounded-pill py-0 px-2 small position-relative";
                } else {
                    btn.className = "btn btn-sm btn-outline-danger rounded-pill py-0 px-2 small position-relative";
                }
                btn.style.fontSize = "0.75rem";

                let badgeHtml = "";
                if (isUnread) {
                    badgeHtml = `<span class="badge badge-new-pulse ms-1">NEW</span>`;
                } else if (isActive) {
                    badgeHtml = `<span class="badge bg-white text-success fw-bold ms-1">${count}</span>`;
                } else {
                    badgeHtml = `<span class="badge ${type === 'tv' ? 'bg-primary' : 'bg-danger'} text-white ms-1">${count}</span>`;
                }

                btn.innerHTML = `${isActive ? '<i class="fa-solid fa-check me-1"></i>' : ''}${cat} ${badgeHtml}`;
                btn.onclick = function(e) {
                    e.stopPropagation();
                    if (isNew) markTagsAsRead([cat]);
                    selectCategoryFromChip(cat);
                };
                return btn;
            }

            renderTypeTree(tvTree, 'tv', tvTreeContainer, tvMainExpanded);
            renderTypeTree(movieTree, 'movie', movieTreeContainer, movieMainExpanded);
        }

        function selectCategoryFromChip(cat) {
            if (activeCategoryFilter === cat) {
                activeCategoryFilter = "";
            } else {
                activeCategoryFilter = cat;
            }

            let selectId = "all-dramas-cat-select";
            if (currentTab === "my_dramas") {
                selectId = "my-dramas-cat-select";
            }
            const selectEl = document.getElementById(selectId);
            if (selectEl) {
                selectEl.value = activeCategoryFilter;
            }

            if (currentTab === "my_dramas") {
                triggerMyDramasSearch();
            } else {
                triggerAllDramasSearch();
            }

            renderVisualChips(cachedCategoriesData);

            if (activeCategoryFilter && selectEl) {
                setTimeout(() => {
                    selectEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 50);
            }
        }

        let userProfile = null;

        function initLiff() {
            liff.init({ liffId: liffId })
                .then(() => {
                    if (!liff.isLoggedIn()) {
                        liff.login();
                    } else {
                        userAccessToken = liff.getAccessToken();
                        lineContext = liff.getContext();

                        // 獲取使用者個人資料並設定問候語
                        liff.getProfile().then(profile => {
                            userProfile = profile;
                            const el = document.getElementById("user-display-name") || document.getElementById("user-name");
                            if (el) el.innerText = profile.displayName;
                            if (profile.pictureUrl) {
                                const avatarEl = document.getElementById("user-avatar-container");
                                if (avatarEl) avatarEl.innerHTML = `<img src="${profile.pictureUrl}" class="rounded-circle" style="width: 32px; height: 32px; object-fit: cover;">`;
                            }
                            if (cachedCategoriesData) {
                                renderVisualChips(cachedCategoriesData);
                            }
                        }).catch(err => {
                            console.error("Failed to get profile", err);
                        });

                        // 抓取好友關係與追劇列表
                        fetchFriends();
                        fetchDramas("my_dramas", 1);
                        fetchDramas("recommendations", 1);
                        fetchDramas("all_dramas", 1);
                        fetchCategories();
                    }
                })
                .catch((err) => {
                    console.error("LIFF initialization failed", err);
                    // 外部瀏覽器降級支援
                    fetchCategories();
                    fetchDramas("my_dramas", 1);
                    fetchDramas("all_dramas", 1);
                });
        }

        // 讀取/儲存顯示設定
        function loadDisplaySettings() {
            const saved = localStorage.getItem("drama_display_settings");
            if (saved) {
                try {
                    displayPrefs = JSON.parse(saved);
                } catch(e) {}
            }
            document.getElementById("pref-category-chk").checked = displayPrefs.category;
            document.getElementById("pref-links-chk").checked = displayPrefs.links;
            document.getElementById("pref-total-chk").checked = displayPrefs.total;
            document.getElementById("pref-creator-chk").checked = displayPrefs.creator;
        }

        function openDisplaySettingsModal() {
            const modal = new bootstrap.Modal(document.getElementById("displaySettingsModal"));
            modal.show();
        }

        function saveDisplaySettings() {
            displayPrefs.category = document.getElementById("pref-category-chk").checked;
            displayPrefs.links = document.getElementById("pref-links-chk").checked;
            displayPrefs.total = document.getElementById("pref-total-chk").checked;
            displayPrefs.creator = document.getElementById("pref-creator-chk").checked;
            localStorage.setItem("drama_display_settings", JSON.stringify(displayPrefs));
            
            // 關閉並重新渲染
            bootstrap.Modal.getInstance(document.getElementById("displaySettingsModal")).hide();
            fetchDramas("my_dramas", myDramasPage);
        }

        // 切換 Tab (當切換至 好友推薦, 好友管理, 或 作品總覽 時，自動清掉/隱藏上方分類導航選項)
        function switchTab(tab) {
            currentTab = tab;
            const navCard = document.getElementById("category-nav-card");
            if (tab === "recommendations" || tab === "friends" || tab === "franchises" || tab === "friend_compare") {
                if (navCard) navCard.classList.add("d-none");
            } else {
                if (navCard) navCard.classList.remove("d-none");
            }

            if (tab === "my_dramas") {
                fetchDramas("my_dramas", myDramasPage);
                fetchCategories();
            } else if (tab === "recommendations") {
                fetchDramas("recommendations", recsPage);
            } else if (tab === "all_dramas") {
                fetchDramas("all_dramas", allDramasPage);
                fetchCategories();
            } else if (tab === "franchises") {
                fetchFranchises();
            } else if (tab === "friends") {
                fetchFriends();
            } else if (tab === "friend_compare") {
                fetchFriendComparison();
            }
        }

        // 讀取動漫作品總覽 (系列關聯) 資料 (前端實施 0 毫秒極速精準搜尋與過濾)
        let franchisePage = 1;
        let franchisePageSize = 10;
        let franchiseTotalPages = 1;

        function fetchFranchises(forceReload = false) {
            if (franchiseMasterList && !forceReload) {
                applyFranchiseLocalFilterAndPaginate(1);
                return;
            }

            const listContainer = document.getElementById("franchises-list");
            listContainer.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-success" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            `;

            fetch(apiBaseUrl + "/line/api/dramas/franchises/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ access_token: userAccessToken })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    franchiseMasterList = data.franchises || [];
                    document.getElementById("franchise-tracked-count").innerText = data.user_tracked_franchises || 0;
                    document.getElementById("franchise-tracked-items-count").innerText = data.user_tracked_items_count || 0;
                    applyFranchiseLocalFilterAndPaginate(1);
                } else {
                    listContainer.innerHTML = `<div class="alert alert-danger text-center small py-2">載入失敗：${data.error}</div>`;
                }
            })
            .catch(err => {
                console.error(err);
                listContainer.innerHTML = `<div class="alert alert-danger text-center small py-2">伺服器連線失敗</div>`;
            });
        }

        function applyFranchiseLocalFilterAndPaginate(page = 1) {
            if (!franchiseMasterList) return;
            franchisePage = page;

            const kwInput = document.getElementById("franchise-search-input");
            const rawKw = kwInput ? kwInput.value : "";
            const searchKw = normalizeSearchText(rawKw);

            const filterTrackedSelect = document.getElementById("franchise-filter-tracked-select");
            const filterTrackedVal = filterTrackedSelect ? filterTrackedSelect.value : "all";

            const sortSelect = document.getElementById("franchise-sort-select");
            const sortVal = sortSelect ? sortSelect.value : "newest";

            // 1. 0ms 記憶體即時精準過濾
            let filtered = franchiseMasterList.filter(f => {
                if (filterTrackedVal === "untracked" && f.tracked_count > 0) return false;
                if (filterTrackedVal === "tracked" && f.tracked_count === 0) return false;

                if (!searchKw) return true;
                
                const normName = normalizeSearchText(f.franchise_name);
                if (normName.includes(searchKw)) return true;

                return f.items.some(item => normalizeSearchText(item.title).includes(searchKw));
            });

            // 2. 0ms 記憶體即時排序
            filtered.sort((a, b) => {
                const aTracked = a.tracked_count > 0 ? 1 : 0;
                const bTracked = b.tracked_count > 0 ? 1 : 0;

                if (sortVal === "oldest") {
                    if (aTracked !== bTracked) return bTracked - aTracked;
                    return a.latest_date_key - b.latest_date_key;
                } else if (sortVal === "most_items") {
                    if (aTracked !== bTracked) return bTracked - aTracked;
                    return b.total_items - a.total_items;
                } else if (sortVal === "fewest_items") {
                    if (aTracked !== bTracked) return bTracked - aTracked;
                    return a.total_items - b.total_items;
                } else { // "newest"
                    if (aTracked !== bTracked) return bTracked - aTracked;
                    return b.latest_date_key - a.latest_date_key;
                }
            });

            // 3. 本地分頁裁切
            const totalCount = filtered.length;
            franchiseTotalPages = Math.max(1, Math.ceil(totalCount / franchisePageSize));
            if (franchisePage > franchiseTotalPages) franchisePage = franchiseTotalPages;

            const startIdx = (franchisePage - 1) * franchisePageSize;
            const pageItems = filtered.slice(startIdx, startIdx + franchisePageSize);

            // 4. 即時更新 UI
            document.getElementById("franchise-total-count").innerText = totalCount;
            document.getElementById("franchise-total-count-badge").innerText = totalCount;
            updateFranchisePaginationControls(franchisePage, franchiseTotalPages, totalCount);
            renderFranchisesList(pageItems);
        }

        function triggerFranchiseSearch() {
            applyFranchiseLocalFilterAndPaginate(1);
        }

        function triggerFranchiseSort() {
            applyFranchiseLocalFilterAndPaginate(1);
        }

        function triggerFranchiseFilterTracked() {
            applyFranchiseLocalFilterAndPaginate(1);
        }

        function changeFranchisePageSize(size) {
            franchisePageSize = parseInt(size) || 10;
            applyFranchiseLocalFilterAndPaginate(1);
        }

        function changeFranchisePage(delta) {
            const nextP = franchisePage + delta;
            if (nextP >= 1 && nextP <= franchiseTotalPages) {
                applyFranchiseLocalFilterAndPaginate(nextP);
            }
        }

        function jumpFranchisePage(pageVal) {
            const p = parseInt(pageVal);
            if (p >= 1 && p <= franchiseTotalPages) {
                applyFranchiseLocalFilterAndPaginate(p);
            }
        }

        function updateFranchisePaginationControls(page, totalPages, totalCount) {
            ["", "-top"].forEach(suffix => {
                const paginationDiv = document.getElementById(`franchise-pagination${suffix}`);
                const pageNumEl = document.getElementById(`franchise-page-num${suffix}`);
                const totalPagesEl = document.getElementById(`franchise-total-pages${suffix}`);
                const totalCountEl = document.getElementById(`franchise-total-count-badge${suffix}`);
                const prevBtn = document.getElementById(`franchise-prev-btn${suffix}`);
                const nextBtn = document.getElementById(`franchise-next-btn${suffix}`);
                const jumpSelect = document.getElementById(`franchise-jump-page-select${suffix}`);
                const pageSizeSelect = document.getElementById(`franchise-page-size-select${suffix}`);

                if (pageNumEl) pageNumEl.innerText = page;
                if (totalPagesEl) totalPagesEl.innerText = totalPages;
                if (totalCountEl) totalCountEl.innerText = totalCount;

                if (prevBtn) prevBtn.disabled = (page <= 1);
                if (nextBtn) nextBtn.disabled = (page >= totalPages);

                if (pageSizeSelect) pageSizeSelect.value = franchisePageSize;

                if (jumpSelect) {
                    jumpSelect.innerHTML = "";
                    for (let i = 1; i <= totalPages; i++) {
                        jumpSelect.innerHTML += `<option value="${i}" ${i === page ? 'selected' : ''}>第 ${i} 頁</option>`;
                    }
                }

                if (paginationDiv) {
                    if (totalPages >= 1 || totalCount > 0) {
                        paginationDiv.classList.remove("d-none");
                        paginationDiv.classList.add("d-flex");
                    } else {
                        paginationDiv.classList.add("d-none");
                        paginationDiv.classList.remove("d-flex");
                    }
                }
            });
        }

        function renderFranchisesList(list) {
            const listContainer = document.getElementById("franchises-list");
            listContainer.innerHTML = "";

            if (!list || list.length === 0) {
                listContainer.innerHTML = `<div class="text-center text-muted py-4 small">查無符合的作品系列關聯</div>`;
                return;
            }

            list.forEach((f, idx) => {
                const accordionId = `franchise-acc-${idx}`;
                const hasTracked = f.tracked_count > 0;
                
                let trackedBadgeHtml = "";
                if (hasTracked) {
                    trackedBadgeHtml = `<span class="badge bg-success text-white shadow-sm small"><i class="fa-solid fa-circle-check me-1"></i>已有 ${f.tracked_count} 部加入觀看清單</span>`;
                } else {
                    trackedBadgeHtml = `<span class="badge bg-secondary text-light small opacity-75">未加入觀看清單</span>`;
                }

                let batchTrackBtnsHtml = "";
                if (f.tracked_count < f.total_items) {
                    batchTrackBtnsHtml += `
                        <button class="btn btn-xs btn-success rounded-pill px-2 py-1 small fw-bold" onclick="batchTrackFranchise(${f.id}, 'track_all', '${f.franchise_name.replace(/'/g, "\\'")}')">
                            <i class="fa-solid fa-plus-circle me-1"></i>一鍵全部追蹤 (${f.total_items}部)
                        </button>
                    `;
                }
                if (f.tracked_count > 0) {
                    batchTrackBtnsHtml += `
                        <button class="btn btn-xs btn-outline-danger rounded-pill px-2 py-1 small fw-bold" onclick="batchTrackFranchise(${f.id}, 'untrack_all', '${f.franchise_name.replace(/'/g, "\\'")}')">
                            <i class="fa-solid fa-trash-can me-1"></i>一鍵取消追蹤
                        </button>
                    `;
                }

                // 預覽多圖示 (Multi-image cover thumbnails preview)
                let previewImagesHtml = "";
                if (f.preview_images && f.preview_images.length > 0) {
                    previewImagesHtml = `<div class="d-flex align-items-center gap-1 my-2 overflow-x-auto py-1">`;
                    f.preview_images.forEach(imgUrl => {
                        previewImagesHtml += `<img src="${imgUrl}" class="rounded border shadow-sm cursor-pointer" style="width: 48px; height: 64px; object-fit: cover;" onclick="openImageLightbox(['${imgUrl.replace(/'/g, "\\'")}'])" onerror="this.style.display='none'">`;
                    });
                    previewImagesHtml += `</div>`;
                }

                // 子類別 (TV/電影/OVA/總集篇) 項目區塊渲染
                const renderSubCategoryItems = (items, label, icon) => {
                    if (!items || items.length === 0) return "";
                    let html = `<div class="mb-3">
                        <div class="fw-bold small mb-2 text-dark border-bottom pb-1">
                            <i class="${icon} me-1 text-success"></i>${label} (${items.length} 部)
                        </div>
                        <div class="d-flex flex-column gap-2">`;
                    
                    items.forEach(item => {
                        let joinBtn = "";
                        if (item.is_tracked) {
                            joinBtn = `<span class="badge bg-success text-white py-1 px-2 small shadow-sm"><i class="fa-solid fa-check me-1"></i>已在清單中</span>`;
                        } else {
                            joinBtn = `<button class="btn btn-xs btn-outline-success rounded-pill px-2 py-1 small fw-bold text-nowrap" onclick="joinDramaFromFranchise(${item.id}, '${f.franchise_name.replace(/'/g, "\\'")}')">
                                <i class="fa-solid fa-plus me-1"></i>加入追劇
                            </button>`;
                        }

                        let itemImgHtml = "";
                        if (item.image_url) {
                            itemImgHtml = `<img src="${item.image_url}" class="rounded border me-2" style="width: 36px; height: 48px; object-fit: cover;" onerror="this.style.display='none'">`;
                        }

                        html += `
                            <div class="p-2 rounded bg-light d-flex justify-content-between align-items-center border border-secondary border-opacity-25 gap-2">
                                <div class="d-flex align-items-center" style="min-width: 0;">
                                    ${itemImgHtml}
                                    <div style="min-width: 0;">
                                        <div class="fw-bold small text-dark">${item.title}</div>
                                        <div class="small text-muted" style="font-size: 0.75rem;">${item.category} | 共 ${item.total_seasons} 季 ${item.total_episodes} 集</div>
                                    </div>
                                </div>
                                <div>${joinBtn}</div>
                            </div>
                        `;
                    });

                    html += `</div></div>`;
                    return html;
                };

                const tvItemsHtml = renderSubCategoryItems(f.tv_seasons, "📺 TV 正篇 / 季番", "fa-solid fa-tv");
                const movieItemsHtml = renderSubCategoryItems(f.movies, "🎬 劇場版 / 電影", "fa-solid fa-film");
                const ovaItemsHtml = renderSubCategoryItems(f.ovas, "📼 OVA / 特別篇", "fa-solid fa-video");
                const recapItemsHtml = renderSubCategoryItems(f.recaps, "🎞️ 總集篇", "fa-solid fa-clapperboard");

                const cardHtml = `
                    <div class="glass-card p-3 drama-item" style="border-left-color: ${hasTracked ? '#10b981' : '#6b7280'};">
                        <div class="d-flex justify-content-between align-items-start mb-1 flex-wrap gap-1">
                            <div>
                                <h5 class="fw-bold mb-1 text-dark">${f.franchise_name}</h5>
                                <div class="d-flex align-items-center gap-2 flex-wrap mb-1">
                                    <span class="badge bg-secondary text-light small">共 ${f.total_items} 部關聯作品</span>
                                    ${trackedBadgeHtml}
                                </div>
                            </div>
                            <div class="d-flex gap-1 flex-wrap align-items-center mt-1">
                                ${batchTrackBtnsHtml}
                                <button class="btn btn-sm btn-outline-primary rounded-pill px-3 py-1 small fw-bold" type="button" data-bs-toggle="collapse" data-bs-target="#${accordionId}">
                                    <i class="fa-solid fa-folder-open me-1"></i>展開篇章 (${f.total_items})
                                </button>
                            </div>
                        </div>
                        ${previewImagesHtml}
                        <div class="collapse mt-2 pt-2 border-top" id="${accordionId}">
                            ${tvItemsHtml}
                            ${movieItemsHtml}
                            ${ovaItemsHtml}
                            ${recapItemsHtml}
                        </div>
                    </div>
                `;
                listContainer.innerHTML += cardHtml;
            });
        }

        function batchTrackFranchise(franchiseId, action, franchiseName) {
            const isTrack = (action === "track_all");
            const actionTitle = isTrack ? `一鍵全部追蹤【${franchiseName}】` : `一鍵取消追蹤【${franchiseName}】`;
            const actionMsg = isTrack ? "確定要把該系列底下的所有篇章與劇場版通通加入您的追劇清單嗎？" : "確定要將該系列底下的所有作品從您的追劇清單中移除嗎？";
            
            Swal.fire({
                title: actionTitle,
                text: actionMsg,
                icon: isTrack ? "question" : "warning",
                showCancelButton: true,
                confirmButtonColor: isTrack ? "#10b981" : "#ef4444",
                confirmButtonText: isTrack ? "確定全部追蹤" : "確定取消追蹤",
                cancelButtonText: "取消"
            }).then(result => {
                if (result.isConfirmed) {
                    fetch(apiBaseUrl + "/line/api/dramas/franchise_batch_track/", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            access_token: userAccessToken,
                            franchise_id: franchiseId,
                            action: action
                        })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === "success") {
                            Swal.fire({ title: isTrack ? "已成功追蹤全部作品！" : "已成功取消追蹤！", icon: "success", timer: 1200, showConfirmButton: false });
                            myDramasMasterList = null;
                            fetchDramas("my_dramas", 1, true);
                            fetchFranchises(true);
                        } else {
                            Swal.fire("錯誤", "操作失敗：" + data.error, "error");
                        }
                    });
                }
            });
        }

        function joinDramaFromFranchise(dramaId, franchiseName) {
            fetch(apiBaseUrl + `/line/api/dramas/join/${dramaId}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ access_token: userAccessToken })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    Swal.fire({ title: '已成功加入您的追劇清單！', icon: 'success', timer: 1500, showConfirmButton: false });
                    myDramasMasterList = null;
                    fetchDramas("my_dramas", 1, true);
                    fetchFranchises(true);
                } else {
                    Swal.fire("錯誤", "加入失敗：" + data.error, "error");
                }
            });
        }

        // 讀取追劇列表或推薦 (一次性載入全量 MasterList，隨後於前端實施 0 毫秒極速搜尋與分頁)
        function fetchDramas(tab, page, forceReload = false) {
            let masterList = null;
            if (tab === "my_dramas") masterList = myDramasMasterList;
            else if (tab === "all_dramas") masterList = allDramasMasterList;
            else if (tab === "recommendations") masterList = recsMasterList;

            // 若已有 MasterList 且不強制重載，直接執行前端極速渲染
            if (masterList && !forceReload) {
                renderClientSideFilteredData(tab, page);
                return;
            }

            let listContainerId = "my-dramas-list";
            if (tab === "recommendations") listContainerId = "recs-list";
            else if (tab === "all_dramas") listContainerId = "all-dramas-list";
            
            const listContainer = document.getElementById(listContainerId);
            listContainer.innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-success" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            `;

            // 向後端請求全量 MasterList (帶入大 page_size)
            const reqBody = {
                access_token: userAccessToken,
                tab: tab,
                sub_tab: recSubTab,
                page: 1,
                page_size: 10000
            };

            fetch(apiBaseUrl + "/line/api/dramas/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(reqBody)
            })
            .then(res => res.json())
            .then(data => {
                if (tab === "my_dramas") {
                    document.getElementById("loading-section").classList.add("d-none");
                    document.getElementById("main-section").classList.remove("d-none");
                }
                if (data.status === "success") {
                    if (tab === "my_dramas") myDramasMasterList = data.list || [];
                    else if (tab === "all_dramas") allDramasMasterList = data.list || [];
                    else if (tab === "recommendations") {
                        recsMasterList = data.list || [];
                        if (data.rec_counts) {
                            const elP = document.getElementById("rec-pending-count");
                            const elA = document.getElementById("rec-accepted-count");
                            const elR = document.getElementById("rec-rejected-count");
                            if (elP) elP.innerText = data.rec_counts.pending || 0;
                            if (elA) elA.innerText = data.rec_counts.accepted || 0;
                            if (elR) elR.innerText = data.rec_counts.rejected || 0;
                        }
                    }
                    
                    renderClientSideFilteredData(tab, page);
                } else {
                    listContainer.innerHTML = `<div class="alert alert-danger text-center small py-2">載入失敗：${data.error}</div>`;
                }
            })
            .catch(err => {
                console.error(err);
                listContainer.innerHTML = `<div class="alert alert-danger text-center small py-2">伺服器連線失敗</div>`;
            });
        }

        // 前端 0 毫秒極速過濾、搜尋與分頁切片渲染
        function renderClientSideFilteredData(tab, targetPage) {
            let masterList = [];
            let searchInputId = "all-dramas-search";
            let catSelectId = "all-dramas-cat-select";
            let pageSize = allDramasPageSize;
            let page = targetPage || allDramasPage;

            if (tab === "my_dramas") {
                masterList = myDramasMasterList || [];
                searchInputId = "my-dramas-search";
                catSelectId = "my-dramas-cat-select";
                pageSize = myDramasPageSize;
                page = targetPage || myDramasPage;
            } else if (tab === "recommendations") {
                masterList = recsMasterList || [];
                pageSize = recsPageSize;
                page = targetPage || recsPage;
            } else {
                masterList = allDramasMasterList || [];
            }

            const searchInput = document.getElementById(searchInputId);
            const catSelect = document.getElementById(catSelectId);
            const rawQ = searchInput ? searchInput.value.trim() : "";
            const normQ = normalizeSearchText(rawQ);
            const catVal = activeCategoryFilter || (catSelect ? catSelect.value.trim() : "");

            let trackedFilter = "all";
            if (tab === "all_dramas") {
                const trackedSelect = document.getElementById("all-dramas-tracked-select");
                if (trackedSelect) trackedFilter = trackedSelect.value;
            }

            // 前端 0ms 記憶體過濾 (關鍵字搜尋與分類過濾雙重交集)
            const filteredList = masterList.filter(item => {
                if (catVal && item.category !== catVal) return false;
                if (normQ) {
                    const normTitle = normalizeSearchText(item.title);
                    if (!normTitle.includes(normQ)) return false;
                }
                if (tab === "all_dramas") {
                    if (trackedFilter === "untracked" && item.is_added) return false;
                    if (trackedFilter === "tracked" && !item.is_added) return false;
                }
                return true;
            });

            const totalCount = filteredList.length;
            const totalPages = Math.ceil(totalCount / pageSize) || 1;
            
            if (page > totalPages) page = totalPages;
            if (page < 1) page = 1;

            if (tab === "my_dramas") myDramasPage = page;
            else if (tab === "all_dramas") allDramasPage = page;
            else if (tab === "recommendations") recsPage = page;

            const start = (page - 1) * pageSize;
            const end = start + pageSize;
            const slicedList = filteredList.slice(start, end);
            const hasMore = page < totalPages;

            renderDramaList(slicedList, tab);
            updatePaginationControls(tab, page, totalPages, totalCount, hasMore);
        }

        function isMovieItem(item) {
            if (!item) return false;
            if (item.media_type === "MOVIE") return true;
            const title = (item.title || "").toLowerCase();
            const cat = (item.category || "").toLowerCase();
            return title.includes("劇場版") || title.includes("電影") || title.includes("movie") || cat.includes("劇場版") || cat.includes("電影");
        }

        function renderDramaList(list, tab) {
            let containerId = "my-dramas-list";
            if (tab === "recommendations") {
                containerId = "recs-list";
            } else if (tab === "all_dramas") {
                containerId = "all-dramas-list";
            }
            const container = document.getElementById(containerId);
            container.innerHTML = "";

            if (list.length === 0) {
                container.innerHTML = `
                    <div class="glass-card p-4 text-center text-muted">
                        <i class="fa-solid fa-tv fa-2x mb-2 text-secondary"></i>
                        <p class="mb-0 small">目前沒有任何劇集項目</p>
                    </div>
                `;
                return;
            }

            list.forEach(item => {
                const isMovie = isMovieItem(item);

                if (tab === "my_dramas") {
                    // 渲染相關連結
                    let linksHtml = "";
                    if (item.info_links && item.info_links.length > 0) {
                        linksHtml = `<div class="d-flex flex-wrap gap-1 mt-2 pref-links ${displayPrefs.links ? '' : 'd-none'}">`;
                        item.info_links.forEach(link => {
                            linksHtml += `
                                <a href="${link.url}" target="_blank" class="badge bg-white text-info border border-info text-decoration-none px-2 py-1 small" style="font-size: 0.7rem; border-radius: 5px;">
                                    <i class="fa-solid fa-link me-1"></i>${link.title}
                                </a>
                            `;
                        });
                        linksHtml += '</div>';
                    }

                    let imgHtml = renderPreviewImagesHtml(item.image_url);

                    let progressInfoHtml = "";
                    let actionBtnsHtml = "";

                    if (isMovie) {
                        progressInfoHtml = `
                            <div class="small fw-bold mb-1">
                                <span class="badge bg-danger bg-opacity-25 text-danger border border-danger"><i class="fa-solid fa-film me-1"></i>🎬 劇場版 / 電影</span>
                            </div>
                        `;
                        actionBtnsHtml = `
                            <button class="btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="openRecommendModal(${item.drama_id}, '${item.title.replace(/'/g, "\\'")}')">
                                <i class="fa-solid fa-share-nodes me-1"></i>推薦
                            </button>
                            <button class="btn btn-sm btn-outline-danger py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="removeDrama(${item.drama_id}, '${item.title.replace(/'/g, "\\'")}', this)">
                                <i class="fa-solid fa-trash-can me-1"></i>移除
                            </button>
                        `;
                    } else {
                        progressInfoHtml = `
                            <div class="text-success small fw-bold mb-1">
                                目前看至：第 ${item.current_episode} 集
                            </div>
                        `;
                        actionBtnsHtml = `
                            <button class="btn btn-sm btn-outline-success fw-bold py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="addOneEpisode(${item.drama_id}, ${item.current_season}, ${item.current_episode})">
                                <i class="fa-solid fa-plus me-1"></i>1 集
                            </button>
                            <button class="btn btn-sm btn-outline-primary py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="editDramaProgressModal(${item.drama_id}, '${item.title.replace(/'/g, "\\'")}', ${item.current_season}, ${item.current_episode})">
                                <i class="fa-regular fa-pen-to-square me-1"></i>進度
                            </button>
                            <button class="btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="openRecommendModal(${item.drama_id}, '${item.title.replace(/'/g, "\\'")}')">
                                <i class="fa-solid fa-share-nodes me-1"></i>推薦
                            </button>
                            <button class="btn btn-sm btn-outline-danger py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="removeDrama(${item.drama_id}, '${item.title.replace(/'/g, "\\'")}', this)">
                                <i class="fa-solid fa-trash-can me-1"></i>移除
                            </button>
                        `;
                    }

                    const html = `
                        <div class="glass-card p-3 drama-item d-flex justify-content-between align-items-center">
                            <div class="d-flex align-items-center flex-grow-1 me-2" style="max-width: 80%;">
                                ${imgHtml}
                                <div class="flex-grow-1" style="min-width: 0;">
                                    <div class="d-flex align-items-center mb-1 gap-2 flex-wrap">
                                        <span class="badge bg-primary small pref-category ${displayPrefs.category ? '' : 'd-none'}">${item.category}</span>
                                        <span class="badge ${item.is_tracked ? 'bg-success' : 'bg-secondary'} small" style="cursor: pointer;" onclick="toggleTrack(${item.drama_id}, ${!item.is_tracked})">
                                            <i class="fa-solid fa-bell me-1"></i>${item.is_tracked ? '追蹤中' : '開啟追蹤'}
                                        </span>
                                    </div>
                                    <h5 class="fw-bold mb-1 text-dark" style="font-size: 1.05rem; word-break: break-all;">${item.title}</h5>
                                    ${progressInfoHtml}
                                    ${linksHtml}
                                    <div class="text-muted pref-creator ${displayPrefs.creator ? '' : 'd-none'}" style="font-size: 0.7rem; margin-top: 5px;">
                                        👥 ${item.tracked_users_count || 0} 人收藏 | 更新: ${item.updated_at}
                                    </div>
                                </div>
                            </div>
                            <div class="d-flex flex-column gap-1">
                                ${actionBtnsHtml}
                            </div>
                        </div>
                    `;
                    container.innerHTML += html;
                } else if (tab === "all_dramas") {
                    // 探索新番/劇庫
                    let linksHtml = "";
                    if (item.info_links && item.info_links.length > 0) {
                        linksHtml = '<div class="d-flex flex-wrap gap-1 mt-2">';
                        item.info_links.forEach(link => {
                            linksHtml += `
                                <a href="${link.url}" target="_blank" class="badge bg-white text-info border border-info text-decoration-none px-2 py-1 small" style="font-size: 0.7rem; border-radius: 5px;">
                                    <i class="fa-solid fa-link me-1"></i>${link.title}
                                </a>
                            `;
                        });
                        linksHtml += '</div>';
                    }

                    let joinBtnHtml = "";
                    if (item.is_added) {
                        joinBtnHtml = `
                            <button class="btn btn-sm btn-secondary py-1 px-2 text-nowrap text-white" style="font-size: 0.75rem; cursor: default;" disabled>
                                <i class="fa-solid fa-check me-1"></i>已在清單
                            </button>
                        `;
                    } else {
                        joinBtnHtml = `
                            <button class="btn btn-sm btn-success py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="joinDrama(${item.drama_id}, this)">
                                <i class="fa-solid fa-plus me-1"></i>加入清單
                            </button>
                        `;
                    }

                    let allImgHtml = renderPreviewImagesHtml(item.image_url);
                    let movieBadgeHtml = isMovie ? `<div class="small fw-bold mb-1"><span class="badge bg-danger bg-opacity-25 text-danger border border-danger"><i class="fa-solid fa-film me-1"></i>🎬 劇場版 / 電影</span></div>` : "";

                    const html = `
                        <div class="glass-card p-3 drama-item d-flex justify-content-between align-items-center">
                            <div class="d-flex align-items-center flex-grow-1 me-2" style="max-width: 80%;">
                                ${allImgHtml}
                                <div class="flex-grow-1" style="min-width: 0;">
                                    <div class="d-flex align-items-center mb-1 gap-2 flex-wrap">
                                        <span class="badge bg-primary small">${item.category}</span>
                                    </div>
                                    <h5 class="fw-bold mb-1 text-dark" style="font-size: 1.05rem; word-break: break-all;">${item.title}</h5>
                                    ${movieBadgeHtml}
                                    ${linksHtml}
                                    <div class="text-muted" style="font-size: 0.7rem; margin-top: 5px;">
                                        👥 ${item.tracked_users_count || 0} 人收藏 | 更新: ${item.updated_at}
                                    </div>
                                </div>
                            </div>
                            <div class="d-flex flex-column gap-1">
                                ${joinBtnHtml}
                                <button class="btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="openRecommendModal(${item.drama_id}, '${item.title.replace(/'/g, "\\'")}')">
                                    <i class="fa-solid fa-share-nodes me-1"></i>推薦
                                </button>
                            </div>
                        </div>
                    `;
                    container.innerHTML += html;
                } else {
                    // 好友推薦清單
                    let recImgHtml = renderPreviewImagesHtml(item.image_url);

                    let actionHtml = "";
                    let alreadyInListBadge = "";
                    if (item.is_already_in_my_list) {
                        alreadyInListBadge = `<span class="badge bg-success text-white small mb-1 shadow-sm"><i class="fa-solid fa-circle-check me-1"></i>已在您的追劇清單中</span>`;
                    }

                    if (recSubTab === "pending" || (!item.is_accepted && !item.is_rejected)) {
                        if (item.is_already_in_my_list) {
                            actionHtml = `
                                <div class="d-flex flex-column gap-1 align-items-stretch align-items-sm-end w-100 w-sm-auto mt-2 mt-sm-0">
                                    <button class="btn btn-sm btn-success py-1 px-2 text-nowrap shadow-sm" style="font-size: 0.75rem;" onclick="acceptRecommend(${item.recommendation_id})">
                                        <i class="fa-solid fa-check me-1"></i>已在清單 (移至已加入)
                                    </button>
                                    <button class="btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="ignoreRecommend(${item.recommendation_id})">
                                        <i class="fa-solid fa-eye-slash me-1"></i>忽略 / 隱藏
                                    </button>
                                </div>
                            `;
                        } else {
                            actionHtml = `
                                <div class="d-flex flex-column gap-1 align-items-stretch align-items-sm-end w-100 w-sm-auto mt-2 mt-sm-0">
                                    <button class="btn btn-sm btn-success py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="acceptRecommend(${item.recommendation_id})">
                                        <i class="fa-solid fa-plus me-1"></i>接受 (加入追劇)
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="rejectRecommend(${item.recommendation_id})">
                                        <i class="fa-solid fa-xmark me-1"></i>拒絕
                                    </button>
                                    <button class="btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="ignoreRecommend(${item.recommendation_id})">
                                        <i class="fa-solid fa-eye-slash me-1"></i>忽略 / 隱藏
                                    </button>
                                </div>
                            `;
                        }
                    } else if (recSubTab === "accepted" || item.is_accepted) {
                        actionHtml = `
                            <div class="d-flex flex-column gap-1 align-items-stretch align-items-sm-end w-100 w-sm-auto mt-2 mt-sm-0">
                                <span class="badge bg-success py-1 px-2 text-nowrap shadow-sm mb-1 text-center" style="font-size: 0.75rem;">
                                    <i class="fa-solid fa-circle-check me-1"></i>已加入個人追劇清單
                                </span>
                                <button class="btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="ignoreRecommend(${item.recommendation_id})">
                                    <i class="fa-solid fa-eye-slash me-1"></i>忽略 / 隱藏紀錄
                                </button>
                            </div>
                        `;
                    } else if (recSubTab === "rejected" || item.is_rejected) {
                        actionHtml = `
                            <div class="d-flex flex-column gap-1 align-items-stretch align-items-sm-end w-100 w-sm-auto mt-2 mt-sm-0">
                                <span class="badge bg-secondary py-1 px-2 text-nowrap mb-1 text-center" style="font-size: 0.75rem;">
                                    <i class="fa-solid fa-ban me-1"></i>${item.status === 'ignored' ? '已忽略/隱藏' : '已拒絕'}
                                </span>
                                <button class="btn btn-sm btn-outline-success py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="acceptRecommend(${item.recommendation_id})">
                                    <i class="fa-solid fa-rotate-left me-1"></i>重新接受
                                </button>
                            </div>
                        `;
                    }

                    const html = `
                        <div class="glass-card p-3 drama-item d-flex flex-column flex-sm-row justify-content-between align-items-start align-items-sm-center gap-2" style="border-left-color: ${recSubTab === 'accepted' ? '#10b981' : (recSubTab === 'rejected' ? '#6b7280' : '#ff9f43')};">
                            <div class="d-flex align-items-center flex-grow-1 w-100 me-0 me-sm-2" style="min-width: 0;">
                                ${recImgHtml}
                                <div class="flex-grow-1" style="min-width: 0;">
                                    <div class="d-flex align-items-center mb-1 gap-2 flex-wrap">
                                        <span class="badge ${recSubTab === 'accepted' ? 'bg-success' : 'bg-warning text-dark'} small">${item.category}</span>
                                        ${alreadyInListBadge}
                                        <span class="small text-muted"><i class="fa-regular fa-user me-1"></i>推薦人: <strong>${item.from_user}</strong></span>
                                    </div>
                                    <h5 class="fw-bold mb-1 text-dark" style="font-size: 1.05rem;">${item.title}</h5>
                                    ${item.recommend_notes ? `<div class="bg-light p-2 rounded text-secondary mb-2 small" style="border-left: 2px solid #ff9f43;">推薦短評: ${item.recommend_notes}</div>` : ""}
                                </div>
                            </div>
                            ${actionHtml}
                        </div>
                    `;
                    container.innerHTML += html;
                }
            });
        }

        // 分頁控制 (動態頁數、每頁筆數與跳頁選單，同時同步頂部與底部分頁列)
        function updatePaginationControls(tab, page, totalPages, totalCount, hasMore) {
            let prefix = "my";
            if (tab === "recommendations") {
                prefix = "recs";
            } else if (tab === "all_dramas") {
                prefix = "all";
            }

            ["", "-top"].forEach(suffix => {
                const paginationDiv = document.getElementById(`${prefix}-pagination${suffix}`);
                const pageNumSpan = document.getElementById(`${prefix}-page-num${suffix}`);
                const totalPagesSpan = document.getElementById(`${prefix}-total-pages${suffix}`);
                const totalCountSpan = document.getElementById(`${prefix}-total-count${suffix}`);
                const prevBtn = document.getElementById(`${prefix}-prev-btn${suffix}`);
                const nextBtn = document.getElementById(`${prefix}-next-btn${suffix}`);
                const jumpSelect = document.getElementById(`${prefix}-jump-page-select${suffix}`);
                const pageSizeSelect = document.getElementById(`${prefix}-page-size-select${suffix}`);

                if (pageNumSpan) pageNumSpan.innerText = page;
                if (totalPagesSpan) totalPagesSpan.innerText = totalPages;
                if (totalCountSpan) totalCountSpan.innerText = totalCount;

                if (prevBtn) prevBtn.disabled = (page <= 1);
                if (nextBtn) nextBtn.disabled = !hasMore && (page >= totalPages);

                if (pageSizeSelect) {
                    let curSize = 10;
                    if (prefix === "my") curSize = myDramasPageSize;
                    else if (prefix === "all") curSize = allDramasPageSize;
                    else if (prefix === "recs") curSize = recsPageSize;
                    pageSizeSelect.value = curSize;
                }

                if (jumpSelect) {
                    jumpSelect.innerHTML = "";
                    for (let i = 1; i <= totalPages; i++) {
                        const opt = document.createElement("option");
                        opt.value = i;
                        opt.innerText = `第 ${i} 頁`;
                        if (i === page) opt.selected = true;
                        jumpSelect.appendChild(opt);
                    }
                }

                if (paginationDiv) {
                    if (totalPages >= 1 || totalCount > 0) {
                        paginationDiv.classList.remove("d-none");
                        paginationDiv.classList.add("d-flex");
                    } else {
                        paginationDiv.classList.add("d-none");
                        paginationDiv.classList.remove("d-flex");
                    }
                }
            });
        }

        // 修改每頁顯示筆數 (前端0ms即時分頁)
        function changePageSize(newSize) {
            const size = parseInt(newSize);
            if (currentTab === "my_dramas") {
                myDramasPageSize = size;
                myDramasPage = 1;
                renderClientSideFilteredData("my_dramas", 1);
            } else if (currentTab === "recommendations") {
                recsPageSize = size;
                recsPage = 1;
                renderClientSideFilteredData("recommendations", 1);
            } else if (currentTab === "all_dramas") {
                allDramasPageSize = size;
                allDramasPage = 1;
                renderClientSideFilteredData("all_dramas", 1);
            }
        }

        // 直接跳轉至指定頁數 (前端0ms即時跳轉)
        function jumpToPage(targetPage) {
            const page = parseInt(targetPage);
            if (isNaN(page) || page < 1) return;

            if (currentTab === "my_dramas") {
                myDramasPage = page;
                renderClientSideFilteredData("my_dramas", page);
            } else if (currentTab === "recommendations") {
                recsPage = page;
                renderClientSideFilteredData("recommendations", page);
            } else if (currentTab === "all_dramas") {
                allDramasPage = page;
                renderClientSideFilteredData("all_dramas", page);
            }
        }

        function changePage(offset) {
            if (currentTab === "my_dramas") {
                myDramasPage += offset;
                if (myDramasPage < 1) myDramasPage = 1;
                renderClientSideFilteredData("my_dramas", myDramasPage);
            } else if (currentTab === "recommendations") {
                recsPage += offset;
                if (recsPage < 1) recsPage = 1;
                renderClientSideFilteredData("recommendations", recsPage);
            } else if (currentTab === "all_dramas") {
                allDramasPage += offset;
                if (allDramasPage < 1) allDramasPage = 1;
                renderClientSideFilteredData("all_dramas", allDramasPage);
            }
        }

        // 探索新番即時搜尋與分類過濾 (前端0ms打字即時響應)
        function triggerAllDramasSearch() {
            const selectEl = document.getElementById("all-dramas-cat-select");
            if (selectEl) activeCategoryFilter = selectEl.value;
            allDramasPage = 1;
            renderClientSideFilteredData("all_dramas", 1);
            if (cachedCategoriesData) renderVisualChips(cachedCategoriesData);
        }

        // 我的追劇即時搜尋與分類過濾 (前端0ms打字即時響應)
        function triggerMyDramasSearch() {
            const selectEl = document.getElementById("my-dramas-cat-select");
            if (selectEl) activeCategoryFilter = selectEl.value;
            myDramasPage = 1;
            renderClientSideFilteredData("my_dramas", 1);
            if (cachedCategoriesData) renderVisualChips(cachedCategoriesData);
        }

        // 快捷：追劇+1集 (0毫秒前端即時響應)
        function addOneEpisode(id, curS, curE) {
            const nextEp = curE + 1;
            // 樂觀更新內存
            if (myDramasMasterList) {
                const item = myDramasMasterList.find(d => d.drama_id === id);
                if (item) item.current_episode = nextEp;
            }
            renderClientSideFilteredData("my_dramas", myDramasPage);

            fetch(apiBaseUrl + `/line/api/dramas/update_progress/${id}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    access_token: userAccessToken,
                    current_season: curS || 1,
                    current_episode: nextEp
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status !== "success") {
                    Swal.fire("錯誤", "更新進度失敗：" + data.error, "error");
                    myDramasMasterList = null;
                    fetchDramas("my_dramas", myDramasPage, true);
                }
            });
        }

        // 彈出修改個人進度彈窗 (移除季度設定，專注於記錄看至第幾集)
        function editDramaProgressModal(id, title, curS, curE) {
            Swal.fire({
                title: `修改《${title}》觀看進度`,
                html: `
                    <div class="p-1 small text-start">
                        <label class="form-label fw-bold mb-1">目前看至第幾集：</label>
                        <div class="input-group">
                            <span class="input-group-text bg-dark text-white border-secondary">第</span>
                            <input type="number" id="swal-episode" class="form-control" value="${curE}" min="0">
                            <span class="input-group-text bg-dark text-white border-secondary">集</span>
                        </div>
                    </div>
                `,
                showCancelButton: true,
                confirmButtonColor: '#1DB446',
                confirmButtonText: '確定更新進度',
                cancelButtonText: '取消',
                background: '#1a1a2e',
                color: '#e0e0e0',
                preConfirm: () => {
                    const episode = document.getElementById("swal-episode").value;
                    if (!episode || isNaN(episode)) {
                        Swal.showValidationMessage("請輸入有效的集數數字！");
                    }
                    return { season: 1, episode: parseInt(episode) };
                }
            }).then(res => {
                if (res.isConfirmed && res.value) {
                    const newEp = res.value.episode;
                    if (myDramasMasterList) {
                        const item = myDramasMasterList.find(d => d.drama_id === id);
                        if (item) item.current_episode = newEp;
                    }
                    renderClientSideFilteredData("my_dramas", myDramasPage);

                    fetch(apiBaseUrl + `/line/api/dramas/update_progress/${id}/`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            access_token: userAccessToken,
                            current_season: 1,
                            current_episode: newEp
                        })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === "success") {
                            Swal.fire({ title: '已成功更新進度！', icon: 'success', timer: 1000, showConfirmButton: false, background: '#1a1a2e', color: '#e0e0e0' });
                        } else {
                            Swal.fire("錯誤", "更新進度失敗：" + data.error, "error");
                            myDramasMasterList = null;
                            fetchDramas("my_dramas", myDramasPage, true);
                        }
                    });
                }
            });
        }

        // -------------------------------------------------------------------
        // 🤝 好友追劇比對頁籤與比對功能
        // -------------------------------------------------------------------
        let friendCompareData = null;
        let activeCompareSubTab = "both"; // "both", "my", "friend"

        function fetchFriendComparison(friendUserId = null) {
            const container = document.getElementById("compare-list-container");
            if (!container) return;

            container.innerHTML = `
                <div class="glass-card p-4 text-center">
                    <div class="spinner-border text-success" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="small text-muted mt-2">正在比對您與好友的追劇清單...</div>
                </div>
            `;

            fetch(apiBaseUrl + "/line/api/dramas/compare_friends/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    access_token: userAccessToken,
                    friend_user_id: friendUserId
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    friendCompareData = data;
                    renderFriendCompareSelect(data.friends_list, data.selected_friend);
                    renderFriendCompareStats(data.stats);
                    renderFriendCompareList();
                } else {
                    container.innerHTML = `<div class="alert alert-danger text-center small py-2">比對失敗：${data.error}</div>`;
                }
            })
            .catch(err => {
                console.error("fetchFriendComparison error:", err);
                container.innerHTML = `<div class="alert alert-danger text-center small py-2">連線失敗，請稍後再試。</div>`;
            });
        }

        function renderFriendCompareSelect(friendsList, selectedFriend) {
            const selectEl = document.getElementById("compare-friend-select");
            if (!selectEl) return;
            selectEl.innerHTML = "";

            if (!friendsList || friendsList.length === 0) {
                selectEl.innerHTML = `<option value="">尚未加入好友</option>`;
                return;
            }

            friendsList.forEach(f => {
                const isSel = selectedFriend && selectedFriend.user_id === f.user_id;
                selectEl.innerHTML += `<option value="${f.user_id}" ${isSel ? 'selected' : ''}>${f.name} (${f.tracked_count}部)</option>`;
            });
        }

        function triggerFriendCompareChange(val) {
            if (!val) return;
            fetchFriendComparison(parseInt(val));
        }

        function renderFriendCompareStats(stats) {
            if (!stats) return;
            const elBoth = document.getElementById("stat-both-count");
            const elMy = document.getElementById("stat-my-count");
            const elFriend = document.getElementById("stat-friend-count");
            const elOverlap = document.getElementById("stat-overlap-percentage");
            const elDetail = document.getElementById("stat-overlap-detail");

            const both = stats.both_count || 0;
            const my = stats.my_only_count || 0;
            const friend = stats.friend_only_count || 0;
            const totalUnion = both + my + friend;

            if (elBoth) elBoth.innerText = both;
            if (elMy) elMy.innerText = my;
            if (elFriend) elFriend.innerText = friend;
            if (elOverlap) elOverlap.innerText = (stats.overlap_percentage || 0) + "%";
            if (elDetail) {
                elDetail.innerText = `(兩人共涵蓋 ${totalUnion} 部不重複劇集，共同追蹤 ${both} 部)`;
            }
        }

        function switchCompareSubTab(subTab) {
            activeCompareSubTab = subTab;
            const btnBoth = document.getElementById("btn-compare-both");
            const btnMy = document.getElementById("btn-compare-my");
            const btnFriend = document.getElementById("btn-compare-friend");

            if (btnBoth) btnBoth.className = subTab === "both" ? "btn btn-sm btn-outline-success active flex-fill" : "btn btn-sm btn-outline-success flex-fill";
            if (btnMy) btnMy.className = subTab === "my" ? "btn btn-sm btn-outline-primary active flex-fill" : "btn btn-sm btn-outline-primary flex-fill";
            if (btnFriend) btnFriend.className = subTab === "friend" ? "btn btn-sm btn-outline-warning active flex-fill" : "btn btn-sm btn-outline-warning flex-fill";

            renderFriendCompareList();
        }

        function renderFriendCompareList() {
            const container = document.getElementById("compare-list-container");
            if (!container || !friendCompareData) return;

            if (!friendCompareData.selected_friend) {
                container.innerHTML = `
                    <div class="glass-card p-4 text-center">
                        <i class="fa-solid fa-user-plus fa-2x mb-2 text-success"></i>
                        <h6 class="fw-bold text-dark mb-1">尚未建立好友連線</h6>
                        <p class="small text-muted mb-3">請先至「👥 好友管理」頁籤點擊「加好友」，完成連線後即可互相比對追劇清單與品味契合度！</p>
                        <button class="btn btn-sm btn-success rounded-pill px-3 py-1 fw-bold shadow-sm" onclick="switchTab('friends'); document.getElementById('friends-tab').click();">
                            <i class="fa-solid fa-users me-1"></i>前往「👥 好友管理」新增好友
                        </button>
                    </div>
                `;
                return;
            }

            let targetList = [];
            if (activeCompareSubTab === "both") targetList = friendCompareData.both_tracked || [];
            else if (activeCompareSubTab === "my") targetList = friendCompareData.my_only || [];
            else if (activeCompareSubTab === "friend") targetList = friendCompareData.friend_only || [];

            container.innerHTML = "";

            if (targetList.length === 0) {
                let emptyMsg = "此分類下暫無劇集比對資料";
                if (activeCompareSubTab === "both") emptyMsg = "兩人目前尚無共同收藏的劇集";
                else if (activeCompareSubTab === "my") emptyMsg = "您收藏的劇集好友也全都有收藏喔！";
                else if (activeCompareSubTab === "friend") emptyMsg = "好友收藏的劇集您也都已經收藏囉！";

                container.innerHTML = `
                    <div class="glass-card p-4 text-center text-muted">
                        <i class="fa-solid fa-handshake-simple fa-2x mb-2 text-secondary"></i>
                        <p class="mb-0 small text-dark fw-bold">${emptyMsg}</p>
                    </div>
                `;
                return;
            }

            targetList.forEach(item => {
                let imgHtml = renderPreviewImagesHtml(item.image_url);
                let isMovie = isMovieItem(item);
                let progressBadge = "";
                let subtextHtml = "";

                if (isMovie) {
                    progressBadge = `
                        <div class="small fw-bold text-danger mb-1">
                            <span class="badge bg-danger bg-opacity-25 text-danger border border-danger"><i class="fa-solid fa-film me-1"></i>🎬 劇場版 / 電影</span>
                        </div>
                    `;
                    subtextHtml = `👥 ${item.tracked_users_count || 0} 人收藏 | 🎬 劇場版 / 電影`;
                } else {
                    subtextHtml = `👥 ${item.tracked_users_count || 0} 人收藏`;
                    if (activeCompareSubTab === "both") {
                        progressBadge = `
                            <div class="small fw-bold text-success mb-1">
                                <span class="badge bg-success bg-opacity-25 text-success border border-success me-1">我：看至第 ${item.my_episode} 集</span>
                                <span class="badge bg-info bg-opacity-25 text-info border border-info">好友：看至第 ${item.friend_episode} 集</span>
                            </div>
                        `;
                    } else if (activeCompareSubTab === "my") {
                        progressBadge = `
                            <div class="small fw-bold text-primary mb-1">
                                <span class="badge bg-primary bg-opacity-25 text-primary border border-primary">我已看至第 ${item.my_episode} 集</span>
                            </div>
                        `;
                    } else if (activeCompareSubTab === "friend") {
                        progressBadge = `
                            <div class="small fw-bold text-warning mb-1">
                                <span class="badge bg-warning bg-opacity-25 text-warning border border-warning">好友已看至第 ${item.friend_episode} 集</span>
                            </div>
                        `;
                    }
                }

                let actionBtnHtml = "";
                if (activeCompareSubTab === "friend") {
                    actionBtnHtml = `
                        <button class="btn btn-sm btn-success py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="joinDrama(${item.drama_id}, this)">
                            <i class="fa-solid fa-plus me-1"></i>加入我的追劇
                        </button>
                    `;
                }

                const html = `
                    <div class="glass-card p-3 drama-item d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center flex-grow-1 me-2" style="max-width: 80%;">
                            ${imgHtml}
                            <div class="flex-grow-1" style="min-width: 0;">
                                <div class="d-flex align-items-center mb-1 gap-2 flex-wrap">
                                    <span class="badge bg-primary small">${item.category}</span>
                                </div>
                                <h5 class="fw-bold mb-1 text-dark" style="font-size: 1.05rem; word-break: break-all;">${item.title}</h5>
                                ${progressBadge}
                                <div class="text-muted" style="font-size: 0.7rem; margin-top: 3px;">
                                    ${subtextHtml}
                                </div>
                            </div>
                        </div>
                        <div class="d-flex flex-column gap-1">
                            ${actionBtnHtml}
                            <button class="btn btn-sm btn-outline-secondary py-1 px-2 text-nowrap" style="font-size: 0.75rem;" onclick="openRecommendModal(${item.drama_id}, '${item.title.replace(/'/g, "\\'")}')">
                                <i class="fa-solid fa-share-nodes me-1"></i>推薦
                            </button>
                        </div>
                    </div>
                `;
                container.innerHTML += html;
            });
        }

        // 點擊切換追蹤狀態
        function toggleTrack(id, isTracked) {
            fetch(apiBaseUrl + `/line/api/dramas/update_progress/${id}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    access_token: userAccessToken,
                    is_tracked: isTracked
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    fetchDramas("my_dramas", myDramasPage);
                } else {
                    Swal.fire("錯誤", "更改追蹤狀態失敗", "error");
                }
            });
        }

        // 相關活動連結多欄位控制
        function addLinkRow(title = "", url = "") {
            const container = document.getElementById("link-rows-container");
            const rowDiv = document.createElement("div");
            rowDiv.className = "d-flex gap-1 link-row-item";
            rowDiv.innerHTML = `
                <input type="text" class="form-control form-control-sm link-title" placeholder="連結名稱 (如: 巴哈)" value="${title}" style="flex: 2;">
                <input type="url" class="form-control form-control-sm link-url" placeholder="URL 網址" value="${url}" style="flex: 4;">
                <button class="btn btn-sm btn-outline-danger px-2" onclick="this.parentElement.remove()"><i class="fa-solid fa-xmark"></i></button>
            `;
            container.appendChild(rowDiv);
        }

        // 新增劇集
        // 全屏預覽圖 Lightbox 互動邏輯
        let currentLightboxUrls = [];
        let currentLightboxIndex = 0;

        function openLightbox(urls, initialIdx = 0) {
            if (!urls || urls.length === 0) return;
            currentLightboxUrls = urls;
            currentLightboxIndex = initialIdx;

            const overlay = document.getElementById("imageLightboxOverlay");
            const carousel = document.getElementById("lightbox-carousel");
            const prevBtn = document.getElementById("lightbox-prev-btn");
            const nextBtn = document.getElementById("lightbox-next-btn");
            const badge = document.getElementById("lightbox-badge");

            carousel.innerHTML = urls.map((u, i) => `
                <div class="d-flex align-items-center justify-content-center w-100 h-100 flex-shrink-0" style="scroll-snap-align: center; width: 100vw; height: 100vh;">
                    <img src="${u}" style="max-width: 95vw; max-height: 85vh; object-fit: contain; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.8);" alt="預覽圖 ${i+1}">
                </div>
            `).join('');

            if (urls.length > 1) {
                prevBtn.style.display = 'flex';
                nextBtn.style.display = 'flex';
                badge.style.display = 'inline-block';
                badge.innerText = `${initialIdx + 1} / ${urls.length}`;
            } else {
                prevBtn.style.display = 'none';
                nextBtn.style.display = 'none';
                badge.style.display = 'none';
            }

            overlay.classList.remove("d-none");
            overlay.classList.add("d-flex");
            document.body.style.overflow = "hidden";

            setTimeout(() => {
                carousel.scrollLeft = initialIdx * carousel.clientWidth;
            }, 50);
        }

        function closeLightbox() {
            const overlay = document.getElementById("imageLightboxOverlay");
            if (overlay) {
                overlay.classList.remove("d-flex");
                overlay.classList.add("d-none");
            }
            document.body.style.overflow = "";
        }

        function handleLightboxBackdropClick(e) {
            if (e.target.id === 'imageLightboxOverlay' || e.target.classList.contains('w-100')) {
                closeLightbox();
            }
        }

        function navigateLightbox(dir) {
            const carousel = document.getElementById("lightbox-carousel");
            if (!carousel || currentLightboxUrls.length <= 1) return;
            
            let newIdx = currentLightboxIndex + dir;
            if (newIdx < 0) newIdx = 0;
            if (newIdx >= currentLightboxUrls.length) newIdx = currentLightboxUrls.length - 1;
            
            currentLightboxIndex = newIdx;
            carousel.scrollTo({
                left: newIdx * carousel.clientWidth,
                behavior: 'smooth'
            });
        }

        function onLightboxScroll(el) {
            if (!el || currentLightboxUrls.length <= 1) return;
            const idx = Math.round(el.scrollLeft / el.clientWidth);
            if (idx >= 0 && idx < currentLightboxUrls.length) {
                currentLightboxIndex = idx;
                const badge = document.getElementById("lightbox-badge");
                if (badge) {
                    badge.innerText = `${idx + 1} / ${currentLightboxUrls.length}`;
                }
            }
        }

        document.addEventListener('keydown', function(e) {
            const overlay = document.getElementById("imageLightboxOverlay");
            if (overlay && !overlay.classList.contains("d-none")) {
                if (e.key === "Escape") closeLightbox();
                else if (e.key === "ArrowLeft") navigateLightbox(-1);
                else if (e.key === "ArrowRight") navigateLightbox(1);
            }
        });

        // 滑動切換多張預覽圖 (Carousel) 輔助函式
        function scrollCarousel(uid, direction, btn) {
            if (btn) event.stopPropagation();
            const el = document.getElementById(uid);
            if (el) {
                el.scrollBy({ left: direction * 85, behavior: 'smooth' });
            }
        }

        function updateCarouselBadge(uid, total, el) {
            const badge = document.getElementById(uid + '-badge');
            if (badge && el) {
                const idx = Math.round(el.scrollLeft / 85) + 1;
                badge.innerText = `${Math.max(1, Math.min(idx, total))}/${total}`;
            }
        }

        function renderPreviewImagesHtml(imageUrlData) {
            let urls = [];
            if (Array.isArray(imageUrlData)) {
                urls = imageUrlData;
            } else if (typeof imageUrlData === 'string' && imageUrlData.trim()) {
                const str = imageUrlData.trim();
                if (str.startsWith('[')) {
                    try {
                        const arr = JSON.parse(str);
                        if (Array.isArray(arr)) urls = arr;
                    } catch(e) {
                        urls = str.split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
                    }
                } else {
                    urls = str.split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
                }
            }

            urls = urls.filter(u => u && typeof u === 'string');
            if (urls.length === 0) return '';

            const urlsJson = JSON.stringify(urls).replace(/"/g, '&quot;');

            if (urls.length === 1) {
                return `<img src="${urls[0]}" class="drama-cover me-3" style="width: 85px; height: 115px; object-fit: cover; border-radius: 8px; flex-shrink: 0; box-shadow: 0 4px 10px rgba(0,0,0,0.3); cursor: pointer;" onclick="openLightbox(${urlsJson}, 0)" onerror="this.style.display='none';" alt="預覽圖">`;
            }

            const uid = 'carousel-' + Math.random().toString(36).substr(2, 9);
            const imgsHtml = urls.map((u, idx) => 
                `<img src="${u}" style="width: 85px; height: 115px; object-fit: cover; scroll-snap-align: start; flex-shrink: 0; border-radius: 8px; cursor: pointer;" onclick="openLightbox(${urlsJson}, ${idx})" onerror="this.style.display='none';" alt="預覽圖 ${idx+1}">`
            ).join('');

            return `
                <div class="drama-cover-carousel me-3 position-relative" style="width: 85px; height: 115px; flex-shrink: 0;">
                    <div id="${uid}" class="d-flex" style="width: 85px; height: 115px; overflow-x: auto; scroll-snap-type: x mandatory; scroll-behavior: smooth; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); scrollbar-width: none; -ms-overflow-style: none;" onscroll="updateCarouselBadge('${uid}', ${urls.length}, this)">
                        ${imgsHtml}
                    </div>
                    <span id="${uid}-badge" class="badge bg-dark bg-opacity-75 text-white position-absolute" style="bottom: 3px; right: 3px; font-size: 0.55rem; padding: 2px 4px; border-radius: 4px; pointer-events: none; backdrop-filter: blur(2px); z-index: 3;">1/${urls.length}</span>
                    <button type="button" class="btn p-0 text-white position-absolute top-50 start-0 translate-middle-y d-flex align-items-center justify-content-center" style="width: 16px; height: 26px; background: rgba(0,0,0,0.5); border: none; border-radius: 0 4px 4px 0; font-size: 0.75rem; z-index: 3; line-height: 1;" onclick="scrollCarousel('${uid}', -1, this)">‹</button>
                    <button type="button" class="btn p-0 text-white position-absolute top-50 end-0 translate-middle-y d-flex align-items-center justify-content-center" style="width: 16px; height: 26px; background: rgba(0,0,0,0.5); border: none; border-radius: 4px 0 0 4px; font-size: 0.75rem; z-index: 3; line-height: 1;" onclick="scrollCarousel('${uid}', 1, this)">›</button>
                </div>
            `;
        }

        function openAddDramaModal() {
            document.getElementById("dramaModalTitle").innerText = "新增劇集項目";
            document.getElementById("edit-drama-id").value = "";
            document.getElementById("drama-title").value = "";
            
            const selectEl = document.getElementById("drama-category-select");
            selectEl.value = "其他";
            const inputEl = document.getElementById("drama-category");
            inputEl.value = "其他";
            inputEl.classList.add("d-none");

            document.getElementById("drama-seasons").value = "1";
            document.getElementById("drama-episodes").value = "12";
            document.getElementById("drama-image-url").value = "";
            document.getElementById("link-rows-container").innerHTML = "";
            
            const modal = new bootstrap.Modal(document.getElementById("dramaModal"));
            modal.show();
        }

        // 編輯劇集主檔資訊
        function editDramaDetailsModal(id, title, category, seasons, episodes, links) {
            document.getElementById("dramaModalTitle").innerText = "編輯劇集共享資訊";
            document.getElementById("edit-drama-id").value = id;
            document.getElementById("drama-title").value = title;
            
            const selectEl = document.getElementById("drama-category-select");
            const inputEl = document.getElementById("drama-category");
            inputEl.value = category;
            
            let matched = false;
            for (let i = 0; i < selectEl.options.length; i++) {
                if (selectEl.options[i].value === category) {
                    selectEl.value = category;
                    matched = true;
                    break;
                }
            }
            if (!matched) {
                selectEl.value = "__custom__";
                inputEl.classList.remove("d-none");
            } else {
                inputEl.classList.add("d-none");
            }

            document.getElementById("drama-seasons").value = seasons;
            document.getElementById("drama-episodes").value = episodes;
            
            const container = document.getElementById("link-rows-container");
            container.innerHTML = "";
            if (links && links.length > 0) {
                links.forEach(l => addLinkRow(l.title, l.url));
            }

            const modal = new bootstrap.Modal(document.getElementById("dramaModal"));
            modal.show();
        }

        function submitDramaForm() {
            const id = document.getElementById("edit-drama-id").value;
            const title = document.getElementById("drama-title").value;
            
            const selectEl = document.getElementById("drama-category-select");
            const inputEl = document.getElementById("drama-category");
            let finalCategory = inputEl.value.trim();
            if (selectEl.value !== "__custom__") {
                finalCategory = selectEl.value;
            }
            if (!finalCategory) {
                finalCategory = "其他";
            }

            const totalSeasons = document.getElementById("drama-seasons").value;
            const totalEpisodes = document.getElementById("drama-episodes").value;
            const imageUrl = document.getElementById("drama-image-url").value.trim();

            if (!title) {
                alert("劇名不可空白！");
                return;
            }

            const linkRows = document.querySelectorAll(".link-row-item");
            const links = [];
            linkRows.forEach(row => {
                const lt = row.querySelector(".link-title").value;
                const lu = row.querySelector(".link-url").value;
                if (lt && lu) {
                    links.push({ title: lt, url: lu });
                }
            });

            const url = id ? `/line/api/dramas/update/${id}/` : "/line/api/dramas/create/";
            const payload = {
                access_token: userAccessToken,
                title: title,
                category: finalCategory,
                total_seasons: parseInt(totalSeasons),
                total_episodes: parseInt(totalEpisodes),
                info_links: links,
                image_url: imageUrl
            };

            fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    bootstrap.Modal.getInstance(document.getElementById("dramaModal")).hide();
                    Swal.fire({ title: '儲存成功！', text: id ? '如果連結有異動，系統將自動推播通知其他追蹤該劇的好友。' : '', icon: 'success' });
                    fetchDramas("my_dramas", myDramasPage);
                } else {
                    Swal.fire("錯誤", "儲存失敗：" + data.error, "error");
                }
            });
        }

        // 好友管理與搜尋
        function fetchFriends(query = "") {
            fetch(apiBaseUrl + "/line/api/friends/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    access_token: userAccessToken,
                    query: query
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    myFriendsList = data.friends;
                    renderFriends(data.friends);
                    renderSearchResults(data.others);
                    renderRecommendFriendsSelector(data.friends);
                }
            });
        }

        function handleFriendSearch() {
            const query = document.getElementById("friend-search-input").value;
            fetchFriends(query);
        }

        function renderFriends(friends) {
            const container = document.getElementById("friends-list");
            container.innerHTML = "";
            if (!friends || friends.length === 0) {
                container.innerHTML = `
                    <div class="p-3 text-center rounded bg-light border">
                        <i class="fa-solid fa-user-group mb-1 text-secondary" style="font-size: 1.2rem;"></i>
                        <p class="small text-dark fw-bold mb-1">目前尚無已連線好友</p>
                        <p class="small text-muted mb-0" style="font-size: 0.75rem;">請在下方「可新增的 LINE 用戶」點擊「加好友」即可完成連線！</p>
                    </div>
                `;
                return;
            }
            friends.forEach(f => {
                container.innerHTML += `
                    <div class="d-flex align-items-center justify-content-between p-2 border rounded bg-white shadow-sm small mb-1">
                        <div class="d-flex align-items-center">
                            <i class="fa-brands fa-line text-success me-2" style="font-size: 1.1rem;"></i>
                            <span class="fw-bold text-dark">${f.display_name}</span>
                        </div>
                        <span class="badge bg-success">好友已連線</span>
                    </div>
                `;
            });
        }

        function renderSearchResults(others) {
            const container = document.getElementById("search-results-list");
            container.innerHTML = "";
            if (!others || others.length === 0) {
                container.innerHTML = `<div class="p-2 text-center text-muted small">暫無可新增的 LINE 用戶</div>`;
                return;
            }
            others.forEach(o => {
                container.innerHTML += `
                    <div class="d-flex align-items-center justify-content-between p-2 border rounded bg-white shadow-sm small mb-1">
                        <span class="fw-bold text-dark"><i class="fa-brands fa-line text-success me-1"></i>${o.display_name}</span>
                        <button class="btn btn-sm btn-outline-success py-1 px-2 fw-bold" style="font-size: 0.75rem;" onclick="handleAddFriend(${o.id})">
                            <i class="fa-solid fa-user-plus me-1"></i>加好友
                        </button>
                    </div>
                `;
            });
        }

        function handleAddFriend(friendId) {
            if (!friendId) return;

            fetch(apiBaseUrl + "/line/api/friends/add/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    access_token: userAccessToken,
                    friend_id: parseInt(friendId)
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    Swal.fire({ title: '好友已建立！', text: '現在您可以互相推薦喜愛的神劇清單了。', icon: 'success' });
                    document.getElementById("friend-search-input").value = "";
                    fetchFriends();
                } else {
                    Swal.fire("錯誤", "加好友失敗：" + data.error, "error");
                }
            });
        }


        function switchRecSubTab(subTab) {
            recSubTab = subTab;
            const btnPending = document.getElementById("rec-tab-pending");
            const btnAccepted = document.getElementById("rec-tab-accepted");
            const btnRejected = document.getElementById("rec-tab-rejected");

            [btnPending, btnAccepted, btnRejected].forEach(b => {
                if (b) {
                    b.classList.remove("active", "btn-success", "btn-secondary");
                    b.classList.add("btn-outline-success", "text-dark");
                }
            });

            const targetBtn = document.getElementById("rec-tab-" + subTab);
            if (targetBtn) {
                targetBtn.classList.remove("btn-outline-success", "btn-outline-secondary", "text-dark");
                targetBtn.classList.add("active");
            }

            recsMasterList = null;
            fetchDramas("recommendations", 1, true);
        }

        // 推薦劇集 Modal 好友選擇器 (顯示好友暱稱與該劇集是否已加入對方的追劇清單狀態)
        function renderRecommendFriendsSelector(friends, statusMap = {}) {
            const container = document.getElementById("rec-friends-checkboxes");
            if (!container) return;
            container.innerHTML = "";
            if (!friends || friends.length === 0) {
                container.innerHTML = `<p class="small text-muted py-1">請先至好友管理頁面加好友！</p>`;
                return;
            }
            friends.forEach(f => {
                const fStatus = statusMap[f.id] || {};
                let statusBadge = "";
                let isDisabled = false;

                if (fStatus.is_in_watchlist || fStatus.is_accepted) {
                    statusBadge = `<span class="badge bg-success ms-2 shadow-sm" style="font-size: 0.72rem;"><i class="fa-solid fa-check me-1"></i>已在對方的追劇清單中</span>`;
                    isDisabled = true;
                } else if (fStatus.is_pending) {
                    statusBadge = `<span class="badge bg-warning text-dark ms-2" style="font-size: 0.72rem;"><i class="fa-solid fa-clock me-1"></i>已發送推薦，等待中</span>`;
                    isDisabled = true;
                }

                container.innerHTML += `
                    <div class="form-check d-flex align-items-center justify-content-between py-1 border-bottom border-light">
                        <div>
                            <input class="form-check-input rec-friend-chk" type="checkbox" value="${f.id}" id="rec-friend-${f.id}" ${isDisabled ? 'disabled' : ''}>
                            <label class="form-check-label small fw-bold ${isDisabled ? 'text-muted' : 'text-dark'}" for="rec-friend-${f.id}">
                                ${f.display_name}
                            </label>
                        </div>
                        <div>${statusBadge}</div>
                    </div>
                `;
            });
        }

        function openRecommendModal(dramaId, dramaTitle) {
            document.getElementById("rec-drama-id").value = dramaId;
            document.getElementById("rec-drama-title").value = dramaTitle;
            document.getElementById("rec-notes").value = "";
            
            const container = document.getElementById("rec-friends-checkboxes");
            if (container) {
                container.innerHTML = `<div class="text-center py-2 text-muted small"><div class="spinner-border spinner-border-sm me-1 text-success"></div>檢查好友追劇清單狀態...</div>`;
            }

            const modal = new bootstrap.Modal(document.getElementById("recommendModal"));
            modal.show();

            // 檢查好友對此劇集的追劇清單與推薦狀態
            fetch(apiBaseUrl + "/line/api/dramas/check_friend_status/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    access_token: userAccessToken,
                    drama_id: parseInt(dramaId)
                })
            })
            .then(res => res.json())
            .then(data => {
                const statusMap = (data.status === "success") ? (data.friend_status || {}) : {};
                renderRecommendFriendsSelector(myFriendsList, statusMap);
            })
            .catch(err => {
                console.error(err);
                renderRecommendFriendsSelector(myFriendsList, {});
            });
        }

        // 推薦劇集送出
        function submitRecommendForm() {
            const dramaId = document.getElementById("rec-drama-id").value;
            const notes = document.getElementById("rec-notes").value;
            const checkboxes = document.querySelectorAll(".rec-friend-chk:checked");
            
            if (checkboxes.length === 0) {
                alert("請至少選擇一位好友推薦！");
                return;
            }

            const friendIds = [];
            checkboxes.forEach(chk => friendIds.push(parseInt(chk.value)));

            fetch(apiBaseUrl + "/line/api/dramas/recommend/", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    access_token: userAccessToken,
                    drama_id: parseInt(dramaId),
                    friend_ids: friendIds,
                    recommend_notes: notes
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    bootstrap.Modal.getInstance(document.getElementById("recommendModal")).hide();
                    let text = '已向可接收的好友發送 LINE 推播推薦。';
                    if (data.skipped_list && data.skipped_list.length > 0) {
                        text += '\n\n以下因重複已被過濾：\n' + data.skipped_list.join('\n');
                    }
                    Swal.fire({ title: '推薦發送成功！', text: text, icon: 'success' });
                } else {
                    Swal.fire("發送失敗", "無法推薦：\n" + data.error, "warning");
                }
            });
        }

        // 接受推薦：立刻移至已加入清單，並立刻更新「我的追劇清單」
        function acceptRecommend(id) {
            fetch(apiBaseUrl + `/line/api/dramas/accept_recommend/${id}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ access_token: userAccessToken })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    Swal.fire({ title: '已成功接受並加入您的追劇清單！', icon: 'success', timer: 1500, showConfirmButton: false });
                    myDramasMasterList = null;
                    recsMasterList = null;
                    fetchDramas("my_dramas", 1, true);
                    fetchDramas("recommendations", 1, true);
                    fetchCategories();
                } else {
                    Swal.fire("錯誤", "接受失敗：" + data.error, "error");
                }
            });
        }

        // 拒絕推薦 (移至拒絕/歷史紀錄)
        function rejectRecommend(id) {
            fetch(apiBaseUrl + `/line/api/dramas/reject_recommend/${id}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ access_token: userAccessToken })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    Swal.fire({ title: '已拒絕此推薦', icon: 'info', timer: 1200, showConfirmButton: false });
                    recsMasterList = null;
                    fetchDramas("recommendations", 1, true);
                } else {
                    Swal.fire("錯誤", "拒絕失敗：" + data.error, "error");
                }
            });
        }

        // 忽略 / 隱藏推薦 (直接從待處理中隱藏)
        function ignoreRecommend(id) {
            fetch(apiBaseUrl + `/line/api/dramas/ignore_recommend/${id}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ access_token: userAccessToken })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    Swal.fire({ title: '已忽略/隱藏此推薦', icon: 'info', timer: 1200, showConfirmButton: false });
                    recsMasterList = null;
                    fetchDramas("recommendations", 1, true);
                } else {
                    Swal.fire("錯誤", "忽略失敗：" + data.error, "error");
                }
            });
        }

        // 一鍵全選批次操作 (一鍵全部接受 / 一鍵全部忽略)
        function batchRecommendAction(action) {
            const actionText = (action === "accept_all") ? "全部接受並加入追劇清單" : "全部忽略隱藏";
            Swal.fire({
                title: `確定要【${actionText}】嗎？`,
                text: "此操作將批次處理所有未讀待處理的好友推薦項目！",
                icon: "warning",
                showCancelButton: true,
                confirmButtonColor: action === 'accept_all' ? '#10b981' : '#6b7280',
                confirmButtonText: "確定執行",
                cancelButtonText: "取消"
            }).then(result => {
                if (result.isConfirmed) {
                    fetch(apiBaseUrl + "/line/api/dramas/batch_recommend_action/", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ access_token: userAccessToken, action: action })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === "success") {
                            Swal.fire("執行完成！", `成功批次處理 ${data.count} 筆推薦項目。`, "success");
                            myDramasMasterList = null;
                            recsMasterList = null;
                            fetchDramas("my_dramas", 1, true);
                            fetchDramas("recommendations", 1, true);
                            fetchCategories();
                        } else {
                            Swal.fire("執行失敗", data.error, "error");
                        }
                    })
                    .catch(err => {
                        console.error(err);
                        Swal.fire("連線錯誤", "無法連線至伺服器", "error");
                    });
                }
            });
        }

        // 劇名自動搜尋/自動填寫功能
        let searchTimeout = null;
        const dramaTitleInput = document.getElementById("drama-title");
        const suggestionsBox = document.getElementById("drama-suggestions");

        dramaTitleInput.addEventListener("input", function() {
            clearTimeout(searchTimeout);
            const q = this.value.trim();
            const editId = document.getElementById("edit-drama-id").value;
            if (editId) {
                suggestionsBox.classList.add("d-none");
                return;
            }

            if (q.length < 1) {
                suggestionsBox.classList.add("d-none");
                return;
            }

            searchTimeout = setTimeout(() => {
                fetch(apiBaseUrl + "/line/api/dramas/search/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ q: q })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.status === "success" && data.results.length > 0) {
                        suggestionsBox.innerHTML = "";
                        data.results.forEach(d => {
                            const btn = document.createElement("button");
                            btn.type = "button";
                            btn.className = "list-group-item list-group-item-action text-start small py-2";
                            btn.style.fontSize = "0.85rem";
                            btn.innerHTML = `<i class="fa-solid fa-film me-2 text-success"></i><strong>${d.title}</strong> <span class="badge bg-secondary ms-2">${d.category}</span>`;
                            btn.addEventListener("click", () => {
                                dramaTitleInput.value = d.title;
                                document.getElementById("drama-category").value = d.category;
                                document.getElementById("drama-seasons").value = d.total_seasons;
                                document.getElementById("drama-episodes").value = d.total_episodes;

                                const container = document.getElementById("link-rows-container");
                                container.innerHTML = "";
                                if (d.info_links && d.info_links.length > 0) {
                                    d.info_links.forEach(l => addLinkRow(l.title, l.url));
                                }

                                suggestionsBox.classList.add("d-none");
                            });
                            suggestionsBox.appendChild(btn);
                        });
                        suggestionsBox.classList.remove("d-none");
                    } else {
                        suggestionsBox.classList.add("d-none");
                    }
                });
            }, 300);
        });

        document.addEventListener("click", function(e) {
            if (e.target !== dramaTitleInput && e.target !== suggestionsBox) {
                suggestionsBox.classList.add("d-none");
            }
        });

        // 探索劇庫：將特定劇集加入個人追劇清單
        function joinDrama(id, btnEl) {
            // --- 樂觀更新 UI (Optimistic Update) ---
            // 1. 立即把按鈕換成「已在清單」，防止重複點擊
            if (btnEl) {
                btnEl.disabled = true;
                btnEl.className = "btn btn-sm btn-secondary py-1 px-2 text-nowrap text-white";
                btnEl.style.cssText = "font-size: 0.75rem; cursor: default;";
                btnEl.innerHTML = '<i class="fa-solid fa-check me-1"></i>已在清單';
            }
            // 2. 同步更新內存中的 allDramasMasterList，使切換頁面後按鈕狀態也正確
            if (allDramasMasterList) {
                const item = allDramasMasterList.find(d => d.drama_id === id);
                if (item) item.is_added = true;
            }
            // 清空 myDramasMasterList 快取，確保使用者切換至「我的追劇」頁籤時能重新加載新資料
            myDramasMasterList = null;

            fetch(apiBaseUrl + `/line/api/dramas/join/${id}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ access_token: userAccessToken })
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "success") {
                    Swal.fire({ title: '成功加入個人清單！', icon: 'success', timer: 1000, showConfirmButton: false });
                } else {
                    Swal.fire("錯誤", "加入失敗：" + data.error, "error");
                    // 失敗時還原按鈕
                    if (btnEl) {
                        btnEl.disabled = false;
                        btnEl.className = "btn btn-sm btn-success py-1 px-2 text-nowrap";
                        btnEl.style.cssText = "font-size: 0.75rem;";
                        btnEl.innerHTML = '<i class="fa-solid fa-plus me-1"></i>加入清單';
                    }
                    if (allDramasMasterList) {
                        const item = allDramasMasterList.find(d => d.drama_id === id);
                        if (item) item.is_added = false;
                    }
                }
            })
            .catch(err => {
                console.error("joinDrama error:", err);
                // 網路錯誤時也還原
                if (btnEl) {
                    btnEl.disabled = false;
                    btnEl.className = "btn btn-sm btn-success py-1 px-2 text-nowrap";
                    btnEl.style.cssText = "font-size: 0.75rem;";
                    btnEl.innerHTML = '<i class="fa-solid fa-plus me-1"></i>加入清單';
                }
                if (allDramasMasterList) {
                    const item = allDramasMasterList.find(d => d.drama_id === id);
                    if (item) item.is_added = false;
                }
            });
        }

        // 我的清單：移除個人收藏 (極速無縫更新，無需全頁重載)
        function removeDrama(id, title, btnEl) {
            Swal.fire({
                title: '確定移除收藏？',
                html: `<span style="color:#ccc">將從清單移除：<br><b>${title}</b></span>`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#e74c3c',
                cancelButtonColor: '#6c757d',
                confirmButtonText: '確定移除',
                cancelButtonText: '取消',
                background: '#1a1a2e',
                color: '#e0e0e0'
            }).then(result => {
                if (!result.isConfirmed) return;

                // 1. 樂觀即時刪除：從記憶體 myDramasMasterList 中除名
                if (myDramasMasterList) {
                    myDramasMasterList = myDramasMasterList.filter(d => d.drama_id !== id);
                }
                // 同步更新 allDramasMasterList 狀態
                if (allDramasMasterList) {
                    const item = allDramasMasterList.find(d => d.drama_id === id);
                    if (item) item.is_added = false;
                }

                // 2. 樂觀 UI 動畫：將對應的卡片元素縮小淡出並從 DOM 移除
                const card = btnEl ? btnEl.closest('.drama-item') : null;
                if (card) {
                    card.style.transition = 'all 0.3s ease';
                    card.style.opacity = '0';
                    card.style.transform = 'scale(0.92)';
                    setTimeout(() => {
                        card.remove();
                        // 重新繪製目前頁面的分頁與選單計數 (完全不發起網路重載與 Loading Spinner)
                        renderClientSideFilteredData('my_dramas', myDramasPage);
                    }, 300);
                } else {
                    renderClientSideFilteredData('my_dramas', myDramasPage);
                }

                // 3. 背景非同步發起 API 移除請求
                fetch(apiBaseUrl + `/line/api/dramas/remove/${id}/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ access_token: userAccessToken })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'success') {
                        // 成功時彈出輕量提示，不觸發任何全頁重載
                        Swal.fire({ 
                            title: '已移除收藏', 
                            icon: 'success', 
                            timer: 1000, 
                            showConfirmButton: false,
                            background: '#1a1a2e', 
                            color: '#e0e0e0' 
                        });
                    } else {
                        Swal.fire('錯誤', '移除失敗：' + data.error, 'error');
                        // 失敗時重新讀取還原畫面
                        myDramasMasterList = null;
                        fetchDramas('my_dramas', myDramasPage, true);
                    }
                })
                .catch(err => {
                    console.error('removeDrama error:', err);
                    Swal.fire('錯誤', '網路連線失敗', 'error');
                    myDramasMasterList = null;
                    fetchDramas('my_dramas', myDramasPage, true);
                });
            });
        }

        // 抓取所有唯一的分類並填入下拉選單 (分組：動畫類 vs 動畫電影類，由新至舊排序)
        function fetchCategories() {
            const url = apiBaseUrl + "/line/api/dramas/categories/";
            fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ access_token: userAccessToken })
            })
            .then(res => {
                if (!res.ok) {
                    throw new Error("HTTP status " + res.status);
                }
                return res.json();
            })
            .then(data => {
                if (data.status === "success") {
                    // 計算總部數
                    let totalAll = 0;
                    if (data.all_counts) {
                        Object.values(data.all_counts).forEach(v => totalAll += v);
                    }
                    let totalMy = 0;
                    if (data.my_counts) {
                        Object.values(data.my_counts).forEach(v => totalMy += v);
                    }

                    // 輔助函數：將分類清單拆分為「動畫新番」與「動畫電影」兩個分組
                    function buildGroupedOptions(catList, countsObj) {
                        const tvCats = [];
                        const movieCats = [];
                        
                        catList.forEach(cat => {
                            if (cat.includes("電影") || cat.includes("劇場版")) {
                                movieCats.push(cat);
                            } else {
                                tvCats.push(cat);
                            }
                        });

                        const tvUnknownIdx = tvCats.indexOf("動畫化決定");
                        if (tvUnknownIdx > -1) {
                            tvCats.splice(tvUnknownIdx, 1);
                            tvCats.unshift("動畫化決定");
                        }

                        const movieUnknownIdx = movieCats.indexOf("日本動畫電影製作決定");
                        if (movieUnknownIdx > -1) {
                            movieCats.splice(movieUnknownIdx, 1);
                            movieCats.unshift("日本動畫電影製作決定");
                        }

                        let html = "";
                        if (tvCats.length > 0) {
                            html += `<optgroup label="📺 季番動畫 (由新至舊)">`;
                            tvCats.forEach(cat => {
                                const count = countsObj ? (countsObj[cat] || 0) : 0;
                                html += `<option value="${cat}">${cat} (${count}部)</option>`;
                            });
                            html += `</optgroup>`;
                        }
                        if (movieCats.length > 0) {
                            html += `<optgroup label="🎬 動畫電影 / 劇場版 (由新至舊)">`;
                            movieCats.forEach(cat => {
                                const count = countsObj ? (countsObj[cat] || 0) : 0;
                                html += `<option value="${cat}">${cat} (${count}部)</option>`;
                            });
                            html += `</optgroup>`;
                        }
                        return html;
                    }

                    // 1. 全部劇集的分類選單 (探索新番)
                    const searchSelect = document.getElementById("all-dramas-cat-select");
                    if (searchSelect) {
                        const currentVal = searchSelect.value;
                        searchSelect.innerHTML = `<option value="">所有分類 (${totalAll}部)</option>` + buildGroupedOptions(data.categories, data.all_counts);
                        searchSelect.value = currentVal;
                    }

                    // 2. 我的追劇分類選單 (個人清單：只顯示個人有追過的分類選項 count > 0)
                    const mySelect = document.getElementById("my-dramas-cat-select");
                    if (mySelect) {
                        const currentVal = mySelect.value;
                        const myCategoriesOnly = data.my_categories || data.categories.filter(cat => (data.my_counts && data.my_counts[cat] > 0));
                        mySelect.innerHTML = `<option value="">所有我的追劇 (${totalMy}部)</option>` + buildGroupedOptions(myCategoriesOnly, data.my_counts);
                        mySelect.value = currentVal;
                    }

                    // 渲染快捷年度視覺 Chips 導航面板 (季番 vs 電影，預設前5項)
                    renderVisualChips(data);
                    const modalSelect = document.getElementById("drama-category-select");
                    if (modalSelect) {
                        modalSelect.innerHTML = buildGroupedOptions(data.categories, null);
                        const customOpt = document.createElement("option");
                        customOpt.value = "__custom__";
                        customOpt.innerText = "➕ 自訂新分類...";
                        modalSelect.appendChild(customOpt);
                    }
                } else {
                    console.error("fetchCategories status error", data);
                }
            })
            .catch(err => {
                console.error("fetchCategories failed", err);
            });
        }

        // 切換自訂分類輸入框顯示
        function toggleCustomCategoryInput() {
            const selectEl = document.getElementById("drama-category-select");
            const inputEl = document.getElementById("drama-category");
            if (selectEl.value === "__custom__") {
                inputEl.classList.remove("d-none");
                inputEl.value = "";
                inputEl.focus();
            } else {
                inputEl.classList.add("d-none");
                inputEl.value = selectEl.value;
            }
        }

        // 探索新番即時搜尋與分類過濾
        let allDramasSearchTimeout = null;
        function triggerAllDramasSearch() {
            clearTimeout(allDramasSearchTimeout);
            allDramasSearchTimeout = setTimeout(() => {
                allDramasPage = 1;
                fetchDramas("all_dramas", 1);
            }, 300);
        }

        // 我的追劇即時搜尋與分類過濾
        let myDramasSearchTimeout = null;
        function triggerMyDramasSearch() {
            clearTimeout(myDramasSearchTimeout);
            myDramasSearchTimeout = setTimeout(() => {
                myDramasPage = 1;
                fetchDramas("my_dramas", 1);
            }, 300);
        }
    