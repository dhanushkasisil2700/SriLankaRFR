import numpy as np
from scipy.optimize import curve_fit
import scipy.interpolate as interp
from typing import List, Tuple

def nelson_siegel(t, beta0, beta1, beta2, tau):
    t = np.maximum(t, 1e-6)
    factor1 = (1 - np.exp(-t / tau)) / (t / tau)
    factor2 = factor1 - np.exp(-t / tau)
    return beta0 + beta1 * factor1 + beta2 * factor2

def fit_nelson_siegel(data_points: List[Tuple[float, float]], target_tenors: List[float] = None) -> List[Tuple[float, float]]:
    if not data_points: return []
    tenors = np.array([p[0] for p in data_points])
    yields = np.array([p[1] for p in data_points])
    bounds = ([0.01, -0.50, -0.50, 0.1], [0.50,  0.50,  0.50, 10.0])
    guess = [0.10, 0.0, 0.0, 1.5]
    
    try:
        popt, _ = curve_fit(nelson_siegel, tenors, yields, p0=guess, bounds=bounds, method='trf')
    except Exception:
        popt = guess
        
    if target_tenors is None: target_tenors = np.arange(0.25, int(np.ceil(max(tenors))) + 0.25, 0.25)
    return list(zip(target_tenors, nelson_siegel(np.array(target_tenors), *popt)))

def svensson(t, beta0, beta1, beta2, beta3, tau1, tau2):
    t = np.maximum(t, 1e-6)
    factor1 = (1 - np.exp(-t / tau1)) / (t / tau1)
    factor2 = factor1 - np.exp(-t / tau1)
    factor3 = ((1 - np.exp(-t / tau2)) / (t / tau2)) - np.exp(-t / tau2)
    return beta0 + beta1 * factor1 + beta2 * factor2 + beta3 * factor3

def fit_nelson_siegel_svensson(data_points: List[Tuple[float, float]], target_tenors: List[float] = None) -> List[Tuple[float, float]]:
    if not data_points: return []
    tenors = np.array([p[0] for p in data_points])
    yields = np.array([p[1] for p in data_points])
    
    # beta0, beta1, beta2, beta3, tau1, tau2
    bounds = (
        [0.01, -0.50, -0.50, -0.50, 0.1, 0.1],
        [0.50,  0.50,  0.50,  0.50, 10.0, 10.0]
    )
    guess = [0.10, 0.0, 0.0, 0.0, 1.5, 3.0]
    
    try:
        popt, _ = curve_fit(svensson, tenors, yields, p0=guess, bounds=bounds, method='trf')
    except Exception:
        # Fall back to NS if NSS fails
        try:
            popt_ns, _ = curve_fit(nelson_siegel, tenors, yields, bounds=([0.01, -0.50, -0.50, 0.1], [0.50, 0.50, 0.50, 10.0]))
            popt = [popt_ns[0], popt_ns[1], popt_ns[2], 0.0, popt_ns[3], 3.0]
        except Exception:
            popt = guess
            
    if target_tenors is None: target_tenors = np.arange(0.25, int(np.ceil(max(tenors))) + 0.25, 0.25)
    return list(zip(target_tenors, svensson(np.array(target_tenors), *popt)))

def fit_cubic_spline(data_points: List[Tuple[float, float]], target_tenors: List[float] = None) -> List[Tuple[float, float]]:
    if not data_points: return []
    # Sort data directly to satisfy strictly increasing requirements for splines
    data_points = sorted(data_points, key=lambda x: x[0])
    
    # UnivariateSpline handles multiple points at same x by taking average or noise. But to be safe, average duplicate tenors.
    unique_data = {}
    for t, y in data_points:
        unique_data.setdefault(t, []).append(y)
    
    clean_tenors = np.array(list(unique_data.keys()))
    clean_yields = np.array([np.mean(unique_data[t]) for t in clean_tenors])
    
    # Smoothing factor s. Higher s = more smooth line, ignores individual noisy points.
    s_val = len(clean_tenors) * 0.0005 
    spline = interp.UnivariateSpline(clean_tenors, clean_yields, k=3, s=s_val)
    
    if target_tenors is None: target_tenors = np.arange(0.25, int(np.ceil(max(clean_tenors))) + 0.25, 0.25)
    return list(zip(target_tenors, spline(np.array(target_tenors))))

def fit_monotone_convex(data_points: List[Tuple[float, float]], target_tenors: List[float] = None) -> List[Tuple[float, float]]:
    if not data_points: return []
    data_points = sorted(data_points, key=lambda x: x[0])
    
    unique_data = {}
    for t, y in data_points:
        unique_data.setdefault(t, []).append(y)
    clean_tenors = np.array(list(unique_data.keys()))
    clean_yields = np.array([np.mean(unique_data[t]) for t in clean_tenors])
    
    pchip = interp.PchipInterpolator(clean_tenors, clean_yields)
    
    if target_tenors is None: target_tenors = np.arange(0.25, int(np.ceil(max(clean_tenors))) + 0.25, 0.25)
    return list(zip(target_tenors, pchip(np.array(target_tenors))))

def fit_smith_wilson(data_points: List[Tuple[float, float]], target_tenors: List[float] = None, ufr=0.04, alpha=0.1) -> List[Tuple[float, float]]:
    """
    EIOPA Smith-Wilson Zero Curve Extrapolator
    ufr: Ultimate Forward Rate (4.0% default)
    alpha: Convergence speed
    """
    if not data_points: return []
    # Strip exactly duplicate tenors or very closely adjacent noise by bucketing to 3 decimal places
    unique_data = {}
    for t, y in data_points:
        unique_data.setdefault(round(t, 3), []).append(y)
    
    u = np.array(list(unique_data.keys()))
    y = np.array([np.mean(unique_data[t]) for t in u])
    
    # Convert yields to Zero Coupon Bond prices
    P = np.exp(-y * u)
    
    # Vectorized Wilson Function
    def W(t_arr, u_arr):
        T, U = np.meshgrid(t_arr, u_arr, indexing='ij')
        min_tu = np.minimum(T, U)
        max_tu = np.maximum(T, U)
        term1 = alpha * min_tu
        term2 = 0.5 * np.exp(-alpha * max_tu) * (np.exp(alpha * min_tu) - np.exp(-alpha * min_tu))
        return np.exp(-ufr * (T + U)) * (term1 - term2)
        
    # Solve for Zeta
    W_mat = W(u, u)
    m = P - np.exp(-ufr * u)
    
    try:
        zeta = np.linalg.solve(W_mat, m)
    except np.linalg.LinAlgError:
        # Fall back to pseudo-inverse if W_mat is singular due to clustered points
        zeta = np.linalg.pinv(W_mat).dot(m)
        
    if target_tenors is None: target_tenors = np.arange(0.25, int(np.ceil(max(u))) + 0.25, 0.25)
    
    # Evaluate at target tenors
    t_targets = np.array(target_tenors)
    W_eval = W(t_targets, u)
    P_eval = np.exp(-ufr * t_targets) + W_eval.dot(zeta)
    
    # Convert prices back to zero rates, protecting against P_eval <= 0
    smooth_yields = []
    for p_val, t_val in zip(P_eval, t_targets):
        if p_val <= 0:
            smooth_yields.append(ufr)
        else:
            smooth_yields.append(-np.log(p_val) / t_val)
            
    return list(zip(target_tenors, smooth_yields))
