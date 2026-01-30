"""
Global styling module for the CyberFinancial Dashboard.
"""
import streamlit as st

def apply_tech_theme():
    """Inject custom CSS for the Cyber/Tech aesthetic."""
    st.markdown("""
    <style>
        /* Import a tech-looking font (optional, using system fonts for performance) */

        /* Global Background adjustment (gradual) */
        .stApp {
            background-color: #0F1116;
            background-image: radial-gradient(circle at 50% 0%, #1c2333 0%, #0F1116 70%);
        }

        /* --- Glassmorphism Cards --- */
        .tech-card {
            background: rgba(30, 33, 43, 0.7);
            border: 1px solid rgba(0, 180, 216, 0.2);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.08);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            transition: all 0.3s ease;
        }

        .tech-card:hover {
            border-color: rgba(0, 180, 216, 0.6);
            box-shadow: 0 0 15px rgba(0, 180, 216, 0.2);
            transform: translateY(-2px);
        }

        /* --- Neon Text Utilities --- */
        .neon-text-blue {
            color: #00B4D8;
            text-shadow: 0 0 5px rgba(0, 180, 216, 0.5);
        }

        .neon-text-pink {
            color: #FF0055;
            text-shadow: 0 0 5px rgba(255, 0, 85, 0.5);
        }

        .neon-text-purple {
            color: #BC13FE;
            text-shadow: 0 0 5px rgba(188, 19, 254, 0.5);
        }

        /* --- Metric Styling --- */
        /* Target the standard st.metric container to make it pop */
        div[data-testid="stMetric"] {
            background: rgba(30, 33, 43, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 8px;
            transition: border-color 0.3s;
        }
        div[data-testid="stMetric"]:hover {
            border-color: #00B4D8;
        }

        div[data-testid="stMetricLabel"] {
            color: #94A3B8 !important;
            font-size: 0.9rem !important;
        }

        div[data-testid="stMetricValue"] {
            color: #FAFAFA !important;
            font-family: 'SF Mono', 'Roboto Mono', monospace;
            font-weight: 700 !important;
        }

        /* --- DataFrame/Table Styling --- */
        div[data-testid="stDataFrame"] {
            background: rgba(30, 33, 43, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 5px;
        }

        /* Headers in tables */
        th {
            background-color: #1E212B !important;
            color: #00B4D8 !important;
            border-bottom: 1px solid #334155 !important;
        }

        /* --- Tabs --- */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: transparent;
        }

        .stTabs [data-baseweb="tab"] {
            height: 45px;
            background-color: rgba(30, 33, 43, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            color: #94A3B8;
            padding: 0 20px;
        }

        .stTabs [aria-selected="true"] {
            background-color: rgba(0, 180, 216, 0.1) !important;
            border: 1px solid #00B4D8 !important;
            color: #00B4D8 !important;
            box-shadow: 0 0 10px rgba(0, 180, 216, 0.2);
        }

        /* --- Sidebar --- */
        section[data-testid="stSidebar"] {
            background-color: #0B0D11;
            border-right: 1px solid #1E212B;
        }

        /* --- Buttons --- */
        button[kind="primary"] {
            background: linear-gradient(90deg, #00B4D8 0%, #0077B6 100%);
            border: none;
            color: white;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        button[kind="primary"]:hover {
            box-shadow: 0 0 15px rgba(0, 180, 216, 0.4);
            transform: scale(1.02);
        }

        button[kind="secondary"] {
            border: 1px solid rgba(255, 255, 255, 0.2);
            background: transparent;
            color: #E0E0E0;
        }
        button[kind="secondary"]:hover {
            border-color: #00B4D8;
            color: #00B4D8;
        }

    </style>
    """, unsafe_allow_html=True)

def card_container(key=None):
    """Returns a container styled as a card.
    Note: Streamlit containers can't accept classes directly easily.
    We use HTML/CSS wrapper for pure visuals, or st.container with border for standard.
    For this theme, we recommend using `st.markdown('<div class="tech-card">...</div>', ...)`
    for pure content, OR use st.container(border=True) and let global CSS style it.

    The global CSS `div[data-testid="stVerticalBlockBorderWrapper"] > div > div` selectors are flaky.
    Best to rely on standard elements styled globally.
    """
    return st.container(border=True)
