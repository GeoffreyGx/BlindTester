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
    hideAll();

    switch (state.phase) {
        case 'WAITING':
            showWaitingBox();
            break;
        case 'ANSWERING':
            showAnsweringBox(state.can_answer);
            break;
        case 'LEADERBOARD':
            showLeaderboard(state.leaderboard);
            break;
        case 'LOCKED':
            showLocked();
            break;
        case 'KICKED':
            showKicked();
            break;
        default:
            showError();
            break;
    };
}

function hideAll() {
    for (const [_, value] of Object.entries(phase)) {
        value.classList.add("hidden");
    };
}

function showWaitingBox() {
    phase.waitingBox.classList.remove("hidden");
}

function showAnsweringBox(canAnswer) {
    phase.answeringBox.classList.remove("hidden");
}

function showLeaderboard(leaderboard) {
    phase.leaderboardBox.classList.remove("hidden");
}

function showLocked() {
    phase.lockedBox.classList.remove("hidden");
}

function showKicked() {
    phase.kickedBox.classList.remove("hidden");
}

function showError() {
    phase.errorBox.classList.remove("hidden");
}

ws.onopen = () => {
    try {
        ws.send(JSON.stringify({type: "hello"}));
    } catch (e) {
        console.log(`Error while connecting to server... : ${e}`);
    }
}

ws.onmessage = (message) => {
    const msg = JSON.parse(message.data);

    if (msg.type === "snapshot") {
        state = {
            ...state,
            ...msg
        }
    }

    console.log(msg);
    render(state);
}