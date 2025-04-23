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

st.title("🔐 Genera Bearer Token per EpCube")
st.markdown("Enter the email and password you use to log in via the APP (if it gives an error, try again until successful)")

email = st.text_input("Email", value="", placeholder="Inserisci la tua email")
password = st.text_input("Password", type="password", placeholder="Inserisci la tua password")

if st.button("Genera Token"):
    if not email or not password:
        st.error("Inserisci email e password")
    else:
        try:
            with st.spinner("🧩 Risolvo CAPTCHA..."):
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

                # CAPTCHA GET
                r = requests.post("https://monitoring-eu.epcube.com/api/open/common/captcha/get",
                                  json={"clientUid": client_uid}, headers=headers)
                rep_data = r.json()["data"]["repData"]
                captcha_token = rep_data["token"]
                secret_key = rep_data["secretKey"]
                original = decode_base64_image(rep_data["originalImageBase64"])
                puzzle = decode_base64_image(rep_data["jigsawImageBase64"])

                # === 2. Trova posizione ===
                bg_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
                piece_gray = cv2.cvtColor(puzzle, cv2.COLOR_BGR2GRAY)

                # Fallback: swap se dimensioni non corrette
                if piece_gray.shape[0] > bg_gray.shape[0] or piece_gray.shape[1] > bg_gray.shape[1]:
                    bg_gray, piece_gray = piece_gray, bg_gray

                res = cv2.matchTemplate(bg_gray, piece_gray, cv2.TM_CCOEFF_NORMED)
                _, _, _, max_loc = cv2.minMaxLoc(res)
                x = float(max_loc[0])
                y = 5
                

                # CAPTCHA CHECK
                point_json = encrypt_point_json(x, y, secret_key)
                check = requests.post(
                    "https://monitoring-eu.epcube.com/api/open/common/captcha/check",
                    json={"clientUid": client_uid, "token": captcha_token, "pointJson": point_json},
                    headers=headers
                ).json()

                if check["data"]["repData"]["result"]:
                    captcha_verification = generate_captcha_verification(captcha_token, x, y, secret_key)
                    login = requests.post(
                        "https://monitoring-eu.epcube.com/api/open/common/login",
                        json={"userName": email, "password": password, "captchaVerification": captcha_verification},
                        headers=headers
                    ).json()

                    elapsed = time.perf_counter() - start_time
                    token = login.get("data", {}).get("token")
                    if token:
                        st.success(f"✅ Token generato in {elapsed:.2f}s")
                        st.code(token, language="text")
                    else:
                        st.error(f"❌ Login fallito: {login}")
                else:
                    st.error("❌ CAPTCHA non riuscito.")
        except Exception as e:
            st.exception(e)
