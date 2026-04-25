import math

def to_continuous(rate: float, freq: int) -> float:
    """
    Convert a discrete compounded rate to a continuously compounded rate.
    freq = 2 for semi-annual (Standard T-bonds)
    freq = 1 for annual
    """
    if rate <= -1:
         raise ValueError("Rate must be > -1")
    return freq * math.log(1 + rate / freq)

def to_discrete(rate_continuous: float, freq: int) -> float:
    """
    Convert a continuous rate to a discrete compounded rate.
    """
    return freq * (math.exp(rate_continuous / freq) - 1)

def yield_to_price(ytm: float, coupon_rate: float, tenor_years: float, freq: int = 2) -> float:
    """
    Calculate the clean price of a bond given YTM (discrete).
    This assumes exact coupon periods remaining for simplicity.
    ytm: yield to maturity (e.g., 0.10 for 10%)
    coupon_rate: annualized coupon rate (e.g., 0.08 for 8%)
    tenor_years: years to maturity
    """
    periods = int(round(tenor_years * freq))
    if periods <= 0:
        return 100.0 # Matured
        
    price = 0.0
    df = 1.0 / (1 + ytm / freq)
    
    # Coupons
    for i in range(1, periods + 1):
        price += (coupon_rate / freq * 100) * (df ** i)
        
    # Principal
    price += 100 * (df ** periods)
    return price
    
def continuous_curve_to_price(zero_curve_func, coupon_rate: float, tenor_years: float, freq: int = 2) -> float:
    """
    Calculate the price of a bond given a continuous zero curve function z(t).
    zero_curve_func: callable that takes tenor in years and returns continuous zero rate
    """
    periods = int(round(tenor_years * freq))
    if periods <= 0:
        return 100.0
        
    price = 0.0
    for i in range(1, periods + 1):
        t = i / freq
        z = zero_curve_func(t)
        price += (coupon_rate / freq * 100) * math.exp(-z * t)
        
    # Principal
    t = periods / freq
    z = zero_curve_func(t)
    price += 100 * math.exp(-z * t)
    return price
