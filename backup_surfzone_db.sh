#!/bin/bash
# =============================================================
# SURFZONE — backup_surfzone_db.sh
# Automated backup: MySQL surfzone_db (from the surfzone_db container) → Google Drive via rclone
# Mirrors the pattern in /home/stratum/stratum/backup.sh (Stratum's SQLite/rclone backup).
#
# Run via cron (not installed yet - shown for review first):
#   0 3 * * * /home/stratum/surfzone-repo/backup_surfzone_db.sh >> /var/log/surfzone-backup.log 2>&1
# =============================================================

set -euo pipefail

# ── CONFIG ────────────────────────────────────────────────────
REPO_DIR="/home/stratum/surfzone-repo"
ENV_FILE="${REPO_DIR}/.env"
DB_CONTAINER="surfzone_db"
BACKUP_DIR="/tmp/surfzone-backups"
RCLONE_REMOTE="gdrive:surfzone-backups"     # same remote as Stratum (gdrive:), own top-level folder
RETENTION_DAYS=30
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_PREFIX="[SurfZone Backup ${TIMESTAMP}]"

# ── COLOUR HELPERS ────────────────────────────────────────────
info()    { echo "${LOG_PREFIX} INFO:    $*"; }
success() { echo "${LOG_PREFIX} SUCCESS: $*"; }
warn()    { echo "${LOG_PREFIX} WARN:    $*"; }
error()   { echo "${LOG_PREFIX} ERROR:   $*" >&2; }

# ── PRE-FLIGHT ────────────────────────────────────────────────

info "Starting backup"

# Check required tools
for cmd in docker rclone gzip; do
  if ! command -v "$cmd" &>/dev/null; then
    error "Required tool not found: $cmd"
    exit 1
  fi
done

if [ ! -f "$ENV_FILE" ]; then
  error "Env file not found: $ENV_FILE"
  exit 1
fi

# Pull DB_NAME/DB_USER/DB_PASSWORD from the same .env the docker-compose
# stack itself uses, rather than hardcoding credentials in this script.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${DB_NAME:?DB_NAME not set in $ENV_FILE}"
: "${DB_USER:?DB_USER not set in $ENV_FILE}"
: "${DB_PASSWORD:?DB_PASSWORD not set in $ENV_FILE}"

if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  error "Container not running: $DB_CONTAINER"
  exit 1
fi

mkdir -p "$BACKUP_DIR"

# ── STEP 1: MySQL dump (from inside the container, so no local mysql client required) ──
# --single-transaction: consistent snapshot without locking tables (safe for a live app).
# --no-tablespaces: avoids a PROCESS-privilege warning/failure for non-SUPER users on MySQL 8.

DB_BACKUP_NAME="surfzone-db-${TIMESTAMP}.sql"
DB_BACKUP_PATH="${BACKUP_DIR}/${DB_BACKUP_NAME}"
DB_GZ_PATH="${DB_BACKUP_PATH}.gz"

info "Backing up database..."
docker exec "$DB_CONTAINER" mysqldump \
  -u"$DB_USER" -p"$DB_PASSWORD" \
  --single-transaction --quick --routines --triggers --no-tablespaces \
  "$DB_NAME" > "$DB_BACKUP_PATH"
gzip -9 "$DB_BACKUP_PATH"

if [ ! -f "$DB_GZ_PATH" ]; then
  error "Database backup failed — gzip not produced"
  exit 1
fi

DB_SIZE=$(du -sh "$DB_GZ_PATH" | cut -f1)
success "Database backed up: ${DB_BACKUP_NAME}.gz (${DB_SIZE}) at ${DB_GZ_PATH}"

# ── STEP 2: Upload DB backup to Google Drive ──────────────────

info "Uploading database backup to Google Drive..."
if rclone copy \
  "$DB_GZ_PATH" \
  "${RCLONE_REMOTE}/database" \
  --log-level=INFO; then
  success "Database backup uploaded to ${RCLONE_REMOTE}/database/${DB_BACKUP_NAME}.gz"
else
  error "Failed to upload database backup to Google Drive"
  exit 1
fi

# ── STEP 3: Remove old local backup files ─────────────────────

info "Cleaning up local backup files older than ${RETENTION_DAYS} days..."
DELETED=$(find "$BACKUP_DIR" -name "surfzone-db-*.sql.gz" \
  -mtime +${RETENTION_DAYS} -print -delete | wc -l)
info "Removed ${DELETED} old local backup file(s)"

# ── STEP 4: Remove old remote DB backups ─────────────────────
# Keep last RETENTION_DAYS backups on Google Drive.

info "Pruning old remote database backups (keeping last ${RETENTION_DAYS})..."
REMOTE_BACKUPS=$(rclone lsf "${RCLONE_REMOTE}/database" \
  --format "t;p" \
  --files-only \
  --include "surfzone-db-*.sql.gz" \
  2>/dev/null | sort -r)

COUNT=0
while IFS= read -r line; do
  [ -z "$line" ] && continue
  COUNT=$((COUNT + 1))
  if [ $COUNT -gt $RETENTION_DAYS ]; then
    FNAME=$(echo "$line" | cut -d';' -f2)
    if rclone delete "${RCLONE_REMOTE}/database/${FNAME}" 2>/dev/null; then
      info "Deleted old remote backup: ${FNAME}"
    fi
  fi
done <<< "$REMOTE_BACKUPS"

# ── STEP 5: Health record ─────────────────────────────────────
# Write a small JSON status file so admin can verify backups ran

HEALTH_FILE="/tmp/surfzone-backup-health.json"
cat > "$HEALTH_FILE" <<EOF
{
  "last_backup":    "${TIMESTAMP}",
  "db_name":        "${DB_NAME}",
  "db_backup":      "${DB_BACKUP_NAME}.gz",
  "db_size":        "${DB_SIZE}",
  "status":         "ok",
  "rclone_remote":  "${RCLONE_REMOTE}"
}
EOF

rclone copy "$HEALTH_FILE" "${RCLONE_REMOTE}" --log-level=ERROR 2>/dev/null || true

# ── DONE ──────────────────────────────────────────────────────

success "Backup completed successfully at ${TIMESTAMP}"
echo ""
