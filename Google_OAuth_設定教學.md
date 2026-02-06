# Google OAuth 設定完整教學

## 📋 目錄
1. [創建 Google Cloud 專案](#1-創建-google-cloud-專案)
2. [啟用 Google+ API](#2-啟用-google-api)
3. [建立 OAuth 同意畫面](#3-建立-oauth-同意畫面)
4. [創建 OAuth 2.0 憑證](#4-創建-oauth-20-憑證)
5. [配置應用程式](#5-配置應用程式)

---

## 1. 創建 Google Cloud 專案

### 步驟 1.1：前往 Google Cloud Console
👉 開啟瀏覽器，前往：https://console.cloud.google.com/

### 步驟 1.2：登入 Google 帳號
- 使用你的 Google 帳號登入

### 步驟 1.3：創建新專案
1. 點擊頂部導航欄的 **「選取專案」** 下拉選單
2. 點擊 **「新增專案」** (NEW PROJECT)
3. 填寫專案資訊：
   - **專案名稱**：例如 `Vocabulary Learning App`
   - **組織**：可選，個人使用可以留空
4. 點擊 **「建立」** (CREATE)
5. 等待專案創建完成（約 10-30 秒）

---

## 2. 啟用 Google+ API

### 步驟 2.1：開啟 API 程式庫
1. 確認已選擇剛創建的專案
2. 在左側選單中，點擊 **「API 和服務」** → **「程式庫」** (Library)

### 步驟 2.2：搜尋並啟用 API
1. 在搜尋框中輸入：`Google+ API` 或 `People API`
2. 點擊 **「Google+ API」** 或 **「Google People API」**
3. 點擊 **「啟用」** (ENABLE) 按鈕

---

## 3. 建立 OAuth 同意畫面

### 步驟 3.1：前往 OAuth 同意畫面設定
1. 在左側選單中，點擊 **「API 和服務」** → **「OAuth 同意畫面」**

### 步驟 3.2：選擇使用者類型
- **外部 (External)**：任何 Google 帳號都可以登入（建議選擇）
- **內部 (Internal)**：僅限組織內的使用者

選擇 **「外部」**，然後點擊 **「建立」**

### 步驟 3.3：填寫應用程式資訊

#### 第 1 頁：OAuth 同意畫面
填寫以下必填欄位：
- **應用程式名稱**：`Vocabulary Learning App`（使用者會看到的名稱）
- **使用者支援電子郵件**：選擇你的 Google 電子郵件
- **應用程式標誌**：可選
- **應用程式首頁**：`https://lab-i7-ethan-test.hat-and-cat.cc/`
- **應用程式隱私權政策連結**：可選（測試階段可跳過）
- **應用程式服務條款連結**：可選（測試階段可跳過）
- **已授權網域**：
  - 點擊 **「新增網域」**
  - 輸入：`hat-and-cat.cc`
- **開發人員聯絡資訊**：填寫你的電子郵件

點擊 **「儲存並繼續」**

#### 第 2 頁：範圍 (Scopes)
1. 點擊 **「新增或移除範圍」**
2. 選擇以下範圍：
   - `openid`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
3. 點擊 **「更新」**
4. 點擊 **「儲存並繼續」**

#### 第 3 頁：測試使用者（如果是外部應用程式）
- 在開發階段，可以新增測試使用者的電子郵件
- 點擊 **「+ADD USERS」**
- 輸入測試使用者的 Gmail 地址（例如你自己的信箱）
- 點擊 **「儲存並繼續」**

#### 第 4 頁：摘要
- 檢查所有設定
- 點擊 **「返回資訊主頁」**

---

## 4. 創建 OAuth 2.0 憑證

### 步驟 4.1：前往憑證頁面
1. 在左側選單中，點擊 **「API 和服務」** → **「憑證」** (Credentials)

### 步驟 4.2：建立 OAuth 2.0 用戶端 ID
1. 點擊頂部的 **「+ 建立憑證」** (CREATE CREDENTIALS)
2. 選擇 **「OAuth 2.0 用戶端 ID」**

### 步驟 4.3：配置 OAuth 用戶端
1. **應用程式類型**：選擇 **「網頁應用程式」** (Web application)
2. **名稱**：輸入 `Vocabulary App Web Client`

#### 設定已授權的 JavaScript 來源
點擊 **「+ 新增 URI」**，依序新增：
```
https://lab-i7-ethan-test.hat-and-cat.cc
```

如果需要本地開發，也可以加入：
```
http://localhost:8000
http://127.0.0.1:8000
```

#### ⚠️ 重要：設定已授權的重新導向 URI
這是 **最關鍵** 的步驟！點擊 **「+ 新增 URI」**，依序新增：

**生產環境（必填）：**
```
https://lab-i7-ethan-test.hat-and-cat.cc/auth/google
```

**本地開發（選填）：**
```
http://localhost:8000/auth/google
http://127.0.0.1:8000/auth/google
```

> 💡 **說明**：`/auth/google` 是你的應用程式中處理 Google OAuth 回調的路徑，在 `main.py` 的第 46 行定義。

3. 點擊 **「建立」** (CREATE)

### 步驟 4.4：保存憑證
創建完成後，會彈出一個視窗顯示：
- **用戶端編號** (Client ID)：一串長字串，類似 `123456789-abcdefg.apps.googleusercontent.com`
- **用戶端密碼** (Client Secret)：一串隨機字串

**⚠️ 重要**：
- 點擊 **「下載 JSON」** 按鈕備份（建議）
- 或者手動複製並保存這兩個值

---

## 5. 配置應用程式

### 步驟 5.1：編輯 .env 檔案

在你的專案目錄中，找到或創建 `.env` 檔案：

```bash
cd /home/ethan/cool-vocabulary-learning-app-v2
nano .env
```

### 步驟 5.2：填入 OAuth 憑證

將以下內容貼到 `.env` 檔案中，並替換掉實際的值：

```env
# Google OAuth 憑證
GOOGLE_CLIENT_ID=你的用戶端編號.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=你的用戶端密碼

# OpenAI API Key（用於句子評分）
OPENAI_API_KEY=你的_openai_api_key

# Session 密鑰（自己生成一個隨機字串）
SESSION_SECRET_KEY=your_random_secret_key_here_min_32_chars
```

### 步驟 5.3：生成 Session Secret Key

可以用以下 Python 命令生成一個安全的隨機密鑰：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

複製輸出的字串，貼到 `SESSION_SECRET_KEY=` 後面。

### 步驟 5.4：保存檔案
- 按 `Ctrl + O` 儲存
- 按 `Enter` 確認
- 按 `Ctrl + X` 退出

---

## ✅ 驗證設定

### 測試 OAuth 登入流程

1. **啟動應用程式**：
   ```bash
   conda activate vocab-app
   python main.py
   ```

2. **開啟瀏覽器**，前往：
   ```
   https://lab-i7-ethan-test.hat-and-cat.cc/
   ```

3. **點擊 "Login with Google" 按鈕**

4. **預期流程**：
   - 跳轉到 Google 登入頁面
   - 選擇或輸入你的 Google 帳號
   - Google 顯示授權同意畫面，列出應用程式要求的權限
   - 點擊「允許」
   - 自動跳轉回你的應用程式（`/auth/google` 路徑）
   - 成功登入後進入課程頁面

---

## 🔧 常見問題排解

### ❌ 錯誤：redirect_uri_mismatch

**問題**：
```
Error 400: redirect_uri_mismatch
The redirect URI in the request: https://lab-i7-ethan-test.hat-and-cat.cc/auth/google 
does not match the ones authorized for the OAuth client.
```

**解決方法**：
1. 確認 Google Cloud Console 中的「已授權的重新導向 URI」完全一致
2. 注意以下細節：
   - 確保包含 `https://`
   - 確保沒有多餘的斜線 `/`
   - 路徑必須是 `/auth/google`
3. 修改後需要等待 5-10 分鐘生效

### ❌ 錯誤：Access blocked: This app's request is invalid

**原因**：OAuth 同意畫面設定不完整

**解決方法**：
1. 回到 Google Cloud Console
2. 檢查「OAuth 同意畫面」設定
3. 確保已填寫「已授權網域」：`hat-and-cat.cc`
4. 確保應用程式狀態不是「已停用」

### ❌ 錯誤：Origin not allowed

**原因**：JavaScript 來源未授權

**解決方法**：
1. 在憑證設定中的「已授權的 JavaScript 來源」
2. 新增：`https://lab-i7-ethan-test.hat-and-cat.cc`

### ⚠️ 應用程式處於測試模式

如果你的應用程式顯示「此應用程式未經驗證」：
- **開發階段**：這是正常的，點擊「進階」→「前往（不安全）」即可
- **正式上線**：需要向 Google 申請驗證（需要隱私權政策等文件）

---

## 📚 相關資源

- **Google Cloud Console**：https://console.cloud.google.com/
- **OAuth 2.0 文件**：https://developers.google.com/identity/protocols/oauth2
- **專案程式碼**：[main.py](file:///home/ethan/cool-vocabulary-learning-app-v2/main.py) (第 29-44 行)

---

## 📝 設定清單

完成後請確認：
- [ ] Google Cloud 專案已創建
- [ ] OAuth 同意畫面已設定
- [ ] OAuth 2.0 用戶端 ID 已創建
- [ ] 已授權的重新導向 URI 已正確設定為：`https://lab-i7-ethan-test.hat-and-cat.cc/auth/google`
- [ ] Client ID 和 Client Secret 已複製到 `.env` 檔案
- [ ] Session Secret Key 已生成並填入
- [ ] 測試登入流程成功

---

🎉 **完成！現在你的應用程式可以使用 Google OAuth 登入了！**
