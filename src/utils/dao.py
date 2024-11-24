import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from utils.entity import Status, BotStatus, User, Song, SongQueue, Playlist


class MusicDAO:
    def __init__(self, db_path):
        engine = create_engine(db_path, echo=False, connect_args={"check_same_thread": False})
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

    def add_song(self, song: Song) -> None:
        self.session.add(song)
        self.session.commit()

    def get_playlist(self, user: User):
        user_id = user.id
        user_songs = self.session.query(Song).join(Playlist).filter(Playlist.user_id == user_id).all()
        return user_songs

    def add_song_to_playlist(self, user: User, song: Song) -> bool:
        playlist = self.session.query(Playlist).filter_by(user_id=user.id, song_id=song.id).first()
        if not playlist:
            playlist = Playlist(
                user_id = user.id,
                song_id = song.id
            )
            self.session.add(playlist)
            self.session.commit()
            return False
        return True

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
