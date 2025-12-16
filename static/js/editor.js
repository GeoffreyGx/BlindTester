let songList = []
let player

window.addEventListener("DOMContentLoaded", async () => {
    document.getElementById("content").innerHTML = `Loading saved song list...`
    let savedSongList = await localStorage.getItem("savedSongList")
    if (savedSongList) {
        songList = loadJSON(savedSongList);
        refreshSidebar()
        refreshContent(0)
    } else {
        document.getElementById("content").innerHTML = `No saved song list found. Click on "Add a new song" to begin`
    }
});

document.getElementById("jsonLoadingButton").addEventListener("click", () => {
    document.getElementById('jsonFileInput').click()
})

document.getElementById('jsonFileInput').addEventListener('change', () => {
    const file = document.getElementById('jsonFileInput').files[0];
    if (!file) return;  
    const reader = new FileReader();    
    reader.onload = () => {
      try {
        songList = loadJSON(reader.result)
        refreshSidebar()
        refreshContent(0)
      } catch (err) {
        alert('Invalid JSON file');
      }
    };  
    reader.readAsText(file);    
})

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
    timestamp = song.get("timestamp")

    if (youtube_url) {
        html = `<h3>${title} - ${artist}</h3><h5>${youtube_url} Starting at : ${timestamp} seconds</h5><label>Artist : </label><input id="artist"></input><br /><label>Title : </label><input id="title"></input><br /><label>Youtube URL : </label><input id="youtube_url"></input><br /><button onclick="updateSong(${index})">Update</button><button onclick="setCurrentTimestamp(${index})">Set current timestamp</button><br /><div id="player"></div>`
    } else {
        html = `<h3>${title} - ${artist}</h3><h5>${youtube_url}</h5><label>Artist : </label><input id="artist"></input><br /><label>Title : </label><input id="title"></input><br /><label>Youtube URL : </label><input id="youtube_url"></input><br /><button onclick="updateSong(${index})">Update</button>`
    }

    content.innerHTML = html

    if (youtube_url) {
        loadYouTubePlayer(youtube_url, timestamp)
    }
}

function newSong() {
    const emptyTemplate = new Map([
        ["artist", ""],
        ["title", ""],
        ["youtube_url", ""],
        ["timestamp", 0]
    ]);
    songList.push(emptyTemplate)
    refreshSidebar()
    refreshContent(songList.length - 1)
}

function updateSong(index) {
    artist = document.getElementById("artist")
    title = document.getElementById("title")
    youtube_url = document.getElementById("youtube_url")
    if (youtube_url.value) {
        youtube_url_formatted = `${youtube_url.value.split("watch?v=")[1].split("?")[0].split("&")[0]}`
    } else {
        youtube_url_formatted = ''
    }
    song = songList[index]
    if (artist.value) {
        song.set("artist", artist.value)
    }
    if (title.value) {
        song.set("title", title.value)
    }
    if (youtube_url_formatted) {
        song.set("youtube_url", youtube_url_formatted)
    }
    console.log(youtube_url_formatted)
    refreshSidebar()
    refreshContent(index)
    localStorage.setItem("savedSongList", convertToJSON(songList)) 
}

function loadYouTubePlayer(video_id, video_timestamp) {
    player = new YT.Player('player', {
        height: '390',
        width: '640',
        videoId: video_id,
        playerVars: {
            start: video_timestamp
        },
        events: {
            'onReady': (event) => {
                event.target.playVideo();
            }
        }
    });
}

function setCurrentTimestamp(index) {
    startTime = Math.floor(player.getCurrentTime())
    const song = songList[index]
    song.set("timestamp", startTime)
    refreshContent(index)
    localStorage.setItem("savedSongList", convertToJSON(songList)) 
}

function loadJSON(json_string) {
    json = JSON.parse(json_string)
    let songList = []
    json["songs"].forEach((dict, index) => {
        const song = new Map([
            ["artist", dict["artist"]],
            ["title", dict["title"]],
            ["youtube_url", dict["youtube_url"]],
            ["timestamp", dict["timestamp"]]
        ]);
        songList.push(song)
    })
    return songList
}

function convertToJSON() {
    let songs_json = { "songs": [] }
    songList.forEach((song, index) => {
        const obj = Object.fromEntries(song)
        songs_json["songs"].push(obj)
    })
    return JSON.stringify(songs_json)
}

function exportToJSON() {
    json = convertToJSON()
    var file = new Blob([json], {
        type: 'application/json'
    })
    saveAs(file, "songs.json")
}