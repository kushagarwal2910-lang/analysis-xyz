from fastapi import FastAPI, Request, File, UploadFile, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
import shutil
import os
import uuid
from .utils import process_data_and_generate_report

import os

# Get base directory of the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/about")
async def read_about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/privacy")
async def read_privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})

@app.get("/contact")
async def read_contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

@app.get("/terms")
async def read_terms(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})

@app.get("/cookies")
async def read_cookies(request: Request):
    return templates.TemplateResponse("cookies.html", {"request": request})

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="No file sent")
    
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in [".csv", ".xlsx", ".pdf"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Only CSV, Excel, and PDF allowed.")

    # Save temp file
    # Vercel only allows writing to /tmp
    temp_dir = "/tmp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}{ext}")
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Pass BASE_DIR to utils (though we won't write to it anymore)
        report_html = await run_in_threadpool(process_data_and_generate_report, temp_path, ext, BASE_DIR)
        return JSONResponse(content={
            "status": "success", 
            "report_html": report_html
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)
    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
@app.post("/demo")
async def demo_analysis():
    try:
        sample_path = os.path.join(BASE_DIR, "sample_data.csv")
        if not os.path.exists(sample_path):
             raise HTTPException(status_code=404, detail="Sample data not found")
        
        # Process the sample file
        report_html = await run_in_threadpool(process_data_and_generate_report, sample_path, ".csv", BASE_DIR)
        
        return JSONResponse(content={
            "status": "success", 
            "report_html": report_html
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)
    finally:
        # No cleanup needed for sample file
        pass
