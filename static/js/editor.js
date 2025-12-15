let origin = window.location.origin;

let songList = []
let player

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
        html = `<h3>${title} - ${artist}</h3><h5>${youtube_url} Starting at : ${timestamp} seconds</h5><label>Artist : </label><input id="artist"></input><br /><label>Title : </label><input id="title"></input><br /><label>Youtube URL : </label><input id="youtube_url"></input><br /><button onclick="updateSong(${index})">Update</button><button onclick="setCurrentTimestamp(${index})">Set current timestamp</button><br /><div id="player"></div><br /><h3>Orthographic variations</h3><button onclick="generateVariations(${index})">Automatic AI-powered generation</button><br /><div id="name_variations" class="nameVariationsBox"></div>`
    } else {
        html = `<h3>${title} - ${artist}</h3><h5>${youtube_url}</h5><label>Artist : </label><input id="artist"></input><br /><label>Title : </label><input id="title"></input><br /><label>Youtube URL : </label><input id="youtube_url"></input><br /><button onclick="updateSong(${index})">Update</button><br /><h3>Orthographic variations</h3><button onclick="generateVariations(${index})">Automatic AI-powered generation</button><br /><div id="name_variations" class="nameVariationsBox"></div>`
    }

    content.innerHTML = html

    if (youtube_url) {
        loadYouTubePlayer(youtube_url, timestamp)
    }

    refreshNameVariations(index)
}

function refreshNameVariations(index) {
    const song = songList[index]

    artist_writings = song.get("artist_writings")
    title_writings = song.get("title_writings")

    html = "<h4>Artist variations : </h4>"
    artist_writings.forEach((element) => {
        html = html + `<div class="element"><p>${element}</p><button onclick="removeVariation(${index}, 'artist_writings', '${element}')">-</button></div>`
    })

    html = html + `<div class="element"><input id='variationArtistInput' placeholder='Add your own variations...'></input><button onclick="addVariation(${index}, 'artist_writings')" class='add'>+</button></div>`
    
    html = html + "<h4>Title variations : </h4>"
    title_writings.forEach((element) => {
        html = html + `<div class="element"><p>${element}</p><button onclick="removeVariation(${index}, 'title_writings', '${element}')" class="remove">-</button></div>`
    })
    html = html + `<div class="element"><input id='variationTitleInput' placeholder='Add your own variations...'></input><button onclick="addVariation(${index}, 'title_writings')" class='add'>+</button></div>`
    
    document.getElementById("name_variations").innerHTML = html
}

function newSong() {
    const emptyTemplate = new Map([
        ["artist", ""],
        ["title", ""],
        ["youtube_url", ""],
        ["timestamp", 0],
        ["artist_writings", []],
        ["title_writings", []]
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
}

async function generateVariations(index) {
    const song = songList[index];

    console.log(`${song.get("title")} - ${song.get("artist")}`)
    const params = new URLSearchParams({
        artist: song.get("artist"),
        title: song.get("title"),
    });

    const res = await fetch(`${origin}/get_variations?${params}`, { method: 'POST' });
    const data = await res.json();

    song.set("title_writings", data["title_writings"]);
    song.set("artist_writings", data["artist_writings"]);

    refreshNameVariations(index)
}

function addVariation(index, type) {
    const song = songList[index]
    const name = (document.getElementById('variationTitleInput').value ? document.getElementById('variationTitleInput').value : document.getElementById('variationArtistInput').value)
    if (name) {
        let varList = song.get(type)
        varList.push(name)
        song.set(type, varList)
        refreshNameVariations(index)
    }
}

function removeVariation(index, type, name) {
    const song = songList[index]
    let varList = song.get(type)

    varList = varList.filter(v => v !== name)
    song.set(type, varList)

    refreshNameVariations(index)
}

function exportToJSON() {
    let songs_json = { "songs": [] }
    songList.forEach((song, index) => {
        const obj = Object.fromEntries(song)
        songs_json["songs"].push(obj)
    })
    json = JSON.stringify(songs_json)
    
    var file = new Blob([json], {
        type: 'application/json'
    })

    saveAs(file, "songs.json")
}