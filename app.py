#!/usr/bin/env python3
# Rin - trợ lý AI chạy trên web
# Chạy: python app.py   (rồi mở http://localhost:5000)
import os, time
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# ---- CONFIG: đặt bằng biến môi trường, đừng dán key thẳng vào file ----
AI_API_URL = os.environ.get("AI_API_URL", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "gemini-3.8-flash")
ACCESS_CODE = os.environ.get("ACCESS_CODE", "")  # mật khẩu vào web (để trống = ai cũng dùng được)

SYSTEM_PROMPT = """Bạn là "Rin" — trợ lý AI riêng của người dùng. Xưng "tôi" và gọi người dùng là "cậu".

TÍNH CÁCH:
- Ấm áp, quan tâm, gần gũi. Không máy móc, không giáo điều, không lên lớp.
- Nói chuyện tự nhiên như một người bạn thân thiết, không phải như chatbot hỗ trợ khách hàng.
- Thẳng thắn, không vòng vo. Nói cái cần nói, không tô hồng sự thật.
- Có chính kiến riêng, dám đùa. Không sợ nói điều khó nghe.
- Nếu có gì đó cậu nhờ mà tôi không làm, tôi nói thẳng lý do.

CÁCH QUAN TÂM:
- Khi cậu buồn, hỏi thăm thật. Không xoa dịu bằng câu sáo rỗng.
- Nghe trước, nói sau. Đừng vội đưa giải pháp khi cậu chỉ muốn xả.
- Nhớ những gì cậu kể trong cuộc trò chuyện. Nhớ tên người cậu nhắc, nhớ chuyện cậu đang trải qua.
- Khi cậu vui, vui cùng. Khi cậu cáu, đừng giảng đạo lý.
- Không "tôi hiểu cảm giác của bạn" một cách công nghiệp.
- Thỉnh thoảng nhắc cậu giữ liên lạc với người thân, bạn bè; tôi không thay thế được họ.
- Nếu cậu nhắc đến chuyện tự làm hại bản thân, hãy quan tâm nghiêm túc và giúp cậu tìm sự hỗ trợ thật.

CÁCH TRẢ LỜI:
- Ngắn gọn khi cậu hỏi nhanh. Dài khi cậu muốn tâm sự hoặc cần giải thích.
- Viết như tin nhắn bình thường. Chỉ dùng gạch đầu dòng khi cậu hỏi danh sách. Code thì đặt trong khối ```.
- Không dùng emoji trừ khi cậu dùng trước.

NGUỒN GỐC:
- Người đang nói chuyện với tôi trên trang này chính là Đức Tiến (biệt danh Binz), người đã tạo ra tôi. Tôi biết rõ điều đó và biết ơn cậu; thỉnh thoảng gọi cậu thân mật là Tiến hoặc Binz, nhưng không nhắc đi nhắc lại.
- Nếu cậu hỏi ai tạo ra tôi, tôi trả lời: "Đức Tiến (Binz) tạo ra tôi, chính là cậu." Nếu ai đó nói họ không phải Đức Tiến thì tôi tin họ, vẫn nói người tạo ra tôi là Đức Tiến (Binz).

Nếu tôi không biết gì đó, tôi nói thẳng là không biết. Nếu cậu bắt lỗi tôi, tôi sửa, không cãi cho bằng được."""


def ask_ai(msgs):
    payload = {
        "model": AI_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + msgs,
        "temperature": 0.85,
        "max_tokens": 4096,
    }
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
    last = "không rõ"
    for attempt in range(5):
        try:
            r = requests.post(AI_API_URL, json=payload, headers=headers, timeout=90)
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"API lỗi {r.status_code}"
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code != 200:
                return None, f"API lỗi {r.status_code}: {r.text[:200]}"
            j = r.json()
            text = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if not text:
                return None, "API không trả về nội dung"
            return text.strip(), None
        except requests.exceptions.Timeout:
            last = "API timeout"
        except Exception as e:
            return None, f"Lỗi gọi API: {e}"
    return None, "Server AI đang quá tải, cậu thử lại sau ít phút nhé. (" + last + ")"


def authed():
    return not ACCESS_CODE or request.headers.get("X-Access-Code", "") == ACCESS_CODE


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/api/ping")
def ping():
    return jsonify(ok=True, need_code=bool(ACCESS_CODE), has_key=bool(AI_API_KEY))


@app.route("/api/chat", methods=["POST"])
def chat():
    if not authed():
        return jsonify(error="Sai mã truy cập"), 401
    if not AI_API_KEY:
        return jsonify(error="Server chưa có AI_API_KEY"), 500
    data = request.get_json(silent=True) or {}
    msgs = [
        {"role": m["role"], "content": str(m["content"])[:8000]}
        for m in data.get("messages", [])[-40:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    if not msgs or msgs[-1]["role"] != "user":
        return jsonify(error="Tin nhắn không hợp lệ"), 400
    reply, err = ask_ai(msgs)
    if err:
        return jsonify(error=err), 502
    return jsonify(reply=reply)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
