# models.py

from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base  # Импортируем Base из database

# Ассоциативная таблица для связи многие-ко-многим
editor_channel_association = Table(
    'editor_channel',
    Base.metadata,
    Column('editor_id', Integer, ForeignKey('editors.id'), primary_key=True),
    Column('channel_id', Integer, ForeignKey('channels.id'), primary_key=True)
)

class Editor(Base):
    __tablename__ = 'editors'
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    
    channels = relationship(
        "Channel", 
        secondary=editor_channel_association,
        back_populates="editors"
    )

class Channel(Base):
    __tablename__ = 'channels'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    twitter_id = Column(String, unique=True, nullable=False)
    last_post_time = Column(String)  # Можно заменить на DateTime при необходимости
    
    editors = relationship(
        "Editor", 
        secondary=editor_channel_association,
        back_populates="channels"
    )