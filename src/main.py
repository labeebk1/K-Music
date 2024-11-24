import os
import uvicorn
import asyncio
import discord
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from utils import MusicBot

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Discord Bot Setup
intents = discord.Intents.all()
music_bot = MusicBot(db_path="sqlite:///music.db", command_prefix="!", intents=intents)

app = FastAPI()

@app.on_event("startup")
async def startup():
    loop = asyncio.get_event_loop()
    loop.create_task(music_bot.start(DISCORD_TOKEN))

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


@app.post("/play_now")
async def play_now(request: PlayRequest):
    """
    Add a song to the song queue or play it immediately if the queue is empty.
    """
    # Extract data from the request
    title = request.title
    url = request.url
    user_name = request.user_name

    # Ensure the song is in the database
    user = music_bot.get_user_from_db(user_name)

    # Get the streamable URL
    streamable_url = music_bot.get_streamable_url(url)

    # Create song object
    song = music_bot.get_or_create_song(title=title, url=streamable_url)

    # Connect to Voice Channel
    voice_client = await music_bot.connect_to_voice_channel()

    # Stream the song
    await music_bot.stream_song(voice_client, song)

    return {"message": f"Streaming"}

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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)