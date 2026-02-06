from fastapi import APIRouter, Depends, Form, Request, HTTPException, UploadFile, File, Body
from typing import List, Optional
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from database import get_db, Vocabulary, User, QuizResult, Course, Enrollment, ImageInteraction
from utils import score_sentence_ai, ADMIN_EMAILS
from auth import get_current_user_req
import io
import base64
import shutil
import os

router = APIRouter(prefix="/admin_api")

@router.post("/upload_media")
async def upload_media(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file or not file.filename:
        return {"status": "error", "msg": "No file uploaded"}
        
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._- ")
    import time
    filename = f"{int(time.time())}_{safe_filename}"
    # Ensure directory
    if not os.path.exists("static/images"):
        os.makedirs("static/images")
        
    filepath = os.path.join("static/images", filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    url = f"/static/images/{filename}"
    return {"status": "success", "url": url}


@router.post("/create_course")
async def create_course(name: str = Form(...), description: str = Form(""), groups: str = Form("A,B"), quiz_time_limit: int = Form(5), db: Session = Depends(get_db)):
    # Validate groups format
    group_list = [g.strip() for g in groups.split(",") if g.strip()]
    cleaned_groups = ",".join(group_list)
    
    new_course = Course(name=name, description=description, group_names=cleaned_groups, quiz_time_limit=quiz_time_limit)
    db.add(new_course)
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/update_course/{course_id}")
async def update_course(course_id: int, name: str = Form(...), description: str = Form(""), groups: str = Form(""), quiz_time_limit: int = Form(5), redirect_to: str = Form(None), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        # Validate groups logic similar to create
        group_list = [g.strip() for g in groups.split(",") if g.strip()]
        cleaned_groups = ",".join(group_list)
        
        course.name = name
        course.description = description
        course.group_names = cleaned_groups
        course.quiz_time_limit = quiz_time_limit
        db.commit()
    
    if redirect_to == "content_manager":
        return RedirectResponse(url=f"/admin/course/{course_id}/content_manager", status_code=303)
    if redirect_to:
        return RedirectResponse(url=redirect_to, status_code=303)
    return RedirectResponse(url=f"/admin/course/{course_id}", status_code=303)

@router.post("/update_course_stages/{course_id}")
async def update_course_stages(
    course_id: int, 
    stage_config: str = Form("[]"), 
    target_group: str = Form(None), # Optional: if set, only update this group's key
    redirect_to: str = Form(None), 
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        import json
        new_stages = json.loads(stage_config)
        
        if target_group:
            # Merging Logic
            current_config = {}
            try:
                raw = json.loads(course.stage_config) if course.stage_config else {}
                if isinstance(raw, list):
                    # Migration: If it was a list, assume it was "Common" or migration base
                    current_config = {"Common": raw}
                elif isinstance(raw, dict):
                    current_config = raw
            except:
                current_config = {}
            
            # Update specific group
            current_config[target_group] = new_stages
            course.stage_config = json.dumps(current_config)
        else:
            # Legacy/Full Overwrite mode
            course.stage_config = stage_config
            
        db.commit()
    
    if redirect_to == "content_manager":
         return RedirectResponse(url=f"/admin/course/{course_id}/content_manager", status_code=303)
    return RedirectResponse(url=f"/admin/course/{course_id}", status_code=303)


@router.post("/rename_group")
async def rename_group(
    course_id: int = Form(...),
    old_name: str = Form(...),
    new_name: str = Form(...),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # 1. Update Course.group_names
    if course.group_names:
        groups = [g.strip() for g in course.group_names.split(",") if g.strip()]
        if old_name in groups:
            groups = [new_name if g == old_name else g for g in groups]
            course.group_names = ",".join(groups)

    # 2. Update Stage Config Keys
    if course.stage_config:
        import json
        try:
            config = json.loads(course.stage_config)
            if isinstance(config, dict):
                if old_name in config:
                    config[new_name] = config.pop(old_name)
                    course.stage_config = json.dumps(config)
        except:
            pass # Handle json error gracefully

    # 3. Update Vocabulary
    db.query(Vocabulary).filter(Vocabulary.course_id == course_id, Vocabulary.group == old_name).update({Vocabulary.group: new_name}, synchronize_session=False)

    # 4. Update Enrollments
    db.query(Enrollment).filter(Enrollment.course_id == course_id, Enrollment.group == old_name).update({Enrollment.group: new_name}, synchronize_session=False)

    db.commit()
    return {"status": "success", "new_name": new_name}

@router.post("/add_group")
async def add_group(
    course_id: int = Form(...),
    group_name: str = Form(...),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    current_groups = [g.strip() for g in (course.group_names or "").split(",") if g.strip()]
    if group_name not in current_groups:
        current_groups.append(group_name)
        course.group_names = ",".join(current_groups)
        db.commit()
        return {"status": "success", "new_group": group_name}
    return {"status": "error", "msg": "Group already exists"}

@router.post("/delete_group")
async def delete_group(
    course_id: int = Form(...),
    group_name: str = Form(...),
    db: Session = Depends(get_db)
):
    group_name = group_name.strip()
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # 1. Update Course.group_names
    current_groups = [g.strip() for g in (course.group_names or "").split(",") if g.strip()]
    if group_name in current_groups:
        current_groups.remove(group_name)
        course.group_names = ",".join(current_groups)
        
    # 2. Update Stage Config
    if course.stage_config:
        import json
        try:
            config = json.loads(course.stage_config)
            if isinstance(config, dict) and group_name in config:
                del config[group_name]
                course.stage_config = json.dumps(config)
        except:
            pass

    # 3. Clean up Vocab/Enrollment?
    # Requirement: "orphaned" is acceptable for now.
    
    db.commit()
    return {"status": "success"}

@router.post("/delete_stage")
async def delete_stage(
    course_id: int = Form(...),
    group_name: str = Form(...),
    stage_name: str = Form(...),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    if course.stage_config:
        import json
        try:
            config = json.loads(course.stage_config)
            if isinstance(config, dict) and group_name in config:
                # Filter out the stage
                config[group_name] = [s for s in config[group_name] if s.get('name') != stage_name]
                course.stage_config = json.dumps(config)
                db.commit()
        except Exception as e:
            return {"status": "error", "msg": str(e)}

    return {"status": "success"}


@router.post("/add_word")
async def add_word(
    word: str = Form(...), 
    chinese: str = Form(...), 
    story: str = Form(...), 
    image: str = Form(""), 
    group: str = Form("Common"), 
    stage: str = Form("Unassigned"),
    course_id: int = Form(...),
    display_order: int = Form(0),
    audio_file: UploadFile = File(None),
    image_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    audio_url = ""
    if audio_file and audio_file.filename:
        # Sanitize filename
        safe_filename = "".join(c for c in audio_file.filename if c.isalnum() or c in "._- ")
        filename = f"audio_{word}_{safe_filename}"
        filepath = os.path.join("static/audio", filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        audio_url = f"/static/audio/{filename}"

    image_url = image
    if image_file and image_file.filename:
        safe_filename = "".join(c for c in image_file.filename if c.isalnum() or c in "._- ")
        filename = f"image_{word}_{safe_filename}"
        # Ensure static/images exists or just put in static?
        if not os.path.exists("static/images"):
            os.makedirs("static/images")
        filepath = os.path.join("static/images", filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)
        image_url = f"/static/images/{filename}"

    new_vocab = Vocabulary(
        word=word, 
        chinese_meaning=chinese, 
        story=story, 
        image_url=image_url, 
        group=group, 
        stage=stage,
        course_id=course_id,
        audio_url=audio_url,

        display_order=display_order
    )
    db.add(new_vocab)
    db.commit()
    # Always redirect to Content Manager now as it is the primary interface
    return RedirectResponse(url=f"/admin/course/{course_id}/content_manager", status_code=303)

@router.post("/delete_vocab/{vocab_id}")
async def delete_vocab(vocab_id: int, db: Session = Depends(get_db)):
    vocab = db.query(Vocabulary).filter(Vocabulary.id == vocab_id).first()
    if vocab:
        # Soft Delete
        vocab.is_deleted = True
        db.commit()
    return {"status": "success", "msg": "Vocabulary deleted"}

@router.post("/delete_vocab_batch")
async def delete_vocab_batch(ids: List[int] = Body(...), db: Session = Depends(get_db)):
    # Soft Delete Batch
    db.query(Vocabulary).filter(Vocabulary.id.in_(ids)).update({Vocabulary.is_deleted: True}, synchronize_session=False)
    db.commit()
    return {"status": "success", "msg": f"{len(ids)} items deleted"}

@router.post("/restore_vocab/{vocab_id}")
async def restore_vocab(vocab_id: int, db: Session = Depends(get_db)):
    vocab = db.query(Vocabulary).filter(Vocabulary.id == vocab_id).first()
    if vocab:
        # Restore
        vocab.is_deleted = False
        db.commit()
    return {"status": "success", "msg": "Vocabulary restored"}

@router.post("/restore_vocab_batch")
async def restore_vocab_batch(ids: List[int] = Body(...), db: Session = Depends(get_db)):
    # Restore Batch
    db.query(Vocabulary).filter(Vocabulary.id.in_(ids)).update({Vocabulary.is_deleted: False}, synchronize_session=False)
    db.commit()
    return {"status": "success", "msg": f"{len(ids)} items restored"}

@router.get("/get_trash/{course_id}")
async def get_trash(course_id: int, db: Session = Depends(get_db)):
    deleted_items = db.query(Vocabulary).filter(
        Vocabulary.course_id == course_id,
        Vocabulary.is_deleted == True
    ).all()
    
    return {
        "status": "success",
        "items": [
            {
                "id": v.id,
                "word": v.word,
                "chinese_meaning": v.chinese_meaning,
                "group": v.group,
                "stage": v.stage
            } for v in deleted_items
        ]
    }

@router.post("/permanent_delete_vocab/{vocab_id}")
async def permanent_delete_vocab(vocab_id: int, db: Session = Depends(get_db)):
    vocab = db.query(Vocabulary).filter(Vocabulary.id == vocab_id).first()
    if vocab:
        db.delete(vocab)
        db.commit()
    return {"status": "success", "msg": "Permanently deleted"}

@router.post("/empty_trash/{course_id}")
async def empty_trash(course_id: int, db: Session = Depends(get_db)):
    db.query(Vocabulary).filter(
        Vocabulary.course_id == course_id,
        Vocabulary.is_deleted == True
    ).delete(synchronize_session=False)
    db.commit()
    return {"status": "success", "msg": "Trash emptied"}

@router.post("/update_vocab/{vocab_id}")
async def update_vocab(
    vocab_id: int,
    word: str = Form(...), 
    chinese: str = Form(...), 
    story: str = Form(...), 
    image: str = Form(""), 
    group: str = Form("Common"), 
    stage: str = Form("Unassigned"),
    course_id: int = Form(...),

    display_order: int = Form(0),

    audio_file: UploadFile = File(None),
    image_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    vocab = db.query(Vocabulary).filter(Vocabulary.id == vocab_id).first()
    if not vocab:
        return RedirectResponse(url="/admin?error=VocabNotFound&tab=content", status_code=303)

    vocab.word = word
    vocab.chinese_meaning = chinese
    vocab.story = story
    vocab.group = group
    vocab.stage = stage
    vocab.course_id = course_id
    vocab.course_id = course_id
    vocab.display_order = display_order
    # vocab.custom_distractors = distractors # Managed separately now
    
    if image:
        vocab.image_url = image
        
    if image_file and image_file.filename:
        safe_filename = "".join(c for c in image_file.filename if c.isalnum() or c in "._- ")
        filename = f"image_{vocab_id}_{safe_filename}"
        if not os.path.exists("static/images"):
            os.makedirs("static/images")
        filepath = os.path.join("static/images", filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)
        vocab.image_url = f"/static/images/{filename}"

    if audio_file and audio_file.filename:
        safe_filename = "".join(c for c in audio_file.filename if c.isalnum() or c in "._- ")
        filename = f"audio_{vocab_id}_{safe_filename}"
        filepath = os.path.join("static/audio", filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        vocab.audio_url = f"/static/audio/{filename}"

    db.commit()
    # Redirect to content manager
    return RedirectResponse(url=f"/admin/course/{course_id}/content_manager", status_code=303)

@router.get("/get_course_quiz_config/{course_id}")
async def get_course_quiz_config(course_id: int, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"status": "error", "msg": "Course not found"}
    return {"status": "success", "config": course.quiz_config}

@router.post("/save_course_quiz_config/{course_id}")
async def save_course_quiz_config(
    course_id: int,
    quiz_config: str = Form(...),
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"status": "error", "msg": "Course not found"}
        
    course.quiz_config = quiz_config
    db.commit()
    
    return {"status": "success", "msg": "Quiz configuration saved"}

@router.post("/copy_single_vocab")
async def copy_single_vocab(
    vocab_id: int = Form(...),
    target_course_id: int = Form(...),
    target_stage: str = Form(...),
    target_group: str = Form("Common"),
    db: Session = Depends(get_db)
):
    source = db.query(Vocabulary).filter(Vocabulary.id == vocab_id).first()
    if not source:
        return RedirectResponse(url="/admin", status_code=303)
    
    # Create copy
    new_vocab = Vocabulary(
        word=source.word,
        chinese_meaning=source.chinese_meaning,
        story=source.story,
        image_url=source.image_url,
        audio_url=source.audio_url,
        course_id=target_course_id,
        stage=target_stage,
        group=target_group,
        display_order=999 # Append to end
    )
    db.add(new_vocab)
    db.commit()
    # Redirect back to source course content manager
    return RedirectResponse(url=f"/admin/course/{source.course_id}/content_manager", status_code=303)


@router.post("/move_vocab/{vocab_id}")
async def move_vocab(
    vocab_id: int,
    direction: str = Form(...), # "up" or "down"
    db: Session = Depends(get_db)
):
    target = db.query(Vocabulary).filter(Vocabulary.id == vocab_id).first()
    if not target:
        return RedirectResponse(url="/admin?tab=content&error=VocabNotFound", status_code=303)
    
    # Isolate targets within the SAME STAGE (and usually same group scope, but stage is the primary view context)
    # The user is looking at a Stage list and clicking Up/Down.
    # So we should swap with the adjacent word IN THAT STAGE.
    
    # 1. Get all vocab for this course AND this stage, sorted
    vocabs = db.query(Vocabulary).filter(
        Vocabulary.course_id == target.course_id,
        Vocabulary.stage == target.stage
    ).order_by(Vocabulary.display_order, Vocabulary.id).all()
    
    # 2. Re-index to ensure continuity (0, 1, 2...) for logic simplicity in this subset? 
    # Actually, display_order might be shared globally. 
    # We just need to swap display_order values with the neighbor.
    
    # 3. Find target index in this filtered list
    try:
        curr_idx = vocabs.index(target)
    except ValueError:
        return RedirectResponse(url="/admin", status_code=303)
        
    # 4. Swap logic
    if direction == "up" and curr_idx > 0:
        neighbor = vocabs[curr_idx - 1]
        # Swap their order values. 
        # Note: If their gap is large (e.g. 10 and 20), swapping them (10->20, 20->10) works fine.
        target.display_order, neighbor.display_order = neighbor.display_order, target.display_order
        
    elif direction == "down" and curr_idx < len(vocabs) - 1:
        neighbor = vocabs[curr_idx + 1]
        target.display_order, neighbor.display_order = neighbor.display_order, target.display_order
        
    db.commit()
    # Redirect back to Content Manager if referer suggests, or generic
    # We can rely on the frontend to reload or return a 204 if we move to AJAX later.
    # For now, redirect to content_manager
    return RedirectResponse(url=f"/admin/course/{target.course_id}/content_manager", status_code=303)

@router.post("/delete_user_result/{result_id}")
async def delete_user_result(
    result_id: int, 
    request: Request,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user_req) # Ensure auth
):
    if not current_user or not current_user.is_admin:
        return RedirectResponse(url="/", status_code=303)
        
    # Soft Delete Single Result
    res = db.query(QuizResult).filter(QuizResult.id == result_id).first()
    if res:
        res.is_deleted = True
        db.commit()
        
    return RedirectResponse(url="/admin/users", status_code=303)

@router.get("/get_result_trash")
async def get_result_trash(db: Session = Depends(get_db)):
    deleted_results = db.query(QuizResult).filter(QuizResult.is_deleted == True).all()
    data = []
    for r in deleted_results:
        # Fetch meta info
        u = db.query(User).filter(User.id == r.user_id).first()
        email = u.email if u else "Unknown User"
        c = db.query(Course).filter(Course.id == r.course_id).first()
        course_name = c.name if c else "Unknown Course"
        
        from datetime import timedelta
        local_time = r.submitted_at + timedelta(hours=8) if r.submitted_at else None
        
        data.append({
            "id": r.id,
            "email": email,
            "course": course_name,
            "score": f"{r.translation_score} / {r.sentence_score}",
            "date": local_time.strftime("%Y-%m-%d %H:%M") if local_time else "-"
        })
    return JSONResponse(data)

@router.post("/restore_result/{result_id}")
async def restore_result(result_id: int, db: Session = Depends(get_db)):
    res = db.query(QuizResult).filter(QuizResult.id == result_id).first()
    if res:
        res.is_deleted = False
        db.commit()
    return JSONResponse({"status": "success"})

@router.post("/permanent_delete_result/{result_id}")
async def permanent_delete_result(result_id: int, db: Session = Depends(get_db)):
    res = db.query(QuizResult).filter(QuizResult.id == result_id).first()
    if res:
        db.delete(res)
        db.commit()
    return JSONResponse({"status": "success"})

@router.post("/empty_result_trash")
async def empty_result_trash(db: Session = Depends(get_db)):
    db.query(QuizResult).filter(QuizResult.is_deleted == True).delete()
    db.commit()
    return JSONResponse({"status": "success"})

from utils import ADMIN_EMAILS

@router.post("/reset_course_data/{course_id}")
async def reset_course_data(course_id: int, db: Session = Depends(get_db)):
    # Delete QuizResults for this course
    db.query(QuizResult).filter(QuizResult.course_id == course_id).delete()
    
    # Delete Enrollments for this course
    db.query(Enrollment).filter(Enrollment.course_id == course_id).delete()
    
    # Optionally delete Users who have NO other enrollments if we wanted to be strict,
    # but for "Reset Course Data", cleaning results/enrollments is usually enough.
    
    db.commit()
    return RedirectResponse(url=f"/admin/course/{course_id}", status_code=303)

@router.post("/delete_all_data")
async def delete_all_data(db: Session = Depends(get_db)):
    db.query(QuizResult).delete()
    db.query(Enrollment).delete()
    
    # Delete only NON-ADMIN users
    # Filter users where email NOT IN ADMIN_EMAILS
    db.query(User).filter(User.email.notin_(ADMIN_EMAILS)).delete(synchronize_session=False)

    db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@router.get("/export_csv")
async def export_csv(course_id: int = None, db: Session = Depends(get_db)):
    import pandas as pd
    import io
    from datetime import timedelta
    query = db.query(QuizResult)
    filename = "export_all_data.csv"
    
    if course_id:
        query = query.filter(QuizResult.course_id == course_id)
        filename = f"export_course_{course_id}.csv"
        
    results = query.filter(QuizResult.is_deleted == False).all()
    
    data = []
    
    # Adjust time to Taipei (UTC+8)
    from datetime import timedelta

    for r in results:
        # Get user group for this course
        enrollment = db.query(Enrollment).filter(
            Enrollment.user_id == r.user_id, 
            Enrollment.course_id == r.course_id
        ).first()
        group = enrollment.group if enrollment else "Unknown"
        
        # Better: get course from r.course_id
        course = db.query(Course).filter(Course.id == r.course_id).first()
        course_name = course.name if course else "Unknown"
        
        local_time = r.submitted_at + timedelta(hours=8) if r.submitted_at else None

        data.append({
            "User ID": r.user_id,
            "Email": r.user.email,
            "Course": course_name,
            "Group": group,
            "Translation Score": r.translation_score,
            "Sentence Score": r.sentence_score,
            "NASA TLX": r.nasa_tlx_score,
            "Learning Duration (s)": r.learning_duration_seconds,
            "Submitted At": local_time.strftime("%Y-%m-%d %H:%M") if local_time else "-"
        })
    
    df = pd.DataFrame(data)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

# Statistical imports moved to function scope

# Set Matplotlib backend inside functions instead of globally

def perform_stats_and_plot(df, val_col, group_col, title):
    """
    Helper to perform stats (Wilcoxon or Kruskal) and plot.
    Returns: dict with stats_result and plot_base64
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns
    import io
    import base64
    
    # Descriptive Stats
    stats_df = df.groupby(group_col)[val_col].agg(['count', 'mean', 'std', 'median'])
    
    unique_groups = sorted(df[group_col].unique())
    groups_data = [df[df[group_col] == g][val_col].values for g in unique_groups]
    valid_groups = [g for g in groups_data if len(g) > 0]
    
    if len(valid_groups) < 2:
        return {"error": "Insufficient data"}

    # Statistical Test
    stat_res = {}
    p_val = 1.0
    test_name = ""
    
    if len(valid_groups) == 2:
        # Wilcoxon Rank-Sum
        from scipy.stats import ranksums
        stat, p_val = ranksums(*valid_groups)
        test_name = "Wilcoxon Rank-Sum"
        stat_res = {"test": test_name, "stat": stat, "p_value": p_val}
    else:
        # Kruskal-Wallis
        from scipy.stats import kruskal
        stat, p_val = kruskal(*valid_groups)
        test_name = "Kruskal-Wallis"
        dunn_res = None
        if p_val < 0.05:
            try:
                # Dunn's Test
                dunn = sp.posthoc_dunn(df, val_col=val_col, group_col=group_col, p_adjust='bonferroni')
                dunn_res = dunn.to_dict()
            except: pass
        stat_res = {"test": test_name, "stat": stat, "p_value": p_val, "dunn": dunn_res}

    # Plotting
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Boxplot + Stripplot
    sns.boxplot(x=group_col, y=val_col, data=df, ax=ax, palette="Set2", order=unique_groups)
    sns.stripplot(x=group_col, y=val_col, data=df, ax=ax, color='black', alpha=0.5, jitter=True, order=unique_groups)
    
    # Title Color
    color = '#D62728' if p_val < 0.05 else 'black'
    ax.set_title(f"{title}\n({test_name} p={p_val:.3f})", color=color, fontweight='bold')
    
    # Custom X-Labels
    new_labels = []
    for g in unique_groups:
        if g in stats_df.index:
            row = stats_df.loc[g]
            label = (f"{g}\n(n={int(row['count'])})\n"
                     f"Mean={row['mean']:.2f}\n"
                     f"Med={row['median']:.2f}\n"
                     f"SD={row['std']:.2f}")
        else:
            label = g
        new_labels.append(label)
    
    ax.set_xticklabels(new_labels)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    plot_url = base64.b64encode(buf.getvalue()).decode('utf-8')
    
    return {"stats": stat_res, "plot": plot_url}

@router.get("/stats")
async def get_stats(course_id: int = 1, db: Session = Depends(get_db)):
    import pandas as pd
    import json
    # Fetch data joined with Enrollment to get group correctly
    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    user_groups = {e.user_id: e.group for e in enrollments}
    
    results = db.query(QuizResult).filter(QuizResult.course_id == course_id, QuizResult.is_deleted == False).all()
    if not results:
        return {"msg": "No data for this course"}

    data = []
    dynamic_metrics = set()
    import json
    
    # Get current course config to filter active stages
    course = db.query(Course).filter(Course.id == course_id).first()
    try:
        course_config = json.loads(course.stage_config) if course.stage_config else {}
    except:
        course_config = {}

    for r in results:
        # Fallback Logic: Priority 1: QuizResult.group snapshot, Priority 2: Enrollment record
        group = r.group
        if not group or group == "Unknown":
            group = user_groups.get(r.user_id, "Unknown")
        
        # Determine active stages for this specific student's group
        if isinstance(course_config, list):
            active_stage_names = {s['name'] for s in course_config}
        else:
            active_stage_names = {s['name'] for s in course_config.get(group, course_config.get("Common", []))}
        
        # 1. Calculate Calculated Duration Breakdown
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
            calculated_total = r.learning_duration_seconds # Fallback
            learning_time = calculated_total
            quiz_time = 0

        row = {
            "group": group,
            "nasa_tlx": r.nasa_tlx_score,
            "Total Duration": calculated_total,
            "Learning Duration": learning_time,
            "Quiz Duration": quiz_time
        }
        dynamic_metrics.update(["Total Duration", "Learning Duration", "Quiz Duration"])
        
        # 2. Parse Section Stats (Scores)
        try:
            sections = json.loads(r.section_stats) if r.section_stats else {}
            if not sections and r.translation_score:
                sections = {"Translation": r.translation_score}
            
            for k, v in sections.items():
                row[k] = v
                dynamic_metrics.add(k)
        except: pass
        
        # 3. Parse NASA-TLX Details (6 Dimensions)
        try:
            nasa_det = json.loads(r.nasa_details_json) if r.nasa_details_json else {}
            for k, v in nasa_det.items():
                metric_name = f"NASA: {k.capitalize()}"
                row[metric_name] = v
                dynamic_metrics.add(metric_name)
        except: pass

        data.append(row)
        
    df = pd.DataFrame(data)

    # Metrics to analyze: derived from dynamic sets + duplicates logic
    # Filter out redundant single NASA if details exist
    metrics = sorted(list(dynamic_metrics))
    if not metrics: metrics = ["Total Duration", "nasa_tlx"] # Fallback
    
    stats_results = {}
    plot_urls = {}
    interpretations = {} # Keeping this key for frontend compatibility, but logic is strict stats now.

    for m in metrics:
        if m not in df.columns: continue
        
        # Filter groups with data
        valid_df = df.dropna(subset=[m])
        # Only keep groups that exist for this course (filter out stray data if any)
        
        try:
            res = perform_stats_and_plot(valid_df, m, 'group', f"Analysis: {m}")
            
            if "error" in res:
                interpretations[m] = f"Unable to perform analysis: {res['error']} (Reason: Only one group or insufficient samples)"
                continue
                
            stats_results[m] = res["stats"]
            plot_urls[m] = res["plot"]
            
            # Simple Text Summary
            p = res["stats"]["p_value"]
            test = res["stats"]["test"]
            sig = "Significant difference" if p < 0.05 else "No significant difference"
            interpretations[m] = f"Method: {test}. Result: {sig} (p={p:.4f})."
            
        except Exception as e:
            interpretations[m] = f"分析過程出錯：{str(e)}"

    return {"stats": stats_results, "plots": plot_urls, "interpretations": interpretations}

# --- STAGE & CONTENT MANAGEMENT ---

@router.post("/paste_content")
async def paste_content(
    source_ids: List[int] = Form(...),
    operation: str = Form(...), # "copy" or "cut"
    target_course_id: int = Form(...),
    target_group: str = Form(...),
    target_stage: str = Form(...),
    db: Session = Depends(get_db)
):
    # Retrieve Source Items
    words = db.query(Vocabulary).filter(Vocabulary.id.in_(source_ids)).all()
    if not words:
        return {"status": "error", "msg": "No source items found"}

    if operation == "cut":
        # MOVE: Update Group, Stage, and Course (if different)
        # For Undo: Return modified IDs and their previous locations? 
        # Actually simplest format: Return modified IDs. 
        # Frontend state usually knows where they came from? No.
        # Let's return the IDs so we can track them.
        modified_ids = []
        for w in words:
            w.group = target_group
            w.stage = target_stage
            w.course_id = target_course_id
            modified_ids.append(w.id)
        db.commit()
        return {"status": "success", "msg": f"Moved {len(words)} items.", "mode": "cut", "ids": modified_ids}

    elif operation == "copy":
        # CLONE: Create duplicates
        new_items = []
        for w in words:
            new_vocab = Vocabulary(
                word=w.word,
                chinese_meaning=w.chinese_meaning,
                story=w.story,
                image_url=w.image_url,
                audio_url=w.audio_url,
                course_id=target_course_id,
                group=target_group, # Assign to target Group
                stage=target_stage, # Assign to target Stage
                display_order=w.display_order
            )
            new_items.append(new_vocab)
        
        db.add_all(new_items)
        db.commit()
        # Refresh to get IDs
        for i in new_items: db.refresh(i)
        
        new_ids = [i.id for i in new_items]
        return {"status": "success", "msg": f"Copied {len(new_items)} items.", "mode": "copy", "ids": new_ids}
    
    return {"status": "error", "msg": "Invalid operation"}

# BATCH OPERATIONS (Ensuring they exist)
@router.post("/delete_vocab_batch")
async def delete_vocab_batch(ids: List[int], db: Session = Depends(get_db)):
    # Soft Delete Batch
    db.query(Vocabulary).filter(Vocabulary.id.in_(ids)).update({Vocabulary.is_deleted: True}, synchronize_session=False)
    db.commit()
    return {"status": "success"}

@router.post("/restore_vocab_batch")
async def restore_vocab_batch(ids: List[int], db: Session = Depends(get_db)):
    # Restore Batch
    db.query(Vocabulary).filter(Vocabulary.id.in_(ids)).update({Vocabulary.is_deleted: False}, synchronize_session=False)
    db.commit()
    return {"status": "success"}

@router.post("/paste_folder")
async def paste_folder(
    course_id: int = Form(...),
    source_type: str = Form(...), # "group" or "stage"
    source_name: str = Form(...), # Name of group or stage
    source_group: str = Form(None), # Required if source_type is stage (parent group)
    target_group: str = Form(None), # Target parent group
    operation: str = Form(...), # "copy" or "cut"
    db: Session = Depends(get_db)
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return {"status": "error", "msg": "Course not found"}

    import json
    try:
        config = json.loads(course.stage_config) if course.stage_config else {}
        if isinstance(config, list): config = {"Common": config} # Migration
    except:
        config = {}

    # --- STAGE OPERATION ---
    if source_type == "stage":
        if not source_group or not target_group:
            return {"status": "error", "msg": "Missing group info for stage operation"}
        
        # 1. Get Source Config
        source_stages = config.get(source_group, [])
        target_stages = config.get(target_group, [])
        
        # Find source stage object
        src_stage_obj = next((s for s in source_stages if s['name'] == source_name), None)
        if not src_stage_obj:
            return {"status": "error", "msg": "Source stage not found"}

        new_stage_name = source_name
        
        # COPY Logic
        if operation == "copy":
            # If target has same name, append "Copy"
            while any(s['name'] == new_stage_name for s in target_stages):
                new_stage_name += " Copy"
            
            # Add to target config
            new_stage_obj = src_stage_obj.copy()
            new_stage_obj['name'] = new_stage_name
            if target_group not in config: config[target_group] = []
            config[target_group].append(new_stage_obj)
            
            # Duplicate Vocab
            vocabs = db.query(Vocabulary).filter(
                Vocabulary.course_id == course_id,
                Vocabulary.group == source_group,
                Vocabulary.stage == source_name
            ).all()
            
            new_vocabs = []
            for v in vocabs:
                nv = Vocabulary(
                    word=v.word, chinese_meaning=v.chinese_meaning, story=v.story,
                    image_url=v.image_url, audio_url=v.audio_url,
                    course_id=course_id, group=target_group, stage=new_stage_name,
                    display_order=v.display_order
                )
                new_vocabs.append(nv)
            db.add_all(new_vocabs)
            
        # CUT Logic
        elif operation == "cut":
            # Prevent move to same group? No, reordering maybe? 
            # If same group, just reordering/rename logic handled elsewhere usually.
            
            # Remove from source
            config[source_group] = [s for s in config[source_group] if s['name'] != source_name]
            
            # Add to target
            # Rename if collision
            while any(s['name'] == new_stage_name for s in target_stages):
                new_stage_name += " Copy"
            
            src_stage_obj['name'] = new_stage_name
            if target_group not in config: config[target_group] = []
            config[target_group].append(src_stage_obj)
            
            # Update Vocab
            db.query(Vocabulary).filter(
                Vocabulary.course_id == course_id,
                Vocabulary.group == source_group,
                Vocabulary.stage == source_name
            ).update({
                Vocabulary.group: target_group,
                Vocabulary.stage: new_stage_name
            }, synchronize_session=False)

    # --- GROUP OPERATION ---
    elif source_type == "group":
        # Target usually ignored for Group ops unless we supported "Parent Groups" (not yet).
        # So Copy just clones it. Cut is Rename? Or "Move to another course"?
        # Requirement: "Copy and Cut". Cut for Group effectively means Rename or Move.
        # Let's assume Cut inside same course is just ignored or treated as Copy then Delete? 
        # Actually standard OS behavior: Cut Group -> Paste elsewhere. 
        # But we are pasting into "Root"? 
        # For this system, let's treat Group Copy = Clone Group. Group Cut = Rename (if pasted).
        
        new_group_name = source_name
        current_groups = [g.strip() for g in (course.group_names or "").split(",") if g.strip()]
        
        if operation == "copy":
            while new_group_name in current_groups:
                new_group_name += " Copy"
            
            # 1. Update Group List
            current_groups.append(new_group_name)
            course.group_names = ",".join(current_groups)
            
            # 2. Duplicate Config
            if source_name in config:
                config[new_group_name] = config[source_name] # Deep copy needed?
                # JSON dump/load does deep copy
                import copy
                config[new_group_name] = copy.deepcopy(config[source_name])
            
            # 3. Duplicate Vocab
            vocabs = db.query(Vocabulary).filter(
                Vocabulary.course_id == course_id,
                Vocabulary.group == source_name
            ).all()
            new_vocabs = []
            for v in vocabs:
                nv = Vocabulary(
                    word=v.word, chinese_meaning=v.chinese_meaning, story=v.story,
                    image_url=v.image_url, audio_url=v.audio_url,
                    course_id=course_id, group=new_group_name, stage=v.stage,
                    display_order=v.display_order
                )
                new_vocabs.append(nv)
            db.add_all(new_vocabs)
            
        elif operation == "cut":
            # Essentially a Rename if pasting to root.
             while new_group_name in current_groups:
                new_group_name += " Copy" # Valid conflict resolution
                
             # Update List
             idx = current_groups.index(source_name)
             current_groups[idx] = new_group_name
             course.group_names = ",".join(current_groups)
             
             # Update Config Key
             if source_name in config:
                 config[new_group_name] = config.pop(source_name)
             
             # Update Vocab
             db.query(Vocabulary).filter(Vocabulary.course_id == course_id, Vocabulary.group == source_name).update({Vocabulary.group: new_group_name}, synchronize_session=False)
             db.query(Enrollment).filter(Enrollment.course_id == course_id, Enrollment.group == source_name).update({Enrollment.group: new_group_name}, synchronize_session=False)

    course.stage_config = json.dumps(config)
    db.commit()
    return {"status": "success"}

@router.post("/update_vocab_stage/{vocab_id}")
async def update_vocab_stage(vocab_id: int, stage_name: str = Form("Unassigned"), db: Session = Depends(get_db)):
    v = db.query(Vocabulary).filter(Vocabulary.id == vocab_id).first()
    if v:
        v.stage = stage_name
        db.commit()
    return "OK"

@router.post("/batch_update_stage")
async def batch_update_stage(vocab_ids: str = Form(...), stage_name: str = Form("Unassigned"), db: Session = Depends(get_db)):
    # vocab_ids is comma separated
    ids = [int(i) for i in vocab_ids.split(",") if i.isdigit()]
    db.query(Vocabulary).filter(Vocabulary.id.in_(ids)).update({Vocabulary.stage: stage_name}, synchronize_session=False)
    db.commit()
    return "OK"

    db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/delete_course/{course_id}")
async def delete_course(course_id: int, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        course.is_deleted = True
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/restore_course/{course_id}")
async def restore_course(course_id: int, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        course.is_deleted = False
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@router.get("/get_course_trash")
async def get_course_trash(db: Session = Depends(get_db)):
    deleted = db.query(Course).filter(Course.is_deleted == True).all()
    return {
        "status": "success",
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "group_names": c.group_names
            } for c in deleted
        ]
    }

@router.post("/permanent_delete_course/{course_id}")
async def permanent_delete_course(course_id: int, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        # Cascade delete dependencies if necessary (Enrollments, Results, Vocab)
        # Assuming database.py usage, we should probably manually clean up to be safe
        db.query(Vocabulary).filter(Vocabulary.course_id == course_id).delete()
        db.query(Enrollment).filter(Enrollment.course_id == course_id).delete()
        db.query(QuizResult).filter(QuizResult.course_id == course_id).delete()
        
        db.delete(course)
        db.commit()
    return {"status": "success", "msg": "Course permanently deleted"}

@router.post("/empty_course_trash")
async def empty_course_trash(db: Session = Depends(get_db)):
    courses = db.query(Course).filter(Course.is_deleted == True).all()
    for c in courses:
        db.query(Vocabulary).filter(Vocabulary.course_id == c.id).delete()
        db.query(Enrollment).filter(Enrollment.course_id == c.id).delete()
        db.query(QuizResult).filter(QuizResult.course_id == c.id).delete()
        db.delete(c)
    db.commit()
    return {"status": "success", "msg": "Trash emptied"}

@router.post("/clone_course/{course_id}")
async def clone_course(course_id: int, db: Session = Depends(get_db)):
    original = db.query(Course).filter(Course.id == course_id).first()
    if not original:
        return RedirectResponse(url="/admin", status_code=303)
        
    # 1. Clone Course
    new_course = Course(
        name=f"{original.name} (Copy)",
        description=original.description,
        group_names=original.group_names,
        stage_config=original.stage_config,
        is_deleted=False
    )
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    
    # 2. Clone Vocab
    original_vocabs = db.query(Vocabulary).filter(Vocabulary.course_id == course_id, Vocabulary.is_deleted == False).all()
    for v in original_vocabs:
        new_v = Vocabulary(
            course_id=new_course.id,
            word=v.word,
            chinese_meaning=v.chinese_meaning,
            story=v.story,
            image_url=v.image_url,
            audio_url=v.audio_url,
            group=v.group,
            stage=v.stage,
            display_order=v.display_order
        )
        db.add(new_v)
    
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@router.post("/clone_stage_content")
async def clone_stage_content(
    source_course_id: int = Form(...),
    source_group: str = Form(...),
    source_stage: str = Form(...),
    target_course_id: int = Form(...),
    target_group: str = Form(...),
    target_stage: str = Form(...),
    db: Session = Depends(get_db)
):
    # Select Source Vocab
    # Logic: Vocab must be in Source Course AND (Group == Source Group OR Group == 'Common'?? No, explicit copy usually implies specific group content, OR all content visible to that group)
    # Re-reading req: "Copy assignments". 
    # If source_group is specific, we copy words assigned with that group.
    
    query = db.query(Vocabulary).filter(
        Vocabulary.course_id == source_course_id,
        Vocabulary.stage == source_stage
    )
    
    if source_group != "All":
        query = query.filter(Vocabulary.group == source_group)
        
    source_vocabs = query.all()
    
    count = 0
    for v in source_vocabs:
        # Create Copy assigned to Target
        new_v = Vocabulary(
            course_id=target_course_id,
            word=v.word,
            chinese_meaning=v.chinese_meaning,
            story=v.story,
            image_url=v.image_url,
            audio_url=v.audio_url,
            group=target_group, # Assign to Target Group
            stage=target_stage, # Assign to Target Stage
            display_order=v.display_order
        )
        db.add(new_v)
        count += 1
        
    # Update Target Stage Config to include this new Stage
    target_course = db.query(Course).filter(Course.id == target_course_id).first()
    if target_course:
        import json
        try:
            config = json.loads(target_course.stage_config)
        except:
            config = {}
        if isinstance(config, list): config = {"Common": config}
        
        if target_group not in config:
            config[target_group] = []
            
        # Check if stage exists
        exists = any(s['name'] == target_stage for s in config[target_group])
        if not exists:
            config[target_group].append({"name": target_stage, "count": count})
            target_course.stage_config = json.dumps(config)

    db.commit()
    return JSONResponse({"status": "success", "msg": f"Cloned {count} items"})

@router.post("/clone_group_content")
async def clone_group_content(
    source_course_id: int = Form(...),
    source_group: str = Form(...),
    target_course_id: int = Form(...),
    target_group: str = Form(...),
    db: Session = Depends(get_db)
):
    # 1. Get Source Course Config to find Stages in this Group
    source_course = db.query(Course).filter(Course.id == source_course_id).first()
    if not source_course:
        return JSONResponse({"status": "error", "msg": "Source course not found"}, status_code=404)
        
    # Parse Config
    import json
    try:
        config = json.loads(source_course.stage_config)
    except:
        config = {}
        
    # Handle list legacy
    if isinstance(config, list):
        # Legacy list implies "Common" or single group
        # If source_group is "Common" or matches, we take it all
        stages = config
    else:
        stages = config.get(source_group, [])
        
    # 2. Get Target Course to update its config
    target_course = db.query(Course).filter(Course.id == target_course_id).first()
    if not target_course:
        return JSONResponse({"status": "error", "msg": "Target course not found"}, status_code=404)
        
    try:
        target_config = json.loads(target_course.stage_config)
    except:
        target_config = {}
    if isinstance(target_config, list): target_config = {"Common": target_config}
    
    # Update Target Config
    if target_group not in target_config:
        target_config[target_group] = []
        
    # Copy Stages structure
    # Avoid duplicates? User might want copy. Let's append with distinct check or just append?
    # Requirement: "Copy". Usually implies overwrite or append. Let's append if not exist.
    existing_stage_names = {s['name'] for s in target_config[target_group]}
    
    for s in stages:
        if s['name'] not in existing_stage_names:
            target_config[target_group].append({"name": s['name'], "count": s.get('count', 0)})
        
        # 3. Clone Vocab for this Stage
        # Re-use logic? Or just query loop here.
        query = db.query(Vocabulary).filter(
            Vocabulary.course_id == source_course_id,
            Vocabulary.group == source_group,
            Vocabulary.stage == s['name']
        )
        for v in query.all():
            new_v = Vocabulary(
                course_id=target_course_id,
                word=v.word,
                chinese_meaning=v.chinese_meaning,
                story=v.story,
                image_url=v.image_url,
                audio_url=v.audio_url,
                group=target_group,
                stage=v.stage, # Keep same stage name
                display_order=v.display_order
            )
            db.add(new_v)
            
    target_course.stage_config = json.dumps(target_config)
    
    # Update Group Names list
    current_groups = target_course.group_names.split(",") if target_course.group_names else []
    if target_group not in current_groups:
        current_groups.append(target_group)
        target_course.group_names = ",".join(current_groups)
        
    db.commit()
    
    return JSONResponse({"status": "success", "msg": f"Group cloned successfully"})

@router.post("/duplicate_vocab/{vocab_id}")
async def duplicate_vocab(vocab_id: int, db: Session = Depends(get_db)):
    v = db.query(Vocabulary).filter(Vocabulary.id == vocab_id).first()
    if v:
        new_v = Vocabulary(
            course_id=v.course_id,
            word=f"{v.word} (Copy)",
            chinese_meaning=v.chinese_meaning,
            story=v.story,
            image_url=v.image_url,
            audio_url=v.audio_url,
            group=v.group,
            stage=v.stage,
            display_order=v.display_order + 1
        )
        db.add(new_v)
        db.commit()
        return RedirectResponse(url=f"/admin/course/{v.course_id}", status_code=303)
    return RedirectResponse(url="/admin", status_code=303)

# --- BATCH & GROUP OPERATIONS ---

@router.post("/delete_vocab_batch")
async def delete_vocab_batch(ids: List[int] = Body(...), db: Session = Depends(get_db)):
    db.query(Vocabulary).filter(Vocabulary.id.in_(ids)).update({Vocabulary.is_deleted: True}, synchronize_session=False)
    db.commit()
    return {"status": "success"}

@router.post("/restore_vocab_batch")
async def restore_vocab_batch(ids: List[int] = Body(...), db: Session = Depends(get_db)):
    db.query(Vocabulary).filter(Vocabulary.id.in_(ids)).update({Vocabulary.is_deleted: False}, synchronize_session=False)
    db.commit()
    return {"status": "success"}

@router.post("/add_group")
async def add_group(course_id: int = Form(...), group_name: str = Form(...), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        current = course.group_names.split(",") if course.group_names else []
        if group_name not in current:
            current.append(group_name)
            course.group_names = ",".join(current)
            db.commit()
    return {"status": "success"}

@router.post("/delete_group")
async def delete_group(course_id: int = Form(...), group_name: str = Form(...), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        current = [g for g in course.group_names.split(",") if g != group_name]
        course.group_names = ",".join(current)
        db.commit()
    return {"status": "success"}

@router.post("/rename_group")
async def rename_group(course_id: int = Form(...), old_name: str = Form(...), new_name: str = Form(...), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        groups = course.group_names.split(",")
        if old_name in groups:
            groups[groups.index(old_name)] = new_name
            course.group_names = ",".join(groups)
            # Update Vocab
            db.query(Vocabulary).filter(Vocabulary.course_id == course_id, Vocabulary.group == old_name).update({Vocabulary.group: new_name}, synchronize_session=False)
            # Update Enrollments
            db.query(Enrollment).filter(Enrollment.course_id == course_id, Enrollment.group == old_name).update({Enrollment.group: new_name}, synchronize_session=False)
            # Update Stage Config
            import json
            try:
                config = json.loads(course.stage_config)
                if old_name in config:
                    config[new_name] = config.pop(old_name)
                    course.stage_config = json.dumps(config)
            except: pass
            db.commit()
    return {"status": "success"}

@router.post("/delete_stage")
async def delete_stage(course_id: int = Form(...), group_name: str = Form(...), stage_name: str = Form(...), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        import json
        try:
            config = json.loads(course.stage_config)
            if group_name in config:
                config[group_name] = [s for s in config[group_name] if s['name'] != stage_name]
                course.stage_config = json.dumps(config)
                # Soft delete words
                db.query(Vocabulary).filter(Vocabulary.course_id == course_id, Vocabulary.group == group_name, Vocabulary.stage == stage_name).update({Vocabulary.is_deleted: True}, synchronize_session=False)
                db.commit()
        except: pass
    return {"status": "success"}

@router.post("/paste_content")
async def paste_content(
    source_ids: List[int] = Form(...), 
    operation: str = Form(...),
    target_course_id: int = Form(...), 
    target_group: str = Form(...),
    target_stage: str = Form(...),
    db: Session = Depends(get_db)
):
    source_vocabs = db.query(Vocabulary).filter(Vocabulary.id.in_(source_ids)).all()
    new_ids = []
    
    if operation == 'cut' and str(target_course_id) == str(source_vocabs[0].course_id):
        # Same Course Move
        for v in source_vocabs:
            v.group = target_group
            v.stage = target_stage
            new_ids.append(v.id)
        db.commit()
    else:
        # Copy
        for v in source_vocabs:
            new_v = Vocabulary(
                course_id=target_course_id,
                word=v.word,
                chinese_meaning=v.chinese_meaning,
                story=v.story,
                image_url=v.image_url,
                audio_url=v.audio_url,
                group=target_group,
                stage=target_stage,
                display_order=v.display_order
            )
            db.add(new_v)
            db.commit()
            db.refresh(new_v)
            new_ids.append(new_v.id)
            
        if operation == 'cut':
            # Delete originals
            for v in source_vocabs:
                v.is_deleted = True
            db.commit()
            
    return {"status": "success", "ids": new_ids}

@router.post("/restore_group")
async def restore_group(course_id: int = Form(...), group_name: str = Form(...), db: Session = Depends(get_db)):
    # 1. Restore words
    db.query(Vocabulary).filter(Vocabulary.course_id == course_id, Vocabulary.group == group_name).update({Vocabulary.is_deleted: False}, synchronize_session=False)
    # 2. Restore config (Add back to group list if missing)
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        groups = course.group_names.split(",") if course.group_names else []
        if group_name not in groups:
            groups.append(group_name)
            course.group_names = ",".join(groups)
    db.commit()
    return {"status": "success"}

@router.post("/restore_stage")
async def restore_stage(course_id: int = Form(...), group_name: str = Form(...), stage_name: str = Form(...), db: Session = Depends(get_db)):
    # 1. Restore words
    db.query(Vocabulary).filter(Vocabulary.course_id == course_id, Vocabulary.group == group_name, Vocabulary.stage == stage_name).update({Vocabulary.is_deleted: False}, synchronize_session=False)
    # 2. Restore config logic is complex (depends on JSON), frontend handles it usually. 
    # But let's ensure it exists? 
    # Actually, for Undo, frontend usually restores the UI state (Stage Config) then calls backend to sync.
    # But here we just un-delete words for now.
    db.commit()
    return {"status": "success"}

@router.get("/image_analytics")
async def get_image_analytics(course_id: int = None, db: Session = Depends(get_db)):
    # Query all interactions, optionally filtered by course
    query = db.query(ImageInteraction)
    if course_id:
        query = query.filter(ImageInteraction.course_id == course_id)
    
    interactions = query.all()
    
    # Aggregate data by image_url
    analytics = {}
    for interaction in interactions:
        url = interaction.image_url
        if url not in analytics:
            analytics[url] = {
                "image_url": url,
                "vocab_id": interaction.vocab_id,
                "course_id": interaction.course_id,
                "likes": 0,
                "dislikes": 0,
                "views": 0,
                "unique_viewers": set()
            }
        
        if interaction.action == "like":
            analytics[url]["likes"] += 1
        elif interaction.action == "dislike":
            analytics[url]["dislikes"] += 1
        elif interaction.action == "view":
            analytics[url]["views"] += 1
            analytics[url]["unique_viewers"].add(interaction.user_id)
    
    # Convert to list and add metadata (vocab word, etc.)
    result = []
    for data in analytics.values():
        data["unique_viewers"] = len(data["unique_viewers"])
        data["word"] = "N/A"
        
        # Fetch vocab word if vocab_id exists
        if data["vocab_id"]:
            vocab = db.query(Vocabulary).filter(Vocabulary.id == data["vocab_id"]).first()
            if vocab:
                data["word"] = vocab.word
                data["chinese"] = vocab.chinese_meaning or ""
        
        result.append(data)
    
    return {"analytics": result}


# ==================== TEACHING EFFICIENCY ANALYSIS (Paas 1993) ====================

@router.get("/efficiency_analysis")
async def get_efficiency_analysis(course_id: int, db: Session = Depends(get_db)):
    """
    Teaching Efficiency Analysis (Multi-Section Support)
    """
    try:
        import numpy as np
        import math
        import pandas as pd
        from scipy.stats import kruskal
        import scikit_posthocs as sp
        import json
        
        results = db.query(QuizResult).filter(QuizResult.course_id == course_id, QuizResult.is_deleted == False).all()
        if not results: return {"error": "No data"}
        
        # 1. Collect available sections and pre-fetch users
        all_sections = set(['Overall'])
        user_ids = set()
        for r in results:
            user_ids.add(r.user_id)
            try:
                sec_stats = json.loads(r.section_stats or "{}")
                for s_key in sec_stats.keys():
                    all_sections.add(s_key)
            except: pass
            
        users_map = {u.id: u for u in db.query(User).filter(User.id.in_(list(user_ids))).all()}
        analysis_by_section = {}
        
        for section in sorted(list(all_sections)):
            data = []
            for r in results:
                user = users_map.get(r.user_id)
                if not user: continue
                
                # Performance Score
                if section == 'Overall':
                    total = (r.translation_score or 0) + (r.sentence_score or 0)
                    p_score = float(total) / 2.0
                else:
                    try:
                        sec_stats = json.loads(r.section_stats or "{}")
                        p_score = float(sec_stats.get(section, 0))
                    except: p_score = 0.0
                
                # Effort Score (NASA Mental)
                nasa_details = json.loads(r.nasa_details_json or "{}")
                r_effort = float(nasa_details.get("mental", r.nasa_tlx_score or 50))
                
                data.append({
                    "user_id": user.id,
                    "name": user.email or f"User {user.id}",
                    "group": r.group or "Unknown",
                    "quiz_score": p_score,
                    "nasa_mental": r_effort
                })
                
            if len(data) < 2: continue
            
            # Z-Score Normalization
            scores_p = [p["quiz_score"] for p in data]
            scores_r = [p["nasa_mental"] for p in data]
            
            mp, sdp = float(np.mean(scores_p)), float(np.std(scores_p, ddof=1) or 1.0)
            mr, sdr = float(np.mean(scores_r)), float(np.std(scores_r, ddof=1) or 1.0)
            
            for p in data:
                p["Z_P"] = round((p["quiz_score"] - mp) / sdp, 3)
                p["Z_R"] = round((p["nasa_mental"] - mr) / sdr, 3)
                p["E"] = round((p["Z_P"] - p["Z_R"]) / math.sqrt(2), 3)
            
            groups = {}
            for p in data:
                g = p["group"]
                if g not in groups: groups[g] = []
                groups[g].append(p["E"])
                
            group_averages = []
            for g, e_list in groups.items():
                pts = [p for p in data if p["group"] == g]
                group_averages.append({
                    "group": g,
                    "Z_P_mean": round(float(np.mean([p["Z_P"] for p in pts])), 3),
                    "Z_R_mean": round(float(np.mean([p["Z_R"] for p in pts])), 3),
                    "E_mean": round(float(np.mean(e_list)), 3),
                    "count": len(e_list),
                    "quiz_score_mean": round(float(np.mean([p["quiz_score"] for p in pts])), 2),
                    "nasa_mental_mean": round(float(np.mean([p["nasa_mental"] for p in pts])), 2)
                })
                
            stats = {
                "descriptive": {
                    "M_performance": round(mp, 2), 
                    "SD_performance": round(sdp, 2), 
                    "M_effort": round(mr, 2), 
                    "SD_effort": round(sdr, 2),
                    "total_students": len(data),
                    "num_groups": len(groups)
                }
            }
            
            # Statistical Tests
            if len(groups) == 2:
                try:
                    from scipy.stats import ranksums
                    group_list = list(groups.values())
                    stat, p_val = ranksums(group_list[0], group_list[1])
                    stats["wilcoxon"] = {
                        "U": round(float(stat), 4), 
                        "p": round(float(p_val), 4), 
                        "significant": bool(p_val < 0.05)
                    }
                except Exception as e:
                    stats["error"] = f"Wilcoxon error: {str(e)}"
            elif len(groups) > 2:
                try:
                    H, p_val = kruskal(*groups.values())
                    stats["kruskal_wallis"] = {
                        "H": round(float(H), 4), 
                        "p": round(float(p_val), 4), 
                        "significant": bool(p_val < 0.05)
                    }
                    if p_val < 0.05:
                        df_dunn = pd.DataFrame([{"g": p["group"], "e": p["E"]} for p in data])
                        dunn_res = sp.posthoc_dunn(df_dunn, val_col='e', group_col='g')
                        
                        dunn_list = []
                        cols = dunn_res.columns.tolist()
                        for i in range(len(cols)):
                            for j in range(i+1, len(cols)):
                                g1, g2 = cols[i], cols[j]
                                p_v = float(dunn_res.loc[g1, g2])
                                dunn_list.append({"group1": g1, "group2": g2, "p_value": round(p_v, 4), "significant": bool(p_v < 0.05)})
                        stats["dunn"] = dunn_list
                except Exception as e:
                    stats["error"] = f"Kruskal-Wallis error: {str(e)}"
                    
            analysis_by_section[section] = {
                "individual_points": data,
                "group_averages": group_averages,
                "statistics": stats
            }
                
        return {"sections": analysis_by_section}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@router.get("/efficiency_plot")
async def get_efficiency_plot(course_id: int, db: Session = Depends(get_db)):
    """
    Teaching Efficiency Analysis Plot (Multi-Section Support & Refined Aesthetics)
    """
    try:
        import pandas as pd
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import io
        import base64
        import numpy as np
        
        # Get data for all sections
        results = await get_efficiency_analysis(course_id, db)
        if "error" in results: return results
        
        sections_data = results.get("sections", {})
        plots = {}
        
        # Style settings
        plt.rcParams['font.sans-serif'] = ['Arial', 'sans-serif'] # Fallback
        MARKERS = {'A': 'o', 'B': 'x', 'C': 's', 'D': 'P', 'Unknown': '.'}
        
        # Section Name Translation for Plot (Prevents Font Hang)
        TRANSLATION = {
            "Overall": "Overall",
            "句子": "Sentence",
            "單字": "Vocabulary",
            "翻譯": "Translation"
        }
        
        for section, data in sections_data.items():
            display_name = TRANSLATION.get(section, section)
            # Filter non-ascii for title stability
            safe_title = "".join([c if ord(c) < 128 else "?" for c in display_name])
            
            df = pd.DataFrame(data["individual_points"])
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
            
            # --- LEFT PANEL: Quadrant Scatter Plot ---
            lim = max(abs(df["Z_R"].max()), abs(df["Z_P"].max()), 2.5) + 0.5
            ax1.set_xlim(-lim, lim)
            ax1.set_ylim(-lim, lim)
            ax1.set_facecolor('white')
            
            # Quadrant lines & Diagonal
            ax1.axhline(0, color='gray', alpha=0.3, linewidth=1)
            ax1.axvline(0, color='gray', alpha=0.3, linewidth=1)
            ax1.plot([-lim, lim], [-lim, lim], color='gray', linestyle='--', alpha=0.5, label='Efficiency = 0')
            
            # Text Labels inside quadrants
            ax1.text(-lim+0.2, lim-0.2, "High Efficiency", color='green', fontweight='bold', alpha=0.6, fontsize=12, va='top')
            ax1.text(lim-0.2, -lim+0.2, "Low Efficiency", color='red', fontweight='bold', alpha=0.6, fontsize=12, ha='right', va='bottom')
            
            groups = sorted(df["group"].unique())
            colors = plt.cm.get_cmap('tab10')(np.linspace(0, 1, len(groups)))
            
            for i, grp in enumerate(groups):
                subset = df[df["group"] == grp]
                m = MARKERS.get(grp, '.')
                
                # Individual points
                ax1.scatter(subset["Z_R"], subset["Z_P"], label=grp, alpha=0.5, s=80, color=colors[i], marker=m)
                
                # Group Mean (Stylized: larger, black edge)
                z_r_mean = float(subset["Z_R"].mean())
                z_p_mean = float(subset["Z_P"].mean())
                ax1.scatter(z_r_mean, z_p_mean, color=colors[i], s=350, marker=m, edgecolor='black', linewidth=2.5, zorder=5)

            ax1.set_xlabel("Mental Effort Z-score (R)", fontweight='bold')
            ax1.set_ylabel("Performance Z-score (P)", fontweight='bold')
            ax1.set_title(f"Efficiency Quadrant: {safe_title}", fontsize=14, pad=15)
            ax1.legend(title="Group", loc='upper right', frameon=True, shadow=False)
            ax1.grid(True, linestyle='-', alpha=0.1)
            
            # --- RIGHT PANEL: Boxplot with Stats ---
            eff_by_group = []
            enriched_labels = []
            for grp in groups:
                e_vals = df[df["group"] == grp]["E"].tolist()
                eff_by_group.append(e_vals)
                
                n = len(e_vals)
                mean_val = np.mean(e_vals) if n > 0 else 0
                med_val = np.median(e_vals) if n > 0 else 0
                sd_val = np.std(e_vals, ddof=1) if n > 1 else 0.0
                
                label = f"{grp}\n(n={n})\nMean={mean_val:.2f}\nMed={med_val:.2f}\nSD={sd_val:.2f}"
                enriched_labels.append(label)
                
            bp = ax2.boxplot(eff_by_group, labels=enriched_labels, patch_artist=True, showfliers=False)
            
            for i, (vals, color) in enumerate(zip(eff_by_group, colors)):
                # Jitter points overlay
                x_jitter = np.random.normal(i + 1, 0.04, size=len(vals))
                ax2.scatter(x_jitter, vals, alpha=0.5, color='#444444', s=30, zorder=3)
                
                # Customize boxes
                patch = bp['boxes'][i]
                patch.set_facecolor(color)
                patch.set_alpha(0.5)
                patch.set_edgecolor('#333333')
                
            ax2.axhline(0, color='gray', linestyle='--', alpha=0.5, zorder=1)
            ax2.set_xlabel("Group", fontweight='bold')
            ax2.set_ylabel("Efficiency Score (E)", fontweight='bold')
            ax2.set_title(f"Efficiency Distribution ({safe_title})", fontsize=14, pad=15)
            ax2.grid(True, alpha=0.15, axis='y')
            ax2.tick_params(axis='x', labelsize=9)
            
            plt.suptitle(f"Teaching Efficiency Analysis - {safe_title} (Course {course_id})", fontsize=18, fontweight='bold', y=0.98)
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=85, bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode('utf-8')
            
            plots[section] = {
                "image": f"data:image/png;base64,{img_b64}",
                "statistics": data.get("statistics"),
                "group_averages": data.get("group_averages"),
                "individual_points": data.get("individual_points")
            }
            
        return {"sections": plots}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@router.get("/user_efficiency_plot")
async def get_user_efficiency_plot(course_id: int, user_id: int, db: Session = Depends(get_db)):
    """
    User-facing Efficiency Plot (Simplified for Stability)
    """
    try:
        import pandas as pd
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import io
        import base64
        import numpy as np
        
        # Get data
        analysis_res = await get_efficiency_analysis(course_id, db)
        if "error" in analysis_res: raise HTTPException(400, analysis_res["error"])
        
        # Use 'Overall' section for user plot
        data = analysis_res.get("sections", {}).get("Overall", {})
        if not data: raise HTTPException(404, "Overall analysis data not found")
        
        user_data = next((p for p in data.get("individual_points", []) if p["user_id"] == user_id), None)
        if not user_data: raise HTTPException(404, "User data not found for this course")
        
        df = pd.DataFrame(data["individual_points"])
        fig, ax = plt.subplots(figsize=(10, 8))
        
        lim = max(abs(df["Z_R"].max()), abs(df["Z_P"].max()), 2.5) + 0.5
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        
        # Background
        ax.fill_between([-lim, 0], 0, lim, color='lightgreen', alpha=0.1)
        ax.fill_between([0, lim], -lim, 0, color='lightcoral', alpha=0.1)
        
        ax.axhline(0, color='black', alpha=0.2)
        ax.axvline(0, color='black', alpha=0.2)
        ax.plot([-lim, lim], [-lim, lim], 'k--', alpha=0.3)
        
        # Individual points (faded)
        ax.scatter(df["Z_R"], df["Z_P"], alpha=0.2, s=50, c='gray')
        
        # YOUR POINT (Highlight)
        ax.scatter(user_data["Z_R"], user_data["Z_P"], s=400, marker='*', c='gold', edgecolors='red', linewidths=2, label='YOU', zorder=10)
        
        ax.set_xlabel("Mental Effort (R)")
        ax.set_ylabel("Learning Performance (P)")
        ax.set_title("Your Learning Efficiency Position")
        ax.legend()
        ax.grid(True, alpha=0.2)
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')
        
        # Evaluation
        if user_data["E"] > 0:
            quadrant = "High Efficiency" if user_data["Z_R"] < 0 else "High Performance"
            msg = "Great! You achieved good results with efficient effort."
        else:
            quadrant = "Low Efficiency" if user_data["Z_R"] > 0 else "Low Performance"
            msg = "You might need more practice or a different strategy."
            
        return {
            "image": f"data:image/png;base64,{img_b64}",
            "user_data": user_data,
            "quadrant": quadrant,
            "message": msg,
            "statistics": data.get("statistics")
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


# ==================== IMAGE ENGAGEMENT ANALYSIS ====================

@router.get("/engagement_analysis")
async def get_engagement_analysis(course_id: int, db: Session = Depends(get_db)):
    """
    Statistical analysis of user engagement with images per group.
    """
    try:
        import numpy as np
        import pandas as pd
        from scipy.stats import ranksums, kruskal
        import scikit_posthocs as sp
        
        # 1. Fetch all interactions for the course
        interactions = db.query(ImageInteraction).filter(ImageInteraction.course_id == course_id).all()
        if not interactions:
            return {"error": "No interaction data found for this course"}
            
        # 2. Fetch all enrollments to get user groups
        enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
        user_groups = {e.user_id: e.group for e in enrollments}
        
        # 3. Aggregate data per user
        user_stats = {}
        for action in interactions:
            u_id = action.user_id
            if u_id not in user_stats:
                user_stats[u_id] = {"likes": 0, "dislikes": 0, "views": 0, "group": user_groups.get(u_id, "Unknown")}
            
            if action.action == "like":
                user_stats[u_id]["likes"] += 1
            elif action.action == "dislike":
                user_stats[u_id]["dislikes"] += 1
            elif action.action == "view":
                user_stats[u_id]["views"] += 1
        
        # 4. Calculate engagement rate per user
        data = []
        for u_id, stats in user_stats.items():
            if stats["views"] > 0:
                engagement = (stats["likes"] + stats["dislikes"]) / stats["views"] * 100.0
                data.append({
                    "user_id": u_id,
                    "group": stats["group"],
                    "engagement_rate": round(engagement, 2),
                    "likes": stats["likes"],
                    "dislikes": stats["dislikes"],
                    "views": stats["views"]
                })
        
        if len(data) < 2:
            return {"error": "Insufficient data for statistical analysis"}
            
        df = pd.DataFrame(data)
        
        # 5. Group-wise statistics
        groups = df["group"].unique()
        group_data = {g: df[df["group"] == g]["engagement_rate"].tolist() for g in groups if g != "Unknown"}
        
        summary = []
        for g, vals in group_data.items():
            summary.append({
                "group": g,
                "count": len(vals),
                "mean": round(float(np.mean(vals)), 2),
                "median": round(float(np.median(vals)), 2),
                "std": round(float(np.std(vals, ddof=1)), 2) if len(vals) > 1 else 0.0
            })
            
        # 6. Statistical Tests
        stats_res = {"test": "N/A", "p_value": 1.0, "significant": False}
        if len(group_data) == 2:
            g1, g2 = list(group_data.keys())
            if len(group_data[g1]) > 0 and len(group_data[g2]) > 0:
                stat, p_val = ranksums(group_data[g1], group_data[g2])
                stats_res = {
                    "test": "Wilcoxon Rank-Sum",
                    "stat": round(float(stat), 4),
                    "p_value": round(float(p_val), 4),
                    "significant": bool(p_val < 0.05)
                }
        elif len(group_data) > 2:
            try:
                H, p_val = kruskal(*group_data.values())
                stats_res = {
                    "test": "Kruskal-Wallis",
                    "stat": round(float(H), 4),
                    "p_value": round(float(p_val), 4),
                    "significant": bool(p_val < 0.05)
                }
                if p_val < 0.05:
                    dunn_res = sp.posthoc_dunn(df, val_col='engagement_rate', group_col='group')
                    dunn_list = []
                    cols = dunn_res.columns.tolist()
                    for i in range(len(cols)):
                        for j in range(i+1, len(cols)):
                            g1, g2 = cols[i], cols[j]
                            p_v = float(dunn_res.loc[g1, g2])
                            dunn_list.append({"group1": g1, "group2": g2, "p_value": round(p_v, 4), "significant": bool(p_v < 0.05)})
                    stats_res["dunn"] = dunn_list
            except: pass
            
        return {
            "summary": summary,
            "statistics": stats_res,
            "individual_data": data
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

@router.get("/engagement_plot")
async def get_engagement_plot(course_id: int, db: Session = Depends(get_db)):
    """
    Generate engagement distribution plot.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import seaborn as sns
        import io
        import base64
        import pandas as pd
        import numpy as np
        
        analysis = await get_engagement_analysis(course_id, db)
        if "error" in analysis: return analysis
        
        df = pd.DataFrame(analysis["individual_data"])
        # Filter out 'Unknown' groups for cleaner plot
        df = df[df["group"] != "Unknown"]
        
        if df.empty:
            return {"error": "No valid group data to plot"}
            
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Colors consistent with efficiency analysis
        groups = sorted(df["group"].unique())
        palette = sns.color_palette("Set2", n_colors=len(groups))
        
        sns.boxplot(x="group", y="engagement_rate", data=df, ax=ax, palette=palette, order=groups)
        sns.stripplot(x="group", y="engagement_rate", data=df, ax=ax, color='black', alpha=0.5, jitter=True, order=groups)
        
        stats = analysis["statistics"]
        title_color = 'red' if stats.get("significant") else 'black'
        ax.set_title(f"Image Engagement Rate Distribution\n({stats['test']} p={stats['p_value']:.4f})", 
                     color=title_color, fontweight='bold', fontsize=14)
        
        ax.set_ylabel("Engagement Rate (%)", fontweight='bold')
        ax.set_xlabel("Group", fontweight='bold')
        ax.grid(True, alpha=0.15, axis='y')
        
        # Add stats to X-labels
        new_labels = []
        for g in groups:
            s = next((item for item in analysis["summary"] if item["group"] == g), None)
            if s:
                label = f"{g}\n(n={s['count']})\nMean={s['mean']:.1f}%\nMed={s['median']:.1f}%"
                new_labels.append(label)
            else:
                new_labels.append(g)
        ax.set_xticklabels(new_labels)
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close(fig)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')
        
        return {
            "image": f"data:image/png;base64,{img_b64}",
            "analysis": analysis
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}
