from pydantic import BaseModel


class FunnelStage(BaseModel):
    stage: str
    label: str
    count: int


class HuntTotals(BaseModel):
    matches_scored: int
    applications: int
    outreach_sent: int
    interviews_completed: int


class StreakStats(BaseModel):
    current_days: int
    longest_days: int
    active_days_in_window: int
    window_days: int


class ConversionRates(BaseModel):
    applied_to_interviewing: float | None
    applied_to_offered: float | None


class ActivityDay(BaseModel):
    date: str
    active: bool


class HuntStats(BaseModel):
    funnel: list[FunnelStage]
    totals: HuntTotals
    streak: StreakStats
    conversion: ConversionRates
    activity: list[ActivityDay]
