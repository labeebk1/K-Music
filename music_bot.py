#WaLLE
import asyncio
import discord
from discord.ext import commands,tasks
import os
from dotenv import load_dotenv
import youtube_dl
from youtubesearchpython import VideosSearch

# from sqlalchemy import create_engine
# from sqlalchemy.orm import Session


load_dotenv()
# Get the API token from the .env file.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents().all()
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='.',intents=intents)

youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
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
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

queue = []
download_queue = []
thread_running = False

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

def is_supported(url):
    extractors = youtube_dl.extractor.gen_extractors()
    for e in extractors:
        if e.suitable(url) and e.IE_NAME != 'generic':
            return True
    return False

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = ""

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()

        if(is_supported(url)):
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            if 'entries' in data:
                # take first item from a playlist
                data = data['entries'][0]
            filename = data['title'] if stream else ytdl.prepare_filename(data)
            return filename
        else:
            videosSearch = VideosSearch(url, limit = 1)
            url = videosSearch.result()['result'][0]['link']
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
            if 'entries' in data:
                # take first item from a playlist
                data = data['entries'][0]
            filename = data['title'] if stream else ytdl.prepare_filename(data)
            return filename

@bot.command(name='queue', aliases=["q"], help='List Queue')
async def list_queue(ctx):
    global queue
    embed = discord.Embed(title=f"Queue", 
                color=discord.Color.random())

    queue_list_string = ""
    if not queue:
        queue_list_string = "Empty!"
    for idx, song in enumerate(queue):
        queue_list_string += f'{idx + 1}. {song}\n'

    embed.add_field(name="Music",
                    value=f"```\n{queue_list_string}```", inline=False)

    download_list_string = ""
    if not download_queue:
        download_list_string = "Empty!"
    for idx, download in enumerate(download_queue):
        download_list_string += f'{idx + 1}. {download}\n'

    embed.add_field(name="Downloading [High Quality]",
                    value=f"```\n{download_list_string}```", inline=False)

    embed.set_thumbnail(url='https://img.besthqwallpapers.com/Uploads/7-10-2019/107450/4k-dj-marshmello-violet-brickwall-music-stars-christopher-comstock.jpg')
    await ctx.send(embed=embed)

async def addToQueue(ctx, song):
    download_queue.append(song)
    embed = discord.Embed(title=f"Adding Song to Queue", 
                color=discord.Color.green())
    embed.add_field(name="Song",
                    value=f"```\n{song}```", inline=False)
    embed.set_thumbnail(url='https://www.galxygirl.com/images/itunes2.jpg')
    await ctx.send(embed=embed)
    filename = await YTDLSource.from_url(song, loop=bot.loop)
    queue.append(filename)
    download_queue.remove(song)

@bot.command(name='download', aliases=["dl"], help='To download song')
async def download(ctx,*song):
    song = ' '.join(song)
    download_queue.append(song)

    embed = discord.Embed(title=f"Downloading Song in background...", 
                color=discord.Color.blue())
    embed.add_field(name="Song",
                    value=f"```\n{song}```", inline=False)
    embed.set_thumbnail(url='https://play-lh.googleusercontent.com/WX55VBDZ1CqpNEyWrU1BKgwEnLhr1Z9FpihP_Winh-d3wTlff44Rc_98UXEFUF1ouY4')
    await ctx.send(embed=embed)
    try:
        filename = await YTDLSource.from_url(song, loop=bot.loop)
        download_queue.remove(song)
    except Exception:
        download_queue.remove(song)
    

@bot.command(name='remove', aliases=["r"], help='Remove from song')
async def remove(ctx, pos_to_remove):
    global queue
    if str(pos_to_remove) == 'all':
        queue = []
        embed = discord.Embed(title=f"Queue is now empty!", 
                color=discord.Color.red())
        embed.add_field(name="Removed All Song",
                        value=f"```Empty Queue```", inline=False)
        await ctx.send(embed=embed)
    else:
        if int(pos_to_remove) <= len(queue):
            song_to_remove = queue.pop(int(pos_to_remove) - 1)
        
        embed = discord.Embed(title=f"Updated Queue", 
                    color=discord.Color.red())
        embed.add_field(name="Removed Song",
                        value=f"```{song_to_remove}```", inline=False)
        await ctx.send(embed=embed)

async def togglePlay(ctx, channel):
    global queue
    if queue:
        try:
            await playSong(ctx, channel)
        except discord.errors.ClientException:
            await asyncio.sleep(5)
            loop = bot.loop or asyncio.get_event_loop()
            loop.create_task(togglePlay(ctx, channel))
            return
        
        queue.pop(0)

async def playSong(ctx, channel):
    async with ctx.typing():
        global queue
        song = queue[0]
        channel.play(
            discord.FFmpegPCMAudio(executable="/usr/bin/ffmpeg", source=song), #ffmpeg.exe
        )

    embed = discord.Embed(title=f"Now playing", 
                color=discord.Color.blue())
    embed.add_field(name="Song",
                    value=f"```\n{song}```", inline=False)
    embed.set_thumbnail(url='https://i.pinimg.com/originals/95/3b/11/953b11a5c98c2971b27106509139610a.png')
    await ctx.send(embed=embed)


@bot.command(name='play', aliases=["p"], help='To play song')
async def play(ctx,*url):

    url = ' '.join(url)

    if not ctx.message.author.voice:
        await ctx.send("{} is not connected to a voice channel".format(ctx.message.author.name))
        return
    else:
        try:
            channel = ctx.message.author.voice.channel
            await channel.connect()
        except discord.errors.ClientException:
            pass

    server = ctx.message.guild
    voice_channel = server.voice_client

    await addToQueue(ctx=ctx, song=url)
    await togglePlay(ctx=ctx, channel=voice_channel)
    

@bot.command(name='pause', help='This command pauses the song')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        await voice_client.pause()
    else:
        await ctx.send("The bot is not playing anything at the moment.")
    
@bot.command(name='resume', help='Resumes the song')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        await voice_client.resume()
    else:
        await ctx.send("The bot was not playing anything before this. Use play_song command")
    

@bot.command(name='leave', help='To make the bot leave the voice channel')
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send("The bot is not connected to a voice channel.")

@bot.command(name='skip', help='skips the song')
async def skip(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
    else:
        await ctx.send("The bot is not playing anything at the moment.")
    
    global queue
    if queue:
        server = ctx.message.guild
        voice_channel = server.voice_client
        await togglePlay(ctx=ctx, channel=voice_channel)

@bot.event
async def on_ready():
    print('Running!')
    for guild in bot.guilds:
        for channel in guild.text_channels :
            if str(channel) == "general" :
                await channel.send('Bot Activated..')
        print('Active in {}\n Member Count : {}'.format(guild.name,guild.member_count))


if __name__ == "__main__" :
    bot.run(DISCORD_TOKEN)