const phase = {
    waitingBox: document.getElementById('waiting'),
    answeringBox: document.getElementById('answering'),
    leaderboardBox: document.getElementById('leaderboard'),
    lockedBox: document.getElementById('locked'),
    kickedBox: document.getElementById('kicked'),
    errorBox: document.getElementById('error')
}

const ws = new WebSocket(WS_URL)

let state = {
    phase: null,
    can_answer: false,
    leaderboard: []
}

function render(state) {
    hideAll()

    switch (state.phase) {
        case 'ANSWERING':
            showAnsweringBox(state.canAnswer)
        case 'LEADERBOARD':
            showLeaderboard(state.leaderboard)
        case 'LOCKED':
            showLocked()
        case 'KICKED':
            showKicked()
        default:
            showError()
    }
}

function hideAll() {
    for (const [_, value] of Object.entries(phase)) {
        value.classList.add("hidden")
    }
}

function showAnsweringBox(canAnswer) {
    phase.answeringBox.classList.remove("hidden")
}

function showLeaderboard(leaderboard) {
    phase.leaderboardBox.classList.remove("hidden")
}

function showLocked() {
    phase.lockedBox.classList.remove("hidden")
}

function showKicked() {
    phase.kickedBox.classList.remove("hidden")
}

function showError() {
    phase.errorBox.classList.remove("hidden")
}

ws.onopen = () => {
    ws.send({ type: "hello" })
}

ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);

    if (msg.type === "snapshot") {
        msg = state
    }

    render(state)
}