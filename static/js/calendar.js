/* ========== Homepage Calendar Widget ========== */

class CalendarWidget {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        const now = new Date();
        this.year = now.getFullYear();
        this.month = now.getMonth() + 1; // 1-based
        this._abortController = null;
    }

    init() {
        if (!this.container) return;
        this._renderShell();
        this.fetchItems();
    }

    /* ---------- Shell (header + empty grid) ---------- */
    _renderShell() {
        this.container.innerHTML = `
            <div class="cal-header">
                <button class="cal-prev" aria-label="上個月">&#8249;</button>
                <span class="cal-title"></span>
                <button class="cal-today">今日</button>
                <button class="cal-next" aria-label="下個月">&#8250;</button>
            </div>
            <div class="cal-grid" id="${this.container.id}-grid"></div>
        `;

        this.container.querySelector(".cal-prev").addEventListener("click", () => {
            this.month--;
            if (this.month < 1) { this.month = 12; this.year--; }
            this.fetchItems();
        });
        this.container.querySelector(".cal-next").addEventListener("click", () => {
            this.month++;
            if (this.month > 12) { this.month = 1; this.year++; }
            this.fetchItems();
        });
        this.container.querySelector(".cal-today").addEventListener("click", () => {
            const today = new Date();
            this.year = today.getFullYear();
            this.month = today.getMonth() + 1;
            this.fetchItems();
        });
    }

    /* ---------- Fetch ---------- */
    fetchItems() {
        // Cancel any in-flight request
        if (this._abortController) {
            this._abortController.abort();
        }
        this._abortController = new AbortController();

        this._updateTitle();
        this._renderLoading();

        fetch(`/api/calendar-items?year=${this.year}&month=${this.month}`, {
            signal: this._abortController.signal,
        })
            .then((res) => {
                if (!res.ok) throw new Error("伺服器錯誤");
                return res.json();
            })
            .then((data) => {
                this._renderItems(data.items || []);
            })
            .catch((err) => {
                if (err.name === "AbortError") return; // Intentional cancel — ignore
                this._renderError();
            });
    }

    /* ---------- Title ---------- */
    _updateTitle() {
        const title = this.container.querySelector(".cal-title");
        if (title) {
            title.textContent = `${this.year} 年 ${this.month} 月`;
        }
    }

    /* ---------- Loading skeleton ---------- */
    _renderLoading() {
        const grid = this._grid();
        if (!grid) return;

        const DOW = ["日", "一", "二", "三", "四", "五", "六"];
        let html = DOW.map((d) => `<div class="cal-day-header">${d}</div>`).join("");

        // Fill 5 weeks × 7 days of shimmer cells
        for (let i = 0; i < 35; i++) {
            html += `<div class="cal-day cal-shimmer">
                <span class="shimmer-block" style="width:60%"></span>
                <span class="shimmer-block" style="width:80%;margin-top:6px"></span>
            </div>`;
        }
        grid.innerHTML = html;
        grid.classList.add("cal-shimmer");
    }

    /* ---------- Error state ---------- */
    _renderError() {
        const grid = this._grid();
        if (!grid) return;
        grid.innerHTML = `<div class="cal-error" style="grid-column:1/-1">無法載入日曆，請稍後再試。</div>`;
        grid.classList.remove("cal-shimmer");
    }

    /* ---------- Render items ---------- */
    _renderItems(items) {
        const grid = this._grid();
        if (!grid) return;
        grid.classList.remove("cal-shimmer");

        // Group items by date string "YYYY-MM-DD"
        const byDate = {};
        for (const item of items) {
            if (!byDate[item.date]) byDate[item.date] = [];
            byDate[item.date].push(item);
        }

        // Build calendar days
        const firstDay = new Date(this.year, this.month - 1, 1).getDay(); // 0=Sun
        const daysInMonth = new Date(this.year, this.month, 0).getDate();
        const today = new Date();
        const isCurrentMonth =
            today.getFullYear() === this.year && today.getMonth() + 1 === this.month;
        const todayDate = today.getDate();

        const DOW = ["日", "一", "二", "三", "四", "五", "六"];
        let html = DOW.map((d) => `<div class="cal-day-header">${d}</div>`).join("");

        // Leading empty cells
        for (let i = 0; i < firstDay; i++) {
            html += `<div class="cal-day empty"></div>`;
        }

        // Day cells
        for (let day = 1; day <= daysInMonth; day++) {
            const colIndex = (firstDay + day - 1) % 7;
            const dateStr = `${this.year}-${String(this.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
            const dayItems = byDate[dateStr] || [];
            const isToday = isCurrentMonth && day === todayDate;
            const flipClass = colIndex >= 5 ? " flip-left" : "";

            html += `<div class="cal-day${isToday ? " today" : ""}${flipClass}">`;
            html += `<span class="cal-day-num">${day}</span>`;

            if (dayItems.length > 0) {
                const MAX_CHIPS = 3;
                html += `<div class="cal-chips">`;

                const visible = dayItems.slice(0, MAX_CHIPS);
                for (const item of visible) {
                    const cls = item.type === "product" ? "chip-product" : "chip-diary";
                    const href =
                        item.type === "diary"
                            ? `/organize#diary-${item.id}`
                            : `/organize`;
                    const label = item.title || (item.type === "product" ? "商品" : "日記");
                    html += `<span class="${cls}"><a href="${href}" title="${_esc(label)}">${_esc(label)}</a></span>`;
                }

                if (dayItems.length > MAX_CHIPS) {
                    html += `<span class="chip-more">+${dayItems.length - MAX_CHIPS} 則</span>`;
                }

                html += `</div>`; // .cal-chips

                // Tooltip
                html += `<div class="cal-tooltip">`;
                html += `<div class="cal-tooltip-title">${this.month}/${day}</div>`;
                for (const item of dayItems) {
                    const badgeCls = item.type === "product" ? "product" : "diary";
                    const label = item.type === "product" ? "商品" : "日記";
                    const href =
                        item.type === "diary"
                            ? `/organize#diary-${item.id}`
                            : `/organize`;
                    html += `<div class="cal-tooltip-item">
                        <span class="chip-badge ${badgeCls}">${label}</span>
                        <a href="${href}">${_esc(item.title || label)}</a>
                    </div>`;
                }
                html += `</div>`; // .cal-tooltip
            }

            html += `</div>`; // .cal-day
        }

        grid.innerHTML = html;
    }

    /* ---------- Helper ---------- */
    _grid() {
        return document.getElementById(`${this.container.id}-grid`);
    }
}

/* HTML-escape helper (module-level, not a class method) */
function _esc(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
