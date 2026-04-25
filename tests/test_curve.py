import pytest
import math
from lankarfr.curve.curve import tbill_yield_to_zero_rate, build_tbill_curve, YieldCurve

def test_tbill_yield_to_zero_rate():
    # Example: 91 day at 8.50% discount yield
    # Price = 100 * (1 - 8.50/100 * 91/365) = 100 * (1 - 0.085 * 0.249315) = 100 * (1 - 0.02119178) = 97.88082
    # Continuous rate = -(365/91) * ln(97.88082 / 100) = -4.010989 * -0.021415 = 0.08589
    rate = tbill_yield_to_zero_rate(8.50, 91)
    
    # Let's compute exact expected
    price = 100 * (1 - 0.085 * 91/365)
    expected = -(365/91) * math.log(price/100)
    
    assert math.isclose(rate, expected, rel_tol=1e-9)
    assert rate > 0.085 # Effective yield should be higher than discount yield

def test_yield_curve_interpolation():
    points = [(0.25, 0.085), (0.50, 0.090), (1.0, 0.095)]
    curve = YieldCurve(points)
    
    # Exact points
    assert math.isclose(curve.get_zero_rate(0.25), 0.085)
    assert math.isclose(curve.get_zero_rate(0.50), 0.090)
    assert math.isclose(curve.get_zero_rate(1.0), 0.095)
    
    # Interpolation
    assert math.isclose(curve.get_zero_rate(0.375), 0.0875) # Midpoint between 0.25 and 0.50
    assert math.isclose(curve.get_zero_rate(0.75), 0.0925)  # Midpoint between 0.50 and 1.0

    # Extrapolation
    assert math.isclose(curve.get_zero_rate(0.1), 0.085) # Flat before first
    assert math.isclose(curve.get_zero_rate(2.0), 0.095) # Flat after last
    
def test_discount_factor():
    points = [(1.0, 0.10)] # 10% continuously compounded at 1Y
    curve = YieldCurve(points)
    
    df = curve.get_discount_factor(1.0)
    assert math.isclose(df, math.exp(-0.10 * 1.0))

def test_forward_rate():
    # z1 = 5% at 1Y, z2 = 6% at 2Y
    points = [(1.0, 0.05), (2.0, 0.06)]
    curve = YieldCurve(points)
    
    # Forward rate between 1Y and 2Y
    # f = (0.06 * 2 - 0.05 * 1) / (2 - 1) = (0.12 - 0.05) / 1 = 0.07
    fwd = curve.get_forward_rate(1.0, 2.0)
    assert math.isclose(fwd, 0.07)
