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

# 1. Load API Key dari file .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("Waduh, GEMINI_API_KEY kagak ketemu di file .env!")

# Inisialisasi Client Google GenAI Baru
client = genai.Client(api_key=api_key)

app = FastAPI()

# Middleware CORS (Biar aman dari blocking browser)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SCHEMA STRUKTUR DATA (Disamakan 100% dengan kebutuhan index.html lu) ---
class NutrisiDetail(BaseModel):
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
    nutrisi: NutrisiDetail
    skor_kesehatan: int
    alergen_potensial: list[str]
    catatan: str
# ----------------------------------------------------------------------------

# 2. Endpoint API untuk Menerima Gambar & Analisis AI
@app.post("/api/analisis")
async def analisis_makanan(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File yang lu upload harus berupa gambar ya!")
    
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # Otomatis konversi gambar PNG transparan (RGBA) ke RGB biar gak crash
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        prompt = "Tolong ekstrak dan analisis informasi tabel komposisi/informasi nilai gizi dari gambar ini."
        
        system_instruction = """
        Kamu adalah seorang ahli gizi digital profesional. Tugasmu adalah menganalisis tabel nutrisi produk.
        
        Aturan Pengisian Data:
        1. skor_kesehatan: Berikan nilai integer dari skala 1-10 (10 sangat sehat, 1 sangat tidak sehat/tinggi ultra-proses).
        2. kalori: Ambil nilai kalori per porsi sajian (bentuk angka integer).
        3. alergen_potensial: Deteksi bahan pemicu alergi seperti susu, gandum, kedelai, atau kacang-kacangan.
        4. Jika ada nilai makro nutrisi yang tidak tertulis sama sekali di tabel, isi otomatis dengan angka 0.
        """
        
        # Memanggil Gemini dengan proteksi tipe data terstruktur
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=AnalisisMakanan,  # Jaminan format JSON selalu presisi
                temperature=0.2                  # Suhu rendah agar AI fokus membaca data, bukan berhalusinasi
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

# 3. Hubungkan ke folder Frontend (Static Files)
app.mount("/", StaticFiles(directory="static", html=True), name="static")