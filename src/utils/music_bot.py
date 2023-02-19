import asyncio
import discord
from discord.ext import commands

from utils.dao import MusicDAO
from utils.entity import Status, User, Song
from utils.song_tools import SongTools

class MusicBot(commands.Bot):

    commands_info = {
        'play': 'Play a song. Type .play song name or .play <url>',
        'playlist': 'Show your playlist',
        'queue': 'Show what is playing',
        'skip': 'Skip to the next song in the queue.',
        'pause': 'Pause the song that is currently playing.',
        'resume': 'Resume the song that was playing.',
        'leave': 'Leave the channel K-Music is in.'
    }

    def __init__(self, db_path, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)
        self.database = MusicDAO(db_path=db_path)

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

    async def add_to_playlist(self, ctx, user_name) -> None:
        user = self.database.get_user(user_name)
        song, _ = self.database.get_next_song_from_queue()
        
        song_in_playlist = self.database.add_song_to_playlist(user, song)
        if song_in_playlist:
            await self.send_message(ctx=ctx, message=f"{song.title} is already in {user_name}'s playlist")
        else:
            embed = discord.Embed(title=f"{user.name}'s Playlist", color=discord.Color.green())
            embed.add_field(name="Song Added", value=song.title, inline=False)
            embed.set_thumbnail(url=song.thumbnail)
            await ctx.send(embed=embed)

    async def send_now_playing(self, ctx, song: Song, user: User) -> None:

        embed = discord.Embed(title=f"Now Playing", color=discord.Color.green())
        embed.add_field(name="Title", value=song.title, inline=False)
        embed.add_field(name="Played By", value=user.name, inline=True)
        embed.add_field(name="YouTube", value=f"[Link]({song.url})", inline=True)
        embed.set_thumbnail(url=song.thumbnail)
        
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

    async def show_playlist(self, ctx) -> None:
        user_name = ctx.author.name
        user = self.database.get_user(user_name)
        user_songs = self.database.get_playlist(user)
        print(user_songs)

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


# TODO: How to add a youtube link here as a button?
# youtube_link_button = Button(label='YouTube', style=5, url=song.url)
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
        await self.music_bot.add_to_playlist(
            ctx=self.ctx, 
            user_name=interaction.user.name
        )
        await interaction.response.edit_message(view=self)