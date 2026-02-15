#!/usr/bin/env python3
"""
Complete Database Cleanup Script
Deletes ALL data from the database including users.
"""

from database import SessionLocal, Course, Vocabulary, Enrollment, QuizResult, ImageInteraction, ImageRating, User

def clear_all_data(delete_users=True):
    """Delete all data from the database."""
    db = SessionLocal()
    
    try:
        print("Starting database cleanup...")
        
        # Delete in order to respect foreign key constraints
        print("Deleting ImageRatings...")
        count = db.query(ImageRating).delete()
        print(f"  Deleted {count} image ratings")
        
        print("Deleting ImageInteractions...")
        count = db.query(ImageInteraction).delete()
        print(f"  Deleted {count} image interactions")
        
        print("Deleting QuizResults...")
        count = db.query(QuizResult).delete()
        print(f"  Deleted {count} quiz results")
        
        print("Deleting Enrollments...")
        count = db.query(Enrollment).delete()
        print(f"  Deleted {count} enrollments")
        
        print("Deleting Vocabulary...")
        count = db.query(Vocabulary).delete()
        print(f"  Deleted {count} vocabulary items")
        
        print("Deleting Courses...")
        count = db.query(Course).delete()
        print(f"  Deleted {count} courses")
        
        if delete_users:
            print("Deleting Users...")
            count = db.query(User).delete()
            print(f"  Deleted {count} users")
        
        db.commit()
        print("\n✅ All data deleted successfully!")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during deletion: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE COMPLETE CLEANUP")
    print("=" * 60)
    print("\nThis will DELETE ALL DATA including:")
    print("  - All users")
    print("  - All courses")
    print("  - All vocabulary")
    print("  - All quiz results")
    print("  - All enrollments")
    print("  - All image interactions and ratings")
    print("\n" + "=" * 60)
    
    # Execute the cleanup
    success = clear_all_data(delete_users=True)
    
    if success:
        print("\nDatabase is now empty and ready for fresh data.")
    else:
        print("\nCleanup failed. Please check errors above.")
