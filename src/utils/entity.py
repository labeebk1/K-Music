from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Song(Base):
    __tablename__ = 'songs'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    url = Column(String)

class SongQueue(Base):
    __tablename__ = 'song_queue'
    id = Column(Integer, primary_key=True)
    song_id = Column(Integer, ForeignKey('songs.id'))
    user_id = Column(Integer, ForeignKey('users.id'))

class DownloadQueue(Base):
    __tablename__ = 'download_queue'
    id = Column(Integer, primary_key=True)
    pid = Column(Integer)
    song_id = Column(Integer, ForeignKey('songs.id'))
    user_id = Column(Integer, ForeignKey('users.id'))

class Playlist(Base):
    __tablename__ = 'playlist'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    song_id = Column(Integer, ForeignKey('songs.id'))

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

if __name__ == '__main__':
    engine = create_engine('sqlite:///music.db', echo=True)
    Base.metadata.create_all(engine)
