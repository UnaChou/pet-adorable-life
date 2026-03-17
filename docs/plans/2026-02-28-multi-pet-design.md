# 多隻寵物支援設計

## 目標

支援多隻寵物的使用情境，包含：
1. 寵物檔案管理（名字、品種、生日、照片）
2. 日記與商品可歸屬到特定寵物
3. 日記與整理頁可依寵物篩選

## 方案

方案 B：以寵物為中心的導覽。新增 `/pets` 管理頁，日記和商品各自保留原有流程，多一步選擇歸屬寵物。API 全面改為 RESTful。

---

## 第一節：資料模型

### 新增 `pets` 資料表

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | INT AUTO_INCREMENT PK | |
| `name` | VARCHAR(200) NOT NULL | 寵物名字 |
| `breed` | VARCHAR(200) | 品種/種類 |
| `birthday` | DATE nullable | 生日 |
| `photo_base64` | LONGTEXT nullable | 大頭照 |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### 現有資料表變更

- `pet_diaries` 加 `pet_id` INT nullable（邏輯 FK → `pets.id`）
- `products` 加 `pet_id` INT nullable（邏輯 FK → `pets.id`）

`pet_id` 為 nullable，向下相容既有資料。

---

## 第二節：RESTful API

### `/api/pets`

| 方法 | 路由 | 說明 |
|------|------|------|
| GET | `/api/pets` | 取得所有寵物 |
| POST | `/api/pets` | 新增寵物 |
| GET | `/api/pets/<id>` | 取得單一寵物 |
| PUT | `/api/pets/<id>` | 更新寵物資料 |
| DELETE | `/api/pets/<id>` | 刪除寵物 |

### `/api/products`（取代 form-based `/organize/*`）

| 方法 | 路由 | 說明 |
|------|------|------|
| GET | `/api/products` | 列表（支援 `?pet_id=` 篩選） |
| POST | `/api/products` | 新增（含 `pet_id`） |
| PUT | `/api/products/<id>` | 更新（含 `pet_id`） |
| DELETE | `/api/products/<id>` | 刪除單筆 |
| DELETE | `/api/products` | 批次刪除（body: `{"ids": [...]}`) |

### `/api/diaries`（取代 `/diary/save`、`/diary/remove/batch`）

| 方法 | 路由 | 說明 |
|------|------|------|
| GET | `/api/diaries` | 列表（支援 `?pet_id=` 篩選） |
| POST | `/api/diaries` | 新增（含 `pet_id`） |
| DELETE | `/api/diaries/<id>` | 刪除單筆 |
| DELETE | `/api/diaries` | 批次刪除（body: `{"ids": [...]}`) |

### AI 分析端點不變

- `POST /api/product/analyze`
- `POST /api/diary/analyze`

### 頁面路由（純渲染）

- `GET /`, `/pets`, `/product/analyze`, `/organize`, `/diary`

---

## 第三節：前端與 UI 變更

### 新增 `pets.html`
- 寵物卡片列表（照片、名字、品種、年齡自動計算）
- Inline 新增/編輯表單
- 刪除前確認 dialog

### `organize.html`
- form submit 改為 `fetch()`
- 頂部加寵物篩選 tab（全部 / 各寵物）
- 新增商品時加「適用寵物」下拉（可選，預設「未指定」）

### `organize_edit.html`
- 加「適用寵物」下拉
- 改為 fetch PUT

### `diary.html`
- form submit 改為 fetch POST `/api/diaries`
- 儲存 dialog 加「哪隻寵物」下拉
- 頂部加寵物篩選 tab

### `product_analyze.html`
- 確認儲存步驟加「適用寵物」選單
- 改為 fetch POST `/api/products`

### `base.html`
- 導覽列加「寵物」連結
