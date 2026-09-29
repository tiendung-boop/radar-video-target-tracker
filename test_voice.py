"""
Thu giong TTS - edge-tts
Chay: python test_voice.py
"""
import asyncio
import tempfile
import os
import edge_tts
import pygame

SAMPLE_TEXTS = {
    "vi": "Mục tiêu phát hiện ở cự ly hai trăm kilômét, góc chín mươi độ, tốc độ một nghìn hai trăm kilômét một giờ.",
    "en": "Mục tiêu phát hiện ở cự ly hai trăm kilômét, góc chín mươi độ, tốc độ một nghìn hai trăm kilômét một giờ",
    "zh": "发现目标，距离两百公里，方位九十度，速度一千两百公里每小时。",
    "ja": "目標を探知しました。距離二百キロメートル、方位九十度、速度一千二百キロメートル毎時。",
    "fr": "Cible détectée à deux cents kilomètres, relèvement quatre-vingt-dix degrés, vitesse mille deux cents kilomètres par heure.",
    "de": "Ziel erfasst in zweihundert Kilometer Entfernung, Peilung neunzig Grad, Geschwindigkeit zwölfhundert Kilometer pro Stunde.",
    "ko": "표적 탐지. 거리 이백 킬로미터, 방위각 구십 도, 속도 시속 천이백 킬로미터.",
    "ru": "Обнаружена цель на расстоянии двести километров, пеленг девяносто градусов, скорость тысяча двести километров в час.",
    "ar": "تم اكتشاف هدف على بُعد مئتي كيلومتر، في الاتجاه تسعين درجة، بسرعة ألف ومئتي كيلومتر في الساعة.",
}

# Goi y giong theo nhom ngon ngu
VOICE_SUGGESTIONS = """
=== TIENG VIET ===
  vi-VN-HoaiMyNeural      (nu)
  vi-VN-NamMinhNeural     (nam)  <-- dang dung

=== TIENG ANH ===
  en-US-AriaNeural        (nu, tin tuc)
  en-US-GuyNeural         (nam, manh me)
  en-US-JennyNeural       (nu, than thien)
  en-US-EricNeural        (nam, tin tuc)
  en-GB-RyanNeural        (nam, giong Anh)
  en-GB-SoniaNeural       (nu, giong Anh)
  en-AU-NatashaNeural     (nu, giong Uc)

=== TIENG TRUNG ===
  zh-CN-XiaoxiaoNeural    (nu, am)
  zh-CN-YunxiNeural       (nam, soi noi)
  zh-CN-YunyangNeural     (nam, chuyen nghiep)
  zh-TW-HsiaoChenNeural   (nu, Dai Loan)

=== TIENG NHAT ===
  ja-JP-NanamiNeural      (nu)
  ja-JP-KeitaNeural       (nam)

=== TIENG HAN ===
  ko-KR-SunHiNeural       (nu)
  ko-KR-InJoonNeural      (nam)

=== TIENG PHAP ===
  fr-FR-DeniseNeural      (nu)
  fr-FR-HenriNeural       (nam)

=== TIENG DUC ===
  de-DE-KatjaNeural       (nu)
  de-DE-ConradNeural      (nam)

=== TIENG NGA ===
  ru-RU-SvetlanaNeural    (nu)
  ru-RU-DmitryNeural      (nam)
"""


def get_lang_prefix(voice_name: str) -> str:
    prefix = voice_name[:2].lower()
    return prefix if prefix in SAMPLE_TEXTS else "en"


async def speak(voice: str, text: str):
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        comm = edge_tts.Communicate(text, voice)
        await comm.save(tmp_path)
        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
    finally:
        try: os.unlink(tmp_path)
        except: pass


def main():
    pygame.mixer.init()
    print(VOICE_SUGGESTIONS)
    print("=" * 55)
    print("Nhap ten giong de nghe thu (Enter de thoat)")
    print("Vi du: vi-VN-HoaiMyNeural")
    print("       en-US-AriaNeural")
    print("Hoac nhap: list   -> xem toan bo danh sach")
    print("=" * 55)

    while True:
        voice = input("\nGiong > ").strip()
        if not voice:
            print("Thoat.")
            break
        if voice.lower() == "list":
            os.system("python -m edge_tts --list-voices")
            continue

        lang = get_lang_prefix(voice)
        text = SAMPLE_TEXTS[lang]
        print(f"  -> Dang phat: [{voice}]")
        print(f"  -> Van ban  : {text}")
        try:
            asyncio.run(speak(voice, text))
            print("  -> Xong!")
        except Exception as e:
            print(f"  -> LOI: {e}")
            print("     (Kiem tra lai ten giong, phai dung chinh xac nhu danh sach)")


if __name__ == "__main__":
    main()
