import pytest
import math
from lankarfr.curve.curve import YieldCurve
from lankarfr.curve.bootstrap import bootstrap_curve, Bond
from lankarfr.conventions.compounding import continuous_curve_to_price

def test_bootstrap():
    # Base T-bill curve up to 1Y
    tbill_points = [(0.25, 0.08), (0.50, 0.085), (1.0, 0.09)]
    
    # We create synthetic bonds priced strictly against a known true continuous zero curve
    # Let's assume the true zero curve is flat at 10% after 1Y
    # true_z(t) = 0.10 for t > 1
    
    # Bond 1: 2Y tenor, 10% annual coupon, semi-annual payments (5% per half year)
    # Cashflows:
    # 0.5Y: 5 (z = 0.085)
    # 1.0Y: 5 (z = 0.09)
    # 1.5Y: 5 (*unknown z, we'll construct it using true curve: 0.095)
    # 2.0Y: 105 (*unknown z, we'll construct it using true curve: 0.10)
    
    # Let's say true zero curve extends to: 1.5Y = 0.095, 2.0Y = 0.10
    # Let's calculate the expected strict price for the 2Y bond under this true curve
    true_curve_points = tbill_points + [(2.0, 0.10)]
    true_curve = YieldCurve(true_curve_points)
    
    # Price of 2Y bond under true curve
    p2 = continuous_curve_to_price(true_curve.get_zero_rate, 0.10, 2.0)
    
    # Price of 3Y bond (Coupon 12%)
    true_curve_points = tbill_points + [(2.0, 0.10), (3.0, 0.105)]
    true_curve = YieldCurve(true_curve_points)
    p3 = continuous_curve_to_price(true_curve.get_zero_rate, 0.12, 3.0)
    
    # Now that we have prices p2 and p3, we can create our market bonds
    # Wait, the Bond class is initialized with YTM. We need a way to initialize from price,
    # or we can back out the discrete YTM that gives this price.
    # To keep it simple, we can just modify Bond's price directly for the test.
    
    b2 = Bond(tenor_years=2.0, coupon_rate=0.10, ytm=0.10)
    b2.price = p2 # Override YTM derived price with exact true curve matched price
    
    b3 = Bond(tenor_years=3.0, coupon_rate=0.12, ytm=0.105)
    b3.price = p3
    
    # Run the bootstrap
    bootstrapped_curve = bootstrap_curve(tbill_points, [b2, b3])
    
    # The bootstrapper builds linear piecewise curve. 
    # Because we priced b2 assuming linear interpolation from 1.0Y to 2.0Y, the bootstrapper should find exactly z=0.10 at 2Y.
    z_2 = bootstrapped_curve.get_zero_rate(2.0)
    assert math.isclose(z_2, 0.10, abs_tol=1e-5)
    
    z_3 = bootstrapped_curve.get_zero_rate(3.0)
    assert math.isclose(z_3, 0.105, abs_tol=1e-5)
