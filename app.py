# app.py
import streamlit as st
import pandas as pd
import difflib
from datetime import datetime
from io import StringIO

# Constants
ANNUAL_FEE = 120.0
HOURLY_RATE = 5.0
FUZZY_CUTOFF = 0.86

# Set page config
st.set_page_config(
    page_title="NTU Sports Reconciliation Tool",
    page_icon="🏸",
    layout="wide"
)

# App title and description
st.title("🏸 NTU Sports – Membership & Bookings Reconciliation Tool")
st.markdown("""
This tool automates the reconciliation process for NTU Sports membership payments and court bookings.
Upload your CSV files below to generate reconciliation reports.
""")

# Initialize session state for results
if 'results_generated' not in st.session_state:
    st.session_state.results_generated = False

def normalize_name(name):
    """Normalize names for consistent comparison"""
    if pd.isna(name):
        return ""
    return str(name).lower().strip().replace("  ", " ")

def process_data(members_file, payments_file, external_file):
    """Process uploaded data"""
    try:
        members_df = pd.read_csv(members_file)
        payments_df = pd.read_csv(payments_file)
        external_df = pd.read_csv(external_file)
        
        # Normalize names
        members_df['NormalizedName'] = members_df['FullName'].apply(normalize_name)
        payments_df['NormalizedName'] = payments_df['FullName'].apply(normalize_name)
        external_df['NormalizedName'] = external_df['FullName'].apply(normalize_name)
        
        return members_df, payments_df, external_df, None
    except Exception as e:
        return None, None, None, f"Error reading files: {str(e)}"

def reconcile_memberships(members_df, payments_df):
    """Reconcile membership payments with selected players"""
    # Get selected players
    selected_players = members_df[members_df['IsSelectedOfficialTeam'] == 'Yes'].copy()
    
    # Initialize result columns
    selected_players['PaidAmount'] = 0.0
    selected_players['PaidStatus'] = 'Unpaid'
    selected_players['Outstanding'] = ANNUAL_FEE
    selected_players['PaymentDate'] = None
    
    # Track matched payments
    matched_payment_indices = set()
    fuzzy_suggestions = []
    resolved_payments = []
    
    # First pass: match by StudentID
    for idx, payment in payments_df.iterrows():
        resolved_payment = payment.to_dict()
        resolved_payment['ResolvedStudentID'] = None
        resolved_payment['MatchType'] = 'Unmatched'
        
        if not pd.isna(payment.get('StudentID')):
            student_id = payment['StudentID']
            match = selected_players[selected_players['StudentID'] == student_id]
            if not match.empty:
                matched_idx = match.index[0]
                selected_players.at[matched_idx, 'PaidAmount'] += payment['Amount']
                selected_players.at[matched_idx, 'Outstanding'] = max(0, ANNUAL_FEE - selected_players.at[matched_idx, 'PaidAmount'])
                selected_players.at[matched_idx, 'PaymentDate'] = payment['PaymentDate']
                matched_payment_indices.add(idx)
                resolved_payment['ResolvedStudentID'] = selected_players.at[matched_idx, 'StudentID']
                resolved_payment['MatchType'] = 'StudentID'
        
        resolved_payments.append(resolved_payment)
    
    # Second pass: fuzzy match by name for unmatched payments
    all_selected_names = selected_players['NormalizedName'].tolist()
    
    for idx, payment in payments_df.iterrows():
        if idx in matched_payment_indices:
            continue
            
        normalized_payment_name = normalize_name(payment['FullName'])
        if not normalized_payment_name:
            continue
            
        # Fuzzy match
        matches = difflib.get_close_matches(
            normalized_payment_name, 
            all_selected_names, 
            n=1, 
            cutoff=FUZZY_CUTOFF
        )
        
        if matches:
            matched_name = matches[0]
            match = selected_players[selected_players['NormalizedName'] == matched_name]
            if not match.empty:
                matched_idx = match.index[0]
                selected_players.at[matched_idx, 'PaidAmount'] += payment['Amount']
                selected_players.at[matched_idx, 'Outstanding'] = max(0, ANNUAL_FEE - selected_players.at[matched_idx, 'PaidAmount'])
                selected_players.at[matched_idx, 'PaymentDate'] = payment['PaymentDate']
                matched_payment_indices.add(idx)
                
                # Update resolved payment
                for rp in resolved_payments:
                    if rp['NormalizedName'] == normalized_payment_name and rp['MatchType'] == 'Unmatched':
                        rp['ResolvedStudentID'] = selected_players.at[matched_idx, 'StudentID']
                        rp['MatchType'] = 'FuzzyName'
                
                # Add to suggestions
                if normalized_payment_name != matched_name:
                    fuzzy_suggestions.append({
                        'EnteredName': payment['FullName'],
                        'SuggestedName': selected_players.at[matched_idx, 'FullName']
                    })
    
    # Update payment status
    for idx, player in selected_players.iterrows():
        if player['PaidAmount'] >= ANNUAL_FEE:
            selected_players.at[idx, 'PaidStatus'] = 'Paid'
        elif player['PaidAmount'] > 0:
            selected_players.at[idx, 'PaidStatus'] = 'Underpaid'
        else:
            selected_players.at[idx, 'PaidStatus'] = 'Unpaid'
    
    # Find payments from non-selected players
    all_member_ids = set(members_df['StudentID'])
    paid_not_selected = []
    
    for idx, payment in payments_df.iterrows():
        if idx in matched_payment_indices:
            continue
            
        # Check if this payment is from any member (selected or not)
        payment_matched = False
        if not pd.isna(payment.get('StudentID')):
            if payment['StudentID'] in all_member_ids:
                payment_matched = True
        
        if not payment_matched and not pd.isna(payment.get('FullName')):
            payment_name = normalize_name(payment['FullName'])
            if payment_name in members_df['NormalizedName'].values:
                payment_matched = True
        
        if not payment_matched:
            paid_not_selected.append(payment.to_dict())
    
    # Find completely unmatched payments
    unmatched_payments = []
    for rp in resolved_payments:
        if rp['MatchType'] == 'Unmatched':
            unmatched_payments.append(rp)
    
    return selected_players, fuzzy_suggestions, paid_not_selected, unmatched_payments, resolved_payments

def validate_external_bookings(external_df):
    """Validate external bookings against hourly rate"""
    external_df = external_df.copy()
    external_df['Expected'] = external_df['Hours'] * HOURLY_RATE
    external_df['Underpaid'] = external_df['AmountPaid'] < external_df['Expected'] - 0.01
    external_df['MissingPayment'] = external_df['AmountPaid'] <= 0
    
    # Identify problematic bookings
    external_issues = external_df[
        (external_df['Underpaid']) | 
        (external_df['MissingPayment'])
    ].copy()
    
    return external_df, external_issues

def generate_summary(selected_players, paid_not_selected, unmatched_payments, external_df, external_issues):
    """Generate summary statistics"""
    total_selected = len(selected_players)
    paid_count = len(selected_players[selected_players['PaidStatus'] == 'Paid'])
    underpaid_count = len(selected_players[selected_players['PaidStatus'] == 'Underpaid'])
    unpaid_count = len(selected_players[selected_players['PaidStatus'] == 'Unpaid'])
    
    mismatch_rate = (underpaid_count + unpaid_count) / total_selected * 100 if total_selected > 0 else 0
    
    membership_expected = total_selected * ANNUAL_FEE
    membership_collected = selected_players['PaidAmount'].sum()
    
    external_expected = external_df['Expected'].sum()
    external_collected = external_df['AmountPaid'].sum()
    external_issues_count = len(external_issues)
    
    non_selected_payments_count = len(paid_not_selected)
    unmatched_payments_count = len(unmatched_payments)
    
    summary = f"""NTU Sports - Membership & Bookings Reconciliation
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

MEMBERSHIP SUMMARY:
Total selected members: {total_selected}
- Paid in full: {paid_count}
- Underpaid: {underpaid_count}
- Unpaid: {unpaid_count}
Mismatch rate: {mismatch_rate:.1f}%

Membership revenue:
- Expected: £{membership_expected:,.2f}
- Collected: £{membership_collected:,.2f}
- Difference: £{membership_collected - membership_expected:,.2f}

EXTERNAL BOOKINGS:
Total bookings: {len(external_df)}
- Expected: £{external_expected:,.2f}
- Collected: £{external_collected:,.2f}
- Difference: £{external_collected - external_expected:,.2f}
- Bookings with issues: {external_issues_count}

ADDITIONAL FINDINGS:
- Payments from non-selected players: {non_selected_payments_count}
- Unmatched payments (need review): {unmatched_payments_count}
"""
    return summary

# File upload section
st.header("📤 Step 1: Upload Your CSV Files")

col1, col2, col3 = st.columns(3)
with col1:
    members_file = st.file_uploader("Members CSV", type=['csv'], help="Should contain: StudentID, FullName, Team, IsSelectedOfficialTeam")
with col2:
    payments_file = st.file_uploader("Membership Payments CSV", type=['csv'], help="Should contain: StudentID, FullName, Amount, PaymentDate")
with col3:
    external_file = st.file_uploader("External Bookings CSV", type=['csv'], help="Should contain: BookingID, FullName, BookingStart, Hours, AmountPaid")

# Process button
if st.button("🚀 Run Reconciliation", type="primary", use_container_width=True):
    if members_file and payments_file and external_file:
        with st.spinner("Processing data..."):
            # Process uploaded files
            members_df, payments_df, external_df, error = process_data(members_file, payments_file, external_file)
            
            if error:
                st.error(error)
            else:
                # Run reconciliation
                selected_players, fuzzy_suggestions, paid_not_selected, unmatched_payments, resolved_payments = reconcile_memberships(
                    members_df, payments_df)
                external_df, external_issues = validate_external_bookings(external_df)
                
                # Generate summary
                summary = generate_summary(
                    selected_players, paid_not_selected, unmatched_payments, external_df, external_issues)
                
                # Store results in session state
                st.session_state.selected_players = selected_players
                st.session_state.fuzzy_suggestions = fuzzy_suggestions
                st.session_state.paid_not_selected = paid_not_selected
                st.session_state.unmatched_payments = unmatched_payments
                st.session_state.resolved_payments = resolved_payments
                st.session_state.external_df = external_df
                st.session_state.external_issues = external_issues
                st.session_state.summary = summary
                st.session_state.results_generated = True
                
                st.success("✅ Reconciliation complete!")
    else:
        st.warning("Please upload all three CSV files to proceed.")

# Display results if available
if st.session_state.results_generated:
    st.header("📊 Results Summary")
    
    # Display summary
    st.text_area("Reconciliation Summary", st.session_state.summary, height=300)
    
    # Download section
    st.header("📥 Download Reports")
    
    # Convert DataFrames to CSV for download
    @st.cache_data
    def convert_df_to_csv(df):
        return df.to_csv(index=False).encode('utf-8')
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="Download Selected Members Status",
            data=convert_df_to_csv(st.session_state.selected_players[['StudentID', 'FullName', 'Team', 'PaidAmount', 'PaidStatus', 'Outstanding', 'PaymentDate']]),
            file_name="ntu_membership_selected_status.csv",
            mime="text/csv",
        )
        
        st.download_button(
            label="Download Paid But Not Selected",
            data=convert_df_to_csv(pd.DataFrame(st.session_state.paid_not_selected)),
            file_name="ntu_membership_paid_not_selected.csv",
            mime="text/csv",
        )
        
        st.download_button(
            label="Download Unmatched Payments",
            data=convert_df_to_csv(pd.DataFrame(st.session_state.unmatched_payments)),
            file_name="ntu_membership_unmatched_payments.csv",
            mime="text/csv",
        )
    
    with col2:
        st.download_button(
            label="Download External Bookings Report",
            data=convert_df_to_csv(st.session_state.external_df),
            file_name="ntu_membership_external_all.csv",
            mime="text/csv",
        )
        
        st.download_button(
            label="Download External Issues",
            data=convert_df_to_csv(st.session_state.external_issues),
            file_name="ntu_membership_external_issues.csv",
            mime="text/csv",
        )
        
        st.download_button(
            label="Download Fuzzy Match Suggestions",
            data=convert_df_to_csv(pd.DataFrame(st.session_state.fuzzy_suggestions)),
            file_name="ntu_membership_fuzzy_suggestions.csv",
            mime="text/csv",
        )
    
    # Data preview sections
    st.header("🔍 Data Previews")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Selected Members", "Payment Issues", "External Issues", "Fuzzy Matches"])
    
    with tab1:
        st.dataframe(st.session_state.selected_players[['StudentID', 'FullName', 'Team', 'PaidAmount', 'PaidStatus', 'Outstanding']])
    
    with tab2:
        st.dataframe(pd.DataFrame(st.session_state.unmatched_payments))
    
    with tab3:
        st.dataframe(st.session_state.external_issues)
    
    with tab4:
        st.dataframe(pd.DataFrame(st.session_state.fuzzy_suggestions))

# Sample data section
with st.expander("🧪 Don't have data? Use our sample files"):
    st.markdown("""
    Download these sample files to test the tool:
    - [Sample Members CSV](https://github.com/your-username/NTU-Membership-Checker/raw/main/members.csv)
    - [Sample Payments CSV](https://github.com/your-username/NTU-Membership-Checker/raw/main/membership_payments.csv)
    - [Sample External Bookings CSV](https://github.com/your-username/NTU-Membership-Checker/raw/main/external_bookings.csv)
    """)

# Footer
st.markdown("---")
st.markdown("*Built for NTU Sports Finance Team • Automating reconciliation since 2023*")
