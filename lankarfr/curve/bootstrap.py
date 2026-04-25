import math
from typing import List, Tuple
from scipy.optimize import root_scalar

from lankarfr.conventions.compounding import yield_to_price, continuous_curve_to_price
from lankarfr.curve.curve import YieldCurve

class Bond:
    def __init__(self, tenor_years: float, coupon_rate: float, ytm: float):
        self.tenor_years = tenor_years
        self.coupon_rate = coupon_rate
        self.ytm = ytm
        self.price = yield_to_price(ytm, coupon_rate, tenor_years)

def bootstrap_curve(tbill_points: List[Tuple[float, float]], bonds: List[Bond]) -> YieldCurve:
    """
    Bootstrap a continuous zero-coupon yield curve.
    tbill_points: Sorted list of (tenor, zero_rate) from T-bills (up to 1Y)
    bonds: List of Bond objects, should be sorted by tenor_years.
           Assumes bonds have tenors > 1Y and pay semi-annual coupons.
    """
    
    # Start with T-bill points
    current_points = list(tbill_points)
    
    # Ensure bonds are sorted by maturity
    bonds_sorted = sorted(bonds, key=lambda b: b.tenor_years)
    
    for bond in bonds_sorted:
        if bond.tenor_years <= current_points[-1][0]:
            # Skip bonds that don't extend the curve
            # In a real system, we might fit or average, but bootstrapping requires strictly increasing tenors.
            continue
            
        def pricing_error(z_guess):
            # Create a temporary curve with our current points + this guess
            test_points = current_points + [(bond.tenor_years, z_guess)]
            temp_curve = YieldCurve(test_points)
            
            # Price the bond using this curve
            model_price = continuous_curve_to_price(temp_curve.get_zero_rate, bond.coupon_rate, bond.tenor_years)
            return model_price - bond.price

        # Initial guess based on the YTM itself (converted to continuous)
        # Using YTM as initial guess for continuous rate is a close approximation
        guess = bond.ytm
        
        # Solve for z_guess
        try:
            sol = root_scalar(pricing_error, bracket=[0.001, 0.50], method='brentq')
            if sol.converged:
                z_solved = sol.root
                current_points.append((bond.tenor_years, z_solved))
        except ValueError as e:
            print(f"Skipping bond t={bond.tenor_years:.2f} due to convergence failure: {e}")
            continue
        
    return YieldCurve(current_points)
