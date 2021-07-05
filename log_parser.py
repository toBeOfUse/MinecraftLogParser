import gzip
from pathlib import Path
import re
from datetime import datetime, timezone
import json

from death_messages import is_death_message
from tables import User, UserDeath, VillagerDeath, PlaySession, ChatMessage

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

file_name_parser = re.compile(r"^(\d\d\d\d)-(\d\d)-(\d\d)-\d.log.gz")
time_parser = re.compile(r"(\d\d):(\d\d):(\d\d)")
line_parser = re.compile(r"^\[(\d\d:\d\d:\d\d)\] \[(.*?)\]: (.*)$")

# maps uuids to open session starting times
open_sessions: dict[str, datetime] = {}
# maps usernames to uuids. as the parse function proceeds through the log files, this
# dict is updated to map the most recent username a player was seen with to their
# uuid
usernames: dict[str, str] = {}


def get_user_by_uuid(uuid: str, session: DBSession) -> User:
    """
    Returns a User object obtained by looking up a Minecraft UUID in the database. If
    no user object is found, this method returns None.
    """
    stmt = select(User).where(User.minecraft_uuid == uuid)
    result = session.execute(stmt).first()
    return result[0] if result else None


def get_user_by_username(username: str, session: DBSession) -> User:
    """
    Returns a User object obtained by looking up the Minecraft UUID that is currently
    associated with a username and then using that UUID to obtain a User object from
    the database.
    """
    return get_user_by_uuid(usernames[username], session)


def parse(engine):
    log_files = list(
        Path('./logs/').glob("*.log.gz")) + [Path("./logs/latest.log")]
    for file in list(log_files):
        if file.name == "latest.log":
            now = datetime.utcnow()
            year, month, day = now.year, now.month, now.day
        else:
            year, month, day = [
                int(x)
                for x in file_name_parser.match(file.name).group(1, 2, 3)
            ]
        if file.name.endswith("gz"):
            with open(file, "rb") as data_file:
                try:
                    log_data = gzip.decompress(data_file.read()).decode("utf-8")
                except EOFError:
                    print(
                        f"warning: could not open {file}; it is most likely corrupted"
                    )
                    continue
        else:
            with open(file, "r") as data_file:
                log_data = data_file.read()
        for line in (x for x in log_data.split("\n") if x):
            parsed_line = line_parser.match(line)
            if not parsed_line:
                continue
            time, source, message = parsed_line.group(1, 2, 3)
            hour, minute, second = [
                int(x) for x in time_parser.match(time).group(1, 2, 3)
            ]
            # astimezone with no arguments converts the datetime object to the system
            # local timezone
            timestamp = datetime(year,
                                 month,
                                 day,
                                 hour,
                                 minute,
                                 second,
                                 tzinfo=timezone.utc).astimezone()
            with DBSession(engine) as session:
                if re.match(r"^User Authenticator #\d+/INFO$", source):
                    uuid_declaration = re.match(
                        r"^UUID of player (.*?) is (.*?)$", message)
                    if not uuid_declaration:
                        continue
                    username, uuid = uuid_declaration.group(1, 2)
                    usernames[username] = uuid
                    match = get_user_by_uuid(uuid, session)
                    if not match:
                        new_user = User(username=username, minecraft_uuid=uuid)
                        session.add(new_user)
                    else:
                        if match.username != username:
                            past_usernames = json.loads(
                                match.past_usernames) + [username]
                            match.past_usernames = json.dumps(past_usernames)
                elif source == "Server thread/INFO":
                    if join_message_match := re.match(r"^(.*) joined the game$",
                                                      message):
                        player_uuid = usernames[join_message_match.group(1)]
                        open_sessions[player_uuid] = timestamp
                    elif leave_message_match := re.match(
                            r"^(.*) left the game$", message):
                        player_uuid = usernames[leave_message_match.group(1)]
                        start_time = open_sessions[player_uuid]
                        player = get_user_by_uuid(player_uuid, session)
                        session.add(
                            PlaySession(start_time=start_time,
                                        end_time=timestamp,
                                        user_id=player.id))
                    elif villager_died_message_match := re.match(
                            r"^Villager .*?\[(.*?)\] died, message: '(.*?)'$",
                            message):
                        death_data, death_message = villager_died_message_match.group(
                            1, 2)
                        session.add(
                            VillagerDeath(
                                time=timestamp,
                                had_profession=(
                                    not death_message.startswith("Villager")),
                                villager_data=death_data,
                                message=death_message))
                    elif chat_message_match := re.match(r"^<(.*?)> (.*)$",
                                                        message):
                        chatter, chat_message = chat_message_match.group(1, 2)
                        player = get_user_by_username(chatter, session)
                        session.add(
                            ChatMessage(time=timestamp,
                                        user=player,
                                        message=chat_message))
                    elif died_message_match := is_death_message(message):
                        dier_username = died_message_match.group(1)
                        dier = get_user_by_username(dier_username, session)
                        session.add(
                            UserDeath(time=timestamp,
                                      user=dier,
                                      message=message))
                session.commit()
