import gzip
from pathlib import Path
import re
from datetime import datetime, timezone
import json

from death_messages import is_death_message
from tables import User, UserDeath, VillagerDeath, PlaySession
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

file_name_parser = re.compile(r"^(\d\d\d\d)-(\d\d)-(\d\d)-\d.log.gz")
time_parser = re.compile(r"(\d\d):(\d\d):(\d\d)")
line_parser = re.compile(r"^\[(\d\d:\d\d:\d\d)\] \[(.*?)\]: (.*)$")

open_sessions = {}  # maps usernames to starting times
usernames = {}  # maps usernames to uuids


def get_user_by_uuid(uuid, session):
    stmt = select(User).where(User.minecraft_uuid == uuid)
    return session.execute(stmt).first()


def parse(engine):
    log_files = list(
        Path('./logs/').glob("*.log.gz")) + [Path("./logs/latest.log")]
    print("DEBUG MODE: NOT GOING THROUGH ALL FILES")
    for file in list(log_files)[:5]:
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
                    print("warning: could not open", file,
                          "it is most likely corrupted")
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
            timestamp = datetime(year,
                                 month,
                                 day,
                                 hour,
                                 minute,
                                 second,
                                 tzinfo=timezone.utc)
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
                        if match[0].username != username:
                            past_usernames = json.loads(
                                match[0].past_usernames) + [username]
                            match[0].past_usernames = json.dumps(past_usernames)
                elif source == "Server thread/INFO":
                    if join_message_match := re.match(r"^(.*) joined the game$",
                                                      message):
                        player_uuid = usernames[join_message_match.group(1)]
                        open_sessions[player_uuid] = timestamp
                    elif leave_message_match := re.match(
                            r"^(.*) left the game$", message):
                        player_id = usernames[leave_message_match.group(1)]
                        start_time = open_sessions[player_id]
                        player = get_user_by_uuid(player_id, session)[0]
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
                    elif died_message_match := is_death_message(message):
                        dier_username = died_message_match.group(1)
                        dier_uuid = usernames[dier_username]
                        dier = get_user_by_uuid(dier_uuid, session)[0]
                        session.add(
                            UserDeath(time=timestamp,
                                      user=dier,
                                      message=message))
                session.commit()
