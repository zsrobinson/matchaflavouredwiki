#!/usr/bin/env python3
"""Download transcripts of the developer's videos that are about Matcha Flavoured into
sources/transcripts/ (committed: they are primary sources for design intent and history).

  tools/fetch_transcripts.py VIDEO_ID [VIDEO_ID ...]
  tools/fetch_transcripts.py --all      every upload on the channel (skips ones already saved)

A video is kept when its title mentions Matcha, or its transcript mentions the pack at least
three times; other videos (the channel also has unrelated essays) are skipped.
"""
import glob
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'sources', 'transcripts')
CHANNEL = 'https://www.youtube.com/@kleiwright/videos'


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60]


def fetch(vid):
    if glob.glob(os.path.join(OUT, '*_%s_*.txt' % vid)):
        return 'exists'
    with tempfile.TemporaryDirectory() as tmp:
        meta = subprocess.run(['yt-dlp', '--skip-download', '--print', '%(title)s\t%(upload_date)s',
                               'https://www.youtube.com/watch?v=' + vid], capture_output=True, text=True).stdout.strip()
        if '\t' not in meta:
            return 'unavailable'
        title, date = meta.split('\t', 1)
        subprocess.run(['yt-dlp', '--skip-download', '--write-auto-subs', '--sub-langs', 'en', '--sub-format', 'vtt',
                        '-o', os.path.join(tmp, 'v'), 'https://www.youtube.com/watch?v=' + vid], capture_output=True)
        vtts = glob.glob(os.path.join(tmp, '*.vtt'))
        if not vtts:
            return 'no captions'
        txt = os.path.join(tmp, 't.txt')
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'vtt_to_text.py'), vtts[0], txt, title, vid, date], check=True)
        body = open(txt, encoding='utf-8').read()
        if 'matcha' not in title.lower() and len(re.findall(r'matcha', body, re.I)) < 3:
            return 'not about the pack'
        os.makedirs(OUT, exist_ok=True)
        dest = os.path.join(OUT, '%s-%s-%s_%s_%s.txt' % (date[:4], date[4:6], date[6:], vid, slug(title)))
        os.replace(txt, dest)
        return 'saved ' + os.path.relpath(dest, ROOT)


def main():
    ids = sys.argv[1:]
    if ids == ['--all']:
        out = subprocess.run(['yt-dlp', '--flat-playlist', '--print', '%(id)s', CHANNEL], capture_output=True, text=True).stdout
        ids = out.split()
    for vid in ids:
        print(vid, fetch(vid))


if __name__ == '__main__':
    main()
