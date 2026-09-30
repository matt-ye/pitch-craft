#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_student.py：匯出 pitch-craft 學生版（去掉內部資料並做洩漏檢查）。

流程：複製 skill 根目錄到暫存區 -> 掃描禁字與 IP 標註 -> 全部通過才搬到輸出位置。
任一命中即 FAIL（exit code 1），並且不產出。只用標準庫。
"""
import argparse
import fnmatch
import os
import re
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

EXCLUDE_DIRS = ('INTERNAL', 'evals', 'dist', '__pycache__', '.git')   # 任何層級的同名資料夾都排除
EXCLUDE_GLOBS = ('*-workspace',)
SCAN_EXT = ('.md', '.py', '.json')


def _j(*parts):
    return ''.join(parts)


# 禁字表：用片段拼接，讓本檔自己不含這些字串（否則學生版會掃到自己）。
# 類別：個人知識庫路徑、wikilink 記號、審核狀態字樣、知識庫內部資料夾名。
FORBIDDEN = [_j('Second_', 'Brain_of_Matt'), _j('D:/', 'Second_Brain'), _j('D:\\', 'Second_Brain'), _j('[', '['),
             _j('待 Matt', ' 審'), _j('待Matt', '審'), _j('AI', '草稿'), _j('5_', 'dialogue'), _j('cards', '/'),
             _j('2_', 'compression'), _j('_ext', 'racted')]
UNSOURCED = ('', '未確認')   # 「他人需標註」列的出處不得是這些（純破折號視同空白）


def split_row(line):
    s = line.strip()
    s = s[1:] if s.startswith('|') else s
    s = s[:-1] if s.endswith('|') and not s.endswith('\\|') else s
    return [c.strip() for c in re.split(r'(?<!\\)\|', s)]


def scan_forbidden(root):
    """逐行掃描 .md/.py/.json；回傳 (掃描檔數, [(相對路徑, 行號, 命中, 片段)])。"""
    hits, n = [], 0
    for dp, _, fns in os.walk(root):
        for f in sorted(fns):
            if not f.lower().endswith(SCAN_EXT):
                continue
            n += 1
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace(os.sep, '/')
            with open(p, encoding='utf-8-sig', errors='replace') as fh:
                for i, line in enumerate(fh, 1):
                    for pat in FORBIDDEN:
                        k = line.find(pat)
                        if k >= 0:
                            hits.append((rel, i, pat, line[max(0, k - 15):k + len(pat) + 25].strip()))
    return n, hits


def check_sources(root):
    """references/SOURCES.md：表格含「IP 分級」「出處」兩欄時，「他人需標註」列必須有出處。"""
    p = os.path.join(root, 'references', 'SOURCES.md')
    if not os.path.isfile(p):
        return False, []
    with open(p, encoding='utf-8-sig', errors='replace') as fh:
        lines = fh.read().splitlines()
    fails, i = [], 0
    while i < len(lines):
        if not lines[i].lstrip().startswith('|'):
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].lstrip().startswith('|'):
            j += 1
        hdr = split_row(lines[i])
        ip = next((k for k, x in enumerate(hdr) if re.search(r'IP\s*分級', x)), None)
        so = next((k for k, x in enumerate(hdr) if '出處' in x), None)
        if ip is not None and so is not None:
            for k in range(i + 1, j):
                c = split_row(lines[k])
                if len(c) > max(ip, so) and '他人需標註' in c[ip]:
                    src = c[so]
                    if src in UNSOURCED or re.fullmatch(r'[-—–\s]*', src):
                        fails.append(('references/SOURCES.md', k + 1, 'IP 分級=他人需標註',
                                      f'出處為「{src or "空白"}」：{" | ".join(c)[:60]}'))
        i = j
    return True, fails


def build_parser():
    ap = argparse.ArgumentParser(
        prog='export_student.py', add_help=False, formatter_class=argparse.RawDescriptionHelpFormatter,
        usage='python export_student.py [--src <skill根目錄>] [--out <輸出資料夾>] [--check-only]',
        description='匯出學生版 skill：複製 skill 根目錄（排除內部資料夾），對複製結果做洩漏檢查，全過才產出。',
        epilog=('排除項：' + '、'.join(EXCLUDE_DIRS + EXCLUDE_GLOBS) + '（任何層級）。\n'
                '掃描範圍：複製結果中的 .md／.py／.json，逐行比對禁字表（個人知識庫路徑、wikilink 記號、'
                '審核狀態字樣、知識庫內部資料夾名；完整清單見本檔 FORBIDDEN 常數），任一命中即 FAIL。\n'
                'IP 檢查：references/SOURCES.md 若有含「IP 分級」與「出處」兩欄的表，'
                '「IP 分級」為「他人需標註」的列，出處不得為空白或「未確認」。\n'
                '--out 已存在時會先整個刪掉再放（刪除前印出路徑）。FAIL 時 exit code 1 且不產出。'))
    ap._optionals.title = '參數'
    ap.add_argument('-h', '--help', action='help', help='顯示這段說明後離開')
    ap.add_argument('--src', help='skill 根目錄（預設：本腳本的上一層）')
    ap.add_argument('--out', help='輸出資料夾（預設：<src>/dist/pitch-craft-student）')
    ap.add_argument('--check-only', action='store_true', help='只檢查，不產出')
    return ap


def main():
    a = build_parser().parse_args()
    src = os.path.abspath(a.src or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out = os.path.abspath(a.out or os.path.join(src, 'dist', 'pitch-craft-student'))
    if not os.path.isdir(src):
        sys.exit(f'錯誤：找不到 skill 根目錄：{src}')
    real_src, real_out = os.path.realpath(src), os.path.realpath(out)
    if real_src == real_out or real_src.startswith(real_out.rstrip(os.sep) + os.sep) or os.path.dirname(real_out) == real_out:
        sys.exit(f'錯誤：輸出位置不可以是 src 本身、src 的上層或磁碟根目錄：{out}')

    def ignore(d, names):
        return [n for n in names if n.endswith('.pyc') or (os.path.isdir(os.path.join(d, n)) and (
                n in EXCLUDE_DIRS or any(fnmatch.fnmatch(n, g) for g in EXCLUDE_GLOBS)
                or os.path.abspath(os.path.join(d, n)) == out))]

    tmp = tempfile.mkdtemp(prefix='pitch-craft-export-')
    try:
        stage = os.path.join(tmp, 'pitch-craft-student')
        shutil.copytree(src, stage, ignore=ignore)
        nfiles = sum(len(f) for _, _, f in os.walk(stage))
        nscan, hits = scan_forbidden(stage)
        has_src, ip_fails = check_sources(stage)
        allhits = hits + ip_fails
        print(f'# 學生版匯出檢查\n\n- 來源：{src}\n- 複製檔數：{nfiles}（已排除內部資料夾）；掃描 {nscan} 個 .md/.py/.json 檔\n'
              f'- SOURCES.md：{"已檢查 IP 標註" if has_src else "不存在，略過"}\n')
        if allhits:
            print(f'## FAIL（{len(allhits)} 處命中）\n')
            for rel, ln, pat, snip in allhits:
                print(f'- {rel}:{ln}: 命中「{pat}」：{snip}')
            print('\n**結果：FAIL，未產出學生版。**')
            return 1
        print('## PASS\n\n- 禁字掃描與 IP 標註檢查皆通過。')
        if a.check_only:
            print('\n**結果：PASS（--check-only，未產出）。**')
            return 0
        if os.path.exists(out):
            print(f'- 輸出位置已存在，先刪除：{out}')
            shutil.rmtree(out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.move(stage, out)
        print(f'\n**結果：PASS，已產出：{out}**')
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
