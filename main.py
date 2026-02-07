from fastapi import FastAPI, Request, Form, Response, Cookie, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from database import engine, get_db, init_db, User, Vocabulary, QuizResult, Course, Enrollment, ImageInteraction
import utils
import json
import random
import os
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv

load_dotenv() # Load variables from .env

app = FastAPI()
# Reload Trigger 3

# Session for OAuth - Environment variable used for production
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "fallback-secret-key"))

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

from utils import ADMIN_EMAILS

# Google OAuth Configuration
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@app.get("/login/google")
async def login_google(request: Request):
    redirect_uri = request.url_for('auth_google')
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google")
async def auth_google(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        if not user_info:
             # Try fetching if not in token
             user_info = await oauth.google.userinfo(token=token)
             
        email = user_info['email']
        
        # Check if user exists, else create
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Login (Set Cookie)
        response = RedirectResponse(url="/courses", status_code=303)
        if email in ADMIN_EMAILS:
             response = RedirectResponse(url="/admin/entry_choice", status_code=303)
             
        response.set_cookie(key="user_email", value=email)
        return response
        
    except Exception as e:
        print(f"OAuth Error: {e}")
        return RedirectResponse(url="/?error=OAuthFailed")

# Dependency to get user from cookie
from auth import get_current_user_req

# Dependency to get user from cookie - Moved to auth.py

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request, user: User = Depends(get_current_user_req)):
    if user:
        if user.is_admin:
            return RedirectResponse(url="/admin/entry_choice", status_code=303)
        return RedirectResponse(url="/courses", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Validated by Google or Admin Form
    
    # Case-insensitive admin check
    is_admin_login = email.lower() in [e.lower() for e in ADMIN_EMAILS]

    # Simple session cookie (In prod use secure signed cookies)
    response = RedirectResponse(url="/courses", status_code=status.HTTP_303_SEE_OTHER)
    
    if is_admin_login:
         response = RedirectResponse(url="/admin/entry_choice", status_code=status.HTTP_303_SEE_OTHER)
    
    response.set_cookie(key="user_email", value=email)
    return response

@app.get("/97110424", response_class=HTMLResponse)
async def secret_admin_login(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.get("/courses", response_class=HTMLResponse)
async def course_list(request: Request, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/")
    courses = db.query(Course).filter(Course.is_deleted == False).all()
    # Helper to check if user is enrolled
    user_course_ids = [e.course_id for e in user.enrollments]
    return templates.TemplateResponse("course_list.html", {"request": request, "courses": courses, "user_course_ids": user_course_ids, "is_admin": getattr(user, "is_admin", False)})

@app.get("/join/{course_id}")
async def join_course(course_id: int, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/")
    
    existing = db.query(Enrollment).filter(Enrollment.user_id == user.id, Enrollment.course_id == course_id).first()
    if existing:
        return RedirectResponse(url=f"/learn/{course_id}", status_code=303)
    
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return HTTPException(status_code=404, detail="Course not found")
        
    # Auto-Balancing Logic
    # 1. Parse group names
    group_names = [g.strip() for g in course.group_names.split(",")] if course.group_names else ["A", "B"]
    
    # 2. Count current enrollments per group
    # This query counts users in each group for this course
    group_counts = {}
    for g in group_names:
        count = db.query(Enrollment).filter(Enrollment.course_id == course_id, Enrollment.group == g).count()
        group_counts[g] = count
    
    # 3. Find group with min users
    min_count = min(group_counts.values())
    candidates = [g for g, c in group_counts.items() if c == min_count]
    assigned_group = random.choice(candidates)
    
    new_enrollment = Enrollment(user_id=user.id, course_id=course_id, group=assigned_group)
    db.add(new_enrollment)
    db.commit()
    
    return RedirectResponse(url=f"/learn/{course_id}", status_code=303)

@app.get("/admin/entry_choice", response_class=HTMLResponse)
async def admin_entry_choice(request: Request, user: User = Depends(get_current_user_req)):
    if not user or not user.is_admin:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("admin_entry.html", {"request": request})

@app.get("/admin/learner_view")
async def admin_learner_view(request: Request, user: User = Depends(get_current_user_req)):
    # Redirect admin to course list to choose like a learner
    if not user or not user.is_admin:
        return RedirectResponse(url="/")
    return RedirectResponse(url="/courses", status_code=303)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("user_email")
    return response

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    if not user or user.email not in ADMIN_EMAILS:
        return HTMLResponse(content="Unauthorized", status_code=401)
    
    courses = db.query(Course).filter(Course.is_deleted == False).all()
    # No longer loading all vocab here
    return templates.TemplateResponse("admin.html", {
        "request": request, 
        "courses": courses,
        "is_admin": True
    })

@app.get("/admin/course/{course_id}", response_class=HTMLResponse)
async def admin_course_detail(course_id: int, request: Request, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    # Legacy route: Redirect to new consolidated Content Manager
    return RedirectResponse(url=f"/admin/course/{course_id}/content_manager", status_code=303)

@app.get("/admin/course/{course_id}/quiz_editor", response_class=HTMLResponse)
async def admin_quiz_editor(course_id: int, request: Request, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    if not user or not user.is_admin:
        return RedirectResponse(url="/")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return HTMLResponse("Course not found", status_code=404)
        
    import json
    try:
        quiz_data = json.loads(course.quiz_config) if course.quiz_config else []
    except:
        quiz_data = []
        
    if not isinstance(quiz_data, list):
        quiz_data = []
        
    return templates.TemplateResponse("admin_quiz_editor.html", {
        "request": request, 
        "course": course,
        "quiz_data": quiz_data
    })

@app.get("/admin/course/{course_id}/content_manager", response_class=HTMLResponse)
async def admin_content_manager(course_id: int, request: Request, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    if not user or user.email not in ADMIN_EMAILS:
        return RedirectResponse(url="/")
        
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return RedirectResponse(url="/admin")

    vocab_list = db.query(Vocabulary).filter(Vocabulary.course_id == course_id).order_by(Vocabulary.display_order).all()
    
    # Parse stages
    import json
    try:
        raw_config = json.loads(course.stage_config) if course.stage_config else []
        # Support both List (legacy) and Dict (new)
        if isinstance(raw_config, list):
            stage_list = raw_config
        elif isinstance(raw_config, dict):
            # For admin list view, maybe merge all unique names? 
            # Or just show "Select Group to view stages"
            # For simplicity in list view, we might pick "Common" or first key
            # But actually content manager logic handles this better.
            # Let's just pass the raw object or a flattened list for now?
            # Actually admin_content_manager parses properly now.
            stage_list = [] # Placeholder, will be handled by JS
            if "Common" in raw_config: stage_list = raw_config["Common"]
            elif raw_config: stage_list = list(raw_config.values())[0]
    except:
        stage_list = []
        
    groups = [g.strip() for g in (course.group_names or "").split(",") if g.strip()]

    # To simplify JS, we pass all vocab and let JS filter
    vocab_data = []
    for v in vocab_list:
        vocab_data.append({
            "id": v.id,
            "word": v.word,
            "chinese_meaning": v.chinese_meaning,
            "story": v.story,          # Added
            "image_url": v.image_url,  # Added
            "audio_url": v.audio_url,  # Added
            "group": v.group,
            "stage": v.stage or "Unassigned",
            "display_order": v.display_order,
            "is_deleted": v.is_deleted,
            "custom_distractors": v.custom_distractors
        })

    return templates.TemplateResponse("admin_content_manager.html", {
        "request": request,
        "course": course,
        "vocab_list": vocab_data,
        "groups": groups,
        "stage_list": stage_list,
        "full_stage_config": raw_config 
    })

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, course_id: str = None, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    if not user or user.email not in ADMIN_EMAILS:
        return HTMLResponse(content="Unauthorized", status_code=401)

    # Fetch all courses for dropdown
    courses = db.query(Course).filter(Course.is_deleted == False).all()

    # Build Query
    query = db.query(QuizResult)
    
    current_course_id = None
    if course_id and course_id.strip().isdigit():
        current_course_id = int(course_id)
        query = query.filter(QuizResult.course_id == current_course_id)
    
    raw_results = query.filter(QuizResult.is_deleted == False).order_by(QuizResult.submitted_at.desc()).all()
    
    # Pass 1: Collect All Unique Metric Keys
    section_keys = set()
    timing_keys = set()
    nasa_keys = set()
    
    parsed_rows = []
    
    import json
    
    for r in raw_results:
        # User/Course info
        u = db.query(User).filter(User.id == r.user_id).first()
        email = u.email if u else "Deleted User"
        c = db.query(Course).filter(Course.id == r.course_id).first()
        course_name = c.name if c else "Unknown Course"
        course_name = c.name if c else "Unknown Course"
        enrollment = db.query(Enrollment).filter(Enrollment.user_id == r.user_id, Enrollment.course_id == r.course_id).first()
        
        # Group Logic: 1. Persisted (New) 2. Enrollment (Old) 3. Dash
        group = getattr(r, 'group', None) 
        if not group:
             group = enrollment.group if enrollment else "-"
        
        from datetime import timedelta
        local_time = r.submitted_at + timedelta(hours=8) if r.submitted_at else None
        
        row_data = {
            "meta": {
                "result_id": r.id,
                "user_id": r.user_id,
                "email": email,
                "course_name": course_name,
                "group": group,
                "submitted_at": local_time.strftime("%Y-%m-%d %H:%M") if local_time else "-"
            },
            "sections": {},
            "timings": {},
            "nasa": {}
        }

        # 2. Split Data for Details View
        row_data["timings_learning"] = {}
        row_data["timings_quiz"] = {} 
        row_data["scores_sections"] = {}
        
        # --- TIMINGS (Learning Stages) ---
        try:
            timings = json.loads(r.stage_timing_json) if r.stage_timing_json else {}
            quiz_time = 0
            
            # Identify Allowed Stages from Config
            allowed_stages = set()
            allowed_stage_map = {} # Maps index to title
            try:
                sc = json.loads(c.stage_config) if c and c.stage_config else []
                current_stage_list = []
                if isinstance(sc, dict): 
                    # Use User's Group Config
                    current_stage_list = sc.get(group, sc.get("Common", []))
                elif isinstance(sc, list):
                    current_stage_list = sc
                
                for idx, s in enumerate(current_stage_list):
                    t = s.get('name', s.get('title', f'Stage {idx}')) if isinstance(s, dict) else str(s)
                    allowed_stages.add(t)
                    allowed_stage_map[idx] = t
            except: pass
            
            # Process Timing Keys
            for k, v in timings.items():
                if k == "Quiz":
                    quiz_time = v
                    continue
                elif k == "Learning Total":
                    continue
                
                # Resolve Name
                # 1. Exact Match -> Use it
                # 2. Key is Index ("0", "1") -> Map to Config Title
                # 3. Else -> Use as is (Raw)
                
                final_key = None
                
                if k in allowed_stages:
                     final_key = k
                elif k.isdigit():
                    try:
                        idx = int(k)
                        if idx in allowed_stage_map:
                             final_key = allowed_stage_map[idx]
                    except: pass
                
                # Strict Filtering: Display ONLY if we resolved it to a valid config name
                if final_key:
                    row_data["timings_learning"][final_key] = int(v)
            
            # Total Timings for Main Table
            timing_keys.add("Learning Total")
            # Recalculate Total based on VISIBLE stages only (User Request)
            visible_total = sum(row_data["timings_learning"].values())
            row_data["timings"]["Learning Total"] = visible_total
            
            timing_keys.add("Quiz Total")
            row_data["timings"]["Quiz Total"] = int(quiz_time)
            
            # Quiz Timings for Detail View
            row_data["timings_quiz"]["Total Quiz Time"] = int(quiz_time)
            
        except: pass
        
        # --- SECTIONS (Quiz Scores) ---
        try:
             sections = json.loads(r.section_stats) if r.section_stats else {}
             # Legacy Fallback
             if not sections and r.translation_score is not None:
                sections = {"Legacy Trans": float(r.translation_score), "Legacy Sent": float(r.sentence_score)}
             
             total_score = 0
             count = 0
             for k, v in sections.items():
                 row_data["scores_sections"][k] = v
                 try:
                     total_score += float(v)
                     count += 1
                 except: pass
             
             # Add Average Score to Main Table
             if count > 0:
                 avg = round(total_score / count, 1)
                 section_keys.add("Average Score")
                 row_data["sections"]["Average Score"] = avg
                 
        except: pass
        
        # 3. NASA Details (6 Items)
        try:
            nasa_det = json.loads(r.nasa_details_json) if r.nasa_details_json else {}
            if not nasa_det and r.nasa_tlx_score:
                 # Fallback if no details
                 nasa_det = {"Average": r.nasa_tlx_score}
            for k, v in nasa_det.items():
                nasa_keys.add(k.capitalize())
                row_data["nasa"][k.capitalize()] = v
        except: pass
        
        # --- QUIZ RESPONSES (Per-Question) ---
        try:
             row_data["quiz_responses"] = json.loads(r.open_ended_response) if r.open_ended_response else []
        except:
             row_data["quiz_responses"] = []
             
        parsed_rows.append(row_data)

    # Sort Keys for consistent columns
    sorted_sections = sorted(list(section_keys))
    sorted_timings = sorted(list(timing_keys)) # "Total Time" included
    # Ensure standard NASA order if possible
    nasa_order = ["Mental", "Physical", "Temporal", "Performance", "Effort", "Frustration"]
    sorted_nasa = [k for k in nasa_order if k in nasa_keys] + sorted([k for k in nasa_keys if k not in nasa_order])

    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "results": parsed_rows,
        "headers": {
            "sections": sorted_sections,
            "timings": sorted_timings,
            "nasa": sorted_nasa
        },
        "courses": courses,
        "current_course_id": current_course_id,
        "is_admin": True
    })

from admin_api import router as admin_router
app.include_router(admin_router)

# --- LEARNER ROUTES ---

@app.get("/learn/{course_id}", response_class=HTMLResponse)
async def learn_page(course_id: int, request: Request, stage_index: int = 0, preview_group: str = None, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/")
    
    is_admin = getattr(user, "is_admin", False)
    group = "A" # Default fallbacks
    
    enrollment = db.query(Enrollment).filter(Enrollment.user_id == user.id, Enrollment.course_id == course_id).first()
    
    # Preview Logic
    if is_admin and preview_group:
        group = preview_group
    elif enrollment:
        group = enrollment.group
    else:
        # Not enrolled and not previewing as admin
        return RedirectResponse(url="/courses")

    # Stage Logic
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course or course.is_deleted:
        raise HTTPException(status_code=404, detail="Course not found")

    import json
    has_config = False
    try:
        if course.stage_config and len(str(course.stage_config)) > 2:
             has_config = True
        raw_config = json.loads(course.stage_config) if course.stage_config else []
    except:
        raw_config = []
    
    stages = []
    # Determine which stage list to use based on Group
    if isinstance(raw_config, list):
        stages = raw_config # Legacy support
        if not raw_config and has_config: pass # Empty list from config
    elif isinstance(raw_config, dict):
        # Strict lookup: If config exists, look for group. 
        # If group missing, fallback to "Common". 
        # If "Common" missing, then empty list (don't fallback to 'all vocab' legacy mode)
        stages = raw_config.get(group, raw_config.get("Common", []))


    current_stage_name = "Full List"
    is_last_stage = True
    next_stage_index = -1
    
    # 1. Determine Current Stage Info
    if stages:
        # Validate index
        if stage_index < 0: stage_index = 0
        if stage_index >= len(stages): stage_index = len(stages) - 1
        
        current_stage = stages[stage_index]
        current_stage_name = current_stage.get('name', f"Stage {stage_index + 1}")
        
        # Navigation
        if stage_index < len(stages) - 1:
            is_last_stage = False
            next_stage_index = stage_index + 1
    
    # 2. Fetch Filtered Vocab
    if stages:
         # Query for THIS stage
         vocab_subset = db.query(Vocabulary).filter(
            Vocabulary.course_id == course_id,
            or_(Vocabulary.group == 'Common', Vocabulary.group == group),
            Vocabulary.stage == current_stage_name,
            Vocabulary.is_deleted == False
        ).order_by(Vocabulary.display_order).all()
    elif has_config:
        # Config exists (empty list or dict with empty list) -> Show NOTHING (Empty Stage)
        vocab_subset = []
    else:
        # Fallback to everything if no stages defined (Legacy Mode)
        vocab_subset = db.query(Vocabulary).filter(
            Vocabulary.course_id == course_id,
            or_(Vocabulary.group == 'Common', Vocabulary.group == group),
            Vocabulary.is_deleted == False
        ).order_by(Vocabulary.display_order).all()

    # Check if quiz taken
    has_result = db.query(QuizResult).filter(QuizResult.user_id == user.id, QuizResult.course_id == course_id).first() is not None
    is_completed = has_result and not is_admin and not preview_group

    # Parse available groups for Admin Dropdown
    all_groups = [g.strip() for g in (course.group_names or "").split(",") if g.strip()]
    if not all_groups: all_groups = ["A", "B"]

    return templates.TemplateResponse("learn.html", {
        "all_groups": all_groups,
        "request": request, 
        "vocab_list": vocab_subset, 
        "course_id": course_id,
        "is_admin": is_admin,
        "group": group,
        "is_completed": is_completed,
        "current_stage_name": current_stage_name,
        "stage_index": stage_index,
        "is_last_stage": is_last_stage,
        "next_stage_index": next_stage_index,
        "preview_group": preview_group # Pass to template to persist links
    })

@app.get("/quiz/{course_id}", response_class=HTMLResponse)
async def quiz_page(course_id: int, request: Request, preview_group: str = None, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/")
    
    is_admin = getattr(user, "is_admin", False)
    group = "A"

    enrollment = db.query(Enrollment).filter(Enrollment.user_id == user.id, Enrollment.course_id == course_id).first()
    
    if is_admin and preview_group:
        group = preview_group
    elif enrollment:
        group = enrollment.group
    else:
        return RedirectResponse(url="/courses")

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course or course.is_deleted:
        return RedirectResponse(url="/courses")
    quiz_config = course.quiz_config if course and course.quiz_config else "[]"
    
    # --- LEGACY VOCAB LOGIC (Fallback) ---
    vocab_list = db.query(Vocabulary).filter(
        Vocabulary.course_id == course_id,
        or_(Vocabulary.group == 'Common', Vocabulary.group == group),
        Vocabulary.is_deleted == False
    ).order_by(Vocabulary.display_order).all()
    
    # For MCQ options, we can shuffle or just pick some distractors
    all_meanings = [v.chinese_meaning for v in vocab_list]
    
    processed_vocab = []
    import random
    for v in vocab_list:
        options = []
        if v.custom_distractors and len(v.custom_distractors.strip()) > 0:
            # Use Custom Distractors
            raw_distractors = [d.strip() for d in v.custom_distractors.split(",") if d.strip()]
            distractors = random.sample(raw_distractors, min(len(raw_distractors), 3))
            options = distractors + [v.chinese_meaning]
            random.shuffle(options)
        else:
            # Fallback to Random Distractors
            pool = [m for m in all_meanings if m != v.chinese_meaning]
            distractors = random.sample(pool, min(len(pool), 3)) if pool else []
            options = distractors + [v.chinese_meaning]
            random.shuffle(options)
            
        processed_vocab.append({
            "id": v.id,
            "word": v.word,
            "image_url": v.image_url,
            "options": options
        })
    
    # Parse available groups for Admin Dropdown
    all_groups = [g.strip() for g in (course.group_names or "").split(",") if g.strip()]
    if not all_groups: all_groups = ["A", "B"]

    return templates.TemplateResponse("quiz.html", {
        "all_groups": all_groups,
        "request": request, 
        "vocab_list": processed_vocab, 
        "course_id": course_id,
        "quiz_config": quiz_config, # Pass the JSON config
        "quiz_time_limit": course.quiz_time_limit,
        "preview_group": preview_group,
        "group": group,
        "is_admin": is_admin
    })

@app.post("/submit_quiz/{course_id}")
async def submit_quiz(course_id: int, request: Request, preview_group: str = None, user: User = Depends(get_current_user_req), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/")
    
    is_admin = getattr(user, 'is_admin', False)
    group = "A" # Default

    enrollment = db.query(Enrollment).filter(Enrollment.user_id == user.id, Enrollment.course_id == course_id).first()
    
    # Preview Bypass Logic
    if is_admin and preview_group:
         group = preview_group
    elif enrollment:
         group = enrollment.group
    else:
         if is_admin:
             # Admin taking quiz without preview group? Default to A
             group = "A"
         else:
             return RedirectResponse(url="/courses")
    
    form_data = await request.form()
    
    course = db.query(Course).filter(Course.id == course_id).first()
    # Check for Dynamic Mode
    import json
    is_dynamic = False
    config = []
    if course and course.quiz_config and course.quiz_config != "[]":
        try:
           config = json.loads(course.quiz_config)
           if len(config) > 0: is_dynamic = True
        except: pass

    # ... (form_data retrieved again? remove duplicate) ...
    # Removed 2nd await request.form()
    
    trans_score = 0
    sentence_score = 0
    ai_results_log = {}
    section_stats = {} # New: Breakdown

    if is_dynamic:
        # --- DYNAMIC SCORING ---
        total_q = 0
        correct_q = 0.0
        
        # Section Tracking
        current_section = "General"
        section_accumulator = {}
        quiz_details_log = [] # New: Track Per-Question Details
        
        for block in config:
            # Detect Section Header
            if block.get('block_type') in ['header', 'section_header', 'section']:
                current_section = block.get('title') or block.get('content') or "Section"
                
            if block.get('block_type') == 'question':
                # Init Section Accumulator
                if current_section not in section_accumulator:
                    section_accumulator[current_section] = {"total": 0, "correct": 0}

                total_q += 1
                section_accumulator[current_section]["total"] += 1
                
                q_id = block.get('id')
                q_text = block.get('content') or block.get('title') or block.get('text') or block.get('label', 'Question')
                user_ans = form_data.get(f"q_{q_id}") 
                
                corrects = block.get('correct_answers', [])
                if not corrects and block.get('correct_answer'):
                     corrects = [block.get('correct_answer')]
                
                # Check correctness
                is_correct = False
                user_vals = []
                current_q_score = 0
                
                if block.get('type') == 'checkboxes':
                     user_vals = form_data.getlist(f"q_{q_id}")
                     user_ans = ", ".join(user_vals) # For display
                     if set(user_vals) == set(corrects): 
                         is_correct = True
                         current_q_score = 1
                elif block.get('type') == 'sentence':
                     # AI Scoring for Open Ended Sentences
                     target_word = block.get('word', 'Unknown Word')
                     target_story = block.get('story', '')
                     target_image = block.get('image_url') or block.get('image')
                     target_meaning = block.get('meaning', '')
                     
                     if user_ans:
                         ai_result = utils.score_sentence_ai(
                             target_word, 
                             user_ans, 
                             target_story, 
                             target_meaning, 
                             target_image
                         )
                         score_val = ai_result.get("total_average", 0)
                         current_q_score = float(score_val)
                         # Consider a score >= 3 as "Correct" for binary stats
                         if score_val >= 3.0: is_correct = True
                         
                         correct_q += (score_val / 5.0) # Normalizing 0-5 to 0-1
                         section_accumulator[current_section]["correct"] += (score_val / 5.0)
                         
                         # Log the detailed AI result for this question
                         ai_results_log[f"q_{q_id}"] = ai_result
                else:
                     if user_ans in corrects:
                         is_correct = True
                         current_q_score = 1
                
                if not corrects and block.get('type') != 'sentence': 
                    # No correct answer defined? Skip scoring but log it
                    pass
                else:
                     if is_correct and block.get('type') != 'sentence':
                        correct_q += 1
                        section_accumulator[current_section]["correct"] += 1
                
                # Log Detail
                quiz_details_log.append({
                    "section": current_section,
                    "question": q_text,
                    "user_answer": str(user_ans) if user_ans is not None else "",
                    "correct_answer": ", ".join(corrects) if corrects else (f"AI Comment: {ai_result.get('comment','')}" if block.get('type')=='sentence' else ""),
                    "is_correct": is_correct,
                    "score": current_q_score
                })
        
        if total_q > 0:
            trans_score = int((correct_q / total_q) * 100)
            
        # Compile Section Stats (Percentage 0-100)
        for sec, stats in section_accumulator.items():
            if stats["total"] > 0:
                section_stats[sec] = int((stats["correct"] / stats["total"]) * 100)
            else:
                section_stats[sec] = 0
                
        # Store Log in open_ended_response (or ai_scoring_json)
        # Using open_ended_response as a container for this Quiz Log
        user_response_json = json.dumps(quiz_details_log)
    else:
        # --- LEGACY SCORING ---
        vocab_list = db.query(Vocabulary).filter(
            Vocabulary.course_id == course_id,
            or_(Vocabulary.group == 'Common', Vocabulary.group == group),
            Vocabulary.is_deleted == False
        ).all()

        for v in vocab_list:
            ans = form_data.get(f"translation_{v.id}")
            if ans == v.chinese_meaning:
                trans_score += 1
            
            sentence = form_data.get(f"sentence_{v.id}")
            if sentence:
                ai_result = utils.score_sentence_ai(v.word, sentence, v.story, v.chinese_meaning, v.image_url)
                sentence_score += ai_result.get("total_average", 0)
                ai_results_log[v.word] = ai_result
                
        # Calculate Legacy Section Stats
        vocab_len = len(vocab_list)
        if vocab_len > 0:
            section_stats["Translation"] = int((trans_score / vocab_len) * 100)
            # Sentence max is 5 per word
            section_stats["Sentence"] = int((sentence_score / (vocab_len * 5)) * 100)
        else:
            section_stats["Translation"] = 0
            section_stats["Sentence"] = 0

    # NASA TLX 6-items
    nasa_mental = float(form_data.get("nasa_mental", 0))
    nasa_physical = float(form_data.get("nasa_physical", 0))
    nasa_temporal = float(form_data.get("nasa_temporal", 0))
    nasa_performance = float(form_data.get("nasa_performance", 0))
    nasa_effort = float(form_data.get("nasa_effort", 0))
    nasa_frustration = float(form_data.get("nasa_frustration", 0))
    
    nasa_avg = (nasa_mental + nasa_physical + nasa_temporal + nasa_performance + nasa_effort + nasa_frustration) / 6.0
    
    nasa_details = {
        "mental": nasa_mental,
        "physical": nasa_physical,
        "temporal": nasa_temporal,
        "performance": nasa_performance,
        "effort": nasa_effort,
        "frustration": nasa_frustration
    }
    
    learning_duration = float(form_data.get("learning_duration", 0))
    stage_timing_raw = form_data.get("stage_timing_json", "{}")
    
    # Process Stage Timing: Map Index -> Name
    import json
    try:
        timings = json.loads(stage_timing_raw)
        mapped_timings = {}
        
        # Load Config
        server_stages = []
        if course.stage_config:
            try:
                server_stages = json.loads(course.stage_config)
            except: pass
            
        for k, v in timings.items():
            # k is usually string "0", "1"... or "Stage 1" (Legacy)
            idx = int(k) if k.isdigit() else -1
            
            # Smart Naming Logic
            if idx != -1:
                # Digital Index -> Look up config
                stage_name = f"Stage {k}" # Default Fallback
                if 0 <= idx < len(server_stages):
                    stage_name = server_stages[idx].get('title', stage_name)
            else:
                # Non-digital Key (Already named)
                stage_name = k 
            
            # Special Keys
            if k == "Quiz": stage_name = "Quiz"
            elif k == "test_intro": stage_name = "Test Intro"
            elif idx != -1 and not (0 <= idx < len(server_stages)):
                # Filter out numeric keys that are OUT OF BOUNDS of current config
                # e.g. "Stage 5" when only 2 stages exist
                continue 
                
            mapped_timings[stage_name] = v
            
        stage_timing_json = json.dumps(mapped_timings)
    except:
        stage_timing_json = stage_timing_raw # Fallback

    
    # Save result
    user_response_json = locals().get('user_response_json', '{}')
    new_res = QuizResult(
        user_id=user.id,
        course_id=course_id,
        translation_score=float(trans_score),
        sentence_score=float(sentence_score),
        nasa_tlx_score=nasa_avg,
        nasa_details_json=json.dumps(nasa_details),
        learning_duration_seconds=learning_duration,
        stage_timing_json=stage_timing_json,
        ai_scoring_json=json.dumps(ai_results_log, ensure_ascii=False),
        section_stats=json.dumps(section_stats, ensure_ascii=False),
        open_ended_response=user_response_json,
        group=group # Persist the group choice (Admin Preview or Enrolled)
    )
    db.add(new_res)
    db.commit()
    
    # RETURN RESPONSE
    link = "/logout"
    link_text = "Logout"
    msg = "Quiz Submitted! Thank you for participating."
    
    if is_admin and preview_group:
        link = f"/learn/{course_id}?preview_group={preview_group}"
        link_text = f"Back to Preview ({preview_group})"
        msg = f"Preview Submitted! Score: {trans_score}% (Dynamic) or {trans_score}/{sentence_score} (Legacy)"

    return templates.TemplateResponse("message.html", {
        "request": request, 
        "message": msg,
        "link": link,
        "link_text": link_text,
        "is_admin": is_admin
    })

@app.post("/api/image_interaction")
async def track_image_interaction(
    image_url: str = Form(...),
    action: str = Form(...),  # "like", "dislike", "view"
    course_id: int = Form(...),
    vocab_id: int = Form(None),
    context: str = Form(None),
    user: User = Depends(get_current_user_req),
    db: Session = Depends(get_db)
):
    # Validation
    if action not in ["like", "dislike", "view"]:
        raise HTTPException(400, "Invalid action")
    
    # For like/dislike, check if user already has an interaction
    if action in ["like", "dislike"]:
        existing = db.query(ImageInteraction).filter(
            ImageInteraction.user_id == user.id,
            ImageInteraction.image_url == image_url,
            ImageInteraction.action.in_(["like", "dislike"])
        ).first()
        
        if existing:
            # Update existing
            existing.action = action
            existing.timestamp = func.now()
            existing.course_id = course_id
            existing.vocab_id = vocab_id
            existing.context = context
        else:
            # Create new
            new_interaction = ImageInteraction(
                user_id=user.id,
                course_id=course_id,
                image_url=image_url,
                vocab_id=vocab_id,
                action=action,
                context=context
            )
            db.add(new_interaction)
    else:
        # For views, always create new record
        new_interaction = ImageInteraction(
            user_id=user.id,
            course_id=course_id,
            image_url=image_url,
            vocab_id=vocab_id,
            action=action,
            context=context
        )
        db.add(new_interaction)
    
    db.commit()
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    # For production deployment behind reverse proxy (nginx/caddy)
    # The proxy handles HTTPS and forwards to this port
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
