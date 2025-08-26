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
    # [The entire reconcile_memberships function from your original code goes here]
    # Copy the EXACT function from your original membership_checker.py

def validate_external_bookings(external_df):
    """Validate external bookings against hourly rate"""
    # [The entire validate_external_bookings function from your original code goes here]
    # Copy the EXACT function from your original membership_checker.py

def generate_summary(selected_players, paid_not_selected, unmatched_payments, external_df, external_issues):
    """Generate summary statistics"""
    # [The entire generate_summary function from your original code goes here]
    # Copy the EXACT function from your original membership_checker.py

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
                selected_players, fuzzy_suggestions, paid_not_selected, unmatched_payments, resolved_payments = reconcile_memberships(members_df, payments_df)
                external_df, external_issues = validate_external_bookings(external_df)
                
                # Generate summary
                summary = generate_summary(selected_players, paid_not_selected, unmatched_payments, external_df, external_issues)
                
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
    - [Sample Members CSV](path/to/sample_members.csv)
    - [Sample Payments CSV](path/to/sample_payments.csv)
    - [Sample External Bookings CSV](path/to/sample_external.csv)
    """)

# Footer
st.markdown("---")
st.markdown("*Built for NTU Sports Finance Team • Automating reconciliation since 2023*")