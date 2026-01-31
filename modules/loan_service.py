"""
Loan amortization service.

Handles calculation of loan repayment schedules and automatic payment processing.
"""
from datetime import datetime
import numpy_financial as npf
from models import LoanScheduleItem, LoanPlan
import logging

logger = logging.getLogger(__name__)

def calculate_amortization_schedule(
    principal: float,
    annual_rate: float,
    period_months: int,
    start_date: str,
    repayment_method: str = "equal_principal_interest"
) -> list[LoanScheduleItem]:
    """
    Calculate amortization schedule based on method.
    
    Args:
        principal: Loan amount
        annual_rate: Annual interest rate in %
        period_months: Loan duration in months
        start_date: Loan start date (YYYY-MM-DD)
        repayment_method: "equal_principal_interest" (default) or "equal_principal"
        
    Returns:
        List of LoanScheduleItem
    """
    schedule = []
    monthly_rate = annual_rate / 100 / 12
    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    remaining_balance = principal
    
    # Pre-calculate fixed principal for "equal_principal"
    fixed_principal = principal / period_months if period_months > 0 else 0

    # Pre-calculate fixed payment for "equal_principal_interest" (PMT)
    fixed_payment = 0
    if repayment_method == "equal_principal_interest":
        if monthly_rate > 0:
            fixed_payment = abs(npf.pmt(monthly_rate, period_months, principal))
        else:
            fixed_payment = principal / period_months

    for i in range(1, period_months + 1):
        interest_paid = remaining_balance * monthly_rate
        
        if repayment_method == "equal_principal":
            # 本金平均攤還
            principal_paid = fixed_principal
            monthly_payment = principal_paid + interest_paid

            # Last month adjustment not usually needed for principal,
            # but good to ensure exact zero
            if i == period_months:
                principal_paid = remaining_balance
                monthly_payment = principal_paid + interest_paid

        else:
            # 本息平均攤還 (Default)
            monthly_payment = fixed_payment
            principal_paid = monthly_payment - interest_paid
            
            # Handle last payment rounding
            if i == period_months:
                principal_paid = remaining_balance
                monthly_payment = principal_paid + interest_paid

        remaining_balance -= principal_paid
        if remaining_balance < 0: remaining_balance = 0.0
        
        # Calculate next date (Simple logic: +1 month)
        # Using the same simplified logic as before to maintain consistency
        year = current_date.year + (current_date.month) // 12
        month = (current_date.month % 12) + 1
        day = min(current_date.day, 28)
        next_date = datetime(year, month, day)
        current_date = next_date
        
        item = LoanScheduleItem(
            payment_number=i,
            date=current_date.strftime("%Y-%m-%d"),
            payment_amount=round(monthly_payment, 2),
            principal_paid=round(principal_paid, 2),
            interest_paid=round(interest_paid, 2),
            remaining_balance=round(remaining_balance, 2),
            is_paid=False
        )
        schedule.append(item)
        
    return schedule

def create_loan_plan(
    asset_id: str,
    total_amount: float,
    annual_rate: float,
    period_months: int,
    start_date: str,
    extra_fees: float = 0.0,
    payment_account_id: str = None,
    repayment_method: str = "equal_principal_interest"
) -> LoanPlan:
    """Factory to create a calculated LoanPlan"""
    schedule = calculate_amortization_schedule(
        total_amount, annual_rate, period_months, start_date, repayment_method
    )
    
    return LoanPlan(
        asset_id=asset_id,
        total_amount=total_amount,
        annual_rate=annual_rate,
        period_months=period_months,
        start_date=start_date,
        extra_fees=extra_fees,
        payment_account_id=payment_account_id,
        repayment_method=repayment_method,
        schedule=schedule
    )

def process_loan_payments(portfolio: list, loan_plans: list) -> int:
    """
    Check and process due payments for all loan plans.
    Updates portfolio assets (Cash and Liability) in-place.
    Updates loan_plans (next_payment_number) in-place.

    Args:
        portfolio: List of Asset dicts (from session state)
        loan_plans: List of LoanPlan dicts (from session state)

    Returns:
        int: Number of payments processed
    """
    processed_count = 0
    today = datetime.now().date()

    # Map assets by ID for quick lookup
    assets_map = {a.get("asset_id"): a for a in portfolio}

    for plan in loan_plans:
        # Extract plan details (handle dict)
        asset_id = plan.get("asset_id")
        total_amount = float(plan.get("total_amount", 0))
        annual_rate = float(plan.get("annual_rate", 0))
        period_months = int(plan.get("period_months", 0))
        start_date = plan.get("start_date")
        repayment_method = plan.get("repayment_method", "equal_principal_interest")
        next_num = int(plan.get("next_payment_number", 1))
        pay_asset_id = plan.get("payment_account_id")

        if not asset_id or not start_date:
            continue

        # 1. Regenerate schedule (since it's not persisted fully)
        schedule = calculate_amortization_schedule(
            total_amount, annual_rate, period_months, start_date, repayment_method
        )

        # 2. Check for due payments
        payments_made_for_this_plan = 0

        for item in schedule:
            # Skip already paid
            if item.payment_number < next_num:
                continue

            # Check date
            try:
                item_date = datetime.strptime(item.date, "%Y-%m-%d").date()
            except ValueError:
                continue

            if item_date <= today:
                # Payment is due!

                # A. Deduct from Cash Asset (if linked and exists)
                if pay_asset_id and pay_asset_id in assets_map:
                    cash_asset = assets_map[pay_asset_id]
                    # Simple deduction, ignore currency conversion for now (assume same)
                    curr_qty = float(cash_asset.get("quantity", 0))
                    new_qty = curr_qty - item.payment_amount
                    cash_asset["quantity"] = new_qty if new_qty > 0 else 0.0

                # B. Reduce Liability Principal
                if asset_id in assets_map:
                    liab_asset = assets_map[asset_id]
                    curr_princ = float(liab_asset.get("quantity", 0))
                    new_princ = curr_princ - item.principal_paid
                    liab_asset["quantity"] = new_princ if new_princ > 0 else 0.0

                    # Update 'current_price' to match remaining principal?
                    # For liabilities, quantity usually tracks amount. Price is 1?
                    # Or quantity is 1 and price is amount?
                    # In add_asset_dialog, quantity=Amount, Price=1.
                    # So reducing quantity is correct.

                # C. Update Plan State
                next_num = item.payment_number + 1
                payments_made_for_this_plan += 1
                processed_count += 1

                logger.info(f"Processed payment #{item.payment_number} for Loan {asset_id}: {item.payment_amount}")

            else:
                # Schedule is chronological, so we can stop if we hit a future date
                break

        # Update the plan dict with new next_payment_number
        if payments_made_for_this_plan > 0:
            plan["next_payment_number"] = next_num

    return processed_count
