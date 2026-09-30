#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""timing_check.py：講稿配速檢查（pitch-craft）。
讀「講稿模板」格式的 markdown，逐段估算口說秒數，與計畫秒、總時限比對。
只用標準庫；輸出 markdown 到 stdout，--out 可另存。
"""
import argparse
import os
import re
import sys
import tempfile

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ---- 門檻常數（--help 會列出）----
OVER_RATIO = 0.15                 # 段落估時「慢值」超過計畫秒 15% 以上 -> 超時
LONG_SEG_RATIO = 0.25             # 單段估時（中值）> 總時限 25% -> 太長，考慮拆段
TARGET_LO, TARGET_HI = 0.90, 0.95  # 建議目標：時限的 90-95%（現場一定比排練慢）
DEFAULT_ZH = (180.0, 200.0)       # 字/分。Matt 定案 2026-09-30：目標 180–200，上限 240
DEFAULT_EN = (100.0, 110.0)       # wpm。出自卡片《語速設定（3MT／非母語）》

CJK_RE = re.compile('[一-鿿㐀-䶿]')
WORD_RE = re.compile(r"[A-Za-z0-9'’-]+")

def read_text(path):
    with open(path, encoding='utf-8', newline='') as f:  # newline='' 保留原換行
        return f.read()

def split_row(line):
    s = line.strip()
    s = s[1:] if s.startswith('|') else s
    if s.endswith('|') and not s.endswith('\\|'):
        s = s[:-1]
    return [c.strip().replace('\\|', '|') for c in re.split(r'(?<!\\)\|', s)]

def cell_spans(line):
    """每個儲存格內容在原行中的 (起, 止) 位置，供 --write-back 精準替換。"""
    p = [m.start() for m in re.finditer(r'(?<!\\)\|', line)]
    return [(a + 1, b) for a, b in zip(p, p[1:])]

def find_tables(lines, lo, hi):
    """範圍內所有表：[(表頭 cells, [(行號, cells), ...]), ...]。"""
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
    """讀開頭 --- 包住的簡單 key: value（不巢狀）。"""
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

def parse_range(s):
    nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', str(s or ''))]
    if not nums or min(nums) <= 0:
        return None
    return (nums[0], nums[0]) if len(nums) == 1 else tuple(sorted(nums[:2]))

def pick(cands, default):
    for v, src in cands:
        if v is not None:
            return v, src
    return default

def count(cell):
    """清洗後計 (CJK 字數, 英文詞數)。舞台指示、停頓記號、粗體記號不計。"""
    s = re.sub(r'<br\s*/?>|<[^>]+>', ' ', cell, flags=re.I)
    s = re.sub(r'〔[^〕]*〕', '', s)
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)
    s = s.replace('／', ' ').replace('**', '')
    words = [w for w in WORD_RE.findall(s) if re.search('[A-Za-z0-9]', w)]
    return len(CJK_RE.findall(s)), len(words)

def write_back(path, text, updates):
    """updates: [(行號, 欄位索引, 新數字)]；只換該儲存格內容，原子寫入。"""
    lines = text.splitlines(keepends=True)
    for ln, ci, val in updates:
        line = lines[ln]
        s, e = cell_spans(line)[ci]
        orig = line[s:e]
        lead, trail = (orig[:len(orig) - len(orig.lstrip())], orig[len(orig.rstrip()):]) if orig.strip() else (' ', ' ')
        lines[ln] = line[:s] + lead + str(val) + trail + line[e:]
    data = ''.join(lines).encode('utf-8')          # 先編碼，失敗不會動到原檔
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    except OSError as ex:                          # 例如檔案被別的程式鎖住：清掉暫存檔，原檔不動
        if os.path.exists(tmp):
            os.unlink(tmp)
        sys.exit(f'錯誤：回填失敗，原檔未動：{ex}')

def build_parser():
    ap = argparse.ArgumentParser(
        prog='timing_check.py', add_help=False, formatter_class=argparse.RawDescriptionHelpFormatter,
        usage='python timing_check.py <講稿.md> [--profile p.md] [--limit-sec N] [--zh-rate 180-200] '
              '[--en-rate 100-110] [--write-back] [--out f.md]',
        description='講稿配速檢查：逐段估口說秒數，對照計畫秒與總時限。優先序：CLI > profile > 講稿檔本身 > 預設。',
        epilog=(
            f'門檻常數：\n  段落超時：估時慢值 > 計畫秒 x (1+{OVER_RATIO:.0%})\n'
            f'  單段太長：估時中值 > 總時限 x {LONG_SEG_RATIO:.0%}\n'
            f'  建議目標：估時中值落在時限的 {TARGET_LO:.0%}-{TARGET_HI:.0%}\n'
            f'預設語速：中文 {DEFAULT_ZH[0]:.0f}-{DEFAULT_ZH[1]:.0f} 字/分（目標；上限 240）；'
            f'英文 {DEFAULT_EN[0]:.0f}-{DEFAULT_EN[1]:.0f} wpm（出自卡片《語速設定（3MT／非母語）》，'
            f'最快不超過 140）。\n'
            '計數：CJK 只算漢字；英文詞用 [A-Za-z0-9\'’-]+（阿拉伯數字也算一詞）。'))
    ap._optionals.title, ap._positionals.title = '參數', '位置參數'
    ap.add_argument('-h', '--help', action='help', help='顯示這段說明後離開')
    ap.add_argument('script', help='講稿 markdown 檔（講稿模板格式）')
    ap.add_argument('--profile', help='profile 檔（開頭 --- 包住的 key: value）')
    ap.add_argument('--limit-sec', type=int, help='總時限（秒）；覆蓋 profile 與講稿設定')
    ap.add_argument('--zh-rate', help='中文語速 字/分，單值或區間，例 180-200')
    ap.add_argument('--en-rate', help='英文語速 wpm，單值或區間，例 100-110')
    ap.add_argument('--write-back', action='store_true', help='把算出的字數（中文=字、英文=詞）填回原檔「字數」欄')
    ap.add_argument('--out', help='另存 markdown 報告的路徑')
    return ap

def main():
    a = build_parser().parse_args()
    for flag, val in (('--zh-rate', a.zh_rate), ('--en-rate', a.en_rate)):
        if val and not parse_range(val):
            sys.exit(f'錯誤：{flag} 格式不對（要正數，例如 180-200）：{val}')
    text = read_text(a.script)
    lines = text.splitlines(keepends=True)
    prof = load_profile(a.profile) if a.profile else {}
    fs = {c[0]: c[1] for _, r in find_tables(lines, *section_range(lines, '基本設定'))[:1] for _, c in r if len(c) >= 2}
    fv = lambda pre: next((v for k, v in fs.items() if k.startswith(pre)), '')
    zh_f = re.search(r'中文\s*(\d+(?:\s*[-–~]\s*\d+)?)\s*字', fv('目標語速'))
    en_f = re.search(r'英文\s*(\d+(?:\s*[-–~]\s*\d+)?)\s*wpm', fv('目標語速'))
    limit, s_lim = pick([(a.limit_sec, 'CLI'), (first_int(prof.get('time_limit_sec')), 'profile'),
                         (first_int(fv('時限')), '講稿')], (None, '未設定'))
    zh, s_zh = pick([(parse_range(a.zh_rate), 'CLI'), (parse_range(prof.get('zh_chars_per_min')), 'profile'),
                     (parse_range(zh_f.group(1)) if zh_f else None, '講稿')],
                    (DEFAULT_ZH, '預設（目標 180–200，上限 240）'))
    en, s_en = pick([(parse_range(a.en_rate), 'CLI'), (parse_range(prof.get('en_wpm')), 'profile'),
                     (parse_range(en_f.group(1)) if en_f else None, '講稿')],
                    (DEFAULT_EN, '預設（卡片《語速設定（3MT／非母語）》）'))
    langs = re.findall(r'(?<![A-Za-z])(zh-TW|en|mixed)(?![A-Za-z])', fv('語言'))
    lang, s_lang = pick([(prof.get('language'), 'profile'), (langs[0] if len(langs) == 1 else None, '講稿')],
                        (None, '未指定，依內容判斷'))
    lo, hi = section_range(lines, '段落表')
    seg = next(((h, r) for h, r in find_tables(lines, lo, hi) if h and h[0] == '#' and '講稿' in h), None)
    if not seg:
        sys.exit('錯誤：找不到段落表（表頭第一欄為「#」且含「講稿」欄）。')
    h, body = seg
    ix = {n: i for i, n in enumerate(h)}
    g = lambda c, n: c[ix[n]] if n in ix and ix[n] < len(c) else ''
    zm, em = sum(zh) / 2, sum(en) / 2
    rg = lambda r: f'{r[0]:.0f}' if r[0] == r[1] else f'{r[0]:.0f}-{r[1]:.0f}'
    rows, updates = [], []
    for k, (ln, c) in enumerate(body, 1):
        cjk, words = count(g(c, '講稿'))
        fast = cjk / zh[1] * 60 + words / en[1] * 60
        slow = cjk / zh[0] * 60 + words / en[0] * 60
        rows.append(dict(n=first_int(g(c, '#')) or k, fn=g(c, '功能'), cjk=cjk, words=words, fast=fast, slow=slow,
                         mid=(fast + slow) / 2, plan=first_int(g(c, '秒')) or 0))
        if '字數' in ix and ix['字數'] < len(c):
            updates.append((ln, ix['字數'], cjk + words))
    T = lambda key: sum(r[key] for r in rows)
    e = [f'# 講稿配速檢查｜{os.path.basename(a.script)}', '', '| 項目 | 值 | 來源 |', '|---|---|---|',
          f'| 時限 | {limit if limit else "未確認"} 秒 | {s_lim} |', f'| 語言 | {lang or "未確認"} | {s_lang} |',
          f'| 中文語速 | {rg(zh)} 字/分 | {s_zh} |',
          f'| 英文語速 | {rg(en)} wpm | {s_en} |', '',
          '## 逐段', '', '| # | 功能 | 字數 | 詞數 | 估時（快～慢，秒） | 計畫秒 | 差值（慢−計畫） | 旗標 |',
          '|---|---|---|---|---|---|---|---|']
    flagged = []
    for r in rows:
        fl = []
        if r['plan'] > 0 and r['slow'] > r['plan'] * (1 + OVER_RATIO):
            fl.append('超時')
            flagged.append(f'§{r["n"]}（慢值超計畫約 {r["slow"] - r["plan"]:.0f} 秒）')
        elif r['plan'] == 0 and r['slow'] > 0:
            fl.append('未填計畫秒')
        if limit and r['mid'] > limit * LONG_SEG_RATIO:
            fl.append('太長，考慮拆段')
        if r['cjk'] + r['words'] == 0:
            fl.append('（空）')
        diff = f'{r["slow"] - r["plan"]:+.0f}' if r['plan'] else '—'
        e.append(f'| {r["n"]} | {r["fn"]} | {r["cjk"]} | {r["words"]} | {r["fast"]:.0f}～{r["slow"]:.0f} | '
                 f'{r["plan"]} | {diff} | {"、".join(fl) or "—"} |')
    tf, ts, tm = T('fast'), T('slow'), T('mid')
    e += ['', '## 總結', '',
          f'- 估時總和：{tf:.0f}～{ts:.0f} 秒（中值 {tm:.0f}）；字數 {T("cjk")}、詞數 {T("words")}；計畫秒加總 {T("plan")}']
    if (lang == 'en' and T('cjk')) or (lang == 'zh-TW' and not T('cjk') and T('words')):
        e.append(f'- 注意：語言設為 {lang}，但內容不符（漢字 {T("cjk")}、詞 {T("words")}）。')
    if rows and tm > 0:
        e.append(f'- Hook（第 {rows[0]["n"]} 段）占估時 {rows[0]["mid"] / tm:.0%}（僅報告，不評判）。')
    if not limit:
        e.append('- 未取得時限，略過總時限比對（用 --limit-sec 或在基本設定填「時限（秒）」）。')
    else:
        t_lo, t_hi = limit * TARGET_LO, limit * TARGET_HI
        e.append(f'- 時限 {limit} 秒；建議目標 {t_lo:.0f}–{t_hi:.0f} 秒（{TARGET_LO:.0%}–{TARGET_HI:.0%}）；'
                 f'中值占時限 {tm / limit:.0%}。')
        if tm > t_hi:
            cut = tm - t_hi
            t_zh, t_en = T('cjk') / zm * 60, T('words') / em * 60
            n_zh, n_en = round(cut * t_zh / tm * zm / 60), round(cut * t_en / tm * em / 60)
            unit = '／'.join(x for x in (f'{n_zh} 字' if n_zh else '', f'{n_en} 詞' if n_en else '') if x)
            e.append(f'- **超過目標**：需再省約 {cut:.0f} 秒，約需刪 {unit or "少量字詞"}。'
                     + (f'優先從超時段下手：{"、".join(flagged)}。' if flagged else ''))
        elif tm < t_lo:
            e.append(f'- 低於目標下限約 {t_lo - tm:.0f} 秒：有餘裕，可補內容或放慢；不算問題。')
        else:
            e.append('- PASS：估時中值落在建議目標區間內。')
        if ts > limit:
            e.append(f'- 提醒：慢值 {ts:.0f} 秒已超過時限 {limit} 秒；現場緊張易偏慢，建議再留餘裕。')
    if a.write_back:
        write_back(a.script, text, updates)
        e.append(f'- 已回填「字數」欄 {len(updates)} 列（其他內容未動）。')
    report = '\n'.join(e) + '\n'
    print(report, end='')
    if a.out:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
            f.write(report)

if __name__ == '__main__':
    main()
