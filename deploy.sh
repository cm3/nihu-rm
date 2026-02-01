#!/usr/bin/env bash
set -euo pipefail

### ---- settings (必要ならここだけ変える) ----
DOMAIN="${DOMAIN:-ik1-421-42635.vs.sakura.ne.jp}"

APP_ROOT="${APP_ROOT:-/srv/projects/nihu-rm}"
REPO_DIR="${REPO_DIR:-$APP_ROOT/repo}"
VENV_DIR="${VENV_DIR:-$APP_ROOT/venv}"

DATA_PERSIST_DIR="${DATA_PERSIST_DIR:-/var/lib/nihu-rm}"

PREFIX_A="${PREFIX_A:-/nihu-rm-a}"
PREFIX_C="${PREFIX_C:-/nihu-rm-c}"
PORT_A="${PORT_A:-8000}"
PORT_C="${PORT_C:-8001}"

REPO_URL="${REPO_URL:-https://github.com/cm3/nihu-rm.git}"

NGINX_SITE_NAME="${NGINX_SITE_NAME:-nihu-rm}"
NGINX_AVAIL="/etc/nginx/sites-available/${NGINX_SITE_NAME}.conf"
NGINX_ENABLED="/etc/nginx/sites-enabled/${NGINX_SITE_NAME}.conf"
### -------------------------------------------

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing command: $1" >&2; exit 1; }; }
info() { echo -e "\n==> $*"; }

need_cmd id
need_cmd mkdir
need_cmd ln
need_cmd git
need_cmd python3

USER_NAME="$(id -un)"

info "Install OS packages (nginx/certbot/python venv) if needed"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y nginx python3-venv python3-pip
  # certbot は既にあるかも。無ければ入れる（不要なら後で消してOK）
  sudo apt-get install -y certbot python3-certbot-nginx || true
fi

info "Create directories"
sudo mkdir -p "$APP_ROOT"
sudo chown -R "$USER_NAME:$USER_NAME" "$APP_ROOT"
sudo mkdir -p "$DATA_PERSIST_DIR"/{json,csv,xlsx}
sudo chown -R "$USER_NAME:$USER_NAME" "$DATA_PERSIST_DIR"

info "Clone or update repo"
if [ ! -d "$REPO_DIR/.git" ]; then
  mkdir -p "$REPO_DIR"
  git clone "$REPO_URL" "$REPO_DIR"
else
  ( cd "$REPO_DIR" && git fetch origin && git pull --ff-only )
fi

info "Create venv & install dependencies"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install -U pip wheel
"$VENV_DIR/bin/python" -m pip install -r "$REPO_DIR/requirements.txt"
if [ -f "$REPO_DIR/app_c/requirements.txt" ]; then
  "$VENV_DIR/bin/python" -m pip install -r "$REPO_DIR/app_c/requirements.txt"
fi

info "Prepare repo/data with sub-symlinks to persistent storage (NOT whole data symlink)"
mkdir -p "$REPO_DIR/data"
# 重いものだけ退避＆symlink（repo/data 自体は実ディレクトリのまま）
ln -sfn "$DATA_PERSIST_DIR/json" "$REPO_DIR/data/json"
ln -sfn "$DATA_PERSIST_DIR/csv"  "$REPO_DIR/data/csv"
ln -sfn "$DATA_PERSIST_DIR/xlsx" "$REPO_DIR/data/xlsx"
# DB も永続側に置く（無ければ空ファイルを作っておく）
touch "$DATA_PERSIST_DIR/researchers.db"
ln -sfn "$DATA_PERSIST_DIR/researchers.db" "$REPO_DIR/data/researchers.db"

info "Create systemd user units (nihu-rm-a / nihu-rm-c)"
mkdir -p "$HOME/.config/systemd/user"

cat > "$HOME/.config/systemd/user/nihu-rm-a.service" <<EOF
[Unit]
Description=nihu-rm app_a (FastAPI)
After=network.target

[Service]
Type=simple
WorkingDirectory=$REPO_DIR
Environment=PATH=$VENV_DIR/bin
Environment=NIHU_RM_ROOT_PATH=$PREFIX_A
ExecStart=$VENV_DIR/bin/uvicorn app_a.main:app --host 127.0.0.1 --port $PORT_A --proxy-headers --forwarded-allow-ips=127.0.0.1 --root-path $PREFIX_A
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

cat > "$HOME/.config/systemd/user/nihu-rm-c.service" <<EOF
[Unit]
Description=nihu-rm app_c (FastAPI)
After=network.target

[Service]
Type=simple
WorkingDirectory=$REPO_DIR
Environment=PATH=$VENV_DIR/bin
Environment=NIHU_RM_ROOT_PATH=$PREFIX_C
ExecStart=$VENV_DIR/bin/uvicorn app_c.main:app --host 127.0.0.1 --port $PORT_C --proxy-headers --forwarded-allow-ips=127.0.0.1 --root-path $PREFIX_C
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

info "Enable linger (so user services can run without login) - optional but recommended"
# 既に有効なら何もしない。sudo が必要。
sudo loginctl enable-linger "$USER_NAME" || true

info "Start services"
systemctl --user daemon-reload
systemctl --user enable --now nihu-rm-a nihu-rm-c
systemctl --user status nihu-rm-a --no-pager -l || true
systemctl --user status nihu-rm-c --no-pager -l || true

info "Write nginx site config (dedicated file, not default)"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
HAS_CERT=0
if [ -d "$CERT_DIR" ] && [ -f "$CERT_DIR/fullchain.pem" ] && [ -f "$CERT_DIR/privkey.pem" ]; then
  HAS_CERT=1
fi

sudo mkdir -p /var/log/nginx

if [ "$HAS_CERT" -eq 1 ]; then
  sudo tee "$NGINX_AVAIL" >/dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    access_log /var/log/nginx/${NGINX_SITE_NAME}.access.log;
    error_log  /var/log/nginx/${NGINX_SITE_NAME}.error.log;

    ssl_certificate     $CERT_DIR/fullchain.pem;
    ssl_certificate_key $CERT_DIR/privkey.pem;

    # upload があり得るので一応
    client_max_body_size 50m;

    # 便利: ドメイン直下は app_a に飛ばす（不要なら消してOK）
    location = / {
        return 302 $PREFIX_A/;
    }

    location $PREFIX_A/ {
        proxy_pass http://127.0.0.1:$PORT_A/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix $PREFIX_A;
        proxy_redirect off;
    }

    location $PREFIX_C/ {
        proxy_pass http://127.0.0.1:$PORT_C/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix $PREFIX_C;
        proxy_redirect off;
    }
}
EOF
else
  sudo tee "$NGINX_AVAIL" >/dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    access_log /var/log/nginx/${NGINX_SITE_NAME}.access.log;
    error_log  /var/log/nginx/${NGINX_SITE_NAME}.error.log;

    client_max_body_size 50m;

    location = / {
        return 302 $PREFIX_A/;
    }

    location $PREFIX_A/ {
        proxy_pass http://127.0.0.1:$PORT_A/;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Prefix $PREFIX_A;
    }

    location $PREFIX_C/ {
        proxy_pass http://127.0.0.1:$PORT_C/;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Prefix $PREFIX_C;
    }
}
EOF
fi

sudo ln -sfn "$NGINX_AVAIL" "$NGINX_ENABLED"
sudo nginx -t
sudo systemctl reload nginx

info "Optional: prepare data (skip if you will rsync later)"
if [ -f "$REPO_DIR/data/researchers.csv" ]; then
  info "Found data/researchers.csv -> run download & setup DB"
  "$VENV_DIR/bin/python" "$REPO_DIR/app_a/download_data.py" --csv "$REPO_DIR/data/researchers.csv" --incremental || true
  "$VENV_DIR/bin/python" "$REPO_DIR/app_a/setup_db.py" || true
else
  echo "NOTE: data/researchers.csv not found. Put it under $REPO_DIR/data/ then run:"
  echo "  $VENV_DIR/bin/python $REPO_DIR/app_a/download_data.py --csv $REPO_DIR/data/researchers.csv --incremental"
  echo "  $VENV_DIR/bin/python $REPO_DIR/app_a/setup_db.py"
fi

info "Done. Check URLs:"
echo "  https://$DOMAIN$PREFIX_A/   (UI)"
echo "  https://$DOMAIN$PREFIX_A/docs"
echo "  https://$DOMAIN$PREFIX_C/   (UI)"
echo "  https://$DOMAIN$PREFIX_C/docs"

if [ "$HAS_CERT" -eq 0 ]; then
  echo
  echo "NOTE: Let's Encrypt cert not detected. If you want HTTPS:"
  echo "  sudo certbot --nginx -d $DOMAIN"
fi

