# Calendar View for Diary — Design

**Date:** 2026-03-01
**Status:** Approved

## Summary

Add a calendar view toggle to the `/organize` page's Diaries section. Users can switch between the existing list view and a month-grid calendar. Days with diary entries show a dot indicator. Clicking a day opens a side panel with the entry details. The existing pet filter tabs control which pet's entries appear.

## Scope

- Diary entries only (products remain as a list below)
- No new backend endpoints — reuses `/api/diaries?pet_id=N`
- Vanilla JS, no new dependencies, no build step

---

## UI Layout

The `List | Calendar` toggle appears in the Diaries section header, to the right of the "日記" label. Toggling switches a CSS class (`view-list` / `view-calendar`) on the diary section.

**Calendar grid:**
```
[ < ] March 2026 [ > ]
────────────────────────────────
Sun  Mon  Tue  Wed  Thu  Fri  Sat
                               1
 2    3    4  [ 5 ]  6    7    8
              ( • )
 9   10   11   12   13   14   15
...
```

- Days with entries show a `•` dot indicator
- The selected day is highlighted
- Empty days are inert

**Side panel:** Slides in from the right (or appears beside the calendar on wider screens). Displays: pet name, date, photo thumbnail, title, emotion tag, and description. If multiple entries exist on the same day, a picker list is shown first.

---

## Data Flow

1. **On page load / pet filter change:** fetch `/api/diaries?pet_id=N` (same call as list view)
2. **Build lookup map:** `{ "YYYY-MM-DD": [entry, ...] }` from the response
3. **Render grid:** mark days present in the map with a dot
4. **Month navigation:** no re-fetch — the full diary list is already in memory; prev/next just re-renders the grid for a different month window
5. **Day click:** look up date in map → populate side panel from in-memory data (no fetch)
6. **Multiple entries on one day:** show picker list in side panel → user selects → show detail

---

## Architecture

**No backend changes.**

| File | Change |
|------|--------|
| `templates/organize.html` | Add toggle buttons, calendar container `<div>`, side panel `<div>` |
| `static/js/calendar.js` | New — self-contained `CalendarView` module |
| `static/css/calendar.css` | New (optional) — calendar grid styles |

**`CalendarView` module interface:**

```
CalendarView
  ├── init(containerEl, sidePanelEl)   — mount to DOM elements
  ├── render(year, month, entriesMap)  — draw the month grid
  ├── prevMonth() / nextMonth()        — month navigation
  ├── selectDay(dateStr)               — populate side panel
  └── buildEntriesMap(diaries)         — [{...}] → {"YYYY-MM-DD": [...]}
```

The existing `organize.html` JS passes the already-fetched `diaries` array into `CalendarView.render()` when calendar mode is active.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Month with no entries | Calendar renders normally, no dots; side panel shows "這個月還沒有日記" |
| Pet has no diary entries | Same empty state message |
| Entry has no photo | Placeholder icon in side panel |
| Entry has no title | Date string used as heading fallback |
| Network / fetch error | Existing error handling in organize.html covers both views |

---

## Testing

**Automated:**
- `tests/test_app_pages.py` — verify `/organize` page still renders (no regression)
- Existing `/api/diaries` tests cover the data source

**Manual checklist:**
- [ ] Toggle switches between list and calendar view
- [ ] Dots appear on correct days
- [ ] Clicking a day with one entry populates the side panel
- [ ] Clicking a day with multiple entries shows picker, then detail
- [ ] Prev/next month navigation works
- [ ] Pet filter change re-renders the calendar
- [ ] Empty month shows empty state message
- [ ] Entry with no photo shows placeholder
