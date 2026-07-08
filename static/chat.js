let currentSessionId = null;
let currentSessionName = "新对话";
let voiceEnabled = true;
let currentPromptType = "video";

const voiceSwitch = document.getElementById("voiceSwitch");
const chatBox = document.getElementById("chatBox");
const inputText = document.getElementById("inputText");
const sessionList = document.getElementById("sessionList");
const currentSessionNameEl = document.getElementById("currentSessionName");
const newChatBtn = document.getElementById("newChatBtn");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const logoutBtn = document.getElementById("logoutBtn");
const themeBtn = document.getElementById("themeBtn");
const infoPanel = document.getElementById("infoPanel");
const infoContent = document.getElementById("infoContent");

// 输入框上方按钮切换
document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentPromptType = btn.dataset.type;

        const placeholderMap = {
            video: "请先回复视频核心类型+时长（如：3D国漫+15秒）",
            image: "请先回复图片主题+工具（如：电商香薰+MJ）",
            copy: "请先回复文案类型+场景（如：电商文案+香薰）"
        };
        inputText.placeholder = placeholderMap[currentPromptType];

        if(confirm("切换类型将重置当前对话与收集进度，是否继续？")) {
            await clearCurrentSession();
            // 清空后发送打招呼消息
            if (currentSessionId) {
                await fetch(`/api/sessions/${currentSessionId}/greet`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ prompt_type: currentPromptType })
                });
                // 重新加载历史以显示招呼
                await loadSessionHistory(currentSessionId);
            }
        }
    });
});

// 更新已收集信息面板
function refreshInfoPanel(answers) {
    if(!answers || Object.keys(answers).length === 0) {
        infoPanel.style.display = "none";
        return;
    }
    let html = "";
    if(answers.round1) html += `🔹 第一轮：${answers.round1}<br>`;
    if(answers.round2) html += `🔹 第二轮：${answers.round2}<br>`;
    if(answers.round3) html += `🔹 第三轮：${answers.round3}`;
    infoContent.innerHTML = html;
    infoPanel.style.display = html ? "block" : "none";
}

// 语音开关
if (voiceSwitch) {
    voiceSwitch.addEventListener("click", () => {
        voiceEnabled = !voiceEnabled;
        if (!voiceEnabled) window.speechSynthesis.cancel();
        voiceSwitch.classList.toggle("active", !voiceEnabled);
        voiceSwitch.textContent = voiceEnabled ? "🔊" : "🔇";
    });
}

// 主题切换
window.addEventListener("load", () => {
    const isDark = localStorage.getItem("darkTheme") === "true";
    document.body.classList.toggle("dark-theme", isDark);
});
if (themeBtn) {
    themeBtn.addEventListener("click", () => {
        document.body.classList.toggle("dark-theme");
        localStorage.setItem("darkTheme", document.body.classList.contains("dark-theme"));
    });
}

// 初始化
window.addEventListener("load", async () => {
    await loadSessionList();
    const sessions = await getSessions();
    if (sessions.length) {
        await switchSession(sessions[0].id, sessions[0].name);
    } else {
        await createNewSession();
    }
    bindEvents();
});

function bindEvents() {
    if (newChatBtn) newChatBtn.onclick = createNewSession;
    if (sendBtn) sendBtn.onclick = sendMessage;
    if (clearBtn) clearBtn.onclick = clearCurrentSession;
    if (logoutBtn) logoutBtn.onclick = () => location.href = "/logout";
    if (inputText) inputText.addEventListener("keydown", e => e.key === "Enter" && sendMessage());
}

// 会话接口
async function getSessions() {
    try { return await (await fetch("/api/sessions")).json(); }
    catch (e) { return []; }
}

async function loadSessionList() {
    const sessions = await getSessions();
    sessionList.innerHTML = "";
    sessions.forEach(session => {
        const item = document.createElement("div");
        item.className = `session-item ${session.id === currentSessionId ? "active" : ""}`;
        item.innerHTML = `<span class="session-name">${session.name}</span><button class="delete-btn" data-session-id="${session.id}">×</button>`;
        item.addEventListener("click", (e) => !e.target.classList.contains("delete-btn") && switchSession(session.id, session.name));
        item.querySelector(".delete-btn").addEventListener("click", async (e) => {
            e.stopPropagation();
            if (confirm("确定删除？")) {
                await deleteSession(session.id);
                await loadSessionList();
                const s = await getSessions();
                if (s.length) {
                    await switchSession(s[0].id, s[0].name);
                } else {
                    await createNewSession();
                }
            }
        });
        sessionList.appendChild(item);
    });
}

async function createNewSession() {
    const data = await (await fetch("/api/sessions/new", { method: "POST" })).json();
    await loadSessionList();
    await switchSession(data.id, data.name);
    // 新建会话后发送打招呼消息
    await fetch(`/api/sessions/${data.id}/greet`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt_type: currentPromptType })
    });
    await loadSessionHistory(data.id);
}

async function switchSession(sessionId, sessionName) {
    currentSessionId = sessionId;
    currentSessionName = sessionName;
    currentSessionNameEl.textContent = sessionName;
    await loadSessionHistory(sessionId);
    // 刷新信息面板
    const stateRes = await fetch(`/api/sessions/${sessionId}/state`);
    const state = await stateRes.json();
    refreshInfoPanel(state.user_answers);
    document.querySelectorAll(".session-item").forEach(i => i.classList.toggle("active", i.dataset.sessionId === sessionId));
}

async function loadSessionHistory(sessionId) {
    const res = await fetch(`/api/sessions/${sessionId}/history`);
    const history = await res.json();
    chatBox.innerHTML = "";
    history.forEach(msg => addMessage(msg.role, msg.content));
}

async function deleteSession(sid) {
    await fetch(`/api/sessions/${sid}`, { method: "DELETE" });
}

async function clearCurrentSession() {
    if (!currentSessionId) return;
    if (confirm("确定清空对话并重置收集进度？")) {
        await fetch(`/api/sessions/${currentSessionId}/clear`, { method: "POST" });
        chatBox.innerHTML = "";
        currentSessionNameEl.textContent = "新对话";
        infoPanel.style.display = "none";
        // 清空后需要重新加载空历史（已经清空，无需额外调用）
        // 但为了状态一致，重新拉取一次
        const stateRes = await fetch(`/api/sessions/${currentSessionId}/state`);
        const state = await stateRes.json();
        refreshInfoPanel(state.user_answers);
    }
}

function addMessage(role, text) {
    const div = document.createElement("div");
    div.className = `message ${role === "user" ? "user-message" : "ai-message"}`;
    div.innerHTML = `<div class="avatar ${role === "ai" ? "ai-avatar" : "user-avatar"}">${role === "ai" ? "✨" : "👤"}</div><div class="bubble">${text}</div>`;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage() {
    const text = inputText.value.trim();
    if (!text || !currentSessionId) return;

    addMessage("user", text);
    inputText.value = "";
    const loading = document.createElement("div");
    loading.className = "loading";
    loading.textContent = "灵构思考中...";
    chatBox.appendChild(loading);

    try {
        const res = await fetch(`/api/sessions/${currentSessionId}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ msg: text, prompt_type: currentPromptType })
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let full = "";
        addMessage("ai", "");
        const bubble = chatBox.lastElementChild.querySelector(".bubble");

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            full += decoder.decode(value);
            try {
                const json = JSON.parse(full);
                bubble.textContent = json.reply;
            } catch (e) {
                bubble.textContent = full;
            }
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        // 刷新信息面板
        const stateRes = await fetch(`/api/sessions/${currentSessionId}/state`);
        const state = await stateRes.json();
        refreshInfoPanel(state.user_answers);

        voiceEnabled && speakText(full);
        await loadSessionList(); // 更新侧边栏名称（可选）
    } catch (e) {
        alert("发送失败");
    } finally {
        loading.remove();
    }
}

function speakText(text) {
    try {
        const json = JSON.parse(text);
        const replyText = json.reply;
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(replyText);
        u.lang = "zh-CN";
        window.speechSynthesis.speak(u);
    } catch (e) {
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = "zh-CN";
        window.speechSynthesis.speak(u);
    }
}