
import os
from pathlib import Path

def write_file(rel_path, content):
    p = Path(rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '
')
    print(f'Wrote {rel_path} ({len(content)} chars)')
