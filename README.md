# TCGplayer Card Price Search

A simple web app to search for trading cards by name and filter by price. Uses [TCGplayer](https://www.tcgplayer.com/) as the data source.

## Features

- **Search by name** – Find cards by name or set
- **Price filters** – Set min/max price to narrow results
- **Sort options** – Sort by price (low/high) or name
- **TCGplayer links** – One-click to view cards on TCGplayer.com

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the app:
   ```
   python app.py
   ```

3. Open http://127.0.0.1:5000 in your browser.

## Live Search

This app uses the free [YGOPRODeck API](https://ygoprodeck.com/api-guide/) to search **any** Yu-Gi-Oh! card by name. Prices come from TCGplayer.

- **With a search term**: Live results from YGOPRODeck (10,000+ cards)
- **Without a search term**: Sample cards are shown
- **Price filters** work on all results

## How to Use

1. Enter a card name (e.g., "Charizard", "Pikachu")
2. Optionally set min/max price
3. Choose sort order
4. Click Search

Results show market price and price range. Click any card to open it on TCGplayer.
