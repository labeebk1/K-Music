import asyncio
import discord
from discord.ext import commands
import yt_dlp
from asyncio import Lock

from utils.dao import MusicDAO
from utils.entity import User, Song

TARGET_GUILD = "Sudden Death"
TARGET_CHANNEL = "General"

class MusicBot(commands.Bot):

    def __init__(self, db_path, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.database = MusicDAO(db_path=db_path)
        self.is_playing = False
        self.skip_to_replay = False
        self.lock = Lock()  # Ensure mutual exclusion during playback operations

    def add_song_to_song_queue(self, song: Song, user: User) -> None:
        self.database.add_song_to_song_queue(song, user)

    def get_user_from_db(self, name) -> User:
        return self.database.get_user(name)

    async def connect_to_voice_channel(self):
        """
        Connect to the General voice channel.
        """
        for vc in self.voice_clients:
            if vc.is_connected():
                return vc

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

    async def run_background_task(self):
        """
        Periodically check if the bot is idle and handle playback.
        """
        while True:
            await asyncio.sleep(2)  # Check every 2 seconds
            async with self.lock:
                if not self.is_playing:
                    await self.play_next_song()

    async def play_next_song(self):
        """
        Play the next song in the queue, if available.
        """
        song, user = self.database.get_first_song_from_queue()
        if song:
            voice_client = await self.connect_to_voice_channel()
            await self.stream_song(voice_client, song)
        else:
            self.is_playing = False

    async def stream_song(self, voice_client, song):
        """
        Stream a song from YouTube.
        """
        try:
            print(f"Streaming song: {song.title}")
            self.is_playing = True
            streamable_url = self.get_streamable_url(song.url)
            source = discord.FFmpegPCMAudio(
                executable="./ffmpeg.exe",
                source=streamable_url,
            )

            # Truncate the song title to 32 characters
            nickname = song.title[:32]
            guild = discord.utils.get(self.guilds, name=TARGET_GUILD)
            if guild and guild.me:  # Ensure the bot is in the guild
                await guild.me.edit(nick=nickname)

            voice_client.play(source, after=lambda e: self.handle_end_of_song(song))
        except Exception as e:
            print(f"Error streaming song: {e}")
            song, _ = self.database.get_first_song_from_queue()
            self.database.remove_song_from_queue(song_title=song.title)
            self.is_playing = False
    
    def handle_end_of_song(self, song):
        if self.skip_to_replay:
            self.skip_to_replay = False
            print(f"Skipping removal for replay: {song.title}")
            return

        self.is_playing = False
        self.database.remove_song_from_queue(song_title=song.title)

    async def replay(self):
        """
        Replay the current song.
        """
        song, _ = self.database.get_first_song_from_queue()
        if not song:
            print("No song to replay.")
            return

        print(f"Replaying song: {song.title}")
        voice_client = await self.connect_to_voice_channel()
        
        # Set the replay flag and stop the current song
        self.skip_to_replay = True
        if voice_client.is_playing():
            voice_client.stop()

        # Replay the song
        await self.stream_song(voice_client, song)
        return {"message": "Replaying"}


    async def skip_current_song(self):
        """
        Skip the current song by stopping playback.
        """
        async with self.lock:
            for vc in self.voice_clients:
                if vc.is_playing():
                    vc.stop()
            
            self.database.remove_first_song_from_song_queue()
            self.is_playing = False
            self.skip_to_replay = False

    def get_streamable_url(self, song_url):
        ydl_opts = {'format': 'bestaudio/best', 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(song_url, download=False)
            return info['url']
