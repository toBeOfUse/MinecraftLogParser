from datetime import timedelta, timezone
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean, create_engine
from sqlalchemy.sql.schema import ForeignKey

import json
import logging

logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.engine").addHandler(
    logging.FileHandler('sql.log', mode='w'))

BaseTable = declarative_base()


class User(BaseTable):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String)
    past_usernames = Column(String, default=json.dumps([]))
    minecraft_uuid = Column(String, unique=True, index=True)

    def __repr__(self):
        return f"User(username={self.username}, id={self.id}, minecraft_uuid={self.minecraft_uuid}, past_usernames={self.past_usernames})"


class PlaySession(BaseTable):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    start_time = Column(DateTime, index=True)
    end_time = Column(DateTime, index=True)
    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)

    @property
    def length(self) -> timedelta:
        return self.end_time - self.start_time

    def __repr__(self):
        return f"{self.user.username} played from {self.start_time} to {self.end_time}"


class UserDeath(BaseTable):
    __tablename__ = "user_deaths"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, index=True)
    user_id = Column(Integer, ForeignKey(User.id))
    user = relationship(User)
    message = Column(String)

    def __repr__(self):
        return f"[{self.time}: {self.message}"


class VillagerDeath(BaseTable):
    __tablename__ = "villager_deaths"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, index=True)
    had_profession = Column(Boolean)
    villager_data = Column(String)
    village_name = Column(String, index=True)
    message = Column(String)


class ChatMessage(BaseTable):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, index=True)
    chatter = Column(Integer, ForeignKey(User.id))
    user = relationship(User)
    message = Column(String)


engine = create_engine("sqlite+pysqlite:///:memory:", echo=False, future=True)
BaseTable.metadata.create_all(engine)
