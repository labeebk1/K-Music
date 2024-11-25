import os
import uvicorn
import asyncio
import discord
import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from utils import MusicBot

# Load environment variables
DISCORD_TOKEN = "OTUxNDk3MzE4NzI3ODE5MjY0.G_0Wk2.f9-8UgQsJ7Ap-EAEIqO3t37WFblxNDW3ZbPWvU"

# Discord Bot Setup
intents = discord.Intents.all()
music_bot = MusicBot(db_path="sqlite:///music.db", command_prefix="!", intents=intents)

app = FastAPI()

@app.on_event("startup")
async def startup():
    loop = asyncio.get_event_loop()
    loop.create_task(music_bot.start(DISCORD_TOKEN))
    loop.create_task(music_bot.run_background_task())  # Start the background task for queue management

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your frontend's domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models for API requests
class PlayRequest(BaseModel):
    title: str
    url: str
    user_name: str


class RemoveFromQueueRequest(BaseModel):
    position: int


class UserRequest(BaseModel):
    name: str
    password: str


class UsernameRequest(BaseModel):
    name: str

class PlaylistImportRequest(BaseModel):
    user_name: str
    url: str

@app.get("/pause")
async def pause():
    """
    Pause the current song.
    """
    voice_client = await music_bot.connect_to_voice_channel()
    if voice_client.is_playing():
        voice_client.pause()

    return {"message": "Paused"}

@app.get("/resume")
async def resume():
    """
    Resume the current song.
    """
    voice_client = await music_bot.connect_to_voice_channel()
    if voice_client.is_paused():
        voice_client.resume()

    return {"message": "Resumed"}

@app.get("/replay")
async def replay():
    """
    Replay the current song.
    """
    await music_bot.replay()
    return {"message": "Replaying"}

@app.get("/current_song")
async def get_current_song():
    """
    Fetch the currently playing song.
    """
    song, user = music_bot.database.get_first_song_from_queue()
    if song:
        return {"title": song.title, "user": user.name}
    return {"title": "", "user": ""}

@app.get("/skip")
async def skip():
    """
    Skip the current song and play the next one in the queue.
    """
    await music_bot.skip_current_song()
    return {"message": "Skipped to the next song"}

@app.get("/queue")
async def get_queue():
    queue = music_bot.database.show_queue()
    return {"queue": queue}

@app.post("/add_to_queue")
async def add_to_queue(request: PlayRequest):
    """
    Add a song to the song queue.
    """
    title = request.title
    url = request.url
    user_name = request.user_name
    user = music_bot.get_user_from_db(user_name)
    song = music_bot.get_or_create_song(title=title, url=url)
    music_bot.database.add_song_to_song_queue(song, user)
    return {"message": "Song added to queue."}

@app.post("/add_to_playlist")
async def add_to_playlist(request: PlayRequest):
    """
    Add a song to the user's playlist.
    """
    title = request.title
    url = request.url
    user_name = request.user_name
    user = music_bot.get_user_from_db(user_name)
    song = music_bot.get_or_create_song(title=title, url=url)
    music_bot.database.add_song_to_playlist(user, song)
    return {"message": "Song added to playlist."}

@app.post("/remove_from_playlist")
async def remove_from_playlist(request: PlayRequest):
    """
    Remove a song from the user's playlist.
    """
    title = request.title
    url = request.url
    user_name = request.user_name
    user = music_bot.get_user_from_db(user_name)
    song = music_bot.get_song(title=title)
    music_bot.database.remove_song_from_playlist(user, song)
    return {"message": "Song removed from playlist."}

@app.post("/show_playlist")
async def show_playlist(request: UsernameRequest):
    """
    Show the user's playlist.
    """
    user_name = request.name
    user = music_bot.get_user_from_db(user_name)
    playlist = music_bot.database.show_playlist(user)
    return {"playlist": playlist}

@app.post("/remove_from_queue")
async def remove_from_queue(request: RemoveFromQueueRequest):
    """
    Remove a song from the queue by its position.
    """
    try:
        # Get the queue from the database
        queue = music_bot.database.show_queue()
        position = request.position
        # Check if the position is valid
        if position < 0 or position >= len(queue):
            raise HTTPException(status_code=400, detail="Invalid position")

        # Remove the song from the queue
        song_to_remove = queue[position]
        music_bot.database.remove_song_from_queue(song_to_remove['song'])
        return {"message": f"Removed {song_to_remove['song']} from the queue."}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
async def login(request: UserRequest):
    user_exists = music_bot.database.user_exists(request.name)

    if user_exists:
        authenticated = music_bot.database.authenticate_user(request.name, request.password)
        if not authenticated:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        return {"user": request.name}
    else:
        music_bot.database.create_user(request.name, request.password)
        return {"user": request.name}

@app.post("/import_playlist")
async def import_playlist(request: PlaylistImportRequest):
    """
    Import songs from a YouTube Music playlist URL into the user's playlist.
    """
    user_name = request.user_name
    playlist_url = request.url

    # Validate user
    user = music_bot.get_user_from_db(user_name)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Extract songs from the playlist
    songs = extract_playlist_details(playlist_url)
    if not songs:
        raise HTTPException(status_code=400, detail="No songs found in the playlist.")

    # Add songs to the user's playlist
    for song in songs:
        song_obj = music_bot.get_or_create_song(title=song["title"], url=song["url"])
        music_bot.database.add_song_to_playlist(user, song_obj)

    return {"message": f"Imported {len(songs)} songs to {user_name}'s playlist."}

def extract_playlist_details(playlist_url):
    """
    Extract song titles and URLs from a YouTube Music playlist.
    """
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)
            songs = [
                {"title": entry["title"], "url": entry["url"]}
                for entry in playlist_info.get("entries", [])
            ]
            return songs
    except Exception as e:
        print(f"Error extracting playlist details: {e}")
        raise HTTPException(status_code=400, detail="Failed to extract playlist details.")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)