from datetime import timezone
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean, create_engine
from sqlalchemy.sql.schema import ForeignKey

import json
import logging
logging.basicConfig(filename='sql.log', encoding='utf-8')
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

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
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship(User)


class UserDeath(BaseTable):
    __tablename__ = "user_deaths"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship(User)
    message = Column(String)

    def __repr__(self):
        return f"[{self.time.replace(tzinfo=timezone.utc).astimezone()}: {self.message}"


class VillagerDeath(BaseTable):
    __tablename__ = "villager_deaths"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime, index=True)
    had_profession = Column(Boolean)
    villager_data = Column(String)
    message = Column(String)


engine = create_engine("sqlite+pysqlite:///:memory:", echo=False, future=True)
BaseTable.metadata.create_all(engine)
