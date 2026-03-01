# Calendar View Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a List | Calendar toggle to the `/organize` page's Diaries tab so users can view diary entries on a month-grid calendar with a side panel showing entry details.

**Architecture:** Vanilla JS `CalendarView` module loaded from `static/js/calendar.js`. The module consumes the diaries array already fetched by `organize.html`'s inline JS — no new backend endpoints. The toggle switches CSS display between the existing list and a new calendar+side-panel layout.

**Tech Stack:** Python 3.11, Flask 3, Jinja2, vanilla JS (ES2017), no build step, PyMySQL, pytest

---

### Task 1: Confirm baseline tests pass

**Files:** none

**Step 1: Run the full test suite**

```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v
```

Expected: all tests pass (currently 105). If any fail, stop and fix before continuing.

---

### Task 2: Create `static/js/` directory and `calendar.js` module

**Files:**
- Create: `static/js/calendar.js`

**Step 1: Create the directory and file**

Create `static/js/calendar.js` with this exact content:

```javascript
// static/js/calendar.js
// Self-contained CalendarView module. Exposed as window.CalendarView.
window.CalendarView = (function () {
    const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

    let _container = null;
    let _sidePanel = null;
    let _entriesMap = {};
    let _year = 0;
    let _month = 0; // 0-indexed (Jan = 0)

    /** Convert a diaries array → { "YYYY-MM-DD": [entry, ...] } */
    function buildEntriesMap(diaries) {
        const map = {};
        diaries.forEach(function (d) {
            if (!d.created_at) return;
            const dateStr = d.created_at.slice(0, 10); // "YYYY-MM-DD"
            if (!map[dateStr]) map[dateStr] = [];
            map[dateStr].push(d);
        });
        return map;
    }

    /** Mount to DOM elements. Call once after DOM is ready. */
    function init(containerEl, sidePanelEl) {
        _container = containerEl;
        _sidePanel = sidePanelEl;
        const now = new Date();
        _year = now.getFullYear();
        _month = now.getMonth();
    }

    /** Draw the month grid for (year, month) using entriesMap. */
    function render(year, month, entriesMap) {
        _year = year;
        _month = month;
        _entriesMap = entriesMap;

        _container.innerHTML = _buildGrid();

        // Bind clickable day cells
        _container.querySelectorAll('.cal-day[data-date]').forEach(function (cell) {
            cell.addEventListener('click', function () { selectDay(cell.dataset.date); });
        });

        // Bind prev/next nav (re-bound after each render since innerHTML replaces them)
        var prev = _container.querySelector('.cal-nav-prev');
        var next = _container.querySelector('.cal-nav-next');
        if (prev) prev.addEventListener('click', prevMonth);
        if (next) next.addEventListener('click', nextMonth);
    }

    function _buildGrid() {
        var firstDayOfWeek = new Date(_year, _month, 1).getDay(); // 0 = Sun
        var daysInMonth = new Date(_year, _month + 1, 0).getDate();
        var monthLabel = _year + ' 年 ' + (_month + 1) + ' 月';

        var html = '<div class="cal-header">'
            + '<button class="cal-nav cal-nav-prev">&#8249;</button>'
            + '<span class="cal-month-label">' + monthLabel + '</span>'
            + '<button class="cal-nav cal-nav-next">&#8250;</button>'
            + '</div>'
            + '<div class="cal-grid">';

        // Weekday headers
        WEEKDAYS.forEach(function (d) {
            html += '<div class="cal-weekday">' + d + '</div>';
        });

        // Empty cells before the 1st
        for (var i = 0; i < firstDayOfWeek; i++) {
            html += '<div class="cal-day cal-empty"></div>';
        }

        // Day cells
        for (var day = 1; day <= daysInMonth; day++) {
            var dateStr = _year + '-'
                + String(_month + 1).padStart(2, '0') + '-'
                + String(day).padStart(2, '0');
            var hasEntries = !!_entriesMap[dateStr];
            html += '<div class="cal-day' + (hasEntries ? ' has-entries' : '') + '"'
                + (hasEntries ? ' data-date="' + dateStr + '"' : '') + '>'
                + '<span class="cal-day-num">' + day + '</span>'
                + (hasEntries ? '<span class="cal-dot"></span>' : '')
                + '</div>';
        }

        html += '</div>'; // .cal-grid
        return html;
    }

    function prevMonth() {
        if (_month === 0) { _year--; _month = 11; }
        else { _month--; }
        render(_year, _month, _entriesMap);
    }

    function nextMonth() {
        if (_month === 11) { _year++; _month = 0; }
        else { _month++; }
        render(_year, _month, _entriesMap);
    }

    /** Highlight a day cell and populate the side panel. */
    function selectDay(dateStr) {
        _container.querySelectorAll('.cal-day.selected').forEach(function (el) {
            el.classList.remove('selected');
        });
        var cell = _container.querySelector('.cal-day[data-date="' + dateStr + '"]');
        if (cell) cell.classList.add('selected');

        var entries = _entriesMap[dateStr] || [];
        if (!entries.length) {
            _sidePanel.innerHTML = '<p class="cal-empty-msg">這天沒有日記</p>';
            return;
        }
        if (entries.length === 1) {
            _renderEntry(entries[0], dateStr);
        } else {
            _renderPicker(entries, dateStr);
        }
    }

    function _renderEntry(entry, dateStr) {
        _sidePanel.innerHTML = '<div class="cal-entry">'
            + '<div class="cal-entry-date">' + dateStr + '</div>'
            + (entry.image_base64
                ? '<img class="cal-entry-photo" src="' + entry.image_base64 + '" alt="日記圖片">'
                : '<div class="cal-entry-photo-placeholder">📷</div>')
            + '<h3 class="cal-entry-title">' + (entry.title || dateStr) + '</h3>'
            + '<div class="cal-entry-emotion">' + (entry.main_emotion || '') + '</div>'
            + '<div class="cal-entry-describe">' + (entry.describe_text || '').replace(/\n/g, '<br>') + '</div>'
            + (entry.memo ? '<div class="cal-entry-memo"><strong>備註：</strong>' + entry.memo.replace(/\n/g, '<br>') + '</div>' : '')
            + '</div>';
    }

    function _renderPicker(entries, dateStr) {
        var items = entries.map(function (e, i) {
            return '<li><button class="cal-picker-btn" data-idx="' + i + '">'
                + (e.title || '（無標題）') + ' ' + (e.main_emotion || '')
                + '</button></li>';
        }).join('');

        _sidePanel.innerHTML = '<div class="cal-picker">'
            + '<div class="cal-entry-date">' + dateStr + ' — ' + entries.length + ' 則日記</div>'
            + '<ul class="cal-picker-list">' + items + '</ul>'
            + '</div>';

        _sidePanel.querySelectorAll('.cal-picker-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                _renderEntry(entries[parseInt(btn.dataset.idx)], dateStr);
            });
        });
    }

    return {
        init: init,
        render: render,
        buildEntriesMap: buildEntriesMap,
        prevMonth: prevMonth,
        nextMonth: nextMonth,
        selectDay: selectDay
    };
}());
```

**Step 2: Verify the file was created**

```bash
ls -la /path/to/project/static/js/calendar.js
```

Expected: file exists, non-zero size.

---

### Task 3: Create `static/css/calendar.css`

**Files:**
- Create: `static/css/calendar.css`

**Step 1: Create the file**

```css
/* static/css/calendar.css */

/* View toggle buttons */
.diary-view-controls {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
}

.view-btn {
    padding: 6px 18px;
    border: 1px solid #ccc;
    border-radius: 20px;
    background: #fff;
    cursor: pointer;
    font-size: 14px;
    color: #555;
    transition: background 0.15s, color 0.15s;
}

.view-btn.active {
    background: #4a7c59;
    color: #fff;
    border-color: #4a7c59;
}

/* Calendar + side panel wrapper */
.diary-calendar-wrapper {
    display: flex;
    gap: 24px;
    align-items: flex-start;
    flex-wrap: wrap;
}

/* Month header */
.cal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
}

.cal-month-label {
    font-size: 16px;
    font-weight: 600;
    color: #333;
}

.cal-nav {
    background: none;
    border: none;
    font-size: 28px;
    cursor: pointer;
    color: #4a7c59;
    padding: 0 8px;
    line-height: 1;
}

.cal-nav:hover {
    color: #2d5c3a;
}

/* 7-column grid */
.cal-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
    min-width: 280px;
}

.cal-weekday {
    text-align: center;
    font-size: 12px;
    color: #999;
    padding: 4px 0;
    font-weight: 500;
}

.cal-day {
    text-align: center;
    padding: 6px 2px;
    border-radius: 6px;
    min-height: 38px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    color: #444;
    cursor: default;
}

.cal-day.cal-empty {
    background: none;
}

.cal-day.has-entries {
    background: #f0f7f3;
    cursor: pointer;
}

.cal-day.has-entries:hover {
    background: #d4eadb;
}

.cal-day.selected {
    background: #4a7c59;
    color: #fff;
}

.cal-dot {
    display: block;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #4a7c59;
    margin-top: 3px;
}

.cal-day.selected .cal-dot {
    background: #fff;
}

/* Side panel */
.cal-side-panel {
    flex: 1;
    min-width: 200px;
    border-left: 2px solid #f0f0f0;
    padding-left: 20px;
}

.cal-entry-date {
    font-size: 13px;
    color: #999;
    margin-bottom: 10px;
}

.cal-entry-photo {
    width: 100%;
    max-width: 240px;
    border-radius: 10px;
    margin-bottom: 12px;
    object-fit: cover;
    display: block;
}

.cal-entry-photo-placeholder {
    font-size: 48px;
    margin-bottom: 12px;
    text-align: center;
}

.cal-entry-title {
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 6px 0;
    color: #222;
}

.cal-entry-emotion {
    font-size: 14px;
    color: #4a7c59;
    margin-bottom: 10px;
}

.cal-entry-describe {
    font-size: 14px;
    color: #444;
    line-height: 1.7;
}

.cal-entry-memo {
    font-size: 13px;
    color: #777;
    margin-top: 10px;
}

.cal-empty-msg {
    color: #bbb;
    font-size: 14px;
    padding-top: 8px;
}

/* Multi-entry picker */
.cal-picker-list {
    list-style: none;
    padding: 0;
    margin: 8px 0 0 0;
}

.cal-picker-btn {
    width: 100%;
    text-align: left;
    padding: 9px 12px;
    border: 1px solid #eee;
    border-radius: 8px;
    background: #fafafa;
    cursor: pointer;
    margin-bottom: 6px;
    font-size: 14px;
    color: #333;
}

.cal-picker-btn:hover {
    background: #f0f7f3;
    border-color: #c5dfc9;
}

/* Responsive: stack on small screens */
@media (max-width: 600px) {
    .diary-calendar-wrapper {
        flex-direction: column;
    }
    .cal-side-panel {
        border-left: none;
        border-top: 2px solid #f0f0f0;
        padding-left: 0;
        padding-top: 16px;
    }
}
```

---

### Task 4: Modify `templates/organize.html`

**Files:**
- Modify: `templates/organize.html`

**Step 1: Add CSS and JS `<link>`/`<script>` tags**

At the very end of the file, before `{% endblock %}`, add:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/calendar.css') }}">
<script src="{{ url_for('static', filename='js/calendar.js') }}"></script>
```

Place these **before** the existing inline `<script>` block so `CalendarView` is defined before the inline script runs.

**Step 2: Add toggle buttons and calendar HTML inside `#diaries-tab`**

Replace the current diaries tab content:
```html
<div class="tab-content" id="diaries-tab">
    <section class="diary-list" id="diaryList">
        <div class="loading" id="diariesLoading"><div class="spinner"></div><p>載入中...</p></div>
    </section>
</div>
```

With:
```html
<div class="tab-content" id="diaries-tab">
    <div class="diary-view-controls">
        <button class="view-btn active" id="btnListView">列表</button>
        <button class="view-btn" id="btnCalView">月曆</button>
    </div>

    <!-- List view -->
    <section class="diary-list" id="diaryList">
        <div class="loading" id="diariesLoading"><div class="spinner"></div><p>載入中...</p></div>
    </section>

    <!-- Calendar view (hidden by default) -->
    <div class="diary-calendar-wrapper" id="diaryCalendarWrapper" style="display:none;">
        <div id="calendarContainer"></div>
        <div id="calendarSidePanel" class="cal-side-panel">
            <p class="cal-empty-msg">點選日期查看日記</p>
        </div>
    </div>
</div>
```

**Step 3: Update the inline `<script>` block**

Apply these four changes to the inline `<script>` block inside `(function () { ... })()`:

**3a. Add `currentDiaries` and `diaryViewMode` variables** — add after `let currentPetFilter = null;`:

```javascript
let currentDiaries = [];
let diaryViewMode = 'list';
```

**3b. Initialize CalendarView and wire up toggle buttons** — add after the `tabBtns.forEach(...)` line (after the tab-switching block):

```javascript
// Calendar view setup
CalendarView.init(
    document.getElementById('calendarContainer'),
    document.getElementById('calendarSidePanel')
);

const btnListView = document.getElementById('btnListView');
const btnCalView = document.getElementById('btnCalView');
const diaryListEl = document.getElementById('diaryList');
const calendarWrapperEl = document.getElementById('diaryCalendarWrapper');

btnListView.addEventListener('click', function () {
    diaryViewMode = 'list';
    btnListView.classList.add('active');
    btnCalView.classList.remove('active');
    diaryListEl.style.display = '';
    calendarWrapperEl.style.display = 'none';
});

btnCalView.addEventListener('click', function () {
    diaryViewMode = 'calendar';
    btnCalView.classList.add('active');
    btnListView.classList.remove('active');
    diaryListEl.style.display = 'none';
    calendarWrapperEl.style.display = '';
    var map = CalendarView.buildEntriesMap(currentDiaries);
    var now = new Date();
    CalendarView.render(now.getFullYear(), now.getMonth(), map);
});
```

**3c. Store fetched diaries in `currentDiaries`** — in `loadDiaries()`, change:

```javascript
const data = await res.json();
renderDiaries(data.diaries || []);
```

to:

```javascript
const data = await res.json();
currentDiaries = data.diaries || [];
renderDiaries(currentDiaries);
if (diaryViewMode === 'calendar') {
    var map = CalendarView.buildEntriesMap(currentDiaries);
    var now = new Date();
    CalendarView.render(now.getFullYear(), now.getMonth(), map);
}
```

---

### Task 5: Run regression tests and verify manually

**Step 1: Run the full test suite**

```bash
docker exec pet-adorable-life-web python -m pytest tests/ -v
```

Expected: same number of tests pass as baseline (Task 1). The `/organize` page test (`test_organize_page`) must still pass — it just checks HTTP 200, which is unaffected by the JS/HTML additions.

**Step 2: Manual checklist**

Open `http://localhost:5001/organize` in a browser and verify:

- [ ] Page loads without JS errors in console
- [ ] "列表" and "月曆" toggle buttons appear in the Diaries section
- [ ] Clicking "月曆" shows the calendar grid and hides the list
- [ ] Clicking "列表" shows the list and hides the calendar
- [ ] Days with diary entries show a green dot `•`
- [ ] Clicking a dot-marked day highlights it and shows entry details in the side panel
- [ ] Side panel shows: date, photo (or placeholder if none), title, emotion, description
- [ ] If an entry has no title, the date string is shown as the heading
- [ ] Clicking a day with 2+ entries shows a picker list; selecting one shows its detail
- [ ] Prev `‹` and next `›` buttons navigate months; dots remain on correct days
- [ ] Changing the pet filter tab re-fetches diaries and re-renders the calendar
- [ ] An empty month (no entries) shows "點選日期查看日記" in the side panel
- [ ] On narrow screens (< 600px), the side panel stacks below the calendar

---

### Task 6: Commit

```bash
git add static/js/calendar.js static/css/calendar.css templates/organize.html
git commit -m "feat: add calendar view toggle to diary organize tab"
```

---

## Summary of Files Changed

| File | Action |
|------|--------|
| `static/js/calendar.js` | **Create** — `CalendarView` module |
| `static/css/calendar.css` | **Create** — calendar grid + side panel styles |
| `templates/organize.html` | **Modify** — add toggle, calendar HTML, wire up JS |
