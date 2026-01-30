import sqlite3

conn = sqlite3.connect('data/researchers.db')
c = conn.cursor()

# Get the presentations_text for a_takeuch
c.execute('SELECT presentations_text FROM researchers_fts WHERE id = ?', ('a_takeuch',))
text = c.fetchone()[0]

# Split by separator and find lines with ジェンダー
lines = text.split('\n---\n')
print(f"Total presentations: {len(lines)}")
print("\nPresentations containing ジェンダー:")
for i, line in enumerate(lines):
    if 'ジェンダー' in line:
        print(f"\nLine {i}: {line}")

# Try FTS5 search
c.execute('SELECT COUNT(*) FROM researchers_fts WHERE id = ? AND researchers_fts MATCH ?', ('a_takeuch', 'ジェンダー*'))
count = c.fetchone()[0]
print(f"\nFTS5 search result count: {count}")

# Try searching for the English word "Gender"
c.execute('SELECT COUNT(*) FROM researchers_fts WHERE id = ? AND researchers_fts MATCH ?', ('a_takeuch', 'Gender*'))
count_en = c.fetchone()[0]
print(f"FTS5 search for 'Gender*': {count_en}")

conn.close()
