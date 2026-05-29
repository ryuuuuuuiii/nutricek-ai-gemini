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

# 1. Load API Key dari file .env atau Environment Variable Cloud
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("Waduh, GEMINI_API_KEY kagak ketemu di file .env atau Railway Variables!")

# Inisialisasi Google GenAI Client Resmi (v2)
client = genai.Client(api_key=api_key)
MODEL_NAME = "gemini-2.0-flash"

app = FastAPI(title="NutriCheck AI", version="3.0.0")

# ── Prompt Nutrisi & Aturan JSON ──────────────────────────────────────────
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
Catatan: skor_kesehatan antara 1-10. Jika gambar yang diupload SAMA SEKALI BUKAN MAKANAN, kembalikan format: {"error": "Gambar bukan makanan"}"""


# 2. Endpoint API Analisis Makanan
@app.post("/api/analisis")
async def analisis_makanan(file: UploadFile = File(...)):
    # Validasi input harus file gambar
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File yang lu upload harus berupa gambar ya!")
    
    try:
        contents = await file.read()
        
        # Batasi ukuran file maks 10 MB agar hemat bandwidth server
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Ukuran gambar terlalu besar, maksimal 10 MB.")
            
        # ── PERBAIKAN ROTASI OTOMATIS EXIF CAMERA HP ──
        try:
            img = Image.open(io.BytesIO(contents))
            img = ImageOps.exif_transpose(img)  # Meluruskan gambar otomatis jika miring saat dipotret HP
        except Exception:
            # Fallback jika library Pillow gagal memproses metadata gambar
            img = Image.open(io.BytesIO(contents))

        # ── PANGGIL GEMINI API ──
        # Memanfaatkan mode strict JSON dengan response_mime_type
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[NUTRISI_PROMPT, img],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
                
        text_response = response.text.strip()
        
        # ── PROTEKSI BAN SEREP (Fallback JSON Cleaner) ──
        if "```" in text_response:
            parts = text_response.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    text_response = part
                    break
        
        # Konversi string respon ke JSON Python
        data_json = json.loads(text_response)
        
        # Jika AI mendeteksi objek bukan makanan
        if "error" in data_json:
            return JSONResponse(status_code=400, content=data_json)
            
        return JSONResponse(content=data_json)
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI ngasih format yang meleset, silakan coba scan ulang gambarnya.")
    except Exception as e:
        # Cetak log error asli di terminal server agar gampang ditelusuri jika ada crash
        print("\n=== DETAIL CRASH BACKEND ===")
        import traceback
        traceback.print_exc()
        print("============================\n")
        raise HTTPException(status_code=500, detail=f"Terjadi error internal: {str(e)}")


# 3. Serving File Statis Frontend (index.html, app.js, css)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")