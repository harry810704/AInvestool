"""
診斷工具：檢查 portfolio.xlsx 中的 account_id 問題

使用方法：
1. 從 Google Drive 下載 portfolio.xlsx
2. 將文件放在項目根目錄
3. 運行此腳本：python diagnose_excel.py
"""

import pandas as pd
import os
import sys

def diagnose_portfolio_excel():
    """診斷 portfolio.xlsx 中的帳戶ID問題"""
    
    filename = "portfolio.xlsx"
    
    if not os.path.exists(filename):
        print(f"❌ 找不到 {filename}")
        print(f"請將從 Google Drive 下載的文件放在: {os.getcwd()}")
        return
    
    print("=" * 70)
    print(f"📊 診斷文件: {filename}")
    print("=" * 70)
    print()
    
    try:
        # 讀取所有 sheets
        xl_file = pd.ExcelFile(filename)
        print(f"✅ 成功讀取 Excel 文件")
        print(f"📋 Sheets: {xl_file.sheet_names}")
        print()
        
        # 檢查 Assets sheet
        if 'Assets' not in xl_file.sheet_names:
            print("❌ 找不到 Assets sheet")
            return
        
        df_assets = pd.read_excel(filename, sheet_name='Assets')
        print("-" * 70)
        print("📦 Assets Sheet 分析")
        print("-" * 70)
        print(f"資產數量: {len(df_assets)}")
        print(f"欄位數量: {len(df_assets.columns)}")
        print()
        
        # 檢查欄位
        print("📝 所有欄位:")
        for i, col in enumerate(df_assets.columns, 1):
            print(f"  {i:2d}. {col}")
        print()
        
        # 重點檢查 account_id 相關欄位
        print("-" * 70)
        print("🔍 帳戶ID 欄位檢查")
        print("-" * 70)
        
        account_fields = ['account_id', 'Account_ID', 'AccountID', 'accountid']
        found_fields = []
        
        for field in account_fields:
            if field in df_assets.columns:
                found_fields.append(field)
                print(f"✅ 找到欄位: {field}")
                
                # 顯示值的統計
                unique_values = df_assets[field].dropna().unique()
                print(f"   - 唯一值數量: {len(unique_values)}")
                print(f"   - 唯一值: {list(unique_values)}")
                print(f"   - 空值數量: {df_assets[field].isna().sum()}")
                print()
        
        if not found_fields:
            print("❌ 沒有找到任何帳戶ID欄位！")
            print()
        
        # 顯示前幾行數據
        print("-" * 70)
        print("📊 前5行數據預覽")
        print("-" * 70)
        
        # 選擇要顯示的欄位
        display_cols = []
        for col in ['symbol', 'asset_type', 'asset_class', 'Type', 'quantity', 'account_id', 'Account_ID']:
            if col in df_assets.columns:
                display_cols.append(col)
        
        if display_cols:
            print(df_assets[display_cols].head(5).to_string(index=False))
        else:
            print(df_assets.head(5).to_string(index=False))
        print()
        
        # 檢查 Accounts sheet
        print("-" * 70)
        print("🏦 Accounts Sheet 分析")
        print("-" * 70)
        
        if 'Accounts' in xl_file.sheet_names:
            df_accounts = pd.read_excel(filename, sheet_name='Accounts')
            print(f"帳戶數量: {len(df_accounts)}")
            print()
            
            print("帳戶列表:")
            account_id_col = 'account_id' if 'account_id' in df_accounts.columns else 'id'
            name_col = 'name' if 'name' in df_accounts.columns else df_accounts.columns[1]
            
            for idx, row in df_accounts.iterrows():
                acc_id = row.get(account_id_col, 'N/A')
                acc_name = row.get(name_col, 'N/A')
                print(f"  - {acc_name}: {acc_id}")
            print()
        else:
            print("❌ 找不到 Accounts sheet")
            print()
        
        # 診斷結果總結
        print("=" * 70)
        print("🎯 診斷結果總結")
        print("=" * 70)
        
        issues = []
        
        # 檢查 1: account_id 欄位是否存在
        if 'account_id' in df_assets.columns:
            print("✅ account_id 欄位存在")
        else:
            print("❌ account_id 欄位不存在（這是問題！）")
            issues.append("缺少 account_id 欄位")
        
        # 檢查 2: 是否有舊欄位
        if 'Account_ID' in df_assets.columns:
            print("⚠️  發現舊欄位 Account_ID（大寫）")
            if 'account_id' not in df_assets.columns:
                issues.append("只有舊欄位 Account_ID，缺少新欄位 account_id")
        
        # 檢查 3: 欄位值是否為空
        if 'account_id' in df_assets.columns:
            empty_count = df_assets['account_id'].isna().sum()
            if empty_count > 0:
                print(f"⚠️  有 {empty_count} 個資產的 account_id 為空")
                issues.append(f"{empty_count} 個資產缺少帳戶ID")
        
        print()
        
        if issues:
            print("🔧 建議修復措施:")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
        else:
            print("✅ 未發現明顯問題")
        
        print()
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose_portfolio_excel()
