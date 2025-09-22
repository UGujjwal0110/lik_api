from flask import Flask, request, render_template_string
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import aiohttp
import requests
import json
from google.protobuf.message import DecodeError
from proto import like_pb2, like_count_pb2, uid_generator_pb2

app = Flask(__name__)

# ====================== Helper Functions ======================

def load_tokens(server_name):
    try:
        if server_name == "IND":
            with open("token_ind.json", "r") as f:
                tokens = json.load(f)
        elif server_name in {"BR", "US", "SAC", "NA"}:
            with open("token_br.json", "r") as f:
                tokens = json.load(f)
        else:
            with open("token_bd.json", "r") as f:
                tokens = json.load(f)
        return tokens
    except Exception as e:
        app.logger.error(f"Error loading tokens for server {server_name}: {e}")
        return None

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Error encrypting message: {e}")
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating uid protobuf: {e}")
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    return encrypt_message(protobuf_data)

def make_request(encrypt, server_name, token):
    try:
        url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow" if server_name=="IND" else "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB50"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False)
        binary = bytes.fromhex(response.content.hex())
        return decode_protobuf(binary)
    except Exception as e:
        app.logger.error(f"Error in make_request: {e}")
        return None

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except DecodeError as e:
        app.logger.error(f"Error decoding Protobuf: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return None

async def send_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB50"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers) as resp:
                return await resp.text()
    except Exception as e:
        app.logger.error(f"Error in send_request: {e}")
        return None

async def send_multiple_requests(uid, server_name, url):
    tokens = load_tokens(server_name)
    if not tokens:
        return
    encrypted_uid = enc(uid)
    if not encrypted_uid:
        return
    tasks = []
    for i in range(1000):
        token = tokens[i % len(tokens)]["token"]
        tasks.append(send_request(encrypted_uid, token, url))
    await asyncio.gather(*tasks, return_exceptions=True)

# ====================== Home Page ======================
@app.route("/", methods=["GET", "POST"])
def home():
    result = None

    if request.method == "POST":
        uid = request.form.get("uid")
        server_name = "IND"
        if uid:
            tokens = load_tokens(server_name)
            if not tokens:
                result = {"error": "Failed to load tokens"}
            else:
                token = tokens[0]['token']
                encrypted_uid = enc(uid)
                before_data = make_request(encrypted_uid, server_name, token)
                before_like = int(before_data.AccountInfo.Likes) if before_data else 0
                player_name = before_data.AccountInfo.PlayerNickname if before_data else "Unknown"
                player_uid = int(before_data.AccountInfo.UID) if before_data else int(uid)

                url = "https://client.ind.freefiremobile.com/LikeProfile"
                asyncio.run(send_multiple_requests(uid, server_name, url))

                after_data = make_request(encrypted_uid, server_name, token)
                after_like = int(after_data.AccountInfo.Likes) if after_data else before_like
                like_given = after_like - before_like
                status = 1 if like_given != 0 else 2

                result = {
                    "PlayerName": player_name,
                    "UID": player_uid,
                    "LikesBefore": before_like,
                    "LikesGiven": like_given,
                    "LikesAfter": after_like,
                    "Status": status
                }

    html = f"""
    <!DOCTYPE html>
<html>
<head>
    <title>🚀FREE FIRE 100 LIKES🌍</title>
    <style>
        body {{
            margin: 0;
            overflow: hidden;
            background-color: #0d0d0d;
            color: #fff;
            font-family: Arial, sans-serif;
            text-align: center;
            padding-top: 50px;
        }}
        form {{
            position: relative;
            z-index: 2;
        }}
        input[type=text], button {{
            position: relative;
            z-index: 2;
            background-color: rgba(0,0,0,0.7);
            color: #fff;
        }}
        input[type=text] {{
            padding: 10px;
            font-size: 16px;
            width: 300px;
            border-radius: 5px;
            border: 2px solid #00FF2FFF;
        }}
        button {{
            padding: 10px 20px;
            font-size: 16px;
            border-radius: 5px;
            border: 2px solid #0400FFFF;
            background-color: #00ffff;
            cursor: pointer;
        }}
        .glow {{
            font-size: 24px;
            font-weight: bold;
            color: #fff;
            text-shadow:
                0 0 5px #fff,
                0 0 10px #ff00ff,
                0 0 20px #FF00BFFF,
                0 0 40px #6600FFFF,
                0 0 80px #00BFFFFF;
            margin: 15px 0;
            position: relative;
            z-index: 2;
        }}
        .loader {{
            border: 6px dotted #61EC41FF;
            border-top: 6px solid #00ffff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 2s linear infinite;
            margin: 20px auto;
            display: none;
            position: relative;
            z-index: 2;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        canvas {{
            position: fixed;
            top: 0;
            left: 0;
            z-index: 0;
        }}
    </style>
    <script>
        function showLoader() {{
            document.getElementById("loader").style.display = "block";
        }}
    </script>
</head>
<body>
    <canvas id="starCanvas"></canvas>
    <div class="glow">🚀 OnlyIND SERVER 🌍</div>
    <div class="glow">👨‍💻 UG</div>
    <form method="POST" onsubmit="showLoader()">
        <input type="text" name="uid" placeholder="Enter UID" required>
        <button type="submit">Submit ❤️</button>
    </form>
    <div id="loader" class="loader"></div>
    {f'''
    <div class="glow">Player Name: {result['PlayerName']} 😎</div>
    <div class="glow">UID: {result['UID']} 🔑</div>
    <div class="glow">Likes-Before: {result['LikesBefore']} 🕒</div>
    <div class="glow">Likes-Given: {result['LikesGiven']} ❤️</div>
    <div class="glow">Likes-After: {result['LikesAfter']} ✨</div>
    <div class="glow">Status: {result['Status']} 🎉</div>
    ''' if result else ''}

    <script>
        const canvas = document.getElementById('starCanvas');
        const ctx = canvas.getContext('2d');
        let width = canvas.width = window.innerWidth;
        let height = canvas.height = window.innerHeight;

        window.addEventListener('resize', () => {{
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        }});

        const stars = [];
        const STAR_COUNT = 200;
        for (let i = 0; i < STAR_COUNT; i++) {{
            stars.push({{
                x: Math.random() * width,
                y: Math.random() * height,
                radius: Math.random() * 2,
                speed: Math.random() * 1.5 + 0.5,
                color: `hsl(${{Math.random()*360}}, 100%, 80%)`
            }});
        }}

        let lightningTime = Math.random() * 300 + 300;

        function animate() {{
            ctx.fillStyle = 'rgba(13,13,13,0.4)';
            ctx.fillRect(0, 0, width, height);

            stars.forEach(star => {{
                star.y += star.speed;
                if(star.y > height) {{
                    star.y = 0;
                    star.x = Math.random() * width;
                }}
                ctx.beginPath();
                ctx.arc(star.x, star.y, star.radius, 0, Math.PI*2);
                ctx.fillStyle = star.color;
                ctx.fill();
            }});

            lightningTime--;
            if(lightningTime < 0) {{
                ctx.fillStyle = 'rgba(255,255,255,0.3)';
                ctx.fillRect(0, 0, width, height);
                lightningTime = Math.random() * 500 + 300;
            }}

            requestAnimationFrame(animate);
        }}

        animate();
    </script>
</body>
</html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
