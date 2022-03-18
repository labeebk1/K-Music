import discord
from utils import DISCORD_TOKEN, MusicBot, Request

# Instantiate Discord Bot Object
intents = discord.Intents().all()
client = discord.Client(intents=intents)
music_bot = MusicBot(
    db_path='sqlite:///music.db', 
    command_prefix='.', 
    intents=intents
)

@music_bot.command(name='play', aliases=["p"], help=MusicBot.get_command_info('play'))
async def play(ctx, *song_args):
    
    is_user_connected = await music_bot.check_user_connected(ctx)
    if not is_user_connected:
        chat_notification = f"{ctx.message.author.name} is not connected to a voice channel."
        await music_bot.send_message(ctx, chat_notification)
        return

    is_bot_connected = await music_bot.check_bot_connected(ctx)
    if not is_bot_connected:
        await music_bot.connect_to_channel(ctx)

    # The user input is either a url or a set of words for a song name
    song_argument = ' '.join(song_args)
    song = music_bot.get_song_from_db(song_argument)

    if not song:
        song = music_bot.search_song_from_youtube(song_argument)
        await music_bot.download_song(ctx, song=song, loop=music_bot.loop)
        request = Request(ctx, music_bot)
        await request.create_thread(action=Request.bot_status.PLAYING)
        return

    music_bot.add_song_to_song_queue(song)

    print("Creating request")
    request = Request(ctx, music_bot)
    await request.create_thread(action=Request.bot_status.PLAYING)


@music_bot.command(name='skip', help=MusicBot.get_command_info('skip'))
async def skip(ctx):
    await music_bot.skip(ctx)

@music_bot.command(name='pause', help=MusicBot.get_command_info('pause'))
async def pause(ctx):
    await music_bot.pause(ctx)


@music_bot.command(name='resume', help=MusicBot.get_command_info('resume'))
async def resume(ctx):
    await music_bot.resume(ctx)


@music_bot.command(name='leave', help=MusicBot.get_command_info('leave'))
async def leave(ctx):
    await music_bot.leave(ctx)


@music_bot.event
async def on_ready():
    print('K-Music Bot is Running!')

if __name__ == '__main__':
    music_bot.run(DISCORD_TOKEN)
