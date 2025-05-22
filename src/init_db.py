from database.sqlite import engine, Base
from models.logs import RawLog, JobAnalytics, TaskAnalytics

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_db()
