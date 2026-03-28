import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from PIL import Image

from app.pipeline.detection import run_detection
from app.pipeline.segmentation import run_segmentation
from app.pipeline.style_extraction import run_style_extraction
from app.pipeline.layout import run_layout_reconstruction
from app.pipeline.codegen import run_codegen
from app.pipeline.artifacts import make_output_dir, save_ast, save_code, save_detection_debug, resize_to_perceived

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    target: str = Form("react_native"),
):
    suffix = Path(file.filename).suffix or ".png"
    stem = f"{Path(file.filename).stem}_{uuid.uuid4().hex[:8]}"
    image_path = UPLOADS_DIR / f"{stem}{suffix}"
    with image_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    output_dir = make_output_dir(stem)

    with Image.open(image_path) as img:
        width, height = img.size

    ast, perceived_w, perceived_h = await run_detection(image_path, (width, height))
    resized_path = resize_to_perceived(image_path, perceived_w, perceived_h, output_dir)
    save_ast(ast, "detection", output_dir)
    save_detection_debug(ast, resized_path, output_dir)

    ast = run_segmentation(ast, resized_path, output_dir)
    save_ast(ast, "segmentation", output_dir)

    ast = run_style_extraction(ast)
    save_ast(ast, "style", output_dir)

    ast = run_layout_reconstruction(ast)
    save_ast(ast, "layout", output_dir)

    code = run_codegen(ast, target=target)
    save_code(code, target, output_dir)

    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "ast": ast,
            "code": code,
            "target": target,
            "original_image": str(image_path),
            "output_dir": str(output_dir),
        },
    )
