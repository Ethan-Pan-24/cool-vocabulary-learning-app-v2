from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

URSQLALCHEMY_DATABASE_URL = "sqlite:///./vocab_system_v2.db"

engine = create_engine(URSQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    enrollments = relationship("Enrollment", back_populates="user")
    quiz_results = relationship("QuizResult", back_populates="user")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text)
    group_names = Column(String) # Comma-separated, e.g. "A,B" or "Red,Blue,Green"
    stage_config = Column(Text, default="[]") # JSON: [{"name": "Stage 1", "count": 10}, ...]
    quiz_config = Column(Text, default="[]") # Google Forms style JSON
    quiz_time_limit = Column(Integer, default=5) # Minutes, 0 for unlimited
    is_deleted = Column(Boolean, default=False)
    
    vocabularies = relationship("Vocabulary", back_populates="course")
    enrollments = relationship("Enrollment", back_populates="course")

class Enrollment(Base):
    __tablename__ = "enrollments"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    group = Column(String) # Assigned group for this course
    
    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")

class Vocabulary(Base):
    __tablename__ = "vocabulary"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    word = Column(String, index=True)
    story = Column(Text)
    image_url = Column(String)
    audio_url = Column(String) 
    chinese_meaning = Column(String)
    group = Column(String, default="Common") # Matches one of the group_names or 'Common'
    stage = Column(String, default="Unassigned") # Explicit Stage Name
    is_image_enabled = Column(Boolean, default=True)
    is_audio_enabled = Column(Boolean, default=True)
    display_order = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    custom_distractors = Column(String) # Comma-separated
    
    course = relationship("Course", back_populates="vocabularies")

class QuizResult(Base):
    __tablename__ = "quiz_results"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    
    translation_score = Column(Float, default=0.0)
    sentence_score = Column(Float, default=0.0)
    nasa_tlx_score = Column(Float, default=0.0)
    nasa_details_json = Column(Text, default="{}") # JSON: {"mental": 50, ...}
    group = Column(String) # Snapshot of group used (e.g. "A", "B")
    is_deleted = Column(Boolean, default=False)
    
    learning_duration_seconds = Column(Float, default=0.0) # Total duration
    stage_timing_json = Column(Text, default="{}") # JSON: {"Stage 1": 120, "Stage 2": 90}
    section_stats = Column(Text, default="{}") # JSON: {"Translation": 80, "Sentence": 50, "Part A": 100}

    ai_scoring_json = Column(Text)
    open_ended_response = Column(Text)
    
    submitted_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="quiz_results")

class ImageInteraction(Base):
    __tablename__ = "image_interactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    image_url = Column(String)  # Full URL or relative path
    vocab_id = Column(Integer, ForeignKey("vocabulary.id"), nullable=True)  # If applicable
    action = Column(String)  # "like", "dislike", "view"
    timestamp = Column(DateTime, default=datetime.utcnow)
    context = Column(String, nullable=True)  # "learning", "quiz"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
