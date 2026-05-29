import os
import json
import io
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel
from PIL import Image
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("Waduh, GEMINI_API_KEY kagak ketemu di file .env!")

client = genai.Client(api_key=api_key)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INI YANG DIUBAH: Schema disamakan 100% dengan app.js & index.html lu ---
class Nutrisi(BaseModel):
    gula_g: float
    lemak_g: float
    lemak_jenuh_g: float
    protein_g: float
    karbohidrat_g: float
    serat_g: float
    natrium_mg: float

class AnalisisMakanan(BaseModel):
    nama_makanan: str
    porsi_estimasi: str
    kalori: int
    nutrisi: Nutrisi
    skor_kesehatan: int
    alergen_potensial: list[str]
    catatan: str
# -----------------------------------------------------------------------------

@app.post("/api/analisis")
async def analisis_makanan(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File yang lu upload harus berupa gambar ya!")
    
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        prompt = "Tolong analisis tabel nutrisi/komposisi pada gambar ini dengan sangat teliti."
        
        system_instruction = """
        Kamu adalah ahli gizi digital. Analisis gambar label makanan ini dan kembalikan data faktual.
        1. skor_kesehatan: Berikan nilai 1-10 (10 = sangat sehat, 1 = sangat tidak sehat/ultra proses).
        2. kalori: Estimasi kalori per porsi dalam bentuk angka (integer).
        3. alergen_potensial: Sebutkan jika ada alergen seperti kacang, susu, gluten, kedelai, dll.
        4. catatan: Berikan ringkasan bahaya atau manfaat (contoh: 'Tinggi gula tambahan' atau 'Kaya akan serat').
        5. Jika ada nilai nutrisi yang tidak tercantum di tabel, isi dengan 0.
        """
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=AnalisisMakanan, 
                temperature=0.2 
            )
        )
                
        return json.loads(response.text.strip())
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI ngasih format yang salah, coba foto ulang tabelnya.")
    except Exception as e:
        print("\n=== DETAIL ERROR BACKEND ===")
        import traceback
        traceback.print_exc()
        print("============================\n")
        raise HTTPException(status_code=500, detail=f"Terjadi error Gemini: {str(e)}")

app.mount("/", StaticFiles(directory="static", html=True), name="static")