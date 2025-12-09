let songList = []
let songStartTimes = []

function refreshSidebar() {
    const sidebar = document.getElementById("sidebar")
    let html = ""
    songList.forEach((song, index) => {
        artist = song.get("artist")
        title = song.get("title")
        if (title && artist) {
            html += `<div class="songThumbnail" onclick="refreshContent(${index})"><span>${artist} - ${title}</span></div>`
        } else {
            html += `<div class="songThumbnail" onclick="refreshContent(${index})"><span>New Song</span></div>`
        }
    })
    sidebar.innerHTML = html
}

function refreshContent(index) {
    const content = document.getElementById("content")
    const song = songList[index]
    artist = song.get("artist")
    title = song.get("title")
    youtube_url = song.get("youtube_url")
    if (youtube_url) {
        html = `<h3>${title} - ${artist}</h3><h5>${youtube_url}</h5><label>Artist : </label><input id="artist"></input><br /><label>Title : </label><input id="title"></input><br /><label>Youtube URL : </label><input id="youtube_url"></input><br /><label>Start Time</label><input type="range" id="start_time" min=0 max=300></input><br /><button onclick="updateSong(${index})">Update</button><iframe src="${youtube_url}"></iframe>`
    } else {
        html = `<h3>${title} - ${artist}</h3><h5>${youtube_url}</h5><label>Artist : </label><input id="artist"></input><br /><label>Title : </label><input id="title"></input><br /><label>Youtube URL : </label><input id="youtube_url"></input><br /><label>Start Time</label><input type="range" id="start_time" min=0 max=300></input><br /><button onclick="updateSong(${index})">Update</button>`
    }
    content.innerHTML = html
}

function newSong() {
    const emptyTemplate = new Map([
        ["artist", "zeazoepaz"],
        ["title", "eazeaze"],
        ["youtube_url", "azeoazjkeoakepoazkeazpoekap"]
    ]);
    songList.push(emptyTemplate)
    refreshSidebar()
}

function updateSong(index) {
    artist = document.getElementById("artist")
    title = document.getElementById("title")
    youtube_url = document.getElementById("youtube_url")
    startTime = document.getElementById("start_time")
    if (youtube_url.value) {
        youtube_url_formatted = `https://www.youtube.com/embed/${youtube_url.value.split("watch?v=")[1].split("?")[0].split("&")[0]}?start=${startTime.value}`
    } else {
        youtube_url_formatted = ''
    }
    song = songList[index]
    songStartTime = songStartTimes[index]
    song.set("artist", artist.value)
    song.set("title", title.value)
    song.set("youtube_url", youtube_url_formatted)
    songStartTime = startTime.value
    console.log(youtube_url_formatted)
    refreshSidebar()
    refreshContent(index)
}

function exportToJSON() {
    let songs_json = { "songs": [] }
    songList.forEach((song) => {
        const obj = Object.fromEntries(song)
        songs_json["songs"].push(obj)
    })
    json = JSON.stringify(songs_json)
    
    var file = new Blob([json], {
        type: 'application/json'
    })

    saveAs(file, "songs.json")
}