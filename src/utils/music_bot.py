import asyncio
import discord
from discord.ext import commands
import yt_dlp

from utils.dao import MusicDAO
from utils.entity import Status, User, Song

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
            source = discord.FFmpegPCMAudio(
                executable="./ffmpeg.exe",
                source=song.url,
            )
            voice_client.play(source)
            print(f"Now streaming: {song.title}")
        except Exception as e:
            print(f"Error while streaming song: {e}")


    # async def add_to_playlist(self, ctx, user_name) -> None:
    #     user = self.database.get_user(user_name)
    #     song, _ = self.database.get_next_song_from_queue()
        
    #     song_in_playlist = self.database.add_song_to_playlist(user, song)
    #     if song_in_playlist:
    #         await self.send_message(ctx=ctx, message=f"{song.title} is already in {user_name}'s playlist")
    #     else:
    #         embed = discord.Embed(title=f"{user.name}'s Playlist", color=discord.Color.green())
    #         embed.add_field(name="Song Added", value=song.title, inline=False)
    #         embed.set_thumbnail(url=song.thumbnail)
    #         await ctx.send(embed=embed)

    # async def play_next_song(self) -> None:
    #     """
    #     Play the next song in the queue by streaming it from YouTube.
    #     """
    #     song, user = self.database.get_next_song_from_queue()
    #     if not song:
    #         print("No songs in the queue.")
    #         return

    #     # Stream the song
    #     await self.stream_song(song)

    #     # Remove from queue after playing
    #     self.database.remove_song_from_song_queue(song)

    # async def show_queue(self, ctx) -> None:
    #     pass

    # async def show_playlist(self, ctx) -> None:
    #     user_name = ctx.author.name
    #     user = self.database.get_user(user_name)
    #     user_songs = self.database.get_playlist(user)
    #     print(user_songs)

    # async def skip(self, ctx) -> None:
    #     voice_client = ctx.message.guild.voice_client
    #     if voice_client.is_playing():
    #         self.database.set_bot_status(Status.STOP)
    #         try:
    #             await voice_client.stop()
    #         except Exception:
    #             pass  # TODO: This seems to throw an exception even though it works?
    #     else:
    #         await ctx.send("K-Music is not playing anything.")

    # async def pause(self, ctx) -> None:
    #     voice_client = ctx.message.guild.voice_client
    #     if voice_client.is_playing():
    #         self.database.set_bot_status(Status.PAUSE)
    #         try:
    #             await voice_client.pause()
    #         except Exception:
    #             pass  # TODO: This seems to throw an exception even though it works?
    #     else:
    #         await ctx.send("K-Music is not playing anything.")

    # async def resume(self, ctx) -> None:
    #     voice_client = ctx.message.guild.voice_client
    #     if voice_client.is_paused():
    #         self.database.set_bot_status(Status.PLAYING)
    #         try:
    #             await voice_client.resume()
    #         except Exception:
    #             pass  # TODO: This seems to throw an exception even though it works?

    #     else:
    #         await ctx.send("The bot was not paused before this.")

    # def check_song_playing(self, ctx) -> bool:
    #     voice_client = ctx.message.guild.voice_client
    #     return not voice_client.is_paused()

    # async def leave(self, ctx) -> None:
    #     voice_client = ctx.message.guild.voice_client
    #     if voice_client.is_connected():
    #         self.database.clear_status_table()
    #         await voice_client.disconnect()
    #     else:
    #         await ctx.send("K-Music is not in a channel.")

    def get_streamable_url(self, song_url):
        ydl_opts = {'format': 'bestaudio/best', 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(song_url, download=False)
            return info['url']