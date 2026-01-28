# Changelog
此文件記錄 CSI Portal 專案的所有重大變更。

## [1.1.0] - 2026-01-28
### Added
* 實作智能客服懸浮視窗，支援 Markdown 語法渲染。
* 新增 `AISystemSetting` 後台資料表，支援動態調整 AI 系統指令。
* 導入 `concurrent-log-handler` 解決 Windows 環境下的日誌檔案鎖定問題。

### Changed
* 升級 AI 引擎至 **Gemini 3 Flash** (使用 `gemini-flash-latest` 別名)。
* 程式統一專案註解規範：Python 使用 `#!`，JavaScript 使用 `//`。

## [1.0.0] - 2026-01-21
### Added
* CSI Portal 入口網基礎架構建置。