"""Preview issue creation; explicit --apply uses authenticated gh CLI. Not run by us."""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--repo',required=True,help='owner/repo')
p.add_argument('--apply',action='store_true',help='Actually create issues; check duplicates first')
a=p.parse_args()
issues=json.loads(Path(__file__).with_name('issues.json').read_text())
if not a.apply:
    for x in issues: print(x['title'], 'dependencies:', ', '.join(x['depends_on']) or 'none')
    print('Preview only; no GitHub access.')
else:
    # Existing titles include stable issue IDs; fail closed on lookup error.
    raw=subprocess.check_output(['gh','issue','list','--repo',a.repo,'--state','all','--limit','1000','--json','title'],text=True)
    titles={x['title'] for x in json.loads(raw)}
    if len(titles)>=1000: raise SystemExit('Too many existing issues for safe duplicate check; import manually.')
    for x in issues:
        if any(t.startswith('['+x['id']+']') for t in titles):
            print('Skipping existing',x['id']);continue
        subprocess.run(['gh','issue','create','--repo',a.repo,'--title',x['title'],'--body',x['body']],check=True)
