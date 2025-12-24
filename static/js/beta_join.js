gameCodeBox = document.getElementById('game_code_box');
gameCodeInput = document.getElementById('game_code_input');
usernameBox = document.getElementById('username_box');
errorBox = document.getElementById('error_box')

let lastChecked = "";

async function checkGameCode() {
    gameCode = gameCodeInput.value.trim().toLowerCase();

    if (gameCode === lastChecked) return;
    lastChecked = gameCode;
    
    try {
        const res = await fetch(`/ping/${gameCode}`, { method: 'POST' });
        const data = await res.json();

        if (data.action === "party_found") {
            gameCodeBox.classList.add("hidden");
            usernameBox.classList.remove("hidden");
        } else {
            errorBox.innerHTML = `<p class="error">Game not found!</p>`
            gameCodeBox.classList.remove("hidden");
            usernameBox.classList.add("hidden");
        }
    } catch {
        usernameBox.classList.add("hidden");
    }
}