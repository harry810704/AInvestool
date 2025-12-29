"""
Loan amortization service.

Handles calculation of loan repayment schedules.
"""
from datetime import datetime, timedelta
import math
import numpy_financial as npf
from models import LoanScheduleItem, LoanPlan

def calculate_amortization_schedule(
    principal: float,
    annual_rate: float,
    period_months: int,
    start_date: str
) -> list[LoanScheduleItem]:
    """
    Calculate fixed monthly amortization schedule using numpy-financial.
    
    Args:
        principal: Loan amount
        annual_rate: Annual interest rate in %
        period_months: Loan duration in months
        start_date: Loan start date (YYYY-MM-DD)
        
    Returns:
        List of LoanScheduleItem
    """
    schedule = []
    monthly_rate = annual_rate / 100 / 12
    
    # Calculate monthly payment (PMT)
    # We use numpy_financial.pmt(rate, nper, pv)
    # Result is usually negative representing cash outflow, so we take abs
    if monthly_rate > 0:
        monthly_payment = abs(npf.pmt(monthly_rate, period_months, principal))
    else:
        monthly_payment = principal / period_months
        
    remaining_balance = principal
    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    
    for i in range(1, period_months + 1):
        # Calculate Interest for this period
        interest_paid = remaining_balance * monthly_rate
        
        # Calculate Principal paid
        principal_paid = monthly_payment - interest_paid
        
        # Handle last payment rounding adjustment
        if i == period_months:
            # Adjust last payment to close the balance
            principal_paid = remaining_balance
            monthly_payment = principal_paid + interest_paid
            remaining_balance = 0.0
        else:
            remaining_balance -= principal_paid
            
        # Ensure remaining balance doesn't go negative due to float precision
        if remaining_balance < 0: remaining_balance = 0.0
        
        # Calculate next payment date
        # Simple month addition logic
        # Using a safer way to add months: current_date + ~30 days is risky.
        # Let's use a simple month increment helper or just rely on 30 days approximation for simplicity
        # or relativedelta if available (but only standard libs + numpy/pandas specified)
        # Using a simple approximation for now: 
        # Standard way without dateutil is tricky. Let's just increment by 30 days for now.
        # OR:
        year = current_date.year + (current_date.month) // 12
        month = (current_date.month % 12) + 1
        day = min(current_date.day, 28) # Simplify to 28th to avoid leap year issues for now
        next_date = datetime(year, month, day)
        current_date = next_date
        
        item = LoanScheduleItem(
            payment_number=i,
            date=current_date.strftime("%Y-%m-%d"),
            payment_amount=round(monthly_payment, 2),
            principal_paid=round(principal_paid, 2),
            interest_paid=round(interest_paid, 2),
            remaining_balance=round(remaining_balance, 2)
        )
        schedule.append(item)
        
    return schedule

def create_loan_plan(
    asset_id: str,
    total_amount: float,
    annual_rate: float,
    period_months: int,
    start_date: str,
    extra_fees: float = 0.0
) -> LoanPlan:
    """Factory to create a calculated LoanPlan"""
    schedule = calculate_amortization_schedule(total_amount, annual_rate, period_months, start_date)
    
    return LoanPlan(
        asset_id=asset_id,
        total_amount=total_amount,
        annual_rate=annual_rate,
        period_months=period_months,
        start_date=start_date,
        extra_fees=extra_fees,
        schedule=schedule
    )
