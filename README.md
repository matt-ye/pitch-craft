# pitch-craft：提案簡報教練 skill

把你已經有的講稿、投影片或大綱，依情境（時限 1–20 分鐘、中文或英文、評審是誰、題目是商業提案／研究成果／個人申請理由）精煉成能在時限內說服評審的版本；什麼都還沒有時也能從零起草。給 Claude Code、Codex、Cursor 和任何能讀 Markdown 的 AI agent 用。

它會做的事：問診情境 → 讓你選結構或替你評「這個結構合不合適」 → 講稿（配速檢查）→ 投影片逐頁規劃（自動驗證）→ 135 分評量與處方 → 口語化編修（你勾選才改）→ 評審提問預測與備援頁 → 排練倒推時程。

它不做的事：不做投影片檔、不做美化、不替你編數字與出處。

## 安裝

Claude Code：clone 到 `~/.claude/skills/pitch-craft/`，開新對話就會自動觸發。

```bash
git clone https://github.com/matt-ye/pitch-craft.git ~/.claude/skills/pitch-craft
```

之後更新只要在該目錄 `git pull`。

Codex：`codex exec -C pitch-craft "讀取 ./SKILL.md，然後…（你的要求）"`。Cursor：放到 `~/.cursor/skills/pitch-craft/`。

腳本需要 Python 3（只用標準庫）。

## 怎麼用

直接說話就會命中，例如：

- 「幫我看這份稿，5 分鐘，評審是創投加教授，投影片最多 10 頁。」
- 「我的研究簡報 8 分鐘用 IMRD，評審是業界的人，這樣合適嗎？」
- 「3 分鐘英文自我推薦，爭取交換名額，這是我的重點，幫我寫並告訴我怎麼練。」
- 「只要評量不要改稿。」／「只要看結構。」

流程有四個檢查點會停下來問你，對了才往下。產出放在你材料旁邊的 `pitch-craft/` 資料夾，原檔不會被動。

腳本可以自己跑：

```bash
python scripts/timing_check.py 講稿_v1.md --limit-sec 300
python scripts/slide_plan_check.py 投影片規劃_v1.md --script 講稿_v1.md --limit-sec 300 --slide-limit 10
```

## 檔案

- `SKILL.md` 流程與規則
- `references/` 七份方法說明（結構、論證與故事、開場收尾與編修、投影片、評審與問答、評量表、排練與上台）＋ `SOURCES.md` 每個方法的出處
- `templates/` 各站要填的表
- `profiles/` 三種題目性質的預設值
- `scripts/` 配速檢查、投影片規劃驗證

## 出處與授權

方法整理自 Matt 的教學材料（職能治療、簡報表達、商業提案、學術寫作跨領域整理），引用他人框架處均在 `references/SOURCES.md` 標明出處；標「來源待補」的項目表示教材未載明原始出處，引用時請保留標記。

授權：[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-Hant)（姓名標示 Matt、非商業、相同方式分享），全文見 `LICENSE`。
