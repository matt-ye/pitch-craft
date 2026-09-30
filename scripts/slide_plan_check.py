#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""slide_plan_check.py：投影片規劃表驗證（pitch-craft）。

讀「投影片逐頁規劃表」格式的 markdown，逐項對照範本「自核」段檢查，
輸出 FAIL／WARN／PASS 三級清單；有 FAIL 時 exit code 1。只用標準庫。
"""
import argparse
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ---- 門檻常數（--help 會列出）----
TITLE_MAX_ZH, TITLE_MAX_EN = 24, 14   # 標題句上限：中文字數／英文詞數
POINTS_MAX = 3                        # 每頁內容要點上限
SEC_TOL = 0.10                        # 秒數加總容許誤差（±10%）
VISUALS = ['資料圖：序列', '資料圖：佔比', '資料圖：數字', '資料圖：位置', '圖解：樹狀', '圖解：流程',
           '圖解：矩陣', '圖解：循環', '圖解：對比', '照片／情境圖', '大字一句', '表格', '示範／影片', '人物／團隊']

CJK_RE = re.compile('[一-鿿㐀-䶿]')
WORD_RE = re.compile(r"[A-Za-z0-9'’-]+")

def read_text(path):
    with open(path, encoding='utf-8', newline='') as f:
        return f.read()

def split_row(line):
    s = line.strip()
    s = s[1:] if s.startswith('|') else s
    if s.endswith('|') and not s.endswith('\\|'):
        s = s[:-1]
    return [c.strip().replace('\\|', '|') for c in re.split(r'(?<!\\)\|', s)]

def find_tables(lines, lo, hi):
    out, i = [], lo
    while i < hi:
        if lines[i].lstrip().startswith('|'):
            j = i
            while j < hi and lines[j].lstrip().startswith('|'):
                j += 1
            rows = [(k, split_row(lines[k])) for k in range(i, j)]
            body = [r for r in rows if not all(re.fullmatch(r':?-+:?', c) for c in r[1])]
            if body:
                out.append((body[0][1], body[1:]))
            i = j
        else:
            i += 1
    return out

def section_range(lines, title):
    for i, ln in enumerate(lines):
        if re.match(r'##\s+' + re.escape(title), ln):
            j = i + 1
            while j < len(lines) and not re.match(r'##\s', lines[j]):
                j += 1
            return i + 1, j
    return 0, len(lines)

def load_profile(path):
    lines = read_text(path).lstrip('﻿').splitlines()
    d = {}
    if lines and lines[0].strip() == '---':
        for ln in lines[1:]:
            if ln.strip() == '---':
                break
            m = re.match(r'\s*([A-Za-z_]\w*)\s*:\s*(.*?)\s*$', ln)
            if m:
                d[m.group(1)] = re.sub(r'\s+#.*$', '', m.group(2)).strip().strip('"\'')
    return d

def first_int(s):
    m = re.search(r'\d+', s or '')
    return int(m.group()) if m else None

def pick(cands, default=(None, '未設定')):
    return next(((v, s) for v, s in cands if v is not None), default)

def count(s):
    s = re.sub(r'[*`]|<[^>]+>', '', s)
    return len(CJK_RE.findall(s)), len([w for w in WORD_RE.findall(s) if re.search('[A-Za-z0-9]', w)])

def resolve_script(cli, cell, base):
    """--script 優先；否則把「對應講稿」當相對路徑（相對規劃表所在資料夾，再試目前目錄）。"""
    v = cli or re.sub(r'[`\[\]]', '', cell or '').strip()
    for name in ([v] if cli else [v, v + '.md']) if v else []:
        for root in (base, os.getcwd()):
            p = name if os.path.isabs(name) else os.path.join(root, name)
            if os.path.isfile(p):
                return p
    return None

def script_segments(path):
    lines = read_text(path).splitlines(keepends=True)
    for h, rows in find_tables(lines, *section_range(lines, '段落表')):
        if h and h[0] == '#' and '講稿' in h:
            return {n for n in (first_int(c[0]) for _, c in rows if c) if n is not None}
    return set()

def build_parser():
    ap = argparse.ArgumentParser(
        prog='slide_plan_check.py', add_help=False, formatter_class=argparse.RawDescriptionHelpFormatter,
        usage='python slide_plan_check.py <規劃表.md> [--script 講稿.md] [--profile p.md] [--slide-limit N] '
              '[--limit-sec N] [--title-max-zh 24] [--title-max-en 14] [--out f.md]',
        description='投影片規劃表驗證。優先序：CLI > profile > 規劃表基本設定。有 FAIL 時 exit code 1。',
        epilog=(f'檢查項目與門檻：頁數 <= 上限（頁面目的含「備援」者不計；0 = 無限制）；秒數加總在時限 +-{SEC_TOL:.0%}'
                f'（備援不計）；標題句必填，中文 <= {TITLE_MAX_ZH} 字、英文 <= {TITLE_MAX_EN} 詞；'
                f'內容要點（以「；」或「;」切分）<= {POINTS_MAX}；視覺類型須在範本選單內（可接註記，例「資料圖：序列（折線）」）；'
                '講稿段 §n 須存在於講稿段落表，且每個講稿段至少被一頁引用（未引用為 WARN）。\n'
                '視覺類型選單：' + '、'.join(VISUALS)))
    ap._optionals.title, ap._positionals.title = '參數', '位置參數'
    ap.add_argument('-h', '--help', action='help', help='顯示這段說明後離開')
    ap.add_argument('plan', help='規劃表 markdown 檔（投影片逐頁規劃表格式）')
    ap.add_argument('--script', help='講稿檔；未給時嘗試用基本設定的「對應講稿」當相對路徑')
    ap.add_argument('--profile', help='profile 檔（讀 slide_limit、time_limit_sec）')
    ap.add_argument('--slide-limit', type=int, help='頁數上限（0 = 無限制）')
    ap.add_argument('--limit-sec', type=int, help='總時限（秒）')
    ap.add_argument('--title-max-zh', type=int, default=TITLE_MAX_ZH, help=f'標題句中文字數上限（預設 {TITLE_MAX_ZH}）')
    ap.add_argument('--title-max-en', type=int, default=TITLE_MAX_EN, help=f'標題句英文詞數上限（預設 {TITLE_MAX_EN}）')
    ap.add_argument('--out', help='另存 markdown 報告的路徑')
    return ap

def main():
    a = build_parser().parse_args()
    lines = read_text(a.plan).splitlines(keepends=True)
    prof = load_profile(a.profile) if a.profile else {}
    fs = {}
    for _, rows in find_tables(lines, *section_range(lines, '基本設定'))[:1]:
        fs = {c[0]: c[1] for _, c in rows if len(c) >= 2}
    fv = lambda pre: next((v for k, v in fs.items() if k.startswith(pre)), '')
    slim, s_slim = pick([(a.slide_limit, 'CLI'), (first_int(prof.get('slide_limit')), 'profile'),
                         (first_int(fv('頁數上限')), '規劃表')])
    limit, s_lim = pick([(a.limit_sec, 'CLI'), (first_int(prof.get('time_limit_sec')), 'profile'),
                         (first_int(fv('時限')), '規劃表')])
    tab = next(((h, r) for h, r in find_tables(lines, *section_range(lines, '規劃表')) if '頁' in h and '標題句' in ''.join(h)), None)
    if not tab:
        sys.exit('錯誤：找不到規劃表（表頭含「頁」與「標題句」欄）。')
    h, body = tab
    col = lambda n, ex=False: next((i for i, x in enumerate(h) if (x == n if ex else x.startswith(n))), None)
    ix = dict(pg=col('頁', True), title=col('標題句'), goal=col('頁面目的'), vis=col('視覺類型'),
              pts=col('內容要點'), ref=col('講稿段'), sec=col('秒', True))
    g = lambda c, k: c[ix[k]] if ix[k] is not None and ix[k] < len(c) else ''
    sp = resolve_script(a.script, fv('對應講稿'), os.path.dirname(os.path.abspath(a.plan)))
    if a.script and not sp:
        sys.exit(f'錯誤：找不到 --script 指定的講稿：{a.script}')
    segs = script_segments(sp) if sp else None
    res = {}

    def add(check, level, page, msg='', fix=''):
        res.setdefault(check, {'PASS': [], 'FAIL': [], 'WARN': []})[level].append((page, msg, fix))

    pages = []
    for k, (_, c) in enumerate(body, 1):
        n = first_int(g(c, 'pg'))
        is_backup = '備援' in g(c, 'goal')
        raw_pg = g(c, 'pg').strip()
        lab = raw_pg if is_backup and raw_pg else (f'P{n}' if n else f'第{k}列')
        pages.append(dict(lab=lab, c=c, backup=is_backup))
    main_pages = [p for p in pages if not p['backup']]
    nb = len(pages) - len(main_pages)
    if slim:
        (add('頁數上限', 'PASS', '全表', f'{len(main_pages)} 頁 <= {slim}') if len(main_pages) <= slim else
         add('頁數上限', 'FAIL', '全表', f'正式頁 {len(main_pages)} 頁 > 上限 {slim}', f'合併或刪去 {len(main_pages) - slim} 頁，或移到備援'))
    else:
        add('頁數上限', 'PASS', '全表', '無頁數限制（上限 0 或未設定）')
    total = sum(first_int(g(p['c'], 'sec')) or 0 for p in main_pages)
    if not limit:
        add('秒數加總', 'WARN', '全表', '未取得時限，略過', '用 --limit-sec 或在基本設定填「時限（秒）」')
    elif abs(total - limit) <= limit * SEC_TOL:
        add('秒數加總', 'PASS', '全表', f'{total} 秒，時限 {limit} 秒 +-{SEC_TOL:.0%}')
    else:
        gap = math.ceil(abs(total - limit) - limit * SEC_TOL)
        add('秒數加總', 'FAIL', '全表', f'加總 {total} 秒，超出時限 {limit} 秒 +-{SEC_TOL:.0%}',
            f'至少{"減" if total > limit else "加"}約 {gap} 秒')
    refs_all = set()
    for p in pages:
        c, lab = p['c'], p['lab']
        t = re.sub(r'[*`]', '', g(c, 'title')).strip()
        cjk, words = count(t)
        if not t:
            add('標題句', 'FAIL', lab, '標題句是空的', '寫出這頁要讓評審帶走的結論句，不是主題名')
        elif re.fullmatch(r'[（(].*[）)]', t):
            add('標題句', 'WARN', lab, '標題句仍是範本佔位文字', '換成這頁的結論句')
        elif cjk > a.title_max_zh or words > a.title_max_en:
            add('標題句', 'FAIL', lab, f'太長（{cjk} 字／{words} 詞；上限 {a.title_max_zh} 字／{a.title_max_en} 詞）',
                '只留結論，砍掉修飾語與括號補充')
        else:
            add('標題句', 'PASS', lab)
        pts = [x for x in re.split(r'[；;]', g(c, 'pts')) if x.strip()]
        if len(pts) > POINTS_MAX:
            add('內容要點', 'FAIL', lab, f'{len(pts)} 點 > {POINTS_MAX}', f'砍到 {POINTS_MAX} 點，或拆成兩頁')
        else:
            add('內容要點', 'PASS', lab)
        v = re.sub(r'[`\s]', '', g(c, 'vis')).replace(':', '：').replace('/', '／')
        if any(v.startswith(o) for o in VISUALS):
            add('視覺類型', 'PASS', lab)
        elif v in ('資料圖', '圖解'):
            add('視覺類型', 'WARN', lab, f'「{v}」缺子類型', '補成「資料圖：序列」這類完整選項')
        else:
            add('視覺類型', 'FAIL', lab, f'「{g(c, "vis") or "空白"}」不在選單內', '改成範本選單內的類型（python slide_plan_check.py --help 可列出）')
        refs = [int(x) for x in re.findall(r'§\s*(\d+)', g(c, 'ref'))]
        refs_all.update(refs)
        bad = [r for r in refs if segs is not None and r not in segs]
        if bad:
            add('講稿對應', 'FAIL', lab, '引用的 ' + '、'.join(f'§{r}' for r in bad) + ' 在講稿不存在',
                f'改成講稿現有段落（{"、".join(f"§{s}" for s in sorted(segs))}）或先補該段')
        elif not refs and not p['backup']:
            add('講稿對應', 'WARN', lab, '沒有填講稿段', '填 §n；若是刻意無講稿的頁，在備註說明')
        else:
            add('講稿對應', 'PASS', lab)
    if segs:
        for n in sorted(segs - refs_all):
            add('講稿對應', 'WARN', f'講稿§{n}', '沒有任何一頁引用（那段講的時候畫面是空的）', '掛到某頁的「講稿段」，或確認是刻意留白')
    e = [f'# 投影片規劃檢查｜{os.path.basename(a.plan)}', '',
         f'- 頁數上限：{slim if slim is not None else "未確認"}（{s_slim}）｜時限：{limit or "未確認"} 秒（{s_lim}）｜'
         f'正式頁 {len(main_pages)}、備援 {nb}｜秒數加總 {total}',
         f'- 講稿：{os.path.basename(sp) if sp else "未提供或無法解析，略過講稿對應檢查"}', '']
    nf = nw = 0
    for lv in ('FAIL', 'WARN', 'PASS'):
        items = [(ck, x) for ck, d in res.items() for x in d[lv]]
        if lv == 'FAIL':
            nf = len(items)
        if lv == 'WARN':
            nw = len(items)
        e += [f'## {lv}（{len(items)}）', '']
        if lv == 'PASS':
            for ck, d in res.items():
                ps = [x[0] for x in d['PASS']]
                if ps:
                    e.append(f'- {ck}：' + (d['PASS'][0][1] if ps == ['全表'] else '、'.join(ps) + ' 通過'))
        else:
            e += [f'- [{pg}] {ck}：{msg} → 建議：{fix}' for ck, (pg, msg, fix) in items]
        e.append('')
    e.append(f'**總結：FAIL {nf}，WARN {nw}**')
    report = '\n'.join(e) + '\n'
    print(report, end='')
    if a.out:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
            f.write(report)
    sys.exit(1 if nf else 0)

if __name__ == '__main__':
    main()
