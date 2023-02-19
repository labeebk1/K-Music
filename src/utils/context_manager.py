import os
import asyncio

from utils.music_bot import MusicBot
from utils.entity import Status

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

