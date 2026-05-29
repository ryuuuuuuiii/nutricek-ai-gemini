import os
import json
import io

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image, ImageOps

load_dotenv()

# ── Gemini Client Initialization ─────────────────────────────────────────────
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("Waduh, GEMINI_API_KEY kagak ketemu di file .env atau Railway Variables!")

client = genai.Client(api_key=api_key)
MODEL = "gemini-2.0-flash"

# ── Prompt ───────────────────────────────────────────────────────────────────
NUTRISI_PROMPT = """Kamu adalah ahli gizi profesional. Analisis gambar makanan ini.
Kembalikan HANYA objek JSON valid, tanpa markdown, tanpa backtick, tanpa teks lain.
Format persis seperti ini:
{
  "nama_makanan": "string",
  "porsi_estimasi": "string",
  "kalori": number,
  "nutrisi": {
    "karbohidrat_g": number,
    "protein_g": number,
    "lemak_g": number,
    "serat_g": number,
    "gula_g": number
  },
  "skor_kesehatan": number,
  "catatan": "string",
  "alergen_potensial": ["string"]
}
Catatan: skor_kesehatan antara 1-10. Jika bukan makanan: {"error": "Gambar bukan makanan"}"""

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="NutriCheck AI", version="3.0.0")


@app.post("/api/analisis")
async def analisis_makanan(file: UploadFile = File(...)):
    # 1. Validasi Format File
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File harus berupa gambar.")

    image_bytes = await file.read()
    
    # 2. Validasi Ukuran Gambar Maksimal 10 MB
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ukuran gambar maksimal 10 MB.")

    # 3. --- PERBAIKAN ROTASI EXIF HP ---
    try:
        # Buka gambar menggunakan Pillow
        img = Image.open(io.BytesIO(image_bytes))
        
        # Otomatis meluruskan gambar berdasarkan data EXIF bawaan kamera HP
        img = ImageOps.exif_transpose(img)
    except Exception:
        # Jika gagal memproses (misal file korup), kembali pakai file aslinya
        try:
            img = Image.open(io.BytesIO(image_bytes))
        except Exception:
            raise HTTPException(status_code=400, detail="Gagal membaca file gambar.")

    # 4. Kirim ke Gemini API
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=[NUTRISI_PROMPT, img],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini API error: {str(e)}")

    raw_text = response.text.strip()

    # 5. Bersihkan markdown fence jika ada (Fallback Protection)
    if "```" in raw_text:
        parts = raw_text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw_text = part
                break

    # Cari JSON object dalam teks jika posisinya bergeser
    if not raw_text.startswith("{"):
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start != -1 and end > start:
            raw_text = raw_text[start:end]

    # 6. Validasi & Parsing JSON akhir
    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail={"message": "Model tidak mengembalikan JSON valid.", "raw": raw_text},
        )

    if "error" in result:
        return JSONResponse(status_code=400, content=result)

    return JSONResponse(content=result)


# ── Static Files & Routing ───────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")