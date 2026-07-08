import os
import json
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for

from core.guided_question_flow import GuidedQuestionFlow
from core.prompt_generator import PromptGenerator

app = Flask(__name__)
app.secret_key = "lingou_2026_prompt_craft"
app.config["JSON_AS_ASCII"] = False

guided_flow = GuidedQuestionFlow()
prompt_generator = PromptGenerator()

# ===================== 持久化配置 =====================
SESSIONS_FILE = "sessions.json"

def init_sessions_file():
    if not os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

def load_sessions():
    try:
        with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
            sessions = json.load(f)
            for sess in sessions:
                if "messages" not in sess:
                    sess["messages"] = []
            return sessions
    except:
        init_sessions_file()
        return []

def save_sessions(sessions):
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)

init_sessions_file()

# ===================== 页面路由 =====================
@app.route("/")
def index():
    return redirect(url_for("chat_page"))

@app.route("/chat")
def chat_page():
    return render_template("chat.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    if username == "admin" and password == "123456":
        return redirect(url_for("chat_page"))
    return "登录失败，请检查账号密码"

@app.route("/logout")
def logout():
    return redirect(url_for("login_page"))

# ===================== 会话管理接口 =====================
@app.route("/api/sessions")
def get_all_sessions():
    return jsonify(load_sessions())

@app.route("/api/sessions/new", methods=["POST"])
def new_session():
    sessions = load_sessions()
    session_id = str(uuid.uuid4())
    new_session_data = {
        "id": session_id,
        "name": "新对话",
        "stage": 0,
        "user_answers": {},
        "messages": [],
        "prompt_type": "video"   # 默认为视频类型
    }
    sessions.append(new_session_data)
    save_sessions(sessions)
    return jsonify(new_session_data)

@app.route("/api/sessions/<session_id>/greet", methods=["POST"])
def greet_session(session_id):
    """发送打招呼消息（自动添加到会话消息中）"""
    data = request.get_json() or {}
    prompt_type = data.get("prompt_type", "video")
    sessions = load_sessions()
    current_session = next((s for s in sessions if s["id"] == session_id), None)
    if not current_session:
        return jsonify({"reply": "会话不存在"}), 404

    # 更新会话的 prompt_type
    current_session["prompt_type"] = prompt_type

    # 根据类型生成打招呼语
    if prompt_type == "video":
        greeting = "你好！我是灵构助手，可以帮你生成视频提示词。请告诉我你想制作的视频类型、时长、内容和风格～"
    elif prompt_type == "image":
        greeting = "你好！我是灵构助手，可以帮你生成图片提示词。请描述你想生成的图片主题、风格和构图～"
    else:
        greeting = "你好！我是灵构助手，可以帮你生成文案提示词。请提供文案类型、商品、受众和语气～"

    # 添加招呼消息（仅当该会话还没收到过招呼时才添加，避免重复）
    # 简单判断：如果 messages 为空或者最后一条不是招呼（防止多次调用），这里先简单直接添加，由前端控制调用时机。
    current_session.setdefault("messages", []).append({"role": "ai", "content": greeting})
    save_sessions(sessions)
    return jsonify({"reply": greeting})

@app.route("/api/sessions/<session_id>/history")
def get_session_history(session_id):
    sessions = load_sessions()
    for sess in sessions:
        if sess["id"] == session_id:
            return jsonify(sess.get("messages", []))
    return jsonify([])

@app.route("/api/sessions/<session_id>/state")
def get_session_state(session_id):
    sessions = load_sessions()
    for sess in sessions:
        if sess["id"] == session_id:
            return jsonify({
                "stage": sess["stage"],
                "user_answers": sess["user_answers"]
            })
    return jsonify({"stage": 0, "user_answers": {}})

@app.route("/api/sessions/<session_id>/clear", methods=["POST"])
def clear_session(session_id):
    sessions = load_sessions()
    for sess in sessions:
        if sess["id"] == session_id:
            sess["stage"] = 0
            sess["user_answers"] = {}
            sess["messages"] = []
            # 保留 prompt_type 不变
            break
    save_sessions(sessions)
    return jsonify({"status": "ok"})

@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    sessions = [s for s in load_sessions() if s["id"] != session_id]
    save_sessions(sessions)
    return jsonify({"status": "ok"})

# ===================== 核心聊天接口 =====================
@app.route("/api/sessions/<session_id>/chat", methods=["POST"])
def chat(session_id):
    data = request.get_json()
    user_input = data.get("msg", "").strip()
    prompt_type = data.get("prompt_type", "video")

    sessions = load_sessions()
    current_session = next((s for s in sessions if s["id"] == session_id), None)
    if not current_session:
        return jsonify({"reply": "会话不存在"})

    reply, new_stage, new_answers = guided_flow.process(
        current_session["stage"],
        current_session["user_answers"],
        user_input,
        prompt_type
    )

    current_session["stage"] = new_stage
    current_session["user_answers"] = new_answers

    current_session["messages"].append({"role": "user", "content": user_input})
    current_session["messages"].append({"role": "ai", "content": reply})

    save_sessions(sessions)
    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)