# pitch-craft 腳本

三支純標準庫 Python 腳本（在 Python 3.14 實測，語法上不依賴新版特性；Windows 與 macOS 皆可）。輸出為 markdown，直接印在畫面上，加 `--out 檔名` 可另存。每支都有 `--help`（繁體中文）。CLI 參數優先於 profile，profile 優先於檔案本身的「基本設定」。

## 1. timing_check.py：講稿配速

逐段估算口說秒數，對照計畫秒與總時限。輸入是「講稿模板」格式（基本設定表＋段落表）。
```
python scripts/timing_check.py 講稿.md --profile profiles/competition-pitch.md
python scripts/timing_check.py 講稿.md --limit-sec 180 --en-rate 100-110 --out 配速報告.md
python scripts/timing_check.py 講稿.md --write-back      # 把字數填回「字數」欄，其餘一字不動
```

- 計數：CJK 只算漢字（全形標點不算）；英文詞用 `[A-Za-z0-9'’-]+`。停頓記號、粗體記號、〔舞台指示〕先移除。
- 估時 = 漢字數／中文語速 + 詞數／英文語速，給「快～慢」兩個值；總結以中值判斷。
- 字數欄單位：中文＝字、英文＝詞，混合語言＝兩者相加。

## 2. slide_plan_check.py：投影片規劃驗證

逐項檢查規劃表，輸出 FAIL／WARN／PASS 三級清單（每條含頁碼與修正建議）；有 FAIL 時 exit code 為 1。
```
python scripts/slide_plan_check.py 規劃表.md --script 講稿.md --profile profiles/competition-pitch.md
python scripts/slide_plan_check.py 規劃表.md --slide-limit 10 --limit-sec 300
```

未給 `--script` 時，會把基本設定的「對應講稿」當成相對路徑嘗試解析；解析不到就略過講稿對應檢查。

## 3. export_student.py：學生版匯出

複製 skill 根目錄（排除 INTERNAL、evals、dist、__pycache__、.git、`*-workspace`），對複製結果做洩漏檢查，全部通過才搬到輸出位置。

```
python scripts/export_student.py --check-only      # 只檢查，不產出
python scripts/export_student.py                   # 產出到 dist/pitch-craft-student
python scripts/export_student.py --src <skill根目錄> --out <輸出資料夾>
```

檢查兩類：(a) 禁字掃描：.md／.py／.json 逐行比對個人知識庫路徑、wikilink 記號、審核狀態字樣、知識庫內部資料夾名（清單在腳本的 `FORBIDDEN` 常數）；(b) `references/SOURCES.md` 中「IP 分級」為「他人需標註」的列，「出處」不得空白或「未確認」。輸出位置已存在時，會先印出路徑再整個刪除。

## 門檻常數（改腳本開頭的常數即可）

| 常數 | 值 | 位置 |
|---|---|---|
| 段落超時 | 估時慢值 > 計畫秒 x 1.15 | timing_check |
| 單段太長 | 單段估時（中值）> 總時限 25% | timing_check |
| 建議目標 | 估時中值在時限的 90–95% | timing_check |
| 預設英文語速 | 100–110 wpm（最快不超過 140） | timing_check |
| 預設中文語速 | 180–200 字/分（目標；上限 240，Matt 定案） | timing_check |
| 標題句上限 | 中文 24 字／英文 14 詞 | slide_plan_check |
| 內容要點上限 | 3 點（以「；」或「;」切分） | slide_plan_check |
| 秒數加總容許 | 時限 ±10%（備援頁不計） | slide_plan_check |

## 已知限制

- 中文語速沒有可查證的來源，目前是預設區間，請錄音實測後用 `--zh-rate` 或 profile 覆蓋；英文 100–110 wpm 是非母語／時間壓力情境的建議值，母語者請用 profile 調整。
- 阿拉伯數字一律算一個英文詞，中文講稿裡的「65」會以英文語速估時，略有誤差。
- 標題句長度中英分開判斷（漢字數、詞數各自對上限），混合語言標題不會合併計算。
- 表格解析假設一列一行；儲存格內請用 `<br>` 換行，不要真的換行，也不要在儲存格內放未跳脫的 `|`（要寫成 `\|`）。
- 估時是排練用的近似值，不含停頓長度差異、投影片切換與互動時間；現場請預留餘裕。學生版禁字掃描只看 .md／.py／.json 的文字內容，不檢查圖片、PDF 或檔名。
