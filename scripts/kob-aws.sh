#!/usr/bin/env bash
# kob-aws — wrapper สำหรับจัดการ Odoo บน AWS EC2 ผ่าน SSH alias `kob-prod`
# ใช้ผ่าน Claude หรือ manual ก็ได้
#
# วิธีใช้:
#   bash scripts/kob-aws.sh <command>
#
# Commands:
#   ssh             — เข้า EC2 (interactive)
#   status          — เช็ค container สถานะ
#   logs [service]  — tail logs (default: odoo)
#   restart         — restart Odoo + nginx
#   push-addons     — sync kob_odoo_addons/ ไป EC2 ผ่าน rsync (ใช้ msys2 rsync ถ้ามี)
#   update <mod>    — odoo update module + restart
#   db-backup       — manual pg_dump + filestore tar
#   db-pull <mod>   — ดึง pg_dump จาก EC2 มา local (สำหรับ debug)
#   pull-logs       — copy /home/ubuntu/kob-odoo/logs ลงเครื่อง
#   health          — curl http(s) health endpoint

set -e
HOST="kob-prod"
REMOTE_DIR="/home/ubuntu/kob-odoo"
LOCAL_PROJECT="$(cd "$(dirname "$0")/.." && pwd)"

cmd="${1:-help}"
shift || true

run_ssh() { ssh "$HOST" "$@"; }

case "$cmd" in
  ssh)
    exec ssh "$HOST"
    ;;
  status)
    run_ssh "cd $REMOTE_DIR && docker compose ps && echo && free -h && echo && df -h /"
    ;;
  logs)
    svc="${1:-odoo}"
    run_ssh "cd $REMOTE_DIR && docker compose logs --tail=100 -f $svc"
    ;;
  restart)
    run_ssh "cd $REMOTE_DIR && docker compose restart odoo nginx"
    ;;
  push-addons)
    if command -v rsync >/dev/null; then
      rsync -avz --delete \
        --exclude='*.pyc' --exclude='__pycache__' --exclude='.git' \
        "$LOCAL_PROJECT/kob_odoo_addons/" \
        "$HOST:$REMOTE_DIR/kob_odoo_addons/"
    else
      echo "rsync not found, falling back to scp tarball..."
      tar -czf /tmp/addons.tar.gz -C "$LOCAL_PROJECT" \
        --exclude='*.pyc' --exclude='__pycache__' kob_odoo_addons
      scp /tmp/addons.tar.gz "$HOST:/tmp/"
      run_ssh "cd $REMOTE_DIR && tar -xzf /tmp/addons.tar.gz && rm /tmp/addons.tar.gz"
    fi
    ;;
  update)
    mod="${1:-kob_base}"
    run_ssh "cd $REMOTE_DIR && docker compose exec -T odoo odoo -c /etc/odoo/odoo.conf -d kobdb -u $mod --stop-after-init && docker compose restart odoo"
    ;;
  db-backup)
    TS=$(date +%Y%m%d_%H%M%S)
    run_ssh "cd $REMOTE_DIR && docker compose exec -T odoo-postgres pg_dump -U odoo -d kobdb -Fc > /home/ubuntu/odoo_backups/kobdb_manual_$TS.dump && ls -lh /home/ubuntu/odoo_backups/kobdb_manual_$TS.dump"
    ;;
  db-pull)
    TS=$(date +%Y%m%d_%H%M%S)
    DEST="/tmp/kobdb_prod_$TS.dump"
    run_ssh "cd $REMOTE_DIR && docker compose exec -T odoo-postgres pg_dump -U odoo -d kobdb -Fc > /tmp/_pull.dump"
    scp "$HOST:/tmp/_pull.dump" "$DEST"
    run_ssh "rm /tmp/_pull.dump"
    echo "Saved to: $DEST"
    ;;
  pull-logs)
    DEST="$LOCAL_PROJECT/logs/aws_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$DEST"
    run_ssh "cd $REMOTE_DIR && docker compose logs --tail=500 odoo" > "$DEST/odoo.log"
    run_ssh "cd $REMOTE_DIR && docker compose logs --tail=500 nginx" > "$DEST/nginx.log"
    run_ssh "cd $REMOTE_DIR && docker compose logs --tail=500 odoo-postgres" > "$DEST/postgres.log"
    echo "Logs saved to: $DEST"
    ;;
  health)
    IP=$(grep '^\s*HostName' ~/.ssh/config | grep -A0 -B0 'kob-prod' | awk '{print $2}' | head -1)
    [ -z "$IP" ] && IP=$(awk '/Host kob-prod$/{f=1} f && /HostName/{print $2; exit}' ~/.ssh/config)
    echo "Testing http://$IP/web/login ..."
    curl -s -o /dev/null -w "HTTP %{http_code} | %{time_total}s\n" --max-time 10 "http://$IP/web/login"
    ;;
  help|--help|-h|*)
    sed -n '1,30p' "$0"
    ;;
esac
