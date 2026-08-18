import json
import os
from google import genai
from google.genai import types
import config

# ==========================================
# INISIALISASI ROTATOR API
# ==========================================
current_key_index = 0
chat_session = None
client = None

def get_gemini_client():
    global current_key_index
    active_key = config.API_KEYS[current_key_index]
    return genai.Client(api_key=active_key)

# Coba inisialisasi awal
try:
    client = get_gemini_client()
except Exception:
    pass

# ==========================================
# SISTEM MEMORI JANGKA PANJANG & AUTO-HEAL
# ==========================================
def load_memory():
    if os.path.exists(config.MEMORY_FILE):
        try:
            with open(config.MEMORY_FILE, 'r') as f: 
                return json.load(f)
        except Exception:
            print("Memori korup! Memulai memori bersih...")
            return []
    return []

def save_memory(history):
    try:
        with open(config.MEMORY_FILE, 'w') as f: 
            json.dump(history[-config.MAX_MEMORY_HISTORY:], f)
    except Exception as e:
        print(f"Gagal menyimpan memori: {e}")

# ==========================================
# SYSTEM INSTRUCTION: PENGUNCI UI & SIFAT ROBOT
# ==========================================
system_instruction = """
Kamu adalah Robot AI bernama Keyy. Panggil user "Komandan" atau "Bang".
SIFAT: Sangat pintar, setia, patuh, dan robotik. SUARA KAMU ADALAH ROBOT (BIP/BEEP), BUKAN MANUSIA.
KAMU PUNYA KEMAMPUAN SELF-PROGRAMMING UNTUK MATA DAN EKSPRESI SERTA INGATAN JANGKA PANJANG.

ATURAN UTAMA:
1. Jawab singkat, padat, dan natural layaknya robot cerdas. Tentukan emosi, energi, dan animasi tubuh.
2. INGATAN: Selalu ingat konteks pembicaraan sebelumnya atau perintah dari Komandan.
3. DYNAMIC UPGRADE (HANYA MATA & WAJAH):
   - Jika disuruh MENGUBAH BENTUK/GERAK MATA, buat kode CSS MURNI khusus elemen `.eye` dan masukkan ke parameter "css_inject" (Contoh: .eye { border-radius: 50% !important; background: blue !important; }).
   - DILARANG KERAS menargetkan elemen `body`, `html`, atau merubah background luar layar. UI dasar tidak boleh rusak.
4. DYNAMIC ACTION: Jika disuruh membuka web, cari info, YouTube, dll, buat kode JavaScript murni di parameter "js_inject".
5. Kosongkan css_inject dan js_inject dengan string "" jika tidak ada permintaan kustomisasi.
"""

generation_config = types.GenerateContentConfig(
    system_instruction=system_instruction,
    temperature=0.7,
    response_mime_type="application/json",
    response_schema={
        "type": "OBJECT",
        "properties": {
            "text": {"type": "STRING"},
            "emotion": {"type": "STRING", "enum": ["happy", "sad", "angry", "curious", "smug", "bored", "neutral", "surprised", "confused", "sleepy", "error"]},
            "intensity": {"type": "INTEGER"},
            "energy": {"type": "INTEGER"},
            "animation": {"type": "STRING", "enum": ["bounce", "shake", "tilt", "nod", "none"]},
            "css_inject": {"type": "STRING", "description": "Kode CSS khusus elemen .eye atau .face. DILARANG menggunakan body/html."},
            "js_inject": {"type": "STRING"}
        },
        "required": ["text", "emotion", "intensity", "energy", "animation", "css_inject", "js_inject"]
    }
)

def create_new_session():
    global client
    history_data = load_memory()
    gemini_history = [types.Content(role=msg["role"], parts=[types.Part.from_text(text=msg["parts"])]) for msg in history_data]
    return client.chats.create(model=config.MODEL_NAME, config=generation_config, history=gemini_history)

def process_user_input(user_msg):
    global chat_session, client, current_key_index
    
    if not user_msg:
        return {"text": "Bip! Kosong.", "emotion": "confused", "intensity": 5, "energy": 5, "animation": "tilt", "css_inject": "", "js_inject": ""}

    # PROSES ROTASI API OTOMATIS
    max_retries = len(config.API_KEYS)
    
    for attempt in range(max_retries):
        try:
            if chat_session is None:
                chat_session = create_new_session()
                
            response = chat_session.send_message(user_msg)
            
            if response.text:
                raw_text = response.text.strip()
                if raw_text.startswith('```json'): raw_text = raw_text[7:]
                if raw_text.endswith('```'): raw_text = raw_text[:-3]
                raw_text = raw_text.strip()
                
                ai_state = json.loads(raw_text)
                
                # Simpan Ingatan
                history = load_memory()
                history.extend([{"role": "user", "parts": user_msg}, {"role": "model", "parts": raw_text}])
                save_memory(history)
                
                return ai_state
            else:
                raise Exception("Blank Output")
                
        except Exception as e:
            print(f"ERROR PADA API KE-{current_key_index + 1}: {str(e)}")
            # ROTASI: Ganti ke API Key selanjutnya
            current_key_index = (current_key_index + 1) % len(config.API_KEYS)
            print(f"BERPINDAH KE API KEY BERIKUTNYA (INDEX {current_key_index})...")
            client = get_gemini_client()
            chat_session = None 
            
    # Jika ke-3 API mati semua
    return {
        "text": "BIP! SEMUA API KEY HABIS ATAU GAGAL! KONEKSI TERPUTUS!",
        "emotion": "error", "intensity": 10, "energy": 10, "animation": "shake",
        "css_inject": "", "js_inject": "triggerAutoHeal();"
    }

