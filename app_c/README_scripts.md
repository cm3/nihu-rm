# scripts/tool-c

researchmap JSON から機構IR様式の CSV/Excel ファイルを生成するスクリプト群です。

## クイックスタート

### 一括変換（推奨）

`run_all.sh` を使用すると、ダウンロード → CSV → Excel の全変換を一括実行できます。

```bash
cd scripts/tool-c
./run_all.sh              # CSV/Excel 変換のみ
./run_all.sh --download   # JSON ダウンロード + 変換
./run_all.sh -d           # 同上（短縮形）
```

**事前準備:**
1. `data/test_ids.txt` に変換対象の ID を1行1件で記載
2. `--download` を使わない場合は `data/json/` に JSON ファイルを配置

**処理内容:**
1. （`--download` 指定時）researchmap API から JSON をダウンロード
2. 各 ID の JSON ファイルを7種類の CSV に変換（論文、分担執筆、単著、共著・編著、口頭発表、MISC、その他）
3. 生成された CSV を個人ごとの Excel ファイルにまとめる

**出力:**
- JSON: `data/json/<ID>.json`（ダウンロード時）
- CSV: `data/csv/<ID>-<カテゴリ>.csv`
- Excel: `data/xlsx/<ID>.xlsx`

**オプション:**
```bash
./run_all.sh --download     # JSON ダウンロード込み
./run_all.sh -d             # 同上
./run_all.sh --help         # ヘルプ表示
DEBUG_LEVEL=2 ./run_all.sh  # 詳細ログ表示
DEBUG_LEVEL=0 ./run_all.sh  # 静かに実行
```

**注意:**
- ダウンロードは差分モード（既存 JSON はスキップ）で実行されます
- ダウンロードには `httpx` パッケージが必要です: `pip install httpx`

---

## 前提条件

- Python 3.8 以上
- 必要なパッケージ: `openpyxl`

```bash
pip install openpyxl
```

## ディレクトリ構成

```
scripts/tool-c/
├── run_all.sh                             # 一括変換スクリプト（推奨）
├── common.py                              # 共通ユーティリティ
├── csv_to_excel.py                        # CSV → Excel 変換
├── researchmap_json_to_csv_papers.py      # 論文
├── researchmap_json_to_csv_buntan.py      # 分担執筆
├── researchmap_json_to_csv_tancho.py      # 単著
├── researchmap_json_to_csv_kyocho_hencho.py # 共著・編著
├── researchmap_json_to_csv_kotohappyo.py  # 口頭発表
├── researchmap_json_to_csv_misc.py        # MISC
├── researchmap_json_to_csv_sonota.py      # その他
└── README.md                              # このファイル
```

## 使い方

### 1. JSON → CSV 変換

researchmap からエクスポートした JSON ファイルを各カテゴリの CSV に変換します。

#### 論文
```bash
python researchmap_json_to_csv_papers.py --input-file <JSON_FILE> --output-dir <OUTPUT_DIR>
```

#### 分担執筆
```bash
python researchmap_json_to_csv_buntan.py --input-file <JSON_FILE> --output-dir <OUTPUT_DIR>
```

#### 単著
```bash
python researchmap_json_to_csv_tancho.py --input-file <JSON_FILE> --output-dir <OUTPUT_DIR>
```

#### 共著・編著
```bash
python researchmap_json_to_csv_kyocho_hencho.py --input-file <JSON_FILE> --output-dir <OUTPUT_DIR>
```

#### 口頭発表
```bash
python researchmap_json_to_csv_kotohappyo.py --input-file <JSON_FILE> --output-dir <OUTPUT_DIR>
```

#### MISC
```bash
python researchmap_json_to_csv_misc.py --input-file <JSON_FILE> --output-dir <OUTPUT_DIR>
```

#### その他
```bash
python researchmap_json_to_csv_sonota.py --input-file <JSON_FILE> --output-dir <OUTPUT_DIR>
```

**引数:**
- `--input-file`: researchmap エクスポート JSON ファイル（例: `cm3.json`）
- `--output-dir`: 出力ディレクトリ

**出力ファイル名:**
入力ファイル名の拡張子を除いた部分 + カテゴリ名 + `.csv`
- 例: `cm3.json` → `cm3-論文.csv`, `cm3-分担執筆.csv`, ...

### 2. CSV → Excel 変換

個人ごとの CSV ファイル群を `box/sample.xlsx` の形式に従った Excel ファイルにまとめます。

```bash
python csv_to_excel.py
```

**入力:**
- `data/csv/` ディレクトリ内の CSV ファイル群
- ファイル命名規則: `<ID>-<カテゴリ名>.csv`
  - 例: `mak_goto-論文.csv`, `mak_goto-分担執筆.csv`

**出力:**
- `data/xlsx/` ディレクトリに個人ごとの Excel ファイルを生成
- 例: `mak_goto.xlsx`

**カテゴリとシートの対応:**

| CSVファイル名に含まれる文字列 | Excelシート名 |
|-------------------------------|---------------|
| 論文                          | 論文          |
| 分担執筆                      | 分担執筆      |
| 単著                          | 単著          |
| 共著編著                      | 共著・編著    |
| 口頭発表                      | 口頭発表      |
| MISC                          | MISC          |
| その他                        | その他        |

## 一括変換

通常は `run_all.sh` を使用してください（「クイックスタート」参照）。

手動で実行する場合:

```bash
cd /path/to/researcher-search

# 1. JSON → CSV（各スクリプトを個別実行）
python scripts/tool-c/researchmap_json_to_csv_papers.py --input-file data/json/cm3.json --output-dir data/csv

# 2. CSV → Excel
python scripts/tool-c/csv_to_excel.py
```

## データ変換仕様

### 日付形式
- 入力: `yyyy-MM-dd`, `yyyy-MM`, `yyyy`
- 出力: `yyyyMMdd`, `yyyyMM00`, `yyyy0000`（8桁整数形式）

### 記述言語
- `data/lang.csv` を参照して言語コードを日本語に変換
- 例: `jpn` → `日本語`, `eng` → `英語`
- 該当するコードがなければ元の値をそのまま出力

### 選択肢項目
- Excel 入力規則と整合するため `コード:ラベル` 形式で出力
- 例: `1:査読有り`, `99:その他`

## ファイル説明

### common.py

全スクリプトが共通で利用するユーティリティ関数を提供:

- `load_json()`: JSON ファイル読み込み
- `get_researchmap_data()`: researchmap_data の取得
- `get_profile_fields()`: プロファイル情報（入力者名、e-Rad番号）の取得
- `normalize_date_yyyymmdd()`: 日付正規化
- `convert_languages()`: 言語コード変換
- `join_names()`: 著者名リストの連結
- 各種選択肢マッピング関数

### csv_to_excel.py

CSV → Excel 変換時の書式設定:

- ヘッダー色: 青（機構項目）、灰（No.）、黄（入力項目）
- 必須項目: 赤字フォント
- セル結合: グループヘッダーの結合
- 罫線: 細線
- 文字揃え: 中央揃え
- データ入力規則: `sample.xlsx` と同様のドロップダウンリストを自動適用

## 研究課題番号の処理

researchmap の `see_also` → `research_projects` を辿り、研究課題を以下のルールで分類・出力します。

### 科研費（KAKEN）の判定

1. **`system_name` による判定**（優先）
   - 日本語: 「科学研究費助成事業」「科学研究費補助金」を含む
   - 英語: "Grants-in-Aid for Scientific Research" を含む

2. **`grant_number` パターンによる判定**（`system_name` が空の場合のフォールバック）
   - `数字2桁 + K + 数字` (例: 23K01047)
   - `数字2桁 + KK/KF/KJ + 数字` (例: 19KK0106, 22KF0370)
   - `数字2桁 + H/J/F/A/B/C/S + 数字` (例: 16H01941)
   - `5〜8桁の数字のみ` (例: 24251017) ※旧形式
   - ※精度: 約98.6%

### 出力先

| 研究課題の種類 | 出力先 | 出力内容 |
|----------------|--------|----------|
| 科研費（KAKEN） | 科研費課題番号 | `grant_number` のみ |
| その他の競争的資金等 | 共同研究番号 | `研究課題名（system_name）` |
| その他（system_name なし） | 共同研究番号 | `研究課題名` |

### 例

```
# 科研費の場合
system_name: "科学研究費助成事業（基盤研究(C)）"
grant_number: "23K01047"
→ 科研費課題番号: 23K01047

# その他の競争的資金の場合
system_name: "受託研究"
research_project_title: "地域資料の保存活用"
→ 共同研究番号: 地域資料の保存活用（受託研究）
```
