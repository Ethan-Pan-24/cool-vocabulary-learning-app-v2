from fastapi import APIRouter, Depends, HTTPException, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import get_db, User, Course, QuizResult, Vocabulary, Enrollment, ImageRating
from auth import get_current_user_req
from typing import List, Optional
import json
import numpy as np
import pandas as pd
from datetime import timedelta

router = APIRouter(prefix="/analytics")

@router.get("/", response_class=HTMLResponse)
async def analytics_home(request: Request, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    """
    分析報告主頁 - 顯示學習者已加入的課程列表
    """
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
    
    # 獲取用戶已加入的課程
    enrollments = db.query(Enrollment).filter(Enrollment.user_id == user.id).all()
    course_ids = [e.course_id for e in enrollments]
    courses = db.query(Course).filter(
        Course.id.in_(course_ids)
    ).all() if course_ids else []
    
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("analytics_home.html", {
        "request": request,
        "courses": courses,
        "user": user
    })

@router.get("/{course_id}", response_class=HTMLResponse)
async def course_analytics(
    course_id: int, 
    request: Request,
    user: User = Depends(get_current_user_req), 
    db: Session = Depends(get_db)
):
    """
    單個課程的完整分析報告
    包括：NASA-TLX 6項、統計圖、時間段分析、圖片評分
    """
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
    
    # 檢查用戶是否加入了該課程
    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == user.id,
        Enrollment.course_id == course_id
    ).first()
    
    if not enrollment and not user.is_admin and course.creator_id != user.id:
        raise HTTPException(status_code=403, detail="您未加入此課程")
    
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="課程不存在")
    
    # 獲取用戶的測驗結果
    results = db.query(QuizResult).filter(
        QuizResult.user_id == user.id,
        QuizResult.course_id == course_id,
        QuizResult.is_deleted == False
    ).order_by(QuizResult.submitted_at.asc()).all()
    
    # 處理 NASA-TLX 數據
    nasa_data = None
    if results:
        # Prefer latest result, but fallback to previous if missing NASA data
        target_result = results[-1]
        
        # Check if latest holds valid NASA data
        has_latest_nasa = False
        try:
             if target_result.nasa_details_json:
                 d = json.loads(target_result.nasa_details_json)
                 if d and any(d.values()): # Check if not empty/zero
                     has_latest_nasa = True
        except: pass
        
        if not has_latest_nasa:
            # Find last valid result
            for r in reversed(results):
                try:
                    if r.nasa_details_json:
                        d = json.loads(r.nasa_details_json)
                        if d and any(d.values()):
                            target_result = r
                            break
                except: continue

        try:
            nasa_details = json.loads(target_result.nasa_details_json) if target_result.nasa_details_json else {}
            nasa_data = {
                "mental": nasa_details.get("mental", 0),
                "physical": nasa_details.get("physical", 0),
                "temporal": nasa_details.get("temporal", 0),
                "performance": nasa_details.get("performance", 0),
                "effort": nasa_details.get("effort", 0),
                "frustration": nasa_details.get("frustration", 0)
            }
        except:
            nasa_data = None
    
    # 獲取課程的所有圖片（用於評分）
    vocab_list = db.query(Vocabulary).filter(
        Vocabulary.course_id == course_id,
        Vocabulary.is_deleted == False,
        Vocabulary.image_url != None,
        Vocabulary.image_url != ""
    ).all()
    # Determine Section Headers from Quiz Config
    section_headers = ["Translation", "Sentence"] # Default Legacy
    try:
        if course.quiz_config:
            q_config = json.loads(course.quiz_config)
            dynamic_sections = []
            for block in q_config:
                if block.get('block_type') in ['header', 'section_header', 'section']:
                    title = block.get('title') or block.get('content') or "Section"
                    if title not in dynamic_sections:
                        dynamic_sections.append(title)
            
            if dynamic_sections:
                section_headers = dynamic_sections
    except:
        pass

    # Process Results for Table
    processed_history = []
    for r in results:
        # Basic Info
        item = {
            "id": r.id,
            "attempt": r.attempt,
            "submitted_at": r.submitted_at.strftime('%Y-%m-%d %H:%M') if r.submitted_at else None,
            "total_score": (r.translation_score or 0) + (r.sentence_score or 0),
            "translation_score": r.translation_score, 
            "sentence_score": r.sentence_score,
            "nasa_tlx_score": r.nasa_tlx_score,
            "learning_duration": r.learning_duration_seconds or 0,
            "quiz_duration": 0,
            "section_scores": {}
        }
        
        # Calculate Quiz Duration from stage_timing_json
        try:
            if r.stage_timing_json:
                timings = json.loads(r.stage_timing_json)
                q_time = timings.get("Quiz", 0) + timings.get("Test Intro", 0) + timings.get("Quiz Intro", 0)
                item["quiz_duration"] = q_time
        except: pass
        
        # Parse Section Stats
        stats = {}
        try:
            if r.section_stats:
                stats = json.loads(r.section_stats)
        except: pass
        
        
        # Parse NASA Details
        nasa_details = {"mental": 0, "physical": 0, "temporal": 0, "performance": 0, "effort": 0, "frustration": 0}
        try:
            if r.nasa_details_json:
                details = json.loads(r.nasa_details_json)
                # Ensure all keys exist
                for key in nasa_details:
                     if key in details: nasa_details[key] = details[key]
        except: pass
        item["nasa_details"] = nasa_details

        # Map to Headers
        if stats:
            for h in section_headers:
                item["section_scores"][h] = stats.get(h, 0)
        else:
            # Legacy Fallback
            if len(section_headers) > 0:
                item["section_scores"][section_headers[0]] = r.translation_score or 0
                item["section_scores"][section_headers[1]] = r.sentence_score or 0
                
        # Ensure deep serialization safety
        # import json (Removed to fix UnboundLocalError)
        item = json.loads(json.dumps(item, default=str))
        processed_history.append(item)
    
    # Process results for chart and summary
    # attempts_data removed as requested
        
    latest_result = results[-1] if results else None
    
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    return templates.TemplateResponse("student_analytics.html", {
        "request": request,
        "course": course,
        "user": user,
        "results": results, # Keep for existing logic if any
        "processed_history": processed_history, # New List
        "section_headers": section_headers, # New Headers
        "latest_result": latest_result,
        "nasa_data": nasa_data,
        "vocab_list": vocab_list,
        "group": enrollment.group if enrollment else "Unknown"
    })

@router.get("/{course_id}/images")
async def get_course_images(
    course_id: int,
    user: User = Depends(get_current_user_req),
    db: Session = Depends(get_db)
):
    """
    獲取課程所有圖片及其評分狀態
    """
    if not user:
        raise HTTPException(status_code=401, detail="未登入")
    
    # 檢查權限
    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == user.id,
        Enrollment.course_id == course_id
    ).first()
    
    if not enrollment and not user.is_admin:
        raise HTTPException(status_code=403, detail="無權訪問")
    
    # 獲取課程詞彙及其圖片
    vocab_list = db.query(Vocabulary).filter(
        Vocabulary.course_id == course_id,
        Vocabulary.is_deleted == False
    ).all()
    
    # De-duplicate by word: keep latest ID
    unique_vocab = {}
    for v in vocab_list:
        if v.word:
             current = unique_vocab.get(v.word)
             if not current or v.id > current.id:
                 unique_vocab[v.word] = v
    
    vocab_list = list(unique_vocab.values())
    
    # 獲取用戶的評分記錄
    existing_ratings = db.query(ImageRating).filter(
        ImageRating.user_id == user.id,
        ImageRating.course_id == course_id
    ).all()
    
    rating_dict = {r.image_url: r.rating for r in existing_ratings}
    
    images_data = []
    for vocab in vocab_list:
        if vocab.image_url:
            images_data.append({
                "vocab_id": vocab.id,
                "word": vocab.word,
                "chinese_meaning": vocab.chinese_meaning,
                "image_url": vocab.image_url,
                "rating": rating_dict.get(vocab.image_url, 0),
                "context": "vocab"
            })
    
    return JSONResponse({"images": images_data})

@router.post("/{course_id}/rate_image")
async def rate_image(
    course_id: int,
    data: dict = Body(...),
    user: User = Depends(get_current_user_req),
    db: Session = Depends(get_db)
):
    """
    提交圖片評分
    data: {
        "image_url": str,
        "vocab_id": int,
        "rating": int (1/-1/0),
        "question_context": str
    }
    """
    if not user:
        raise HTTPException(status_code=401, detail="未登入")
    
    image_url = data.get("image_url")
    vocab_id = data.get("vocab_id")
    rating = data.get("rating", 0)
    question_context = data.get("question_context", "vocab")
    
    if not image_url:
        raise HTTPException(status_code=400, detail="缺少圖片 URL")
    
    # 檢查是否已有評分
    existing = db.query(ImageRating).filter(
        ImageRating.user_id == user.id,
        ImageRating.course_id == course_id,
        ImageRating.image_url == image_url
    ).first()
    
    if existing:
        # 更新評分
        existing.rating = rating
        existing.question_context = question_context
        from datetime import datetime
        existing.rated_at = datetime.utcnow()
    else:
        # 創建新評分
        new_rating = ImageRating(
            user_id=user.id,
            course_id=course_id,
            vocab_id=vocab_id,
            image_url=image_url,
            rating=rating,
            question_context=question_context
        )
        db.add(new_rating)
    
    db.commit()
    
    return JSONResponse({"status": "success", "message": "評分已保存"})

@router.get("/{course_id}/nasa_radar")
async def get_nasa_radar_data(
    course_id: int,
    user: User = Depends(get_current_user_req),
    db: Session = Depends(get_db)
):
    """
    獲取 NASA-TLX 雷達圖數據（6維）
    """
    if not user:
        raise HTTPException(status_code=401, detail="未登入")
    
    # 獲取最新的測驗結果
    result = db.query(QuizResult).filter(
        QuizResult.user_id == user.id,
        QuizResult.course_id == course_id,
        QuizResult.is_deleted == False
    ).order_by(QuizResult.submitted_at.desc()).first()
    
    if not result:
        return JSONResponse({"error": "無測驗記錄"})
    
    try:
        nasa_details = json.loads(result.nasa_details_json) if result.nasa_details_json else {}
        data = {
            "mental": nasa_details.get("mental", 0),
            "physical": nasa_details.get("physical", 0),
            "temporal": nasa_details.get("temporal", 0),
            "performance": nasa_details.get("performance", 0),
            "effort": nasa_details.get("effort", 0),
            "frustration": nasa_details.get("frustration", 0)
        }
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/{course_id}/stats")
def get_student_stats(
    course_id: int,
    target_attempt: int = None,
    user: User = Depends(get_current_user_req),
    db: Session = Depends(get_db)
):
    print(f"DEBUG: get_student_stats called for course {course_id}, user {user.id}, attempt {target_attempt}")
    """
    獲取學習者統計分析圖表（與管理員相同的分析，但標示當前用戶的數據點）
    """
    if not user:
        raise HTTPException(status_code=401, detail="未登入")
    
    # 檢查權限
    enrollment = db.query(Enrollment).filter(
        Enrollment.user_id == user.id,
        Enrollment.course_id == course_id
    ).first()
    
    if not enrollment and not user.is_admin:
        raise HTTPException(status_code=403, detail="無權訪問")
    
    import pandas as pd
    # import json (Removed to fix UnboundLocalError)
    from admin_api import perform_stats_and_plot
    
    # 獲取課程的所有enrollment和quiz results
    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    user_groups = {e.user_id: e.group for e in enrollments}
    
    query = db.query(QuizResult).filter(
        QuizResult.course_id == course_id, 
        QuizResult.is_deleted == False
    )
    if target_attempt is not None:
        query = query.filter(QuizResult.attempt == target_attempt)
        
    results = query.all()
    
    if not results:
        return {"msg": "No data for this course"}
    
    data = []
    dynamic_metrics = set()
    
    # Get course config
    course = db.query(Course).filter(Course.id == course_id).first()
    try:
        course_config = json.loads(course.stage_config) if course.stage_config else {}
    except:
        course_config = {}
    
    for r in results:
        # 獲取組別
        group = r.group
        if not group or group == "Unknown":
            group = user_groups.get(r.user_id, "Unknown")
        
        # Determine active stages
        if isinstance(course_config, list):
            active_stage_names = {s['name'] for s in course_config}
        else:
            active_stage_names = {s['name'] for s in course_config.get(group, course_config.get("Common", []))}
        
        # Calculate duration breakdown
        learning_time = 0
        quiz_time = 0
        try:
            timings = json.loads(r.stage_timing_json) if r.stage_timing_json else {}
            for k, v in timings.items():
                if k in active_stage_names:
                    learning_time += v
                elif k in ["Quiz", "Test Intro", "Quiz Intro"]:
                    quiz_time += v
            calculated_total = learning_time + quiz_time
        except:
            calculated_total = r.learning_duration_seconds
            learning_time = calculated_total
            quiz_time = 0
        
        row = {
            "user_id": r.user_id,  # 重要：添加 user_id
            "group": group,
            "nasa_tlx": r.nasa_tlx_score,
            "Total Duration": calculated_total,
            "Learning Duration": learning_time,
            "Quiz Duration": quiz_time
        }
        dynamic_metrics.update(["Total Duration", "Learning Duration", "Quiz Duration"])
        
        # Parse section stats
        try:
            sections = json.loads(r.section_stats) if r.section_stats else {}
            if not sections and r.translation_score:
                sections = {"Translation": r.translation_score}
            
            for k, v in sections.items():
                row[k] = v
                dynamic_metrics.add(k)
        except:
            pass
        
        # Parse NASA-TLX details (6維度)
        try:
            nasa_det = json.loads(r.nasa_details_json) if r.nasa_details_json else {}
            for k, v in nasa_det.items():
                metric_name = f"NASA: {k.capitalize()}"
                row[metric_name] = v
                dynamic_metrics.add(metric_name)
        except:
            pass
        
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # 分析所有指標
    metrics = sorted(list(dynamic_metrics))
    # 將特定指標排在最前
    priority = ["Quiz Duration", "Total Duration", "Learning Duration"]
    metrics = [m for m in priority if m in metrics] + [m for m in metrics if m not in priority]
    
    if not metrics:
        metrics = ["Total Duration", "nasa_tlx"]
    
    stats_results = {}
    plot_urls = {}
    interpretations = {}
    
    for m in metrics:
        if m not in df.columns:
            continue
        
        valid_df = df.dropna(subset=[m])
        
        try:
            # Determine title prefix: "Score Comparison" or "Time Comparison"
            title_prefix = "Time Comparison" if "Duration" in m or "Time" in m else "Score Comparison"
            
            res = perform_stats_and_plot(
                valid_df, 
                m, 
                'group', 
                f"{title_prefix}: {m}", 
                highlight_user_id=user.id  # 標示當前用戶
            )
            
            if "error" in res:
                interpretations[m] = f"Unable to perform analysis: {res['error']}"
                continue
            
            stats_results[m] = res["stats"]
            plot_urls[m] = res["plot"]
            
            p = res["stats"]["p_value"]
            test = res["stats"]["test"]
            sig = "Significant difference" if p < 0.05 else "No significant difference"
            interpretations[m] = f"Method: {test}. Result: {sig} (p={p:.4f})."
            
        except Exception as e:
            interpretations[m] = f"分析錯誤：{str(e)}"
    
    return {"stats": stats_results, "plots": plot_urls, "interpretations": interpretations}


@router.get("/{course_id}/time_series_stats")
async def get_student_time_series_stats(
    course_id: int, 
    attempts: str = None, 
    user: User = Depends(get_current_user_req), 
    db: Session = Depends(get_db)
):
    # Check enrollment
    enrollment = db.query(Enrollment).filter(Enrollment.user_id == user.id, Enrollment.course_id == course_id).first()
    if not enrollment:
        raise HTTPException(403, "Not enrolled")
        
    results = db.query(QuizResult).filter(QuizResult.course_id == course_id, QuizResult.is_deleted == False).all()
    if not results:
        return {"msg": "No data available"}
    
    import pandas as pd
    # import json (Removed to fix UnboundLocalError)
    from collections import defaultdict
    from admin_api import perform_friedman_plot # Local import

    # Parse desired attempts
    target_attempts = []
    if attempts:
        try:
            target_attempts = [int(a) for a in attempts.split(",") if a.strip().isdigit()]
        except: pass
    
    # Data Collector
    section_data = defaultdict(list)
    available_attempts = set()
    
    for r in results:
        available_attempts.add(r.attempt)
        
        if target_attempts and r.attempt not in target_attempts:
            continue
            
        time_label = f"Test {r.attempt}"
        
        try:
            sections = json.loads(r.section_stats) if r.section_stats else {}
        except:
            sections = {}
            
        if not sections:
            total = (r.translation_score or 0) + (r.sentence_score or 0)
            sections = {"Total Score": total}
            
        for sec_name, score in sections.items():
            section_data[sec_name].append({
                "user_id": r.user_id,
                "Time": time_label,
                "Score": score
            })

        # Add Durations
        durations = {
            "Total Duration": r.learning_duration_seconds or 0,
            "Learning Duration": 0,
            "Quiz Duration": 0
        }
        try:
            if r.stage_timing_json:
                timings = json.loads(r.stage_timing_json)
                q_time = timings.get("Quiz", 0) + timings.get("Test Intro", 0) + timings.get("Quiz Intro", 0)
                durations["Quiz Duration"] = q_time
                durations["Learning Duration"] = (r.learning_duration_seconds or 0) - q_time
        except: 
            durations["Learning Duration"] = r.learning_duration_seconds or 0

        for d_name, d_val in durations.items():
            section_data[d_name].append({
                "user_id": r.user_id,
                "Time": time_label,
                "Score": d_val
            })

    if not section_data:
         return {
             "msg": "No data found for selected attempts",
             "available_attempts": sorted(list(available_attempts))
         }
    
    final_output = {
        "sections": [],
        "available_attempts": sorted(list(available_attempts))
    }
    
    for sec_name, data_list in section_data.items():
        if not data_list: continue
        
        df = pd.DataFrame(data_list)
        
        # Determine title prefix: "Score Comparison" or "Time Comparison"
        title_prefix = "Time Comparison" if "Duration" in sec_name or "Time" in sec_name else "Score Comparison"
        
        res = perform_friedman_plot(df, "Score", "Time", "user_id", f"{title_prefix}: {sec_name}")
        
        if "error" not in res:
            final_output["sections"].append({
                "name": sec_name,
                "plot": res["plot"],
                "stats": res["stats"],
                "table_data": res.get("table_data", [])
            })
            
    if not final_output["sections"]:
        return {"msg": "Insufficient data"}
        
    return final_output


@router.get("/{course_id}/efficiency_plot")
async def get_student_efficiency_plot(
    course_id: int, 
    target_attempt: int = None,
    user: User = Depends(get_current_user_req), 
    db: Session = Depends(get_db)
):
    from admin_api import get_user_efficiency_plot
    return await get_user_efficiency_plot(course_id=course_id, user_id=user.id, target_attempt=target_attempt, db=db)

