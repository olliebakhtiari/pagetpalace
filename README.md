# pagetpalace
A modular algorithmic trading framework built in Python, designed specifically for executing live trading strategies with the Oanda V20 API. It provides an end-to-end solution encompassing everything from data retrieval and technical analysis to advanced risk management, precise order placement, and environment monitoring.

## Features
pagetpalace is designed for high-precision, multi-security trading and includes:

### Trading Engine & Strategies
- Strategy Engine: A modular system allowing for rapid development and plug-in of new trading strategies (e.g., ssl_multi, hpdaily, heikin_ashi_ewm).

- Multi-Security Support: Handles trading across various asset classes, including FX Pairs, Commodities, Indices, and Bonds, with instrument-specific attributes.

- Advanced Indicators: Dedicated modules for technical analysis, signal generation, and validating trading sessions.

### Risk & Order Management
- Precise Order Placement: Manages order creation, including the integration of stop-loss (SL) and take-profit (TP) orders as dependent orders.

- Dynamic Risk Management: Includes a dedicated risk_manager for calculating position size, leverage requirements, and ensuring trades adhere to defined risk parameters.

- Currency Conversion: Automated utility (unit_conversions) for accurately calculating trade units and risk across different base currencies.

- Data & Monitoring
Oanda API Integration: Core classes for managing Oanda accounts, retrieving instrument specifications, and fetching historical candlestick data.

- Live Trade Monitor: The live_trade_monitor.py component continuously tracks open trades and adjusts or closes positions based on real-time market data or strategy conditions.

- Remote Configuration: Ability to securely retrieve configuration settings from S3 using aws_utils.

- Event Notifications: Helper tools (email_sender) to dispatch email notifications for noteworthy events, such as successful order placements or errors.