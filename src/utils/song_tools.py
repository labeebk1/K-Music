import asyncio

import youtube_dl
from youtubesearchpython import VideosSearch, Video, ResultMode

from utils.entity import Song

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
