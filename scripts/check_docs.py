"""Check tracked Markdown links and heading anchors without network access."""
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def anchors(text):
    found, counts = set(), {}
    for title in re.findall(r'^#{1,6}\s+(.+)$', text, re.M):
        slug = re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-')
        index = counts.get(slug, 0)
        counts[slug] = index + 1
        found.add(f'{slug}-{index}' if index else slug)
    return found


def main():
    names = subprocess.check_output(['git', 'ls-files', '-z', '*.md'], cwd=ROOT).decode().split('\0')
    errors = []
    for name in filter(None, names):
        source = ROOT / name
        if not source.exists():
            continue
        text = re.sub(r'```.*?```', '', source.read_text(), flags=re.S)
        targets = re.findall(r'\]\(([^)\s]+)\)', text)
        targets += re.findall(r'^\[[^]]+\]:\s*(\S+)', text, re.M)
        for target in targets:
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target):
                continue
            path, _, fragment = unquote(target).partition('#')
            destination = source.parent / path if path else source
            if not destination.exists():
                errors.append(f'{name}: missing target {target}')
            elif fragment and destination.suffix == '.md':
                if fragment not in anchors(destination.read_text()):
                    errors.append(f'{name}: missing anchor {target}')
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print('Markdown links and heading anchors passed.')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
