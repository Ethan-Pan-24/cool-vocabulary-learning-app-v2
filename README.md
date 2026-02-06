# Vocabulary Learning & Analytical System

這是一個專為語言學習設計的整合系統，包含單字管理、測驗功能、以及深度數據分析模組（學習效率與圖片參與度）。

## 🚀 功能特點

- **課程與單字管理**：支援多課程管理，可自定義單字故事、圖片及分組（A/B Testing）。
- **學習與測驗流程**：
    - 分階段學習模式，紀錄各階段停留時間。
    - 動態生成測驗，支援多選題與 AI 自動評分句子。
- **後台管理系統**：
    - **Dashboard**：即時查看所有使用者測驗結果。
    - **Teaching Efficiency (Paas 1993)**：分析學習表現與心智負荷（Mental Effort）的關係，自動生成 E-Scale 象限圖。
    - **Image Engagement Analytics**：統計圖片的點讚、倒讚與瀏覽次數，並進行分組統計檢定（Wilcoxon/Kruskal-Wallis）。
- **統計分析**：
    - 自動判別組別數量並選擇適當的檢定方法。
    - 自動生成盒鬚圖（Boxplot）與詳細統計數據。

## 🛠 核心技術

- **後端**：FastAPI (Python)
- **資料庫**：SQLAlchemy + SQLite
- **前端**：HTML5, CSS (Bootstrap 5), JavaScript (Vanilla)
- **數據分析**：Pandas, NumPy, SciPy, Matplotlib, Seaborn
- **AI 整合**：OpenAI API (GPT-4o) 用於句子評分

## 📦 安裝與啟動

1. **建立虛擬環境**：
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **安裝依賴套件**：
   ```bash
   pip install -r requirements.txt
   ```

3. **啟動伺服器**：
   ```bash
   python main.py
   ```
   伺服器將運行於 `http://127.0.0.1:8000`。

## 📁 專案架構

- `main.py`: 主程式進入點與路由。
- `admin_api.py`: 後台管理與數據分析接口。
- `database.py`: 資料庫模型定義。
- `utils.py`: 工具函數與 AI 評分邏輯。
- `templates/`: Jinja2 HTML 樣板。
- `static/`: 靜態資源（CSS, JS, Images）。

---

## 📅 開發者
*Antigravity AI Assistant*
