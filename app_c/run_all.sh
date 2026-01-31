#!/usr/bin/env bash
set -Eeuo pipefail

# =========================================
# 使い方
# =========================================
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

researchmap JSON → CSV → Excel 一括変換スクリプト

OPTIONS:
  -d, --download     JSON ダウンロードも実行（data/test_ids.txt の ID を対象）
  -h, --help         このヘルプを表示

ENVIRONMENT:
  DEBUG_LEVEL=0|1|2  ログ詳細度（0:静か, 1:通常, 2:詳細）

EXAMPLES:
  ./run_all.sh                  # CSV/Excel 変換のみ
  ./run_all.sh --download       # ダウンロード + 変換
  DEBUG_LEVEL=2 ./run_all.sh    # 詳細ログ表示
EOF
}

# =========================================
# オプション解析
# =========================================
DO_DOWNLOAD=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--download)
      DO_DOWNLOAD=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

# =========================================
# 設定（必要ならここだけ編集）
# =========================================

# 「一行 1 ID」ファイル（固定パスでOKとのことなので直書き）
IDS_FILE="../data/test_ids.txt"

# スクリプト配置（この .sh が app_c/ にある想定）
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# JSON 入力 / CSV 出力（app_c/ から ../data/...）
JSON_DIR="${SCRIPT_DIR}/../data/json"
CSV_DIR="${SCRIPT_DIR}/../data/csv"

# ダウンロードスクリプト（app_a/ に配置）
DOWNLOAD_SCRIPT="${SCRIPT_DIR}/../app_a/download_data.py"

# 実行する Python スクリプト（同一IF: --input-file / --output-dir）
PY_SCRIPTS=(
"researchmap_json_to_csv_buntan.py"
"researchmap_json_to_csv_kotohappyo.py"
"researchmap_json_to_csv_kyocho_hencho.py"
"researchmap_json_to_csv_misc.py"
"researchmap_json_to_csv_papers.py"
"researchmap_json_to_csv_sonota.py"
"researchmap_json_to_csv_tancho.py"
)

# デバッグ度合い: 0=静か, 1=通常, 2=詳細
DEBUG_LEVEL="${DEBUG_LEVEL:-1}"

# =========================================
# ユーティリティ
# =========================================

log()  { echo "$@"; }
dbg1() { [[ "$DEBUG_LEVEL" -ge 1 ]] && echo "$@"; }
dbg2() { [[ "$DEBUG_LEVEL" -ge 2 ]] && echo "$@"; }

die()  { echo "ERROR: $*" >&2; exit 1; }

# 行末CR(\r)や前後空白を除去（CRLF/CR対策も含める）
trim() {
  local s="$1"
  s="${s//$'\r'/}"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

# コマンド存在確認
need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "command not found: $1"
}

# =========================================
# 事前チェック
# =========================================

need_cmd python

[[ -f "$IDS_FILE" ]] || die "IDS_FILE not found: $IDS_FILE"
[[ -d "$JSON_DIR" ]] || die "JSON_DIR not found: $JSON_DIR"
mkdir -p "$CSV_DIR"

log "IDS_FILE : $IDS_FILE"
log "SCRIPT_DIR: $SCRIPT_DIR"
log "JSON_DIR : $JSON_DIR"
log "CSV_DIR  : $CSV_DIR"
log

# IDS ファイルの先頭数行を「可視化」して表示（macOS BSD cat 対応）
# -e: 行末に $ を付ける, -v: 不可視を ^ などで表示
dbg1 "[DEBUG] Head of IDS_FILE (cat -e -v):"
dbg1 "$(cat -e -v "$IDS_FILE" | head -n 20)"
dbg1 ""

# file コマンドも参考表示
if command -v file >/dev/null 2>&1; then
  dbg1 "[DEBUG] file(1) of IDS_FILE:"
  dbg1 "$(file "$IDS_FILE")"
  dbg1 ""
fi

# Python スクリプト存在確認
for s in "${PY_SCRIPTS[@]}"; do
  [[ -f "${SCRIPT_DIR}/${s}" ]] || die "Python script not found: ${SCRIPT_DIR}/${s}"
done

# =========================================
# 0) ダウンロード（オプション指定時のみ）
# =========================================
if [[ "$DO_DOWNLOAD" == "true" ]]; then
  log "=== Download JSON from researchmap ==="

  if [[ ! -f "$DOWNLOAD_SCRIPT" ]]; then
    die "Download script not found: $DOWNLOAD_SCRIPT"
  fi

  log "RUN : python download_data.py --ids-file $IDS_FILE --output $JSON_DIR --incremental"

  if python "$DOWNLOAD_SCRIPT" --ids-file "$IDS_FILE" --output "$JSON_DIR" --incremental; then
    log "Download completed."
  else
    log "WARNING: Some downloads may have failed, continuing..."
  fi
  log
fi

# =========================================
# 1) まず「IDに対応するJSONが存在するか」棚卸し
# =========================================
log "=== Precheck: JSON existence for each ID ==="

total_ids=0
ok_json=0
miss_json=0
comment_or_blank=0

while IFS= read -r line || [[ -n "$line" ]]; do
  total_ids=$((total_ids + 1))

  raw="$line"
  id="$(trim "$raw")"

  if [[ -z "$id" ]] || [[ "${id:0:1}" == "#" ]]; then
    comment_or_blank=$((comment_or_blank + 1))
    dbg2 "SKIP-LINE raw=$(printf '%q' "$raw")"
    continue
  fi

  input_json="${JSON_DIR}/${id}.json"
  if [[ -f "$input_json" ]]; then
    ok_json=$((ok_json + 1))
    dbg1 "OK   id=$(printf '%q' "$id")  json=$input_json"
  else
    miss_json=$((miss_json + 1))
    dbg1 "MISS id=$(printf '%q' "$id")  expected=$input_json"
  fi
done < "$IDS_FILE"

log
log "Precheck summary:"
log "  Lines total        : $total_ids"
log "  Blank/comment lines: $comment_or_blank"
log "  JSON OK            : $ok_json"
log "  JSON MISSING       : $miss_json"
log

if (( ok_json == 0 )); then
  die "No JSON files found for any ID. Check JSON_DIR or ID naming."
fi

# =========================================
# 2) 変換実行（JSONがあるIDのみ）
# =========================================
log "=== Run converters ==="

id_processed=0
skip_count=0
fail_count=0

while IFS= read -r line || [[ -n "$line" ]]; do
  raw="$line"
  id="$(trim "$raw")"

  if [[ -z "$id" ]] || [[ "${id:0:1}" == "#" ]]; then
    continue
  fi

  input_json="${JSON_DIR}/${id}.json"

  if [[ ! -f "$input_json" ]]; then
    log "SKIP: id=$(printf '%q' "$id") JSON not found: $input_json"
    skip_count=$((skip_count + 1))
    continue
  fi

  log "== ID: $id =="
  id_processed=$((id_processed + 1))

  for s in "${PY_SCRIPTS[@]}"; do
    py="${SCRIPT_DIR}/${s}"
    dbg1 "RUN : python $(basename "$py") --input-file $input_json --output-dir $CSV_DIR"

    # 失敗しても続行しつつカウント
    if python "$py" --input-file "$input_json" --output-dir "$CSV_DIR"; then
      :
    else
      log "ERROR: failed: python $py --input-file $input_json --output-dir $CSV_DIR"
      fail_count=$((fail_count + 1))
    fi
  done

  log
done < "$IDS_FILE"

log "CSV conversion DONE"
log "  IDs processed (had JSON): $id_processed"
log "  IDs skipped (no JSON)   : $skip_count"
log "  Script failures         : $fail_count"

if (( fail_count > 0 )); then
  log "WARNING: Some scripts failed, but continuing to Excel conversion..."
fi

# =========================================
# 3) CSV → Excel 変換
# =========================================
log
log "=== Convert CSV to Excel ==="

XLSX_SCRIPT="${SCRIPT_DIR}/csv_to_excel.py"

if [[ -f "$XLSX_SCRIPT" ]]; then
  log "RUN : python csv_to_excel.py"
  if python "$XLSX_SCRIPT"; then
    log "Excel conversion completed successfully."
  else
    log "ERROR: Excel conversion failed."
    fail_count=$((fail_count + 1))
  fi
else
  log "WARNING: csv_to_excel.py not found, skipping Excel conversion."
fi

log
log "ALL DONE"

if (( fail_count > 0 )); then
  exit 1
fi
