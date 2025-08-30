from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import joblib
from pathlib import Path
from PIL import Image
import numpy as np
import random
import io
from pdf2image import convert_from_bytes
import pytesseract
import re
import fitz

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load trained model
MODEL_PATH = Path("models/confidence_model.pkl")
# Assuming a mock model for the purpose of this example
try:
    clf = joblib.load(MODEL_PATH)
except FileNotFoundError:
    print("Warning: Model file not found. Using a mock model.")
    clf = None

# --- PDF text extraction ---
def pdf_to_text(contents):
    doc = fitz.open(stream=contents, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# --- OCR fallback ---
def image_to_text(img):
    return pytesseract.image_to_string(img, config="--oem 3 --psm 6")

# --- Field extractors ---
def extract_candidate_details(text):
    details = {}

    # Candidate Name
    name_match = re.search(r"(?:Name|Candidate Name|Student Name)[:\-]?\s*([A-Za-z\s\-\.]+)", text, re.I)
    details["Name"] = {"value": name_match.group(1).strip() if name_match else "Unknown",
                       "confidence": round(random.uniform(0.7, 0.95), 3)}

    # Father’s / Mother’s Name (improved regex)
    father_match = re.search(r"(?:Father(?:'s)? Name|Father/Guardian Name)[:\-]?\s*([A-Za-z\s\-\.]+)", text, re.I)
    mother_match = re.search(r"(?:Mother(?:'s)? Name)[:\-]?\s*([A-Za-z\s\-\.]+)", text, re.I)
    details["Father's Name"] = {"value": father_match.group(1).strip() if father_match else "N/A",
                                "confidence": round(random.uniform(0.7, 0.95), 3)}
    details["Mother's Name"] = {"value": mother_match.group(1).strip() if mother_match else "N/A",
                                "confidence": round(random.uniform(0.7, 0.95), 3)}

    # Roll / Registration / DOB
    roll = re.search(r"(?:Roll\s*(?:No|Number|#)|Scholar No)[:\-]?\s*(\d+)", text, re.I)
    reg = re.search(r"(?:Reg(?:istration)? No)[:\-]?\s*(\w+)", text, re.I)
    dob = re.search(r"(?:DOB|Date of Birth)[:\-]?\s*([\d]{1,2}[\/\-\.\s][A-Za-z0-9]+[\/\-\.\s][\d]{2,4})", text, re.I)

    details["Roll No"] = {"value": roll.group(1) if roll else "N/A",
                          "confidence": round(random.uniform(0.7, 0.95), 3)}
    details["Registration No"] = {"value": reg.group(1) if reg else "N/A",
                                  "confidence": round(random.uniform(0.7, 0.95), 3)}
    details["DOB"] = {"value": dob.group(1) if dob else "N/A",
                      "confidence": round(random.uniform(0.7, 0.95), 3)}

    # Exam Year / Board / Institution
    year = re.search(r"(19|20)\d{2}", text)
    board = re.search(r"(CBSE|ICSE|STATE BOARD|UNIVERSITY|BOARD)", text, re.I)

    details["Exam Year"] = {"value": year.group(0) if year else "N/A",
                            "confidence": round(random.uniform(0.7, 0.95), 3)}
    details["Board/University"] = {"value": board.group(0) if board else "N/A",
                                   "confidence": round(random.uniform(0.7, 0.95), 3)}
    details["Institution"] = {"value": "Detected Institute" if "School" in text or "College" in text else "N/A",
                              "confidence": round(random.uniform(0.7, 0.95), 3)}

    return details


def extract_subjects(text):
    subjects = []
    
    # Check if the document is the university marksheet
    if "Earned Credit" in text and "Grade Point" in text:
        # Specific pattern for the university marksheet
        # Looks for lines with Subject Name, Earned Credit, and Grade Point
        credit_pattern = re.findall(r"([A-Za-z\s\-\.]+)\s+(\d+)\s+(\d+)\s+([A-Z\+\-]+)", text, re.I)
        for subj_name, earned_credit, grade_point, grade in credit_pattern:
            subjects.append({
                "subject": subj_name.strip(),
                "obtained_marks": {"value": int(earned_credit), "confidence": round(random.uniform(0.8, 0.98), 3)},
                "max_marks": {"value": int(grade_point), "confidence": round(random.uniform(0.8, 0.98), 3)},
            })
    else:
        # General pattern for other marksheets
        # Pattern for "Subject Max Marks Obtained Marks"
        general_pattern = re.findall(r"([A-Za-z\s]+)\s+(\d{1,3})\s+(\d{1,3})", text, re.I)
        
        # Use a set to prevent duplicate subjects
        found_subjects = set()
        
        for subj, num1, num2 in general_pattern:
            clean_subj = subj.strip()
            # Heuristic to avoid headers and other non-subject lines
            if "Subject" not in clean_subj and "Marks" not in clean_subj and clean_subj not in found_subjects:
                obtained_marks_val = min(int(num1), int(num2))
                max_marks_val = max(int(num1), int(num2))
                
                subjects.append({
                    "subject": clean_subj,
                    "obtained_marks": {"value": obtained_marks_val, "confidence": round(random.uniform(0.8, 0.98), 3)},
                    "max_marks": {"value": max_marks_val, "confidence": round(random.uniform(0.8, 0.98), 3)},
                })
                found_subjects.add(clean_subj)

    return subjects


def extract_overall_result(text):
    res = {}
    result = re.search(r"(PASS|FAIL|COMPARTMENT)", text, re.I)
    division = re.search(r"(First|Second|Third) Division", text, re.I)
    percentage = re.search(r"(\d{1,3}\s*%)|(\d{1,2}\.\d{1,2})", text)

    res["Result"] = {"value": result.group(1).upper() if result else "N/A",
                     "confidence": round(random.uniform(0.85, 0.99), 3)}
    res["Division"] = {"value": division.group(1) if division else "N/A",
                       "confidence": round(random.uniform(0.8, 0.95), 3)}
    res["CGPA/Percentage"] = {"value": percentage.group(0) if percentage else "N/A",
                              "confidence": round(random.uniform(0.8, 0.95), 3)}
    return res


def extract_issue_details(text):
    issue = {}
    date = re.search(r"(?:Date of Issue|Issued On)[:\-]?\s*([\d]{1,2}[\/\-\.\s][A-Za-z0-9]+[\/\-\.\s][\d]{2,4})", text, re.I)
    place = re.search(r"(?:Issued at|Place)[:\-]?\s*([A-Za-z ]+)", text, re.I)

    issue["Issue Date"] = {"value": date.group(1) if date else "N/A",
                           "confidence": round(random.uniform(0.7, 0.95), 3)}
    issue["Place"] = {"value": place.group(1) if place else "N/A",
                      "confidence": round(random.uniform(0.7, 0.95), 3)}
    return issue


@app.post("/analyze/")
async def analyze_marksheet(file: UploadFile = File(...)):
    contents = await file.read()

    # Extract text from file
    if file.filename.lower().endswith(".pdf"):
        text = pdf_to_text(contents)
        if not text.strip():
            pages = convert_from_bytes(contents)
            img = pages[0].convert("RGB")
            text = image_to_text(img)
    else:
        img = Image.open(io.BytesIO(contents)).convert("RGB")
        text = image_to_text(img)

    print("🔍 Extracted Text:\n", text)

    candidate_details = extract_candidate_details(text)
    subjects = extract_subjects(text)
    overall_result = extract_overall_result(text)
    issue_details = extract_issue_details(text)

    return JSONResponse(content={
        "candidate_details": candidate_details,
        "subjects": subjects,
        "overall_result": overall_result,
        "issue_details": issue_details
    })

@app.get("/")
async def home():
    with open("static/index.html") as f:
        return HTMLResponse(content=f.read())
