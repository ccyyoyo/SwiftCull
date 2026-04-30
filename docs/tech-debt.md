# 技術債 / 未來工作

> 已知會在某個時點需要處理、但**目前刻意不做**的技術項目。
> 每筆記錄：**現況、為什麼延後、觸發條件、預估工**，避免下次有人重新從頭評估。

---

## 1. DB schema migration framework

### 現況

`app/db/connection.py` 的 `_migrate()` 是手寫的 ad-hoc：

```python
def _migrate(conn):
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(photos)")}
    if "mtime" not in cols:
        conn.execute("ALTER TABLE photos ADD COLUMN mtime REAL")
```

每次 `init_db()` 都跑一次，靠 `PRAGMA table_info` 探測欄位是否存在來決定要不要 ALTER。`SettingsDB`（`app/db/settings_db.py`）也沒有版本機制。

### 為什麼延後

- Phase 1 至今只有**一個** schema 變更（加 `mtime`），4 行 ad-hoc 還寫得下。
- SQLite 的 `ALTER TABLE ADD COLUMN` 是 idempotent 又便宜，配「探測再加」對純加欄位夠用。
- YAGNI：現在抽框架是替「未來可能會」買保險，Phase 1 沒任何下個變更計畫。

### 觸發條件（任一達成就動手）

1. **第三次 schema 變更**。第二次（`if not exists` 變兩條）還可控，第三次 ad-hoc 會開始長雜訊。
2. **第一次出現非 idempotent 變更**。例如「rename 欄位」、「改型別」、「拆表」、「資料補齊」。`if column_exists` 對這些情境根本不適用。
3. **進 Phase 2 時**。AI 偵測會加 `face_count`、`is_blurry`、`detection_results` 等欄位，至少 3 個，正好觸發條件 1。
4. **DB 出事需要追溯**。出 bug 時想知道某個 `project.db` 是哪一版 schema，目前無從查起。

### 目標：程度 1（版本號 + migration 列表）

不引進 Alembic 等重量套件。自己寫一個 30 行版本：

```
app/db/migrations.py
  MIGRATIONS = [
      (1, "ALTER TABLE photos ADD COLUMN mtime REAL"),
      (2, "ALTER TABLE photos ADD COLUMN face_count INTEGER"),
      (3, _migrate_v3_split_camera_field),  # 不能用一句 SQL 表達就傳 callable
      (4, "CREATE INDEX idx_photos_shot_at ON photos(shot_at)"),
  ]

  def apply(conn):
      conn.execute("CREATE TABLE IF NOT EXISTS schema_version (v INTEGER)")
      current = conn.execute("SELECT COALESCE(MAX(v), 0) FROM schema_version").fetchone()[0]
      for version, step in MIGRATIONS:
          if version > current:
              step(conn) if callable(step) else conn.executescript(step)
              conn.execute("INSERT INTO schema_version VALUES (?)", (version,))
      conn.commit()
```

關鍵特徵：
- DB 自帶 `schema_version` 表，記錄走到哪
- migration 是 **append-only list**，編號連續、順序固定
- 跑兩次自動只執行差異
- 跑到比 code 還新的 DB（從更新版降回舊版打開）→ 偵測到後 graceful warn 或 error，看政策決定（建議 error）

### 範圍 / 預估

1-2 hr：

1. 新增 `app/db/migrations.py`（list + `apply()` 函式）
2. `init_db` 改成：建空表 → 呼叫 `migrations.apply(conn)`，舊的 `_migrate()` 移走
3. **同時** `SettingsDB._init_schema` 也改用同一套（避免兩套 migration 並存）
4. 測試：
   - 起一個沒有 `schema_version` 表、且少 `mtime` 欄位的舊 DB → migrate → 拉到最新
   - 跑兩次 `apply()` 結果相同（idempotence）
   - 起一個 `schema_version = 99` 的未來 DB → 拋明確錯誤 / warning
   - 跑 Phase 2 預期會加的 migration 範例（dry run）

### 不做的事

- **不做 downgrade**：rollback 對單人本地工具是 over-engineering。release 出 bug 就修向前。
- **不做 autogenerate**：我們手寫 SQL 比較直觀，autogenerate 必須先有 ORM 模型。
- **不做檔案式 migration**（`001_*.sql`、`002_*.sql`）：list 表達夠，少一層 IO 跟 file ordering 的麻煩。

---

## 模板：新增條目時請保持結構

每筆條目至少四節：

- **現況** — 目前怎麼處理
- **為什麼延後** — 為什麼不現在做
- **觸發條件** — 達到什麼狀況才動手
- **範圍 / 預估** — 動手時要做什麼，多少工

> 加新項目時編號連續往下加，不刪舊項目（除非真的做完）。做完的搬到 `git log` 去找紀錄。
