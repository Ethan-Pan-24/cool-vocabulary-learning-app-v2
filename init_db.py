#!/usr/bin/env python3
"""Initialize the database with all required tables."""

from database import init_db

if __name__ == "__main__":
    print("🗄️  Initializing database...")
    init_db()
    print("✅ Database initialized successfully!")
    print("   Tables created: users, courses, enrollments, vocabulary, quiz_results, image_interactions")
