from tables import UserDeath, VillagerDeath, PlaySession, engine
from log_parser import parse

from datetime import date, datetime, timedelta
from calendar import monthrange, month_name
from math import ceil, floor
from typing import Union
from collections import defaultdict
from random import random
from xml.sax.saxutils import unescape

from sqlalchemy.orm import Session as DBSession
from sqlalchemy import or_, and_

import drawSvg
from webcolors import hex_to_rgb, rgb_to_hex

COLORS = ["#FF9AA2", "#C7CEEA", "#B5EAD7"]


def get_color(user_id: int) -> str:
    return COLORS[user_id % len(COLORS)]


def get_darker_color(user_id: int) -> str:
    original_color = hex_to_rgb(get_color(user_id))
    return rgb_to_hex(tuple(int(x / 2) for x in original_color))


def make_ordinal(n: int) -> str:
    '''
    from https://stackoverflow.com/a/50992575
    Convert an integer into its ordinal representation:

        make_ordinal(0)   => '0th'
        make_ordinal(3)   => '3rd'
        make_ordinal(122) => '122nd'
        make_ordinal(213) => '213th'
    '''
    suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    return str(n) + suffix


class Month():

    def __init__(self, year: int, number: int):
        self.name = month_name[number]
        self.year = year
        self.number = number

        number_of_days = monthrange(year, number)[1]
        number_of_weeks = ceil(number_of_days / 7)

        self.name_height = 55
        self.name_font_size = 50
        self.username_font_size = 15
        self.color_swatch_width = 150
        self.color_swatch_height = 40
        self.user_color_guide_width = 200
        self.margin_below_name = 10
        self.week_height = 200
        self.week_width = 1100
        self.gap_between_weeks = 10

        self.left_right_margins = 10

        self.weeks: list[Week] = []
        for i in range(0, number_of_weeks):
            self.weeks.append(
                Week(date(year, number, 1 + 7 * i),
                     date(year, number, min(7 + 7 * i, number_of_days)),
                     self.week_width, self.week_height))

        # the earliest moment that is part of the month
        self.lower_bound = self.weeks[0].lower_bound
        # the last moment that is part of the month
        self.upper_bound = self.weeks[-1].upper_bound

        self.users = {}

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

        if session.user.username not in self.users:
            self.users[session.user.username] = get_color(session.user.id)

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
        drawing = drawSvg.Drawing(self.week_width + self.left_right_margins * 2,
                                  self.height)
        drawing.append(
            drawSvg.Text(self.name,
                         self.name_font_size,
                         self.left_right_margins,
                         self.height - self.name_height,
                         fill="black"))

        for i, (user, color) in enumerate(self.users.items()):
            swatch_left_edge = self.week_width - (
                (i + 1) * self.user_color_guide_width)
            swatch = drawSvg.Group(transform=f"translate({swatch_left_edge}, " +
                                   f"{-self.height+self.name_height})")
            swatch.append(
                drawSvg.Rectangle(0,
                                  0,
                                  self.color_swatch_width,
                                  self.color_swatch_height,
                                  fill=color))
            swatch.append(
                drawSvg.Text(
                    f"{user}",
                    self.username_font_size,
                    5, (self.color_swatch_height - self.username_font_size) / 2,
                    font_family="monospace"))
            drawing.append(swatch)

        amount_of_page_filled = self.name_height + self.margin_below_name
        for week in self.weeks:
            week_group = week.render()
            week_group.args[
                "transform"] = f"translate({self.left_right_margins}, {-(self.height - amount_of_page_filled) + self.week_height})"
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

        self.numbers_height = 35
        self.numbers_font_size = 20
        self.bottom_row_height = 50
        self.bottom_row_x_height = 20
        self.bottom_row_jitter = 30
        self.session_row_height = (
            height - self.numbers_height -
            self.bottom_row_height) / self.number_of_session_rows
        self.bracket_width = 10
        self.line_width = 3
        self.stats_width = 200
        self.stats_font_size = 15
        self.stats_box_width = 100
        self.stats_box_height = 20
        self.stats_box_spacing = 5

        self.play_sessions: list[PlaySession] = []
        self.user_deaths: list[UserDeath] = []
        self.villager_deaths: list[VillagerDeath] = []
        self.user_ids = set()

    @property
    def length(self) -> timedelta:
        return self.upper_bound - self.lower_bound

    def get_time_played(self, by_user_id=None) -> timedelta:
        seconds_played = sum((x.length
                              for x in self.play_sessions
                              if by_user_id is None or x.user.id == by_user_id),
                             timedelta(days=0)).total_seconds()
        hours_played = floor(seconds_played / (60 * 60))
        minutes_played = floor(seconds_played % (60 * 60) / 60)
        seconds_played = floor(seconds_played) % 60
        return f"{hours_played:02}:{minutes_played:02}:{seconds_played:02}"

    @property
    def villager_deaths_count(self):
        return len(self.villager_deaths)

    def __repr__(self):
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
        self.user_ids.add(session.user.id)

    def add_user_death(self, death: UserDeath) -> None:
        self.user_deaths.append(death)

    def add_villager_death(self, death: VillagerDeath) -> None:
        self.villager_deaths.append(death)

    def render(self) -> drawSvg.Group:
        # distance to keep between the paths that make the enclosing brackets and the edge of the drawing
        bracket_offset = self.line_width / 2
        bracket_height = self.height - self.numbers_height

        numberline = drawSvg.Group(
            transform=f"translate(0, -{self.height-self.numbers_height})")
        timeline = drawSvg.Group()
        timeline_width = self.width - self.stats_width
        day_width = timeline_width / 7

        for i in range(0, 7):
            day_x_pos = i * day_width
            date = self.first_date.day + i
            if date <= self.last_date.day:
                numberline.append(
                    drawSvg.Text(
                        make_ordinal(date),
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
                session_x = week_offset / (timedelta(days=7)) * timeline_width
                session_width = (session.end_time - session.start_time
                                ) / timedelta(days=7) * timeline_width
                timeline.append(
                    drawSvg.Rectangle(session_x,
                                      row_y,
                                      session_width,
                                      self.session_row_height,
                                      fill=get_color(session.user.id),
                                      stroke=get_darker_color(session.user.id),
                                      strokeWidth="2"))

        for death in self.villager_deaths:
            death_x = (death.time -
                       self.lower_bound) / timedelta(days=7) * timeline_width
            timeline.append(
                drawSvg.Text("x",
                             self.bottom_row_x_height,
                             death_x,
                             random() * self.bottom_row_jitter,
                             fill="black",
                             font_family="sans-serif"))

        stats = drawSvg.Group(
            transform=f"translate({self.width-self.stats_width+5})")
        stats.append(
            drawSvg.Text(f"Time played:", self.stats_font_size, 5,
                         bracket_height - self.stats_font_size))
        for i, user_id in enumerate(self.user_ids):
            stats.append(
                drawSvg.Rectangle(5,
                                  bracket_height - self.stats_box_height *
                                  (i + 2) - self.stats_box_spacing * i,
                                  self.stats_box_width,
                                  self.stats_box_height,
                                  fill=get_color(user_id)))
            stats.append(
                drawSvg.Text(
                    self.get_time_played(user_id), self.stats_font_size, 5,
                    bracket_height - self.stats_box_height * (i + 2) -
                    self.stats_box_spacing * i +
                    (self.stats_box_height - self.stats_font_size) / 2))

        if len(self.user_ids) > 1:
            stats.append(
                drawSvg.Text(
                    "&#931;: " + self.get_time_played(), self.stats_font_size,
                    5, bracket_height - self.stats_box_height *
                    (len(self.user_ids) + 2) -
                    self.stats_box_spacing * len(self.user_ids) +
                    (self.stats_box_height - self.stats_font_size) / 2))

        stats.append(
            drawSvg.Text(f"Villager deaths: {self.villager_deaths_count}",
                         self.stats_font_size, 5, 5))

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
        right_bracket.M(timeline_width - (bracket_offset + self.bracket_width),
                        bracket_offset)
        right_bracket.H(timeline_width - bracket_offset)
        right_bracket.V(bracket_height - bracket_offset)
        right_bracket.H(timeline_width - (bracket_offset + self.bracket_width))
        timeline.append(right_bracket)

        drawing = drawSvg.Group()
        drawing.append(numberline)
        drawing.append(timeline)
        drawing.append(stats)
        return drawing


if __name__ == "__main__":
    parse(engine)
    with DBSession(engine) as session:
        first_session: PlaySession = session.query(PlaySession).order_by(
            PlaySession.start_time).first()
        last_session: PlaySession = session.query(PlaySession).order_by(
            PlaySession.end_time.desc()).first()

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
            with open(f"./output/{month.name} {month.year}.svg",
                      "w+") as output_file:
                output_file.write(unescape(drawing.asSvg()))

            start_date = start_date.replace(month=start_date.month + 1)
