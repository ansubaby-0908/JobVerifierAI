from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "your database URL here"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)