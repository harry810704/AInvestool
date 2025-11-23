# 個人投資戰情室 Pro (Cloud)

A cloud-based investment portfolio management dashboard built with Streamlit and Google Drive integration.

## Features

- **Google Drive Integration**: Securely store and sync your portfolio data
- **Real-time Market Data**: Automatic price updates from Yahoo Finance
- **Portfolio Management**: Track multiple asset types (stocks, crypto, precious metals)
- **Asset Allocation**: Set and monitor target allocations with rebalancing suggestions
- **Investment Planning**: Smart fund deployment calculator
- **Secure Authentication**: AES-encrypted token storage

## Prerequisites

- Python 3.9 or higher
- Google Cloud Project with Drive API enabled
- Streamlit Cloud account (for deployment) or local environment

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd mydashboard
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Google OAuth

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Google Drive API
3. Create OAuth 2.0 credentials (Web application)
4. Add authorized redirect URIs

### 4. Set Up Secrets

Create a `.streamlit/secrets.toml` file:

```toml
[google]
client_id = "your-client-id.apps.googleusercontent.com"
client_secret = "your-client-secret"
redirect_uri = "http://localhost:8501"  # or your deployed URL

[security]
encryption_key = "your-fernet-key-here"  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Usage

### Running Locally

```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`.

### First Time Setup

1. Click "使用 Google 帳號登入" to authenticate
2. Grant permissions to access Google Drive
3. Your portfolio data will be stored in a folder called "AInvestool" in your Drive

## Project Structure

```
mydashboard/
├── app.py                      # Main application entry point
├── config.py                   # Centralized configuration
├── models.py                   # Pydantic data models
├── requirements.txt            # Python dependencies
├── modules/
│   ├── data_loader.py         # Portfolio data management
│   ├── drive_manager.py       # Google Drive integration
│   ├── security.py            # Encryption utilities
│   ├── market_service.py      # Market data fetching
│   ├── ui_dashboard.py        # Dashboard UI components
│   ├── ui_manager.py          # Management UI components
│   ├── state_manager.py       # Session state management
│   ├── logger.py              # Logging configuration
│   └── exceptions.py          # Custom exceptions
└── .streamlit/
    └── secrets.toml           # Secret configuration (not in repo)
```

## Configuration

The application uses a centralized configuration system in `config.py`. Key settings include:

- **Google Drive**: Folder name, file names, scopes
- **Market Data**: Cache TTL, retry settings, concurrent updates
- **Security**: Cookie settings, encryption
- **UI**: Asset types, currencies, colors, thresholds

## Data Models

The application uses Pydantic models for type-safe data handling:

- **Asset**: Individual portfolio holdings
- **MarketData**: Real-time market information
- **AllocationSettings**: Target allocation percentages
- **DeploymentAction**: Planned investment actions

## Features in Detail

### Portfolio Management

- Add, edit, and remove assets
- Track multiple asset types and currencies
- Automatic currency conversion (USD ↔ TWD)
- Manual price override for assets without live data

### Market Data

- Automatic daily price updates
- Parallel fetching for improved performance
- Yahoo Finance integration
- Fallback to manual prices

### Asset Allocation

- Set target allocation percentages by asset type
- Visual comparison of current vs. target allocation
- Rebalancing recommendations
- Allocation validation (must sum to 100%)

### Investment Planning

- Calculate optimal fund deployment
- Manual adjustment of suggested allocations
- Transaction planning and execution
- Visual preview of portfolio changes

## Development

### Code Quality

The codebase follows best practices:

- **Type Hints**: Full type annotations throughout
- **Logging**: Structured logging with colored console output
- **Error Handling**: Custom exceptions with detailed messages
- **Validation**: Pydantic models for data validation
- **Documentation**: Comprehensive docstrings

### Adding New Features

1. Define data models in `models.py` if needed
2. Add configuration in `config.py`
3. Implement business logic in appropriate module
4. Add UI components in `ui_dashboard.py` or `ui_manager.py`
5. Update documentation

## Troubleshooting

### Authentication Issues

- Verify Google OAuth credentials are correct
- Check redirect URI matches your deployment URL
- Ensure Drive API is enabled in Google Cloud Console

### Data Not Syncing

- Check internet connection
- Verify Google Drive permissions
- Check logs for error messages

### Price Updates Failing

- Some tickers may not be available on Yahoo Finance
- Use manual price override for unsupported assets
- Check ticker symbol format (e.g., ".TW" for Taiwan stocks)

## Security

- Tokens are encrypted using Fernet (AES-128)
- Credentials stored in browser cookies (30-day expiry)
- No sensitive data in source code
- All secrets managed via Streamlit secrets

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions, please open an issue on GitHub.

## Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Market data from [Yahoo Finance](https://finance.yahoo.com/)
- Icons and UI components from Streamlit and Plotly
