import os
import uuid
import discord
# from discord_components import Button, SelectOption, Select
from discord.ext import commands
import asyncio
from models import Status, BotStatus, User, Song, SongQueue, DownloadQueue, Playlist
import youtube_dl
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from youtubesearchpython import VideosSearch, Video, ResultMode


class MusicDB:
    def __init__(self, db_path):
        engine = create_engine(db_path, echo=False)
        self.session = Session(engine)
        self.clear_status_table()

    def clear_status_table(self) -> None:
        self.session.query(BotStatus).delete()
        self.session.commit()
        self.set_bot_status(Status.STOP)

    def get_bot_status(self) -> BotStatus:
        bot_status = self.session.query(BotStatus).first()
        return bot_status

    def set_bot_status(self, status: Status) -> None:
        current_bot_status = self.get_bot_status()
        if current_bot_status:
            current_bot_status.status = status
            current_bot_status.pid = os.getpid()
        else:
            bot_status = BotStatus(
                status=status,
                pid=os.getpid()
            )
            self.session.add(bot_status)
        self.session.commit()

    def create_user(self, name: str) -> User:
        user = User(name=name)
        self.session.add(user)
        self.session.commit()
        return user

    def get_user(self, name: str) -> User:
        user = self.session.query(User).filter_by(name=name).first()
        if not user:
            user = self.create_user(name)
        return user

    def add_song_to_download_queue(self, song: Song, user: User) -> None:
        download_song = DownloadQueue(
            pid=os.getpid(),
            song_id=song.id,
            user_id=user.id
        )
        self.session.add(download_song)
        self.session.commit()

    def remove_song_from_download_queue(self, song: Song) -> None:
        download_song = self.session.query(
            DownloadQueue).filter_by(song_id=song.id).first()
        if download_song:
            self.session.delete(download_song)
            self.session.commit()

    def add_song(self, song: Song) -> None:
        self.session.add(song)
        self.session.commit()
    
    def add_song_to_playlist(self, user: User, song: Song):
        playlist = self.session.query(Playlist).filter_by(user_id=user.id, song_id=song.id).first()
        if not playlist:
            playlist = Playlist(
                user_id = user.id,
                song_id = song.id
            )
            self.session.add(playlist)
            self.session.commit()

    def add_song_to_song_queue(self, song: Song, user: User) -> None:
        song_item = SongQueue(
            song_id=song.id,
            user_id=user.id
        )
        self.session.add(song_item)
        self.session.commit()

    def get_next_song_from_queue(self) -> Song:
        song_queue_item = self.session.query(SongQueue).first()
        if not song_queue_item:
            return False
        song = self.session.query(Song).filter_by(
            id=song_queue_item.song_id).first()
        user = self.session.query(User).filter_by(
            id=song_queue_item.user_id).first()
        return song, user

    def remove_song_from_song_queue(self, song: Song) -> None:
        song_queue_item = self.session.query(
            SongQueue).filter_by(song_id=song.id).first()
        if song_queue_item:
            self.session.delete(song_queue_item)
            self.session.commit()


class SongTools:

    # Youtube Download Format Settings
    YTDL_SETTINGS = {
        'format': 'bestaudio/best',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'outtmpl': './songs/%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'no_warnings': True,
        'default_search': 'auto',
        # bind to ipv4 since ipv6 addresses cause issues sometimes
        'source_address': '0.0.0.0'
    }
    ytdl = youtube_dl.YoutubeDL(YTDL_SETTINGS)

    @classmethod
    def check_is_url(cls, url: str) -> bool:
        extractors = youtube_dl.extractor.gen_extractors()
        for extractor in extractors:
            if extractor.suitable(url) and extractor.IE_NAME != 'generic':
                return True
        return False

    @classmethod
    def get_song_info_from_youtube(cls, song_search_name: str = None, url=None) -> tuple:
        if song_search_name:
            video_search = VideosSearch(song_search_name, limit=1)
            song_data = video_search.result()['result'][0]
        else:
            song_data = Video.get(url, ResultMode.json)
        song_title = song_data['title']
        song_url = song_data['link']
        thumbnail = song_data['thumbnails'][0]['url']

        return song_title, song_url, thumbnail

    @classmethod
    async def download_from_youtube(cls, song: Song, loop) -> None:
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: SongTools.ytdl.extract_info(song.url, download=True))
        file_name = SongTools.ytdl.prepare_filename(data)
        song.file_path = file_name

class MusicBot(commands.Bot):

    commands_info = {
        'play': 'Play a song. Type .play song name or .play <url>',
        'queue': 'Show what is playing',
        'skip': 'Skip to the next song in the queue.',
        'pause': 'Pause the song that is currently playing.',
        'resume': 'Resume the song that was playing.',
        'leave': 'Leave the channel K-Music is in.'
    }

    def __init__(self, db_path, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.database = MusicDB(db_path=db_path)

    @classmethod
    def get_command_info(self, command: str) -> str:
        command_info = self.commands_info[command]
        return command_info

    def get_song_from_db(self, song_argument) -> Song:
        is_url = SongTools.check_is_url(song_argument)
        if is_url:
            song_file = self.database.session.query(
                Song).filter_by(url=song_argument).first()
            return song_file
        song_title, _, _ = SongTools.get_song_info_from_youtube(
            song_search_name=song_argument)

        song_file = self.database.session.query(
            Song).filter_by(title=song_title).first()
        return song_file

    def search_song_from_youtube(self, song_argument) -> Song:
        is_url = SongTools.check_is_url(song_argument)
        if is_url:
            song_title, song_url, thumbnail = SongTools.get_song_info_from_youtube(
                url=song_argument)
        else:
            song_title, song_url, thumbnail = SongTools.get_song_info_from_youtube(
                song_search_name=song_argument)
        song = Song(
            title=song_title,
            url=song_url,
            file_path=None,
            thumbnail=thumbnail,
            upvotes=0
        )
        return song

    def add_song_to_song_queue(self, song: Song, user: User) -> None:
        self.database.add_song_to_song_queue(song, user)

    async def download_song(self, ctx, song: Song, user: User, loop) -> None:
        self.database.add_song_to_download_queue(song, user)
        await self.send_message(ctx, f"Downloading Song: {song.url}")
        await SongTools.download_from_youtube(song, loop)
        self.database.add_song(song)
        self.database.remove_song_from_download_queue(song)
        self.database.add_song_to_song_queue(song, user)

    async def send_message(self, ctx, message: str) -> None:
        await ctx.send(message)

    def get_user_from_db(self, name) -> User:
        return self.database.get_user(name)

    async def check_user_connected(self, ctx) -> bool:
        if not ctx.message.author.voice:
            return False
        return True

    async def check_bot_connected(self, ctx) -> bool:
        voice_client = ctx.message.guild.voice_client
        if voice_client and voice_client.is_connected():
            return True
        return False

    async def connect_to_channel(self, ctx) -> None:
        try:
            channel = ctx.message.author.voice.channel
            await channel.connect()
        except discord.errors.ClientException:
            await self.send_message("Failed to connect to channel.")

    async def add_to_playlist(self, ctx) -> None:
        user_name = ctx.author.name
        user = self.database.get_user(user_name)
        song, _ = self.database.get_next_song_from_queue()
        self.database.add_song_to_playlist(user, song)

        embed = discord.Embed(title=f"{user.name}'s Playlist", color=discord.Color.green())
        embed.add_field(name="Song Added", value=song.title, inline=False)
        embed.set_thumbnail(url=song.thumbnail)
        await ctx.send(embed=embed)

    async def send_now_playing(self, ctx, song: Song, user: User) -> None:

        embed = discord.Embed(title=f"Now Playing", color=discord.Color.green())
        embed.add_field(name="Title", value=song.title, inline=False)
        embed.add_field(name="Played By", value=user.name, inline=False)
        embed.set_thumbnail(url=song.thumbnail)

        # youtube_link_button = Button(label='YouTube', style=5, url=song.url)
        
        await ctx.send(
                embed=embed,
                view=NowPlayingButtons(self, ctx)
            )

    async def play_next_song(self, ctx) -> None:
        server = ctx.message.guild
        voice_channel = server.voice_client
        event = asyncio.Event()

        song, user = self.database.get_next_song_from_queue()
        await self.send_now_playing(ctx, song, user)

        voice_channel.play(
            discord.FFmpegPCMAudio(
                # executable="/usr/bin/ffmpeg", source=song.file_path),  # ffmpeg.exe
                executable="ffmpeg.exe",
                source=song.file_path),  # ffmpeg.exe
            after=lambda _: self.loop.call_soon_threadsafe(event.set)
        )
        await event.wait()

        self.database.remove_song_from_song_queue(song)

    async def show_queue(self, ctx) -> None:
        pass

    async def skip(self, ctx) -> None:
        voice_client = ctx.message.guild.voice_client
        if voice_client.is_playing():
            self.database.set_bot_status(Status.STOP)
            try:
                await voice_client.stop()
            except Exception:
                pass  # TODO: This seems to throw an exception even though it works?
        else:
            await ctx.send("K-Music is not playing anything.")

    async def pause(self, ctx) -> None:
        voice_client = ctx.message.guild.voice_client
        if voice_client.is_playing():
            self.database.set_bot_status(Status.PAUSE)
            try:
                await voice_client.pause()
            except Exception:
                pass  # TODO: This seems to throw an exception even though it works?
        else:
            await ctx.send("K-Music is not playing anything.")

    async def resume(self, ctx) -> None:
        voice_client = ctx.message.guild.voice_client
        if voice_client.is_paused():
            self.database.set_bot_status(Status.PLAYING)
            try:
                await voice_client.resume()
            except Exception:
                pass  # TODO: This seems to throw an exception even though it works?

        else:
            await ctx.send("The bot was not paused before this.")

    def check_song_playing(self, ctx) -> bool:
        voice_client = ctx.message.guild.voice_client
        return not voice_client.is_paused()

    async def leave(self, ctx) -> None:
        voice_client = ctx.message.guild.voice_client
        if voice_client.is_connected():
            self.database.clear_status_table()
            await voice_client.disconnect()
        else:
            await ctx.send("K-Music is not in a channel.")

class NowPlayingButtons(discord.ui.View):

    def __init__(self, music_bot, ctx):
        super().__init__()
        self.music_bot = music_bot
        self.ctx = ctx

    @discord.ui.button(label='Pause', style=discord.ButtonStyle.red, emoji="⏸️")
    async def play_pause(self, button: discord.ui.Button, interaction: discord.Interaction):
        if button.style == discord.ButtonStyle.green:
            button.style = discord.ButtonStyle.red
            button.emoji = '⏸️'
            button.label = 'Pause'
            await self.music_bot.resume(self.ctx)
        elif button.style == discord.ButtonStyle.red:
            button.style = discord.ButtonStyle.green
            button.emoji = '▶️'
            button.label = 'Play'
            await self.music_bot.pause(self.ctx)
        
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Skip', style=discord.ButtonStyle.red, emoji="⏩")
    async def skip(self, button: discord.ui.Button, interaction: discord.Interaction):
        currently_playing = self.music_bot.check_song_playing(self.ctx)
        if not currently_playing:
           await self.music_bot.resume(self.ctx)
        button.disabled = True
        await self.music_bot.skip(self.ctx)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Add', style=discord.ButtonStyle.green, emoji="➕")
    async def add(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.music_bot.add_to_playlist(self.ctx)
        await interaction.response.edit_message(view=self)


class Request:

    bot_status = Status()

    def __init__(self, ctx, music_bot: MusicBot):
        self.ctx = ctx
        self.music_bot = music_bot
        self.pid = os.getpid()

    async def create_thread(self, action: Status):
        current_status = self.music_bot.database.get_bot_status()

        if not current_status or current_status.status == self.bot_status.STOP:
            if action == self.bot_status.PLAYING:
                self.music_bot.database.set_bot_status(Status.PLAYING)

                await self.music_bot.play_next_song(ctx=self.ctx)

                self.music_bot.database.set_bot_status(Status.STOP)

                if self.music_bot.database.get_next_song_from_queue():
                    await asyncio.sleep(5)
                    await self.create_thread(action=self.bot_status.PLAYING)
                return

        # If the most recent action is to pause, exit this thread.
        if current_status.status == self.bot_status.PAUSE:
            return

        # If the bot is already playing something, exit this thread.
        if current_status.status == self.bot_status.PLAYING:
            return


# Environment Variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
FFMPEG_PATH = os.getenv("FFMPEG_PATH")
