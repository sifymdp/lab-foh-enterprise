"""Deterministic Date & Time Range Resolver for Operational & Reporting AI queries."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import NamedTuple


class ResolvedDateRange(NamedTuple):
    start_date: date
    end_date: date
    start_time: time | None
    end_time: time | None
    label: str


class ComparisonPeriods(NamedTuple):
    period_a: tuple[date, date]
    period_b: tuple[date, date]
    label_a: str
    label_b: str


MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

DAYS_OF_WEEK = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


def resolve_date_expression(text: str) -> ResolvedDateRange | None:
    """Parses natural date expressions into deterministic date ranges.

    Supports: 'today', 'yesterday', 'this week', 'last week', 'this month', 'last month',
    'September', '15 September', 'Saturday', etc.
    """
    if not text:
        return None

    t = text.lower().strip()
    today = datetime.now(timezone.utc).date()
    current_year = today.year

    # Meal shifts
    if "lunch" in t:
        return ResolvedDateRange(
            start_date=today,
            end_date=today,
            start_time=time(11, 0),
            end_time=time(16, 0),
            label="Today's Lunch Shift (11:00 - 16:00)",
        )

    if "dinner" in t:
        return ResolvedDateRange(
            start_date=today,
            end_date=today,
            start_time=time(18, 0),
            end_time=time(23, 0),
            label="Today's Dinner Shift (18:00 - 23:00)",
        )

    # Relative days
    if "today" in t:
        return ResolvedDateRange(
            start_date=today,
            end_date=today,
            start_time=None,
            end_time=None,
            label="Today",
        )

    if "yesterday" in t:
        yd = today - timedelta(days=1)
        return ResolvedDateRange(
            start_date=yd,
            end_date=yd,
            start_time=None,
            end_time=None,
            label="Yesterday",
        )

    if "tomorrow" in t:
        tm = today + timedelta(days=1)
        return ResolvedDateRange(
            start_date=tm,
            end_date=tm,
            start_time=None,
            end_time=None,
            label="Tomorrow",
        )

    # Specific date like "15 September" or "September 15"
    m_day_month = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\b", t)
    if m_day_month and m_day_month.group(2) in MONTH_NAMES:
        day_num = int(m_day_month.group(1))
        month_num = MONTH_NAMES[m_day_month.group(2)]
        try:
            target = date(current_year, month_num, day_num)
            return ResolvedDateRange(
                start_date=target,
                end_date=target,
                start_time=None,
                end_time=None,
                label=f"{day_num} {calendar.month_name[month_num]} {current_year}",
            )
        except ValueError:
            pass

    m_month_day = re.search(r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\b", t)
    if m_month_day and m_month_day.group(1) in MONTH_NAMES:
        month_num = MONTH_NAMES[m_month_day.group(1)]
        day_num = int(m_month_day.group(2))
        try:
            target = date(current_year, month_num, day_num)
            return ResolvedDateRange(
                start_date=target,
                end_date=target,
                start_time=None,
                end_time=None,
                label=f"{day_num} {calendar.month_name[month_num]} {current_year}",
            )
        except ValueError:
            pass

    # Relative weeks
    if "this week" in t:
        start = today - timedelta(days=today.weekday())
        return ResolvedDateRange(
            start_date=start,
            end_date=today,
            start_time=None,
            end_time=None,
            label="This Week",
        )

    if "last week" in t:
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
        return ResolvedDateRange(
            start_date=start,
            end_date=end,
            start_time=None,
            end_time=None,
            label="Last Week",
        )

    # Relative months
    if "this month" in t:
        start = today.replace(day=1)
        return ResolvedDateRange(
            start_date=start,
            end_date=today,
            start_time=None,
            end_time=None,
            label="This Month",
        )

    if "last month" in t:
        first_of_this = today.replace(day=1)
        last_of_prev = first_of_this - timedelta(days=1)
        first_of_prev = last_of_prev.replace(day=1)
        return ResolvedDateRange(
            start_date=first_of_prev,
            end_date=last_of_prev,
            start_time=None,
            end_time=None,
            label=f"{calendar.month_name[first_of_prev.month]} {first_of_prev.year}",
        )

    # Day of week (e.g. "Saturday" or "last Saturday")
    for day_name, day_idx in DAYS_OF_WEEK.items():
        if re.search(rf"\b(?:last\s+)?{day_name}\b", t):
            offset = (today.weekday() - day_idx) % 7
            if offset == 0 and "last" in t:
                offset = 7
            elif offset == 0:
                offset = 7  # referring to past occurrence
            target = today - timedelta(days=offset)
            return ResolvedDateRange(
                start_date=target,
                end_date=target,
                start_time=None,
                end_time=None,
                label=f"{day_name.capitalize()} ({target.isoformat()})",
            )

    # Month name directly (e.g. "September", "August")
    for m_name, m_num in MONTH_NAMES.items():
        if re.search(rf"\b{m_name}\b", t):
            num_days = calendar.monthrange(current_year, m_num)[1]
            return ResolvedDateRange(
                start_date=date(current_year, m_num, 1),
                end_date=date(current_year, m_num, num_days),
                start_time=None,
                end_time=None,
                label=f"{calendar.month_name[m_num]} {current_year}",
            )

    # Explicit DD/MM/YYYY
    match_dmy = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", t)
    if match_dmy:
        d, m, y = int(match_dmy.group(1)), int(match_dmy.group(2)), int(match_dmy.group(3))
        try:
            target = date(y, m, d)
            return ResolvedDateRange(
                start_date=target,
                end_date=target,
                start_time=None,
                end_time=None,
                label=target.isoformat(),
            )
        except ValueError:
            pass

    return None


def extract_comparison_periods(text: str) -> ComparisonPeriods | None:
    """Extracts two periods for comparison from queries like:

    'Compare September revenue with August' or 'September vs August'.
    """
    if not text:
        return None

    t = text.lower()
    today = datetime.now(timezone.utc).date()
    current_year = today.year

    # Search for two distinct month names in query
    found_months = []
    for word in t.split():
        clean_word = re.sub(r"[^\w]", "", word)
        if clean_word in MONTH_NAMES and MONTH_NAMES[clean_word] not in [m[1] for m in found_months]:
            found_months.append((clean_word, MONTH_NAMES[clean_word]))

    if len(found_months) >= 2:
        m1_name, m1_num = found_months[0]
        m2_name, m2_num = found_months[1]

        days1 = calendar.monthrange(current_year, m1_num)[1]
        days2 = calendar.monthrange(current_year, m2_num)[1]

        p1 = (date(current_year, m1_num, 1), date(current_year, m1_num, days1))
        p2 = (date(current_year, m2_num, 1), date(current_year, m2_num, days2))

        return ComparisonPeriods(
            period_a=p1,
            period_b=p2,
            label_a=f"{calendar.month_name[m1_num]} {current_year}",
            label_b=f"{calendar.month_name[m2_num]} {current_year}",
        )

    return None
