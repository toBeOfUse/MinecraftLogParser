from tables import UserDeath, VillagerDeath, PlaySession, engine
from log_parser import parse

from datetime import date, datetime, timedelta
from calendar import monthrange
from math import ceil

from sqlalchemy.orm import Session as DBSession
import drawSvg


class Month():

    def __init__(self, year: int, name: str, number: int):
        self.name = name
        self.year = year
        self.number = number
        self.number_of_days = monthrange(year, number)[1]
        self.number_of_weeks = ceil(self.number_of_days / 7)

        self.name_height = 30
        self.name_vertical_margin = 10
        self.week_height = 200
        self.week_width = 900
        self.gap_between_weeks = 10

        self.weeks: list[Week] = []
        for i in range(0, self.number_of_weeks):
            self.weeks.append(
                Week(date(year, number, 1 + 7 * i),
                     date(year, number, min(8 + 7 * i, self.number_of_days)),
                     self.week_width, self.week_height))

    @property
    def height(self):
        return (self.name_height + self.name_vertical_margin * 2 +
                self.week_height * self.number_of_weeks +
                self.gap_between_weeks * self.number_of_weeks)

    def add_session(self, session: PlaySession):
        # need to split sessions up between weeks if they cover more than one of them
        pass

    def add_user_death(self, death: UserDeath):
        pass


class Week():

    # NOTE: a "Week" might be less than 7 days long if it is truncated by the month ending
    def __init__(self, first_date: date, last_date: date, width: int,
                 height: int):
        self.first_date = first_date  # midnight at the start of the first date in the week
        self.last_date = last_date  # midnight at the Start of the last date in the week
        self.number_of_days = first_date.day - last_date.day
        self.day_numbers = list(range(first_date.day, self.last_date.day + 1))

        self.number_of_session_rows = 2

        self.height = height
        self.width = width

        self.numbers_height = 30
        self.numbers_font_size = 25
        self.bottom_row_height = 10
        self.session_row_height = (
            height - self.number_of_days -
            self.bottom_row_height) / self.number_of_session_rows
        self.bracket_width = 10
        self.line_width = 3

        self.play_sessions: list[PlaySession] = []
        self.user_deaths: list[UserDeath] = []
        self.villager_deaths: list[VillagerDeath] = []

    def add_session(self, session: PlaySession):
        self.play_sessions.append(session)

    def add_user_death(self, death: UserDeath):
        self.user_deaths.append(death)

    def add_villager_death(self, death: VillagerDeath):
        self.villager_deaths.append(death)

    def render(self) -> drawSvg.Drawing:
        day_width = self.width / 7

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
            if i != 1:
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

        drawing = drawSvg.Drawing(self.width, self.height)
        drawing.append(numberline)
        drawing.append(timeline)
        return drawing


week = None
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
        week_start = datetime(start_date.year, start_date.month, start_date.day,
                              0, 0, 0)
        next_month_start = datetime.combine(
            start_date.replace(month=start_date.month + 1), datetime.min.time())
        while week_start < datetime.combine(next_month_start,
                                            datetime.min.time()):
            next_week_start = min(week_start + timedelta(days=7),
                                  next_month_start)
            print("sessions between", week_start, "and", next_week_start)
            sessions_starting_this_week = session.query(PlaySession).filter(
                PlaySession.start_time >= week_start,
                PlaySession.start_time < next_week_start).count()
            print(sessions_starting_this_week)
            week_start += timedelta(days=7)

        start_date = start_date.replace(month=start_date.month + 1)

timeline = week.render()
timeline.saveSvg('example.svg')
