import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from database import (
    init_db,
    save_report,
    get_all_reports,
    get_chart_data,
    delete_report,
    get_report_detail,
    get_reports_with_facts,
    save_report_facts,
    list_patients,
    create_patient,
    ensure_default_patient,
)
from pdf_processor import extract_report_data

load_dotenv()

app = FastAPI(title="血常规 PDF 分析器")

# 初始化数据库
init_db()

API_KEY = os.getenv("ZHIPUAI_API_KEY")


@app.get("/")
async def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/api/patients")
async def get_patients():
    # 确保默认病人存在，避免前端初次打开没有可选项
    ensure_default_patient()
    return list_patients()


@app.post("/api/patients")
async def add_patient(
    name: str = Form(...),
    sex: Optional[str] = Form(None),
    birthday: Optional[str] = Form(None),
):
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="病人姓名不能为空")
    pid = create_patient(name.strip(), sex=sex, birthday=birthday)
    return {"id": pid}


@app.post("/api/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    patient_id: Optional[int] = Form(None),
    report_type: str = Form("cbc"),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")

    if not API_KEY:
        raise HTTPException(status_code=500, detail="未配置 ZHIPUAI_API_KEY")

    pdf_bytes = await file.read()

    try:
        result = extract_report_data(pdf_bytes, API_KEY, report_type=report_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 解析失败: {str(e)}")

    report_date = result.get("date") or datetime.now().strftime("%Y-%m-%d")
    items = result.get("items", [])
    facts = result.get("facts", [])

    if not items and not facts:
        raise HTTPException(status_code=400, detail="未能从 PDF 中提取到可用数据")

    report_id = save_report(file.filename, report_date, items, patient_id=patient_id, report_type=report_type)
    if facts:
        save_report_facts(report_id, facts)

    return {
        "report_id": report_id,
        "date": report_date,
        "item_count": len(items),
        "fact_count": len(facts),
        "items": items,
        "facts": facts,
    }


@app.get("/api/reports")
async def list_reports(
    patient_id: Optional[int] = Query(None),
    report_type: Optional[str] = Query(None),
):
    reports = get_all_reports(patient_id=patient_id, report_type=report_type)
    for r in reports:
        detail = get_report_detail(r["id"])
        r["items"] = detail["items"] if detail else []
    return reports


@app.get("/api/chart-data")
async def chart_data(
    patient_id: Optional[int] = Query(None),
    report_type: Optional[str] = Query(None),
):
    return get_chart_data(patient_id=patient_id, report_type=report_type)


@app.get("/api/reports/{report_id}")
async def report_detail(report_id: int):
    detail = get_report_detail(report_id)
    if not detail:
        raise HTTPException(status_code=404, detail="报告不存在")
    return detail


@app.get("/api/timeline")
async def timeline(
    patient_id: Optional[int] = Query(None),
    report_type: Optional[str] = Query(None),
):
    return get_reports_with_facts(patient_id=patient_id, report_type=report_type)


@app.delete("/api/reports/{report_id}")
async def remove_report(report_id: int):
    if not delete_report(report_id):
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"ok": True}


# 静态文件
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
