import streamlit as st
import base64
import json
import requests
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import time
import uuid

st.set_page_config(page_title="EpCube Token Generator", page_icon="🔐")
st.caption("⚠️ This site does not store your credentials. Full source code is available on GitHub.")

st.title("🔐 EpCube Token Generator")

st.markdown("""
**🇮🇹 Istruzioni**  
Inserisci l'email e la password che usi per accedere all'app EpCube.  
Se il login fallisce, riprova: il CAPTCHA può non riuscire al primo tentativo.

**🇬🇧 Instructions**  
Enter the email and password you use to log into the EpCube mobile app.  
If login fails, try again: CAPTCHA may fail on first attempt.
""")

region = st.selectbox("🌍 Regione / Region", options=["EU", "US"], index=0)
email = st.text_input("📧 Email", value="", placeholder="es. nome@email.com")
password = st.text_input("🔒 Password", type="password", placeholder="Inserisci la password / Enter password")

if st.button("🔐 Genera Token / Generate Token"):
    if not email or not password:
        st.error("❗ Inserisci email e password / Please enter both email and password.")
    else:
        try:
            BASE_URLS = {
                "EU": "https://monitoring-eu.epcube.com/api/",
                "US": "https://epcube-monitoring.com/app-api/"
            }
            BASE_URL = BASE_URLS[region]

            with st.spinner("🧩 Solving CAPTCHA..."):
                start_time = time.perf_counter()
                client_uid = str(uuid.uuid4())

                headers = {
                    "User-Agent": "ReservoirMonitoring/2.1.0 (iPhone; iOS 18.3.2; Scale/3.00)",
                    "Accept": "*/*",
                    "Content-Type": "application/json",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "it-IT"
                }

                def decode_base64_image(b64):
                    image_data = base64.b64decode(b64)
                    pil_image = Image.open(BytesIO(image_data))
                    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

                def encrypt_point_json(x, y, secret_key):
                    data = json.dumps({"x": float(x), "y": float(y)}, separators=(",", ":")).encode("utf-8")
                    cipher = AES.new(secret_key.encode("utf-8"), AES.MODE_ECB)
                    return base64.b64encode(cipher.encrypt(pad(data, AES.block_size))).decode("utf-8")

                def generate_captcha_verification(token, x, y, secret_key):
                    raw = f"{token}---{json.dumps({'x': float(x), 'y': float(y)}, separators=(',', ':'))}".encode("utf-8")
                    cipher = AES.new(secret_key.encode("utf-8"), AES.MODE_ECB)
                    return base64.b64encode(cipher.encrypt(pad(raw, AES.block_size))).decode("utf-8")

                #st.write("📡 Richiesta a:", f"{BASE_URL}/open/common/captcha/get")
                r = requests.post(f"{BASE_URL}/open/common/captcha/get",
                                  json={"clientUid": client_uid}, headers=headers)

                if r.status_code != 200:
                    st.error(f"❌ Errore HTTP: {r.status_code}")
                    st.text(r.text)
                    st.stop()

                try:
                    r_json = r.json()
                except Exception as ex:
                    st.error("❌ La risposta non è un JSON valido.")
                    st.text(r.text)
                    st.stop()

                if "data" not in r_json or "repData" not in r_json["data"]:
                    st.error("❌ Il server non ha restituito repData.")
                    st.text(json.dumps(r_json, indent=2))
                    st.stop()

                rep_data = r_json["data"]["repData"]

                # Decodifica immagini CAPTCHA
                original = decode_base64_image(rep_data["originalImageBase64"])
                puzzle = decode_base64_image(rep_data["jigsawImageBase64"])
                secret_key = rep_data["secretKey"]
                captcha_token = rep_data["token"]

                bg_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
                piece_gray = cv2.cvtColor(puzzle, cv2.COLOR_BGR2GRAY)

                if piece_gray.shape[0] > bg_gray.shape[0] or piece_gray.shape[1] > bg_gray.shape[1]:
                    bg_gray, piece_gray = piece_gray, bg_gray

                res = cv2.matchTemplate(bg_gray, piece_gray, cv2.TM_CCOEFF_NORMED)
                _, _, _, max_loc = cv2.minMaxLoc(res)
                x = float(max_loc[0])
                y = 5

                point_json = encrypt_point_json(x, y, secret_key)
                check = requests.post(
                    f"{BASE_URL}/open/common/captcha/check",
                    json={"clientUid": client_uid, "token": captcha_token, "pointJson": point_json},
                    headers=headers
                ).json()

                if check["data"]["repData"]["result"]:
                    captcha_verification = generate_captcha_verification(captcha_token, x, y, secret_key)
                    login = requests.post(
                        f"{BASE_URL}/open/common/login",
                        json={"userName": email, "password": password, "captchaVerification": captcha_verification},
                        headers=headers
                    ).json()

                    elapsed = time.perf_counter() - start_time
                    token = login.get("data", {}).get("token")
                    if token:
                        st.success(f"✅ Token generato in {elapsed:.2f}s / Token generated in {elapsed:.2f}s")
                        st.code(token, language="text")
                    else:
                        st.error(f"❌ Login fallito / Login failed: {login}")
                else:
                    st.error("❌ CAPTCHA non riuscito / CAPTCHA failed.")
        except Exception as e:
            st.exception(e)
