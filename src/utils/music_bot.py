import asyncio
import discord
from discord.ext import commands
import yt_dlp

from utils.dao import MusicDAO
from utils.entity import User, Song

TARGET_GUILD = "Sudden Death"
TARGET_CHANNEL = "General"

class MusicBot(commands.Bot):

    def __init__(self, db_path, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.database = MusicDAO(db_path=db_path)

    def add_song_to_song_queue(self, song: Song, user: User) -> None:
        self.database.add_song_to_song_queue(song, user)

    def get_user_from_db(self, name) -> User:
        return self.database.get_user(name)
    
    async def connect_to_voice_channel(self):
        # Cleanup stale connections
        for vc in self.voice_clients:
            if vc.is_connected():
                return vc

        # Find the target guild and channel
        guild = discord.utils.get(self.guilds, name=TARGET_GUILD)
        channel = discord.utils.get(guild.voice_channels, name=TARGET_CHANNEL)
        try:
            return await channel.connect(reconnect=True, timeout=60)
        except Exception as e:
            print(f"Failed to connect to {channel.name}: {e}")
            return None

    def get_song(self, title: str):
        return self.database.get_song(title)

    def get_or_create_song(self, title: str, url: str) -> Song:
        """
        Get a song by URL or create it if it doesn't exist.
        """
        song = self.database.session.query(Song).filter_by(url=url).first()
        if not song:
            print("Song not found in the database. Creating a new entry.")
            song = Song(title=title, url=url)
            self.database.add_song(song)
        return song

    async def stream_song(self, voice_client, song) -> None:
        """
        Stream a song directly from YouTube.
        """
        try:
            print(f"Streaming song: {song.title}")
            streamable_url = self.get_streamable_url(song.url)
            source = discord.FFmpegPCMAudio(
                executable="./ffmpeg.exe",
                source=streamable_url,
            )
            voice_client.play(source)
        except Exception as e:
            print(f"Error while streaming song: {e}")

        self.database.remove_first_song_from_song_queue()
        song, _ = self.database.get_first_song_from_queue()
        if song:
            await self.stream_song(voice_client, song)

    def get_streamable_url(self, song_url):
        ydl_opts = {'format': 'bestaudio/best', 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(song_url, download=False)
            return info['url']