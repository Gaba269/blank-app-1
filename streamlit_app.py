import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import plotly.express as px 
import plotly.graph_objects as go
import requests
import json
import time
from typing import List, Dict, Optional, Tuple
from sklearn.linear_model import LinearRegression
import re
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(
    page_title="Portfolio Analyzer Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé amélioré
custom_css = """
<style>
[data-testid="stAppViewContainer"] {
    background-color: #FFFFFF;
}
[data-testid="stSidebar"] {
    background-color: #f0f4ff;
}
.metric-card {
    background-color: #f8f9ff;
    padding: 1rem;
    border-radius: 10px;
    border-left: 4px solid #4f46e5;
    margin: 0.5rem 0;
}
.warning-card {
    background-color: #fef3f2;
    padding: 1rem;
    border-radius: 10px;
    border-left: 4px solid #ef4444;
    margin: 0.5rem 0;
}
.success-card {
    background-color: #f0fdf4;
    padding: 1rem;
    border-radius: 10px;
    border-left: 4px solid #22c55e;
    margin: 0.5rem 0;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

class TickerService:
    """Service amélioré pour la recherche et validation des tickers"""
    
    @staticmethod
    def search_tickers(query: str, limit: int = 10) -> List[Dict]:
        """Recherche avancée de tickers avec multiple sources"""
        results = []
        
        # Source 1: Yahoo Finance Search API
        try:
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&quotesCount={limit}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                quotes = data.get("quotes", [])
                
                for quote in quotes:
                    if quote.get('symbol') and quote.get('shortname'):
                        results.append({
                            'symbol': quote['symbol'],
                            'name': quote['shortname'],
                            'type': quote.get('typeDisp', 'Stock'),
                            'exchange': quote.get('exchange', 'Unknown'),
                            'source': 'Yahoo'
                        })
        except Exception as e:
            st.warning(f"Erreur lors de la recherche Yahoo: {e}")
        
        # Source 2: Recherche par pattern (pour les tickers connus)
        pattern_results = TickerService._pattern_search(query)
        results.extend(pattern_results)
        
        # Déduplication et tri
        seen = set()
        unique_results = []
        for item in results:
            if item['symbol'] not in seen:
                seen.add(item['symbol'])
                unique_results.append(item)
        
        return unique_results[:limit]
    
    @staticmethod
    def _pattern_search(query: str) -> List[Dict]:
        """Recherche par patterns pour les tickers populaires"""
        common_tickers = {
            # Tech US
            'APPLE': 'AAPL', 'MICROSOFT': 'MSFT', 'GOOGLE': 'GOOGL', 'AMAZON': 'AMZN',
            'TESLA': 'TSLA', 'META': 'META', 'NVIDIA': 'NVDA', 'NETFLIX': 'NFLX',
            
            # Actions françaises
            'LVMH': 'MC.PA', 'TOTALENERGIES': 'TTE.PA', 'SANOFI': 'SAN.PA',
            'LOREAL': 'OR.PA', 'ASML': 'ASML.AS', 'NESTLE': 'NESN.SW',
            
            # Cryptos principales
            'BITCOIN': 'BTC-USD', 'ETHEREUM': 'ETH-USD', 'BINANCE': 'BNB-USD'
        }
        
        query_upper = query.upper()
        results = []
        
        for name, symbol in common_tickers.items():
            if query_upper in name or query_upper in symbol:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    results.append({
                        'symbol': symbol,
                        'name': info.get('shortName', name),
                        'type': 'Stock',
                        'exchange': info.get('exchange', 'Unknown'),
                        'source': 'Pattern'
                    })
                except:
                    continue
        
        return results
    
    @staticmethod
    def validate_ticker(symbol: str) -> Dict:
        """Validation complète d'un ticker avec données financières"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Vérification des données essentielles
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not current_price:
                # Tentative via historical data
                hist = ticker.history(period="5d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            
            if not current_price:
                return {'valid': False, 'error': 'Prix indisponible'}
            
            return {
                'valid': True,
                'symbol': symbol,
                'name': info.get('shortName', symbol),
                'price': float(current_price),
                'currency': info.get('currency', 'USD'),
                'exchange': info.get('exchange', 'Unknown'),
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
                'market_cap': info.get('marketCap'),
                'isin': info.get('isin', 'Unknown'),
                'type': TickerService._classify_asset_type(info)
            }
            
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    @staticmethod
    def _classify_asset_type(info: Dict) -> str:
        """Classification automatique du type d'actif"""
        symbol = info.get('symbol', '')
        sector = info.get('sector', '').lower()
        industry = info.get('industry', '').lower()
        name = info.get('shortName', '').lower()
        
        # Crypto
        if any(x in symbol for x in ['-USD', '-EUR']) or 'crypto' in name:
            return 'Cryptocurrency'
        
        # ETF
        if any(x in name for x in ['etf', 'fund', 'index']):
            return 'ETF'
        
        # REIT
        if 'real estate' in sector or 'reit' in name:
            return 'REIT'
        
        # Par secteur
        sector_mapping = {
            'technology': 'Tech Stock',
            'healthcare': 'Healthcare Stock',
            'financial': 'Financial Stock',
            'energy': 'Energy Stock',
            'consumer': 'Consumer Stock',
            'industrial': 'Industrial Stock',
            'utilities': 'Utility Stock',
            'materials': 'Materials Stock',
            'telecommunication': 'Telecom Stock'
        }
        
        for key, value in sector_mapping.items():
            if key in sector:
                return value
        
        return 'Stock'

class DiversificationAnalyzer:
    """Analyseur de diversification avancé"""
    
    @staticmethod
    def calculate_concentration_metrics(df: pd.DataFrame) -> Dict:
        """Calcule les métriques de concentration"""
        weights = df['weight'].values
        
        # Indice Herfindahl-Hirschman
        hhi = np.sum(weights ** 2)
        
        # Nombre effectif d'actions
        effective_stocks = 1 / hhi if hhi > 0 else 0
        
        # Top 3 concentration
        top3_weight = weights[np.argsort(weights)[-3:]].sum()
        
        # Entropy (diversification Shannon)
        entropy = -np.sum(weights * np.log(weights + 1e-10))
        max_entropy = -np.log(1/len(weights))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        
        return {
            'hhi': hhi,
            'effective_stocks': effective_stocks,
            'top3_concentration': top3_weight,
            'entropy_ratio': normalized_entropy,
            'concentration_level': DiversificationAnalyzer._get_concentration_level(hhi)
        }
    
    @staticmethod
    def _get_concentration_level(hhi: float) -> str:
        """Détermine le niveau de concentration"""
        if hhi > 0.25:
            return "Très Concentré"
        elif hhi > 0.15:
            return "Concentré"
        elif hhi > 0.10:
            return "Modérément Concentré"
        else:
            return "Bien Diversifié"
    
    @staticmethod
    def analyze_sector_diversification(df: pd.DataFrame) -> pd.DataFrame:
        """Analyse la diversification sectorielle"""
        if 'sector' not in df.columns:
            return pd.DataFrame()
        
        sector_analysis = df.groupby('sector').agg({
            'weight': 'sum',
            'amount': 'sum',
            'perf': 'mean',
            'name': 'count'
        }).round(4)
        
        sector_analysis.columns = ['Weight', 'Amount', 'Avg_Performance', 'Count']
        sector_analysis['Weight_Pct'] = sector_analysis['Weight'] * 100
        
        return sector_analysis.sort_values('Weight', ascending=False)
    
    @staticmethod
    def analyze_geographic_diversification(df: pd.DataFrame) -> pd.DataFrame:
        """Analyse la diversification géographique"""
        if 'exchange' not in df.columns:
            return pd.DataFrame()
        
        # Mapping exchange -> région
        exchange_to_region = {
            'NYSE': 'USA', 'NASDAQ': 'USA', 'NYSEArca': 'USA',
            'Paris': 'Europe', 'London': 'Europe', 'Frankfurt': 'Europe',
            'Milan': 'Europe', 'Amsterdam': 'Europe', 'Swiss': 'Europe',
            'Tokyo': 'Asia', 'Hong Kong': 'Asia', 'Shanghai': 'Asia',
            'Toronto': 'North America', 'TSX': 'North America'
        }
        
        df['region'] = df['exchange'].map(
            lambda x: next((region for exch, region in exchange_to_region.items() 
                          if exch.lower() in str(x).lower()), 'Other')
        )
        
        geo_analysis = df.groupby('region').agg({
            'weight': 'sum',
            'amount': 'sum',
            'perf': 'mean',
            'name': 'count'
        }).round(4)
        
        geo_analysis.columns = ['Weight', 'Amount', 'Avg_Performance', 'Count']
        geo_analysis['Weight_Pct'] = geo_analysis['Weight'] * 100
        
        return geo_analysis.sort_values('Weight', ascending=False)

class PortfolioManager:
    """Gestionnaire principal du portefeuille"""
    
    def __init__(self):
        if 'portfolio_df' not in st.session_state:
            st.session_state.portfolio_df = pd.DataFrame()
        if 'original_df' not in st.session_state:
            st.session_state.original_df = pd.DataFrame()
    
    def add_stock_to_portfolio(self, ticker_data: Dict, quantity: int):
        """Ajoute une action au portefeuille"""
        new_row = {
            'name': ticker_data['name'],
            'symbol': ticker_data['symbol'],
            'isin': ticker_data.get('isin', 'Unknown'),
            'quantity': quantity,
            'buyingPrice': ticker_data['price'],
            'lastPrice': ticker_data['price'],
            'currency': ticker_data.get('currency', 'USD'),
            'exchange': ticker_data.get('exchange', 'Unknown'),
            'sector': ticker_data.get('sector', 'Unknown'),
            'industry': ticker_data.get('industry', 'Unknown'),
            'asset_type': ticker_data.get('type', 'Stock'),
            'intradayVariation': 0.0,
            'amount': quantity * ticker_data['price'],
            'amountVariation': 0.0,
            'variation': 0.0,
            'Tickers': ticker_data['symbol']  # Pour compatibilité
        }
        
        # Ajout au DataFrame
        if st.session_state.portfolio_df.empty:
            st.session_state.portfolio_df = pd.DataFrame([new_row])
        else:
            st.session_state.portfolio_df = pd.concat([
                st.session_state.portfolio_df, 
                pd.DataFrame([new_row])
            ], ignore_index=True)
        
        return True
    
    def update_portfolio_metrics(self):
        """Met à jour toutes les métriques du portefeuille"""
        if st.session_state.portfolio_df.empty:
            return
        
        df = st.session_state.portfolio_df
        
        # Calculs de base
        total_value = df['amount'].sum()
        df['weight'] = df['amount'] / total_value
        df['perf'] = (df['lastPrice'] - df['buyingPrice']) / df['buyingPrice'] * 100
        df['weight_pct'] = df['weight'] * 100
        
        # Performance pondérée
        portfolio_perf = (df['weight'] * df['perf']).sum()
        
        st.session_state.portfolio_df = df
        
        return {
            'total_value': total_value,
            'portfolio_performance': portfolio_perf
        }

def main():
    """Fonction principale de l'application"""
    
    # Initialisation du gestionnaire de portefeuille
    portfolio_manager = PortfolioManager()
    
    # Header
    st.title("📊 Analyseur de Portefeuille Professionnel")
    st.markdown("*Analyse complète avec diversification, concentration et métriques avancées*")
    
    # Sidebar pour les actions
    with st.sidebar:
        st.header("🔧 Actions")
        
        # Upload de fichier
        uploaded_file = st.file_uploader("📤 Importer un portefeuille CSV", type=["csv"])
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.session_state.original_df = df.copy()
                
                # Amélioration automatique du DataFrame
                df = enhance_dataframe(df)
                st.session_state.portfolio_df = df
                
                st.success(f"✅ Portfolio chargé: {len(df)} positions")
            except Exception as e:
                st.error(f"Erreur lors du chargement: {e}")
        
        # Ajout manuel d'actions
        st.subheader("➕ Ajouter une action")
        
        search_query = st.text_input("🔍 Rechercher (nom ou ticker)", 
                                   placeholder="ex: Apple, AAPL, LVMH...")
        
        if search_query and len(search_query) >= 2:
            with st.spinner("Recherche en cours..."):
                search_results = TickerService.search_tickers(search_query)
            
            if search_results:
                options = [f"{r['symbol']} - {r['name']} ({r['exchange']})" 
                          for r in search_results]
                
                selected_option = st.selectbox("Sélectionner une action:", options)
                
                if selected_option:
                    selected_symbol = selected_option.split(" - ")[0]
                    
                    # Validation du ticker
                    with st.spinner("Validation..."):
                        ticker_data = TickerService.validate_ticker(selected_symbol)
                    
                    if ticker_data['valid']:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Prix actuel", f"{ticker_data['price']:.2f} {ticker_data['currency']}")
                        with col2:
                            st.metric("Secteur", ticker_data['sector'])
                        
                        quantity = st.number_input("Quantité", min_value=1, value=1, step=1)
                        total_cost = quantity * ticker_data['price']
                        st.info(f"💰 Coût total: {total_cost:.2f} {ticker_data['currency']}")
                        
                        if st.button("➕ Ajouter au portefeuille", type="primary"):
                            if portfolio_manager.add_stock_to_portfolio(ticker_data, quantity):
                                st.success(f"✅ {ticker_data['name']} ajouté!")
                                st.rerun()
                    else:
                        st.error(f"❌ Erreur: {ticker_data['error']}")
            else:
                st.warning("Aucun résultat trouvé")
    
    # Contenu principal
    if not st.session_state.portfolio_df.empty:
        df = st.session_state.portfolio_df
        
        # Mise à jour des métriques
        metrics = portfolio_manager.update_portfolio_metrics()
        
        # Overview du portefeuille
        st.header("📈 Vue d'ensemble du portefeuille")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Valeur totale", f"{metrics['total_value']:,.2f} €")
        with col2:
            st.metric("Performance", f"{metrics['portfolio_performance']:.2f}%")
        with col3:
            st.metric("Nombre de positions", len(df))
        with col4:
            avg_position = metrics['total_value'] / len(df)
            st.metric("Position moyenne", f"{avg_position:,.2f} €")
        
        # DataFrame détaillé
        st.subheader("📋 Détail des positions")
        display_df = df[['name', 'symbol', 'quantity', 'buyingPrice', 'lastPrice', 
                        'amount', 'weight_pct', 'perf', 'sector', 'asset_type']].copy()
        display_df.columns = ['Nom', 'Ticker', 'Qté', 'Prix Achat', 'Prix Actuel', 
                             'Montant', 'Poids (%)', 'Perf (%)', 'Secteur', 'Type']
        
        st.dataframe(
            display_df.style.format({
                'Prix Achat': '{:.2f}',
                'Prix Actuel': '{:.2f}',
                'Montant': '{:,.2f}',
                'Poids (%)': '{:.1f}',
                'Perf (%)': '{:.2f}'
            }),
            use_container_width=True
        )
        
        # Analyses avancées
        st.header("🔍 Analyses avancées")
        
        # Concentration
        st.subheader("📊 Analyse de concentration")
        concentration_metrics = DiversificationAnalyzer.calculate_concentration_metrics(df)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Indice HHI", f"{concentration_metrics['hhi']:.3f}")
            st.caption("< 0.10: Bien diversifié | > 0.25: Très concentré")
        with col2:
            st.metric("Actions effectives", f"{concentration_metrics['effective_stocks']:.1f}")
            st.caption("Nombre d'actions équivalentes en poids")
        with col3:
            st.metric("Top 3 concentration", f"{concentration_metrics['top3_concentration']:.1%}")
            st.caption("Poids des 3 plus grosses positions")
        
        # Niveau de concentration
        level = concentration_metrics['concentration_level']
        if level == "Très Concentré":
            st.error(f"⚠️ Portefeuille {level}")
        elif level == "Concentré":
            st.warning(f"⚠️ Portefeuille {level}")
        else:
            st.success(f"✅ Portefeuille {level}")
        
        # Diversification sectorielle
        st.subheader("🏭 Diversification sectorielle")
        sector_analysis = DiversificationAnalyzer.analyze_sector_diversification(df)
        
        if not sector_analysis.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig_sector = px.pie(sector_analysis, values='Weight_Pct', names=sector_analysis.index,
                                  title="Répartition sectorielle")
                fig_sector.update_layout(height=400)
                st.plotly_chart(fig_sector, use_container_width=True)
            
            with col2:
                st.dataframe(
                    sector_analysis.style.format({
                        'Weight_Pct': '{:.1f}%',
                        'Amount': '{:,.2f}',
                        'Avg_Performance': '{:.2f}%'
                    }),
                    use_container_width=True
                )
        
        # Diversification géographique
        st.subheader("🌍 Diversification géographique")
        geo_analysis = DiversificationAnalyzer.analyze_geographic_diversification(df)
        
        if not geo_analysis.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig_geo = px.bar(geo_analysis, x=geo_analysis.index, y='Weight_Pct',
                               title="Exposition géographique")
                fig_geo.update_layout(height=400, xaxis_title="Région", yaxis_title="Poids (%)")
                st.plotly_chart(fig_geo, use_container_width=True)
            
            with col2:
                st.dataframe(
                    geo_analysis.style.format({
                        'Weight_Pct': '{:.1f}%',
                        'Amount': '{:,.2f}',
                        'Avg_Performance': '{:.2f}%'
                    }),
                    use_container_width=True
                )
        
        # Types d'actifs
        st.subheader("🏷️ Répartition par type d'actif")
        asset_analysis = df.groupby('asset_type').agg({
            'weight_pct': 'sum',
            'amount': 'sum',
            'perf': 'mean',
            'name': 'count'
        }).round(2)
        
        col1, col2 = st.columns(2)
        with col1:
            fig_assets = px.donut(asset_analysis, values='weight_pct', names=asset_analysis.index,
                                title="Types d'actifs")
            st.plotly_chart(fig_assets, use_container_width=True)
        
        with col2:
            st.dataframe(
                asset_analysis.style.format({
                    'weight_pct': '{:.1f}%',
                    'amount': '{:,.2f}',
                    'perf': '{:.2f}%'
                }),
                use_container_width=True
            )
        
        # Recommandations
        st.header("💡 Recommandations")
        generate_recommendations(df, concentration_metrics, sector_analysis, geo_analysis)
        
    else:
        # Page d'accueil
        st.header("👋 Bienvenue!")
        st.markdown("""
        ### 🚀 Fonctionnalités principales:
        
        - **📤 Import de portefeuille**: Chargez votre fichier CSV
        - **🔍 Recherche avancée**: Trouvez n'importe quelle action mondiale
        - **➕ Ajout manuel**: Construisez votre portefeuille titre par titre
        - **📊 Analyse de concentration**: Mesurez la diversification
        - **🏭 Diversification sectorielle**: Analysez l'exposition par secteur
        - **🌍 Répartition géographique**: Visualisez l'exposition mondiale
        - **🏷️ Types d'actifs**: ETF, actions, crypto, REIT...
        - **💡 Recommandations**: Conseils personnalisés
        
        ### 📋 Format CSV attendu:
        Colonnes minimum: `name`, `quantity`, `buyingPrice`, `lastPrice`
        """)

def enhance_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Améliore automatiquement un DataFrame importé"""
    
    # Colonnes requises avec leurs alias possibles
    column_mapping = {
        'name': ['name', 'nom', 'title', 'security', 'instrument'],
        'quantity': ['quantity', 'qty', 'quantite', 'shares', 'units'],
        'buyingPrice': ['buyingPrice', 'prix_achat', 'purchase_price', 'cost'],
        'lastPrice': ['lastPrice', 'prix_actuel', 'current_price', 'market_price'],
        'isin': ['isin', 'ISIN'],
        'symbol': ['symbol', 'ticker', 'symbole']
    }
    
    # Standardisation des noms de colonnes
    df_enhanced = df.copy()
    for standard_col, possible_names in column_mapping.items():
        for col in df_enhanced.columns:
            if col.lower() in [name.lower() for name in possible_names]:
                df_enhanced = df_enhanced.rename(columns={col: standard_col})
                break
    
    # Ajout des colonnes manquantes avec des valeurs par défaut
    required_columns = {
        'isin': 'Unknown',
        'symbol': '',
        'currency': 'EUR',
        'exchange': 'Unknown',
        'sector': 'Unknown',
        'industry': 'Unknown',
        'asset_type': 'Stock',
        'intradayVariation': 0.0,
        'amountVariation': 0.0,
        'variation': 0.0
    }
    
    for col, default_value in required_columns.items():
        if col not in df_enhanced.columns:
            df_enhanced[col] = default_value
    
    # Calculs automatiques
    if 'amount' not in df_enhanced.columns:
        df_enhanced['amount'] = df_enhanced['quantity'] * df_enhanced['lastPrice']
    
    # Enrichissement automatique des symboles manquants
    if 'symbol' in df_enhanced.columns:
        for idx, row in df_enhanced.iterrows():
            if not row['symbol'] or row['symbol'] == '':
                # Tentative de recherche automatique
                search_results = TickerService.search_tickers(row['name'], limit=1)
                if search_results:
                    df_enhanced.at[idx, 'symbol'] = search_results[0]['symbol']
                    
                    # Validation et enrichissement
                    ticker_data = TickerService.validate_ticker(search_results[0]['symbol'])
                    if ticker_data['valid']:
                        df_enhanced.at[idx, 'sector'] = ticker_data.get('sector', 'Unknown')
                        df_enhanced.at[idx, 'industry'] = ticker_data.get('industry', 'Unknown')
                        df_enhanced.at[idx, 'asset_type'] = ticker_data.get('type', 'Stock')
                        df_enhanced.at[idx, 'exchange'] = ticker_data.get('exchange', 'Unknown')
    
    # Ajout de la colonne Tickers pour compatibilité
    if 'Tickers' not in df_enhanced.columns and 'symbol' in df_enhanced.columns:
        df_enhanced['Tickers'] = df_enhanced['symbol']
    
    return df_enhanced

def generate_recommendations(df: pd.DataFrame, concentration: Dict, 
                           sector_analysis: pd.DataFrame, geo_analysis: pd.DataFrame):
    """Génère des recommandations personnalisées"""
    
    recommendations = []
    
    # Analyse de concentration
    if concentration['hhi'] > 0.25:
        recommendations.append({
            'type': 'warning',
            'title': '⚠️ Concentration excessive',
            'message': f"Votre portefeuille est très concentré (HHI: {concentration['hhi']:.3f}). "
                      f"Considérez réduire vos {3} plus grosses positions qui représentent "
                      f"{concentration['top3_concentration']:.1%} du total."
        })
    
    # Analyse sectorielle
    if not sector_analysis.empty:
        max_sector = sector_analysis.iloc[0]
        if max_sector['Weight_Pct'] > 40:
            recommendations.append({
                'type': 'warning',
                'title': '🏭 Concentration sectorielle',
                'message': f"Le secteur '{max_sector.name}' représente {max_sector['Weight_Pct']:.1f}% "
                          f"de votre portefeuille. Diversifiez vers d'autres secteurs."
            })
    
    # Analyse géographique
    if not geo_analysis.empty:
        max_region = geo_analysis.iloc[0]
        if max_region['Weight_Pct'] > 70:
            recommendations.append({
                'type': 'info',
                'title': '🌍 Diversification géographique',
                'message': f"Votre exposition à la région '{max_region.name}' est de {max_region['Weight_Pct']:.1f}%. "
                          f"Considérez une exposition internationale plus large."
            })
    
