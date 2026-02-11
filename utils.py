from openai import OpenAI
from dotenv import load_dotenv
import requests
import os
import base64
import json

load_dotenv() # Load variables from .env

# API Configuration
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = "https://chat.otlab.org/api"
MODEL = "gemma3:4b"

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

ADMIN_EMAILS = ["panyihao24@gmail.com", "390010@fhsh.khc.edu.tw"]

def encode_image(image_source):
    """Encodes an image (local or URL) to base64."""
    try:
        # If it's a web URL, download it first
        if image_source.startswith("http"):
            resp = requests.get(image_source, timeout=10)
            if resp.status_code == 200:
                return base64.b64encode(resp.content).decode('utf-8')
            return None

        # Resolve path relative to current app directory
        image_path = image_source
        if not os.path.isabs(image_path):
             # Try common locations
             for prefix in ["", "static", "."]:
                 test_path = os.path.join(os.getcwd(), prefix, image_path.lstrip("/"))
                 if os.path.exists(test_path):
                     image_path = test_path
                     break
        
        if os.path.exists(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        return None
    except Exception as e:
        print(f"Error encoding image {image_source}: {e}")
        return None

import re

def extract_json(text):
    """Aggressively extracts and repairs JSON from LLM output."""
    if not text: return None
    
    # Try simple json.loads first on the whole text
    try:
        return json.loads(text.strip())
    except:
        pass

    try:
        # Step 1: Find valid JSON block { ... }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            candidate = text[start:end+1]
            # Fix trailing commas
            candidate = re.sub(r',\s*([\}\]])', r'\1', candidate)
            try:
                return json.loads(candidate)
            except:
                pass
        
        # Step 2: Fallback to Regex extraction for key fields
        result = {}
        for key in ["semantic_depth", "collocation", "grammar", "image_relevance"]:
            # Match "key": 4.5 or key: 4.5
            val_match = re.search(rf'"{key}"\s*:\s*([\d\.]+)', text, re.I)
            if not val_match: val_match = re.search(rf'{key}\s*:\s*([\d\.]+)', text, re.I)
            if val_match:
                try: 
                    # --- CRITICAL: HARD CLAMP 0-5 ---
                    val = float(val_match.group(1))
                    result[key] = max(0, min(5, val))
                except: 
                    result[key] = 0
        
        # Extract comment (Robust)
        # Match "comment": "..." OR 'comment': '...' OR key: "..."
        comm_match = re.search(r'["\']?comment["\']?\s*:\s*(["\'])(.*?)\1', text, re.S | re.IGNORECASE)
        if comm_match:
            result["comment"] = comm_match.group(2).replace('\\"', '"')
        else:
            result["comment"] = "評分已由系統自動校正(無法讀取AI評語)。"

        if any(k in result for k in ["semantic_depth", "collocation", "grammar", "image_relevance"]):
            return result
            
        return None
    except Exception as e:
        print(f"JSON Parsing Error: {e}")
        return None

def score_sentence_ai(word: str, sentence: str, story: str = "", chinese_meaning: str = "", image_url: str = None) -> dict:
    """
    Uses the AI model to score a sentence. 
    Strict 0-5 scale. Nonsensical Collocations (e.g., lament apple) = 0 points.
    """
    
    # --- Input Validation: Return 0 for invalid inputs ---
    if not sentence or not sentence.strip():
        return {
            "semantic_depth": 0, "collocation": 0, "grammar": 0, "image_relevance": 0,
            "total_average": 0,
            "comment": "未提交任何句子。"
        }
    
    # Check if sentence is only whitespace
    if sentence.strip() == "":
        return {
            "semantic_depth": 0, "collocation": 0, "grammar": 0, "image_relevance": 0,
            "total_average": 0,
            "comment": "句子僅包含空格，無有效內容。"
        }
    
    # Check if sentence contains only Chinese characters (no English)
    import unicodedata
    has_english = any('a' <= c.lower() <= 'z' for c in sentence)
    has_chinese = any('\u4e00' <= c <= '\u9fff' for c in sentence)
    
    if has_chinese and not has_english:
        return {
            "semantic_depth": 0, "collocation": 0, "grammar": 0, "image_relevance": 0,
            "total_average": 0,
            "comment": "句子僅包含中文，請使用英文造句。"
        }
    
    # --- Local Pre-Check for Target Word ---
    clean_word = re.sub(r'[^\w]', '', word.lower())
    clean_sentence = re.sub(r'[^\w]', ' ', sentence.lower())
    words_in_sentence = clean_sentence.split()
    word_found = any(clean_word == w for w in words_in_sentence)
    if not word_found:
        word_found = clean_word in clean_sentence.replace(" ", "")
    
    prompt_text = f"""
    擔任【極其嚴格】的英語考官。全程使用「繁體中文」評分。
    
    【評分資料】
    單字: {word} (意義: {chinese_meaning})
    情境: {story}
    學生造句: {sentence}

    【評分量表: 0.0 ~ 5.0 (絕對嚴禁超過 5 分)】
    - 5.0: Native-like, 完美且具深度。
    - 3.0: 正確但平庸(簡單句)。
    - 1.0: 語法或語意有重大瑕疵。
    - 0.0: 胡言亂語、未包含單字、或邏輯錯誤。

    【核心審核 (如有下列情況，給予基礎分以資鼓勵)】: 
    1. 邏輯與搭配錯誤: 即使單字詞性誤用或語意不合邏輯，但若有基本主謂結構，請給予 0.5 - 1.0 分以資鼓勵。
    2. 幻想物件 (關鍵): 如果造句中提到了「圖片中完全不存在」的具體物件，該物件相關的 Relevance 分數必須大幅扣分。不得憑空想像圖中沒有的東西。
    3. 簡單敷衍: 像「He felt {word}.」這種極短句，最高總分不得超過 2.5。
    4. 評語要求: 評語應針對學生的「實際造句」給予具體建議，禁止提及指令中出現的舉例內容。

    請輸出 JSON (數值範圍 0-5)：
    {{
        "semantic_depth": 0-5,
        "collocation": 0-5,
        "grammar": 0-5,
        "image_relevance": 0-5,
        "comment": "繁體中文評語（若有建議句，請使用『全英文』呈現該句子）。請勿使用換行符號。"
    }}
    """

    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": prompt_text}
        ]}
    ]

    if image_url:
        base64_image = encode_image(image_url)
        if base64_image:
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

    try:
        print(f"--- AI Request: '{word}' | Sentence: '{sentence}' ---")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=600 
        )
        content = response.choices[0].message.content
        print(f"AI Raw Response: {content}")
        
        result = extract_json(content)
        if not result:
            raise ValueError(f"Invalid AI response format")
            
        # Word missing override
        if not word_found:
            has_points = any(result.get(k,0) > 0 for k in ["semantic_depth", "collocation", "grammar", "image_relevance"])
            if has_points:
                return {
                    "semantic_depth": 0, "collocation": 0, "grammar": 0, "image_relevance": 0,
                    "total_average": 0,
                    "comment": f"造句中未包含目標單字『{word}』。"
                }

        scores = [
            result.get("semantic_depth", 0),
            result.get("collocation", 0),
            result.get("grammar", 0),
            result.get("image_relevance", 0)
        ]
        
        # Priority: AI's total_score if available, else average of components
        ai_total = result.get("total_score")
        if ai_total is not None and ai_total > 0:
            result["total_average"] = round(ai_total, 2)
        else:
            result["total_average"] = round(sum(scores) / len(scores), 2) if scores else 0
            
        return result
    except Exception as e:
        print(f"AI Error: {e}")
        return {
            "semantic_depth": 0, "collocation": 0, "grammar": 0, "image_relevance": 0,
            "total_average": 0,
            "comment": f"評分失敗: {str(e)}"
        }
