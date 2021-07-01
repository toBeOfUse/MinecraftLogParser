from tables import User, UserDeath, VillagerDeath, PlaySession, engine
from log_parser import parse

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

parse(engine)
with DBSession(engine) as session:
    for user, in session.execute(select(User)):
        print(user)
        print("deaths", session.query(UserDeath).filter_by(user=user).count())
