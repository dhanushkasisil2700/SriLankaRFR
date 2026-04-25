import math
from typing import List, Tuple

class YieldCurve:
    """
    A simple piecewise-linear continuous zero-coupon yield curve.
    Extrapolates flat before the first point and after the last point.
    """
    def __init__(self, points: List[Tuple[float, float]]):
        """
        points: List of (tenor_in_years, continuously_compounded_zero_rate)
        Should be sorted by tenor.
        """
        self.points = sorted(points, key=lambda x: x[0])
        if not self.points:
            raise ValueError("Curve requires at least one point")
            
    def get_zero_rate(self, t: float) -> float:
        """Evaluate the zero rate at tenor t using linear interpolation"""
        if t <= self.points[0][0]:
            return self.points[0][1]
        
        if t >= self.points[-1][0]:
            return self.points[-1][1]
            
        for i in range(len(self.points) - 1):
            t1, z1 = self.points[i]
            t2, z2 = self.points[i+1]
            
            if t1 <= t <= t2:
                # Linear interpolation
                w = (t - t1) / (t2 - t1)
                return z1 + w * (z2 - z1)
                
        # Fallback (should never be reached due to condition above)
        return self.points[-1][1]
        
    def get_discount_factor(self, t: float) -> float:
        """Returns the discount factor D(0, t)."""
        z = self.get_zero_rate(t)
        return math.exp(-z * t)
        
    def get_forward_rate(self, t1: float, t2: float) -> float:
        """Discrete forward rate between t1 and t2 (t2 > t1)"""
        if t2 <= t1:
            raise ValueError("t2 must be greater than t1")
        
        z1 = self.get_zero_rate(t1)
        z2 = self.get_zero_rate(t2)
        
        return (z2 * t2 - z1 * t1) / (t2 - t1)

def tbill_yield_to_zero_rate(discount_yield: float, days: int) -> float:
    """
    Convert a T-bill discount yield (percentage format, e.g. 8.5 for 8.5%) 
    to a continuously compounded zero rate.
    
    T-bill formula: Price = 100 * (1 - (discount_yield/100) * (days / 365))
    Continuous rate: r_c = -(365/days) * ln(Price/100)
    """
    price = 100 * (1 - (discount_yield / 100) * (days / 365))
    if price <= 0:
        raise ValueError("Invalid discount yield resulting in price <= 0")
    
    r_c = -(365.0 / days) * math.log(price / 100.0)
    return r_c

def build_tbill_curve(yields_dict: dict) -> YieldCurve:
    """
    Builds a YieldCurve from a dictionary of T-bill yields.
    yields_dict: {'91_day_yield': 8.50, '182_day_yield': 9.00, '364_day_yield': 9.50}
    """
    mapping = {
        '91_day_yield': (91, 91 / 365.0),
        '182_day_yield': (182, 182 / 365.0),
        '364_day_yield': (364, 364 / 365.0) # Using 364 instead of 365 per typical CBSL format
    }
    
    points = []
    for k, (days, tenor) in mapping.items():
        val = yields_dict.get(k)
        if val is not None:
            r_c = tbill_yield_to_zero_rate(val, days)
            points.append((tenor, r_c))
            
    return YieldCurve(points)
