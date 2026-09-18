# -*- coding: utf-8 -*-
"""
Created on Thu Sep 17 08:54:48 2026

@author: Kehan

Price a swap based on QuantLib.
"""

import QuantLib as ql
import pandas as pd
import numpy as np
import inspect
import math 
import matplotlib.pyplot as plt  

def ois_swap_par_rate(curve, year, today, settlement_days=2, notional = 1000000, dummy_fixed_rate=0.03):
    tenor = ql.Period(year, ql.Years)
    curve_handle = ql.YieldTermStructureHandle(curve)
    sofr = ql.Sofr(curve_handle)
    
    effective_date = calendar.advance(
    today,
    settlement_days,
    ql.Days
    )
    
    maturity_date = calendar.advance(
        effective_date,
        tenor,
        ql.ModifiedFollowing
    )
    
    # Fixed-leg schedule
    fixed_schedule = ql.Schedule(
        effective_date,
        maturity_date,
        ql.Period(ql.Annual),
        calendar,
        ql.ModifiedFollowing,
        ql.ModifiedFollowing,
        ql.DateGeneration.Backward,
        False
    )
    
    swap = ql.OvernightIndexedSwap(
            ql.OvernightIndexedSwap.Payer,
            notional,                  # notional
            fixed_schedule,
            dummy_fixed_rate,
            ql.Actual360(),             # fixed-leg day count
            sofr
        )
    
    # Discount using the same SOFR curve
    engine = ql.DiscountingSwapEngine(curve_handle)
    swap.setPricingEngine(engine)
    
    fair_rate = swap.fairRate()
    return fair_rate
        
def numeric_deriv( f, x, epsilon=1e-6 ):
    return ( f(x+epsilon) - f(x-epsilon) ) / ( 2*epsilon )

def swap_helper_api(quotes=None, calendar=None, payfreq=None, index = None,
                    busiConv=None,   dcc=None,      settle_days=None, isSOFRois = True):
    helpers = []
    for tenor, rate in quotes.items():
        quote  = ql.QuoteHandle(ql.SimpleQuote(rate))
        if isSOFRois:
            helper = ql.OISRateHelper(settle_days, ql.Period(tenor, ql.Years), quote, index)
        else:
            helper = ql.SwapRateHelper(quote, ql.Period(tenor, ql.Years), calendar, 
                                       payfreq, busiConv, dcc, index)
        
        helpers.append(helper)
 
    return helpers


today = ql.Date(17, 9, 2026)
ql.Settings.instance().evaluationDate = today
# print(dir(today)) # Print out all the attributes of an object
# today.dayOfMonth()

# =============================================================================
# Overnight indexed swap (OIS)
# https://www.implementingquantlib.com/2024/06/different-swaps.html
# =============================================================================

# 1/ To price a OIS, we need a IR curve to
#    1.1/ Project the future cashflows given an index; 
#    1.2/ Discount the cashflows.  
# 2/ The IR curve needs to be constructed (e.g. using bootstrapping).
#    We construct a SOFR curve based on SOFR OIS swap rate.
# 3/ SOFR OIS Swap convention:
#    3.1/ Payment frequency: Annual
#    3.2/ DDC (Day Count Convention): Act/360
#    3.3/ Payment delay: 2 business day    
#    3.4/ Business-day convention: Modified Following
# Reference:
# https://quant.stackexchange.com/questions/44712/quantlib-python-use-zero-rates-to-get-the-originally-bootstrapped-curve/44779#44779
# https://quant.stackexchange.com/questions/53077/quantlib-zerocurve-interpolation  
# https://quant.stackexchange.com/questions/75624/bootstrap-with-quantlib-usd-sofr-vs-fixed-rate-swap-curve             

# 4/ Convention
calendar             = ql.UnitedStates(ql.UnitedStates.SOFR)
index                = ql.Sofr()
settlement_days      = 2
fixed_leg_freq       = ql.Annual
fixed_leg_convention = ql.ModifiedFollowing
fixed_leg_day_count  = ql.Actual360()
# print(dir(calendar))
# calendar.isBusinessDay(today)

# 5/ Floating index
# It will be used to calculate the compounded sofr rate.
index = ql.Sofr()

# 6/ Par swap rates
# https://cf.com/rates/us
swap_rates = {
    1:  0.04404,
    2:  0.04545,
    3:  0.04564,
    5:  0.04556,
    7:  0.04566,
    10: 0.04607,
    15: 0.04702,
    30: 0.04664
}

#quotes = {}
#for tenor, rate in swap_rates.items():
#    quotes[tenor] = 0.3
#swap_rates = quotes

# 7/ Create sofr OIS helpers
helpers = swap_helper_api(quotes=swap_rates, settle_days=settlement_days, index = index, isSOFRois = True)

# 8/ Construct the curve
curve = ql.PiecewiseLogLinearDiscount(
#curve  = ql.PiecewiseCubicZero(
    today,
    helpers,
    ql.Actual365Fixed() # day-count convention you use to parameterize/query the curve
)



results = []

#for year in swap_rates.keys():
for T in np.linspace(1/360, 30, int(1e4)):
# =============================================================================
#     maturity = calendar.advance(
#         today,
#         ql.Period(year, ql.Years)
#     )
#     print(maturity)
# =============================================================================

# =============================================================================
#     zero_rate = curve.zeroRate(
#         maturity,
#         ql.Actual365Fixed(),
#         ql.Continuous,
#         ql.Annual
#     ).rate()
# =============================================================================

    zero_rate = curve.zeroRate(
        T, # Continuous time point rather than a date or Quantlib date.
        ql.Continuous,
        ql.Annual
    ).rate()

    # discount_factor = curve.discount(maturity)
    discount_factor = curve.discount(T)
    zr_df           = - math.log(discount_factor) / T
    ifr             = - numeric_deriv(lambda x: math.log( curve.discount(x) ), x = T)
    #swp_rate        = ois_swap_par_rate(curve, T, today)
    
    results.append({
        "Tenor": T,
        #"Swap Rate": swap_rates[year],
        #"Swp_rate": swp_rate,
        "Zero Rate": zero_rate,
        "Discount Factor": discount_factor,
        "Zero Rate from DF": zr_df,
        "ifr": ifr,
    })

df = pd.DataFrame(results)

print(df)

plt.figure(figsize=(10, 6))

plt.plot(
    df["Tenor"],
    df["Zero Rate"],
    label="Zero Rate",
    linewidth=2
)

plt.plot(
    df["Tenor"],
    df["ifr"],
    label="Instantaneous Forward Rate",
    linewidth=2
)

plt.xlabel("Tenor (Years)")
plt.ylabel("Rate")
plt.title("Zero Rate and Instantaneous Forward Rate")
plt.legend()
plt.grid(True)

plt.show()

# =============================================================================
# Zero rate from Swap rate
# Reference
# https://www.r-bloggers.com/2021/07/bootstrapping-the-zero-curve-from-irs-swap-rates-using-r-code/
# =============================================================================



