"""Własne metody usuwania marży audytora (bez valuebet)."""
import numpy as np
from scipy.optimize import brentq
def shin(odds):
    q = 1.0/np.asarray(odds, float); B = q.sum()
    def p_of(z): return (np.sqrt(z*z + 4*(1-z)*q*q/B) - z)/(2*(1-z))
    f = lambda z: p_of(z).sum() - 1.0
    if B <= 1.0: return None
    lo, hi = 0.0, 0.999
    if f(lo) * f(hi) > 0: return None
    z = brentq(f, lo, hi, xtol=1e-14); return p_of(z)
def mult(odds):
    q = 1.0/np.asarray(odds, float); return q/q.sum()
def power(odds):
    q = 1.0/np.asarray(odds, float)
    if q.sum() <= 1.0: return None
    k = brentq(lambda k: (q**k).sum()-1.0, 1.0, 10.0, xtol=1e-14); return q**k
