from datetime import date
import calendar

def act_365(d1: date, d2: date) -> float:
    """Actual/365 daycount fraction."""
    return (d2 - d1).days / 365.0

def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

def act_act_icma(d1: date, d2: date, freq: int = 2) -> float:
    """
    Simplified Actual/Actual (ICMA) usually used for Treasury Bonds.
    Assuming standard semi-annual coupon periods for the gap.
    This is an approximation suitable for bootstrap purposes where we just need 
    the correct time factor in years.
    If exact coupon payment dates are needed, we need the next coupon date.
    We will use a standard Actual / Actual (ISDA) formulation for continuous time
    if coupon dates aren't fully provided, or ICMA if they are.
    Here we implement a standard Act/Act (ISDA):
    """
    days_in_leap_year = 0
    days_in_normal_year = 0
    
    y1, y2 = d1.year, d2.year
    if y1 == y2:
        days = (d2 - d1).days
        return days / 366.0 if _is_leap_year(y1) else days / 365.0
        
    # Full years between y1 and y2
    for y in range(y1 + 1, y2):
        if _is_leap_year(y):
            days_in_leap_year += 366
        else:
            days_in_normal_year += 365
            
    # Days in y1
    days_y1 = (date(y1, 12, 31) - d1).days
    # Days in y2
    days_y2 = (d2 - date(y2, 1, 1)).days + 1
    
    first_fraction = days_y1 / 366.0 if _is_leap_year(y1) else days_y1 / 365.0
    second_fraction = days_y2 / 366.0 if _is_leap_year(y2) else days_y2 / 365.0
    
    return first_fraction + (days_in_leap_year / 366.0) + (days_in_normal_year / 365.0) + second_fraction

def thirty_360_us(d1: date, d2: date) -> float:
    """30/360 US standard."""
    d1_d, d1_m, d1_y = d1.day, d1.month, d1.year
    d2_d, d2_m, d2_y = d2.day, d2.month, d2.year
    
    if d1_d == 31:
        d1_d = 30
    if d2_d == 31 and d1_d == 30:
        d2_d = 30
        
    days = 360 * (d2_y - d1_y) + 30 * (d2_m - d1_m) + (d2_d - d1_d)
    return days / 360.0

def get_year_fraction(d1: date, d2: date, convention: str = "ACT/365") -> float:
    conv = convention.upper()
    if conv == "ACT/365":
        return act_365(d1, d2)
    elif conv == "ACT/ACT":
        return act_act_icma(d1, d2)
    elif conv == "30/360":
        return thirty_360_us(d1, d2)
    else:
        raise ValueError(f"Unknown daycount convention: {convention}")
