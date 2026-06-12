from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from database import SessionLocal
from model import User, Feedback, Job
import pickle
import re
import os

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ================= REGISTER =================
@app.post("/register")
def register(name: str, email: str, password: str, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already exists")

    new_user = User(
        name=name,
        email=email,
        password=password,
        role="user"
    )

    db.add(new_user)
    db.commit()

    return {"message": "Registered successfully"}

# ================= LOGIN =================
@app.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):

    user = db.query(User).filter(User.email == email).first()

    if not user or user.password != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "message": "Login successful",
        "role": user.role,
        "email": user.email
    }

#===================FEEDBACK===============================
@app.post("/feedback")
def submit_feedback(email: str, message: str, db: Session = Depends(get_db)):

    # Check if user exists
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Save feedback
    fb = Feedback(
        email=email,
        message=message
    )

    db.add(fb)
    db.commit()

    return {"message": "Feedback submitted successfully"}

@app.get("/admin/feedback")
def get_feedback(db: Session = Depends(get_db)):

    feedbacks = db.query(Feedback).all()
    result = []

    for fb in feedbacks:
        user = db.query(User).filter(User.email == fb.email).first()

        result.append({
            "id": fb.id,
            "name": user.name if user else "Unknown",
            "email": fb.email,
            "message": fb.message
        })

    return result

@app.get("/admin/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users

@app.get("/admin/jobs")
def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).all()
    return jobs

@app.get("/admin/stats")
def get_stats(db: Session = Depends(get_db)):

    user_count = db.query(User).count()
    job_count = db.query(Job).count()
    feedback_count = db.query(Feedback).count()

    return {
        "users": user_count,
        "jobs": job_count,
        "feedback": feedback_count
    }

@app.get("/admin/job-stats")
def job_stats(db: Session = Depends(get_db)):

    jobs = db.query(Job).all()

    fake = 0
    genuine = 0
    caution = 0

    for job in jobs:
        if "Scam" in job.result:
            fake += 1
        elif "Genuine" in job.result:
            genuine += 1
        else:
            caution += 1

    return {
        "fake": fake,
        "genuine": genuine,
        "caution": caution
    }

# ====LOAD MODEL ==
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

model_path = os.path.join(BASE_DIR, "model", "fake_job_model.pkl")
vectorizer_path = os.path.join(BASE_DIR, "model", "tfidf_vectorizer.pkl")

model = pickle.load(open(model_path, "rb"))
vectorizer = pickle.load(open(vectorizer_path, "rb"))

# -- CLEAN TEXT -
def clean_text(text):
    text = text.lower()
    text = re.sub(r'<.*?>', '', text)
    text = re.sub(r'[^a-zA-Z]', ' ', text)
    return " ".join(text.split())

# -------- RULES --------
scam_keywords = [
    "earn money fast",
    "work from home",
    "no experience required",
    "investment required",
    "limited seats",
    "urgent hiring",
    "click here",
    "pay registration fee",
    "easy money",
    "guaranteed income"
]

def rule_based_score(text):
    text = text.lower()
    return sum(1 for keyword in scam_keywords if keyword in text)

@app.get("/")
def home():
    return {"message": "Fake Job Detector API is running"}


@app.post("/predict")
def predict(data: dict, db: Session = Depends(get_db)):

    text = data.get("description", "")

    cleaned = clean_text(text)
    vector = vectorizer.transform([cleaned])

    ml_pred = model.predict(vector)[0]
    ml_prob = model.predict_proba(vector)[0]

    rule_score = rule_based_score(text)

    # DECISION LOGIC
    if rule_score >= 2:
        result = "Scam (Rule-Based)"
        confidence = 0.9

    elif ml_pred == 1:
        result = "Scam (ML)"
        confidence = float(ml_prob[1])

    elif rule_score == 1:
        result = "Caution"
        confidence = 0.5

    else:
        result = "Genuine"
        confidence = float(ml_prob[0])

    #  SAVE TO DATABASE
    job = Job(
        description=text,
        result=result,
        confidence=confidence
    )

    db.add(job)
    db.commit()

    # RETURN RESPONSE
    return {
        "result": result,
        "confidence": confidence
    }
    
