# Runbook

<!-- AUTO-GENERATED: Deployment and health-check sections generated from docker-compose.yml and app.py -->

## Architecture Overview

```
Browser → Flask (port 5001) → MySQL 8.0 (port 3306)
                ↓
         Ollama server (external, port 11434)
```

- **Flask app**: `pet-adorable-life-web` container
- **MySQL**: `pet-adorable-life-mysql` container with named volume `mysql_data`
- **Ollama**: External host — not managed by Docker Compose

---

## Deployment

### Start Full Stack

```bash
docker-compose up -d
```

Bring-up order (enforced by `depends_on` with health check):
1. MySQL starts and passes its health check (`mysqladmin ping`)
2. Flask web container starts (waits up to 15s before its own health check fires)

### Stop Stack

```bash
docker-compose down          # stop containers, preserve volumes
docker-compose down -v       # stop containers AND delete mysql_data volume (⚠️ data loss)
```

### Restart a Single Service

```bash
docker-compose restart web   # restart Flask app only
docker-compose restart mysql # restart MySQL only
```

### Deploy Code Updates

Since `.:/app` is volume-mounted, the running container sees code changes immediately in dev. For a clean deploy:

```bash
docker-compose build web     # rebuild image
docker-compose up -d web     # restart with new image
```

---

## Health Checks

<!-- AUTO-GENERATED from docker-compose.yml -->

| Service | Check Command | Interval | Timeout | Retries |
|---------|--------------|----------|---------|---------|
| `mysql` | `mysqladmin ping -h localhost -u root -proot_password` | 10s | 5s | 5 |
| `web` | `wget -qO- http://localhost:5001/` | 30s | 10s | 3 (start: 15s) |

### Manual Health Check

```bash
# Check container status
docker-compose ps

# Verify Flask is responding
curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/
# Expected: 200

# Check MySQL connectivity from web container
docker exec pet-adorable-life-web python -c "import db; print('DB ok')"
```

---

## Monitoring & Logs

```bash
# Follow all logs
docker-compose logs -f

# Flask app logs only
docker-compose logs -f web

# MySQL logs only
docker-compose logs -f mysql

# Last 100 lines from web
docker-compose logs --tail=100 web
```

---

## Common Issues and Fixes

### Flask won't start — MySQL not ready

**Symptom:** Web container exits immediately or shows `Can't connect to MySQL server`.

**Cause:** MySQL health check passes but the database/user is not yet created.

**Fix:**
```bash
docker-compose logs mysql   # look for "ready for connections"
docker-compose restart web  # retry after MySQL is fully up
```

### Ollama returns null / analysis fails

**Symptom:** `/api/product/analyze` or `/api/diary/analyze` returns `{"error": "分析失敗，請確認 Ollama 服務是否運行"}`.

**Check:**
```bash
# Verify OLLAMA_URL is reachable from the container
docker exec pet-adorable-life-web curl -s "${OLLAMA_URL%/api/generate}" | head -c 100

# Check the configured URL
docker exec pet-adorable-life-web printenv OLLAMA_URL
```

**Fix:** Update `OLLAMA_URL` in `docker-compose.yml` or `.env` to point to the correct Ollama host IP/port.

### Port 5001 already in use

**Symptom:** `Error starting userland proxy: listen tcp 0.0.0.0:5001: bind: address already in use`.

**Fix:**
```bash
lsof -ti:5001 | xargs kill -9   # kill process holding the port
docker-compose up -d             # retry
```

### Port 3306 already in use

**Symptom:** MySQL container fails to start, port conflict.

**Fix:** Stop any local MySQL instance, or change the host port in `docker-compose.yml`:
```yaml
ports:
  - "3307:3306"   # use 3307 on host instead
```
Also update `MYSQL_PORT` in `.env`.

### Database schema out of date

**Symptom:** `Unknown column` errors in logs.

**Cause:** Schema is auto-migrated via `init_db()` on first request using `ALTER TABLE ... ADD COLUMN` guards. If this fails, columns may be missing.

**Fix:**
```bash
# Run init_db manually
docker exec pet-adorable-life-web python -c "import db; db.init_db()"
# Check logs for any OperationalError
```

### Container stuck / unresponsive

```bash
docker-compose restart web
# If still stuck:
docker-compose down && docker-compose up -d
```

---

## Rollback Procedures

### Rollback Code

Since the app runs from the volume-mounted source directory:
```bash
git log --oneline -10         # find target commit
git checkout <commit-hash>    # roll back working directory
docker-compose restart web    # pick up old code
```

### Rollback Database

There is no automated migration history. Schema changes are applied via `ALTER TABLE IF NOT EXISTS` in `init_db()` — they are not reversible through the app.

For data rollback:
```bash
# Restore from a MySQL dump (if one exists)
docker exec -i pet-adorable-life-mysql mysql -u pet_user -ppet_password pet_adorable_life < backup.sql
```

---

## Backup

### Create a Database Dump

```bash
docker exec pet-adorable-life-mysql \
  mysqldump -u pet_user -ppet_password pet_adorable_life \
  > backup-$(date +%Y%m%d-%H%M%S).sql
```

### Restore from Dump

```bash
docker exec -i pet-adorable-life-mysql \
  mysql -u pet_user -ppet_password pet_adorable_life \
  < backup-YYYYMMDD-HHMMSS.sql
```

---

## Running Tests

```bash
# Full test suite
docker exec pet-adorable-life-web python -m pytest tests/ -v

# With coverage
docker exec pet-adorable-life-web python -m pytest tests/ --cov --cov-report=term-missing
```
