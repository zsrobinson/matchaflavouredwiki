#!/usr/bin/env python3
"""Turn YouTube auto-caption .vtt files into plain transcripts (rolling duplicates removed).
  tools/vtt_to_text.py in.vtt out.txt "Video title" video_id upload_date"""
import re
import sys

src, dst, title, vid, date = sys.argv[1:6]
lines, out = open(src, encoding='utf-8').read().splitlines(), []
for ln in lines:
    if not ln.strip() or '-->' in ln or ln.startswith(('WEBVTT', 'Kind:', 'Language:')) or re.match(r'^\d+$', ln):
        continue
    t = re.sub(r'<[^>]+>', '', ln).strip()
    if t and (not out or t != out[-1]) and not (out and out[-1].endswith(t)):
        out.append(t)
with open(dst, 'w', encoding='utf-8') as f:
    f.write('# %s\n# https://www.youtube.com/watch?v=%s (uploaded %s-%s-%s by Klei_Wright)\n'
            '# Auto-generated captions: names are often misspelled; the pack\'s code is authoritative.\n\n'
            % (title, vid, date[:4], date[4:6], date[6:]) + '\n'.join(out) + '\n')
