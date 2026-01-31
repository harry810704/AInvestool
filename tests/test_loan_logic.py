import sys
import os
from datetime import datetime, timedelta

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.loan_service import calculate_amortization_schedule, process_loan_payments
from models import Asset, LoanPlan

def test_amortization_equal_principal_interest():
    print("Testing Equal Principal and Interest (PMT)...")
    # Example: 100,000, 12%, 12 months
    # Monthly rate = 1%
    # PMT = 100000 * 0.01 / (1 - (1.01)^-12) = 8884.88

    schedule = calculate_amortization_schedule(
        principal=100000,
        annual_rate=12,
        period_months=12,
        start_date="2024-01-01",
        repayment_method="equal_principal_interest"
    )

    assert len(schedule) == 12

    # Check first payment
    p1 = schedule[0]
    print(f"P1: Amount={p1.payment_amount}, Principal={p1.principal_paid}, Interest={p1.interest_paid}")
    # Interest = 100000 * 0.01 = 1000
    # Payment approx 8884.88
    assert abs(p1.interest_paid - 1000) < 1.0
    assert abs(p1.payment_amount - 8885) < 5.0

    # Check total principal paid
    total_princ = sum(i.principal_paid for i in schedule)
    print(f"Total Principal Paid: {total_princ}")
    assert abs(total_princ - 100000) < 1.0

def test_amortization_equal_principal():
    print("\nTesting Equal Principal...")
    # Example: 100,000, 12%, 10 months
    # Principal per month = 10,000

    schedule = calculate_amortization_schedule(
        principal=100000,
        annual_rate=12,
        period_months=10,
        start_date="2024-01-01",
        repayment_method="equal_principal"
    )

    assert len(schedule) == 10

    # Check first payment
    p1 = schedule[0]
    # Principal = 10000
    # Interest = 100000 * 0.01 = 1000
    # Payment = 11000
    print(f"P1: Amount={p1.payment_amount}, Principal={p1.principal_paid}, Interest={p1.interest_paid}")
    assert abs(p1.principal_paid - 10000) < 1.0
    assert abs(p1.interest_paid - 1000) < 1.0
    assert abs(p1.payment_amount - 11000) < 1.0

    # Check last payment
    p10 = schedule[-1]
    # Remaining before last = 10000
    # Interest = 10000 * 0.01 = 100
    # Payment = 10100
    print(f"P10: Amount={p10.payment_amount}, Principal={p10.principal_paid}, Interest={p10.interest_paid}")
    assert abs(p10.principal_paid - 10000) < 1.0
    assert abs(p10.interest_paid - 100) < 1.0

    total_princ = sum(i.principal_paid for i in schedule)
    assert abs(total_princ - 100000) < 1.0

def test_process_loan_payments():
    print("\nTesting Process Loan Payments...")

    # Setup mock data
    # Loan started 2 months ago
    today = datetime.now()
    start_date = (today - timedelta(days=65)).strftime("%Y-%m-%d") # Should trigger 2 payments

    # Assets
    cash_asset = {
        "asset_id": "cash_1",
        "category": "cash",
        "quantity": 50000.0,
        "name": "Cash",
        "symbol": "CASH-TWD"
    }

    loan_asset = {
        "asset_id": "loan_1",
        "category": "liability",
        "quantity": 100000.0, # Initial principal
        "name": "My Loan",
        "symbol": "DEBT-TWD"
    }

    portfolio = [cash_asset, loan_asset]

    # Plan
    loan_plan = {
        "asset_id": "loan_1",
        "total_amount": 100000.0,
        "annual_rate": 12.0,
        "period_months": 12,
        "start_date": start_date,
        "payment_account_id": "cash_1",
        "repayment_method": "equal_principal_interest",
        "next_payment_number": 1
    }

    loan_plans = [loan_plan]

    # Process
    print(f"Processing... Start Date: {start_date}")
    count = process_loan_payments(portfolio, loan_plans)

    print(f"Processed {count} payments")
    assert count >= 2

    # Verify State
    # 2 payments of ~8885 = ~17770
    # Cash should be 50000 - 17770 = 32230
    print(f"Cash Quantity: {cash_asset['quantity']}")
    assert cash_asset['quantity'] < 40000

    # Loan Principal should be reduced
    # 1st princ ~ 7885, 2nd ~ 7964 -> total ~ 15849 reduced
    # Remaining ~ 84151
    print(f"Loan Remaining: {loan_asset['quantity']}")
    assert loan_asset['quantity'] < 90000

    # Plan next payment should be 3
    print(f"Next Payment Number: {loan_plan['next_payment_number']}")
    assert loan_plan['next_payment_number'] == count + 1

if __name__ == "__main__":
    test_amortization_equal_principal_interest()
    test_amortization_equal_principal()
    test_process_loan_payments()
    print("\nAll tests passed!")
