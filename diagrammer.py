from tables import UserDeath, VillagerDeath, PlaySession, engine
from log_parser import parse

from datetime import date, datetime, timedelta
from calendar import monthrange, month_name
from math import ceil
from typing import Union
from collections import defaultdict

from sqlalchemy.orm import Session as DBSession
from sqlalchemy import or_, and_

import drawSvg

COLORS = ["#FF9AA2", "#C7CEEA", "#B5EAD7"]


class Month():

    def __init__(self, year: int, number: int):
        self.name = month_name[number]
        self.year = year
        self.number = number

        number_of_days = monthrange(year, number)[1]
        number_of_weeks = ceil(number_of_days / 7)

        self.name_height = 55
        self.name_font_size = 50
        self.margin_below_name = 10
        self.week_height = 200
        self.week_width = 900
        self.gap_between_weeks = 10

        self.weeks: list[Week] = []
        for i in range(0, number_of_weeks):
            self.weeks.append(
                Week(date(year, number, 1 + 7 * i),
                     date(year, number, min(8 + 7 * i, number_of_days)),
                     self.week_width, self.week_height))

        # the earliest moment that is part of the month
        self.lower_bound = self.weeks[0].lower_bound
        # the last moment that is part of the month
        self.upper_bound = self.weeks[-1].upper_bound

        self.users = set()

    def __repr__(self) -> str:
        return f"the month of {self.name} ({self.number}), {self.year}"

    @property
    def height(self) -> int:
        return (self.name_height + self.margin_below_name +
                self.week_height * len(self.weeks) +
                self.gap_between_weeks * len(self.weeks))

    def add_session(self, session: PlaySession) -> None:
        # this is an object of an orm mapped class, but it is never entered into the
        # database
        truncated_session = PlaySession(user=session.user,
                                        start_time=max(self.lower_bound,
                                                       session.start_time),
                                        end_time=min(self.upper_bound,
                                                     session.end_time))
        for week in self.weeks:
            # two time ranges overlap if the earliest end time is after the latest
            # start time
            if min(week.upper_bound, truncated_session.end_time) > max(
                    week.lower_bound, truncated_session.start_time):
                week.add_session(truncated_session)

        self.users.add((session.user.id, session.user.username))

    def add_death(self, death: Union[UserDeath, VillagerDeath]) -> None:
        for week in self.weeks:
            if week.lower_bound <= death.time <= week.upper_bound:
                if isinstance(death, UserDeath):
                    week.add_user_death(death)
                else:
                    week.add_villager_death(death)
                return

    def render(self) -> drawSvg.Drawing:
        # might want to add left and right margins
        drawing = drawSvg.Drawing(self.week_width, self.height)
        drawing.append(
            drawSvg.Text(self.name,
                         self.name_font_size,
                         0,
                         self.height - self.name_height,
                         fill="black"))
        amount_of_page_filled = self.name_height + self.margin_below_name
        for week in self.weeks:
            week_group = week.render()
            week_group.args[
                "transform"] = f"translate(0, {-(self.height - amount_of_page_filled) + self.week_height})"
            drawing.append(week_group)
            amount_of_page_filled += self.week_height + self.gap_between_weeks
        return drawing


class Week():

    # NOTE: a "Week" might be less than 7 days long if it is truncated by the month ending
    def __init__(self, first_date: date, last_date: date, width: int,
                 height: int):
        self.first_date = first_date  # the first date in the week
        self.last_date = last_date  # the last date in the week
        self.number_of_days = first_date.day - last_date.day

        #  the earliest moment that is part of the week
        self.lower_bound = datetime.combine(self.first_date,
                                            datetime.min.time())
        #  the last moment that is part of the week
        self.upper_bound = datetime.combine(self.last_date, datetime.max.time())

        self.number_of_session_rows = 2

        self.height = height
        self.width = width

        self.numbers_height = 30
        self.numbers_font_size = 25
        self.bottom_row_height = 30
        self.session_row_height = (
            height - self.numbers_height -
            self.bottom_row_height) / self.number_of_session_rows
        self.bracket_width = 10
        self.line_width = 3

        self.play_sessions: list[PlaySession] = []
        self.user_deaths: list[UserDeath] = []
        self.villager_deaths: list[VillagerDeath] = []

    @property
    def length(self) -> timedelta:
        return self.upper_bound - self.lower_bound

    def __repr__(self) -> str:
        return f"week from {self.first_date} to {self.last_date}"

    def add_session(self, session: PlaySession) -> None:
        # this is an object of an orm mapped class, but it is never entered into the
        # database
        truncated_session = PlaySession(user=session.user,
                                        start_time=max(self.lower_bound,
                                                       session.start_time),
                                        end_time=min(self.upper_bound,
                                                     session.end_time))
        self.play_sessions.append(truncated_session)

    def add_user_death(self, death: UserDeath) -> None:
        self.user_deaths.append(death)

    def add_villager_death(self, death: VillagerDeath) -> None:
        self.villager_deaths.append(death)

    def render(self) -> drawSvg.Group:
        day_width = self.width / 7

        # distance to keep between the paths that make the enclosing brackets and the edge of the drawing
        bracket_offset = self.line_width / 2
        bracket_height = self.height - self.numbers_height

        numberline = drawSvg.Group(
            transform=f"translate(0 -{self.height-self.numbers_height})")
        timeline = drawSvg.Group()

        for i in range(0, 7):
            day_x_pos = i * day_width
            date = self.first_date.day + i
            if date <= self.last_date.day:
                numberline.append(
                    drawSvg.Text(
                        str(date),
                        self.numbers_font_size,
                        day_x_pos,
                        (self.numbers_height - self.numbers_font_size) / 2,
                        fill="black"))
            if i != 0:
                timeline.append(
                    drawSvg.Lines(day_x_pos,
                                  0,
                                  day_x_pos,
                                  bracket_height,
                                  stroke="black",
                                  stroke_width=self.line_width / 2,
                                  stroke_dasharray="5 2"))

        left_bracket = drawSvg.Path(stroke="black",
                                    stroke_width=self.line_width,
                                    fill='none')
        left_bracket.M(bracket_offset + self.bracket_width, bracket_offset)
        left_bracket.H(bracket_offset)
        left_bracket.V(bracket_height - bracket_offset)
        left_bracket.H(bracket_offset + self.bracket_width)
        timeline.append(left_bracket)

        right_bracket = drawSvg.Path(stroke="black",
                                     stroke_width=self.line_width,
                                     fill="none")
        right_bracket.M(self.width - (bracket_offset + self.bracket_width),
                        bracket_offset)
        right_bracket.H(self.width - bracket_offset)
        right_bracket.V(bracket_height - bracket_offset)
        right_bracket.H(self.width - (bracket_offset + self.bracket_width))
        timeline.append(right_bracket)

        sorted_sessions = sorted(self.play_sessions, key=lambda x: x.start_time)
        #  organize sessions into rows by inserting each session into the first row
        #  that doesn't have a session already in it that overlaps it
        rows = defaultdict(list)
        for session in sorted_sessions:
            for i in range(self.number_of_session_rows):
                if (not len(
                        rows[i])) or rows[i][-1].end_time < session.start_time:
                    rows[i].append(session)
                    break

        for i in range(self.number_of_session_rows):
            row_y = (self.height - self.numbers_height -
                     i * self.session_row_height - self.session_row_height)
            for session in rows[i]:
                week_offset = session.start_time - self.lower_bound
                session_x = week_offset / (self.length) * self.width
                session_width = (session.end_time -
                                 session.start_time) / self.length * self.width
                timeline.append(
                    drawSvg.Rectangle(session_x,
                                      row_y,
                                      session_width,
                                      self.session_row_height,
                                      fill=COLORS[session.user.id %
                                                  len(COLORS)]))

        for death in self.villager_deaths:
            death_x = (death.time - self.lower_bound) / self.length * self.width
            timeline.append(
                drawSvg.Text("X",
                             self.bottom_row_height * 0.8,
                             death_x,
                             0,
                             fill="black",
                             font_family="sans-serif"))

        drawing = drawSvg.Group()
        drawing.append(numberline)
        drawing.append(timeline)
        return drawing


if __name__ == "__main__":
    parse(engine)
    with DBSession(engine) as session:
        first_session: PlaySession = session.query(PlaySession).order_by(
            PlaySession.start_time).first()
        last_session: PlaySession = session.query(PlaySession).order_by(
            PlaySession.end_time.desc()).first()
        print(first_session)
        print(last_session)
        first_year, first_month = first_session.start_time.year, first_session.start_time.month
        last_year, last_month = last_session.end_time.year, last_session.end_time.month

        start_date = date(first_year, first_month, 1)
        end_date = date(last_year, last_month + 1, 1)

        while start_date < end_date:
            month = Month(start_date.year, start_date.month)
            #  note that this query will miss sessions that completely encompass a
            #  month, which should not normally happen
            sessions_starting_this_month = session.query(PlaySession).filter(
                or_(
                    and_(PlaySession.start_time >= month.lower_bound,
                         PlaySession.start_time <= month.upper_bound),
                    and_(PlaySession.end_time >= month.lower_bound,
                         PlaySession.end_time <= month.upper_bound)))
            for x in sessions_starting_this_month.all():
                month.add_session(x)

            user_deaths_this_month = session.query(UserDeath).filter(
                UserDeath.time >= month.lower_bound,
                UserDeath.time <= month.upper_bound)
            for x in user_deaths_this_month.all():
                month.add_death(x)
            villager_deaths_this_month = session.query(VillagerDeath).filter(
                VillagerDeath.time >= month.lower_bound,
                VillagerDeath.time <= month.upper_bound)
            for x in villager_deaths_this_month.all():
                month.add_death(x)

            drawing = month.render()
            drawing.saveSvg(f"./output/{month.name} {month.year}.svg")

            start_date = start_date.replace(month=start_date.month + 1)
