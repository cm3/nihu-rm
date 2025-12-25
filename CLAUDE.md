# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NIHU Researcher Search is a FastAPI-based web application for searching researchers affiliated with the National Institutes for the Humanities (NIHU). The system fetches researcher data from researchmap and provides full-text search capabilities across profiles, publications, presentations, and other academic achievements.

## Development Commands

### Setup and Database

```bash
# Install dependencies
pip install -r requirements.txt

# Download researcher data from researchmap
# Full download (default: overwrites existing files)
python scripts/download_data.py --csv data/tool-a-1225-converted.csv

# Incremental download (skip existing researchers, only download new ones)
python scripts/download_data.py --csv data/tool-a-1225-converted.csv --incremental
python scripts/download_data.py --csv data/tool-a-1225-converted.csv -i

# Initialize database and import JSON data
python scripts/setup_db.py

# Test FTS5 search functionality
python test_fts.py
```

### Running the Application

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Alternative: Run directly
python app/main.py
```

### Testing

No formal test suite exists yet. Use `test_fts.py` for manual FTS5 search verification.

## Architecture

### Data Flow

1. **Data Acquisition**: `scripts/download_data.py` reads CSV file, extracts researchmap IDs, and fetches researcher data via researchmap API (async with rate limiting). Supports incremental mode (`--incremental`) to skip existing researchers and only download new ones
2. **Database Setup**: `scripts/setup_db.py` creates SQLite database with dual tables:
   - `researchers`: Base table with researcher metadata
   - `researchers_fts`: FTS5 virtual table for full-text search using trigram tokenizer
3. **API Layer**: FastAPI serves search endpoints with filtering by organization, initial, and full-text query
4. **Frontend**: Single-page application using Jinja2 templates with vanilla JavaScript

### Database Schema

**researchers table**: Stores core researcher information
- Primary key: `id` (researchmap ID)
- Fields: `name_ja`, `name_en`, `avatar_url`, `org1`, `org2`, `position`, `researchmap_url`
- JSON blob: `researchmap_data` (full researchmap API response)

**researchers_fts table**: FTS5 virtual table with trigram tokenizer for Japanese text support
- Contains 20+ searchable fields including basic info, papers, books, presentations, awards, research interests, research areas, projects, works, education, committee memberships, teaching experience, and association memberships
- Text extraction logic in `setup_db.py:extract_texts_from_researchmap_items()` flattens nested researchmap JSON into searchable strings
- Snippet generation: Returns highlighted matches using `snippet()` function with `<mark>` tags

### Full-Text Search Implementation

The FTS5 search uses **trigram tokenizer** (`tokenize='trigram'`), which is critical for Japanese language support:
- Splits text into 3-character n-grams
- Query handling in `database.py:search_researchers()`:
  - Single-word queries: passed directly to FTS5
  - Multi-word queries: joined with OR operator for broader matching
- Important: Trigram search is substring-based, so "ジェンダー" matches anywhere in text

### API Router Pattern

`app/routers/researchers.py` contains all researcher-related endpoints. The router is registered in `app/main.py` with `/api` prefix:
- `GET /api/researchers`: Search with pagination, filtering by org1/org2/initial, full-text query
- `GET /api/researchers/{researcher_id}`: Fetch individual researcher details
- `GET /api/organizations`: Return hardcoded list of NIHU institutions

All database operations go through `app/database.py:Database` class for connection management.

## Key Implementation Details

### researchmap Data Extraction

`scripts/setup_db.py:extract_texts_from_researchmap_items()` is the core text extraction logic:
- Iterates through `items` arrays in researchmap JSON responses
- Extracts multilingual fields (prefers `ja`, falls back to `en`)
- Builds searchable text from: titles, author names, publication names, summaries (truncated to 200 chars), dates
- Different achievement types (papers, books, presentations, etc.) processed separately
- Text length limits prevent FTS5 table bloat (e.g., 10000 chars for papers, 5000 for awards)

### Initial Filtering Logic

Name-based alphabetical filtering (`A-G`, `H-N`, `O-U`, `V-Z`) is implemented via SQL LIKE clauses on `name_en` field. This logic is duplicated in both `search_researchers()` and `count_researchers()` methods.

## Important Notes

- **researchmap API**: Current implementation uses `https://api.researchmap.jp/{id}/{endpoint}`. Verify this matches actual API before production use.
- **Rate Limiting**: `download_data.py` uses semaphore (max 3 concurrent) + 0.5s sleep per researcher. Adjust based on researchmap's ToS.
- **Incremental Downloads**: When CSV is updated, use `--incremental` flag to download only new researchers, saving time and API calls.
- **SQLite Limitations**: Consider PostgreSQL migration for datasets exceeding tens of thousands of researchers.
- **No Authentication**: Current implementation has no auth layer. Add before exposing publicly.
- **CORS**: Currently set to allow all origins (`allow_origins=["*"]`) in `app/main.py`. Restrict for production.

## Common Patterns

When modifying search functionality:
1. Update FTS5 table definition in `scripts/setup_db.py:create_database()`
2. Update text extraction in `scripts/setup_db.py:extract_achievement_texts()`
3. Update search query in `app/database.py:search_researchers()` to include new snippet
4. Add corresponding field to `app/models.py:Researcher` model
5. Re-run `python scripts/setup_db.py` to rebuild database

When adding new API endpoints:
- Add route handler to `app/routers/researchers.py`
- Define Pydantic response model in `app/models.py`
- Router is automatically registered via `app.include_router()` in `main.py`
