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
        # Vérifier que les colonnes nécessaires existent
        if 'weight' not in df.columns:
            if 'amount' in df.columns:
                total_value = df['amount'].sum()
                if total_value > 0:
                    df = df.copy()
                    df['weight'] = df['amount'] / total_value
                else:
                    return {
                        'hhi': 0,
                        'effective_stocks': 0,
                        'top3_concentration': 0,
                        'entropy_ratio': 0,
                        'concentration_level': "Indéterminé"
                    }
            else:
                return {
                    'hhi': 0,
                    'effective_stocks': 0,
                    'top3_concentration': 0,
                    'entropy_ratio': 0,
                    'concentration_level': "Indéterminé"
                }
        
        weights = df['weight'].values
        
        # S'assurer que les poids sont valides
        weights = weights[weights > 0]  # Exclure les poids zéro ou négatifs
        if len(weights) == 0:
            return {
                'hhi': 0,
                'effective_stocks': 0,
                'top3_concentration': 0,
                'entropy_ratio': 0,
                'concentration_level': "Indéterminé"
            }
        
        # Indice Herfindahl-Hirschman
        hhi = np.sum(weights ** 2)
        
        # Nombre effectif d'actions
        effective_stocks = 1 / hhi if hhi > 0 else 0
        
        # Top 3 concentration
        sorted_weights = np.sort(weights)[::-1]  # Tri décroissant
        top3_weight = sorted_weights[:min(3, len(sorted_weights))].sum()
        
        # Entropy (diversification Shannon)
        weights_clean = weights[weights > 0]  # Éviter log(0)
        entropy = -np.sum(weights_clean * np.log(weights_clean + 1e-10))
        max_entropy = -np.log(1/len(weights_clean)) if len(weights_clean) > 0 else 1
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
        if 'sector' not in df.columns or 'weight' not in df.columns:
            return pd.DataFrame()
        
        # Calculer weight si manquant
        df_work = df.copy()
        if 'weight' not in df_work.columns and 'amount' in df_work.columns:
            total_value = df_work['amount'].sum()
            if total_value > 0:
                df_work['weight'] = df_work['amount'] / total_value
            else:
                return pd.DataFrame()
        
        try:
            sector_analysis = df_work.groupby('sector').agg({
                'weight': 'sum',
                'amount': 'sum',
                'perf': 'mean',
                'name': 'count'
            }).round(4)
            
            sector_analysis.columns = ['Weight', 'Amount', 'Avg_Performance', 'Count']
            sector_analysis['Weight_Pct'] = sector_analysis['Weight'] * 100
            
            return sector_analysis.sort_values('Weight', ascending=False)
        except Exception as e:
            st.warning(f"Erreur dans l'analyse sectorielle: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def analyze_geographic_diversification(df: pd.DataFrame) -> pd.DataFrame:
        """Analyse la diversification géographique"""
        if 'exchange' not in df.columns or 'weight' not in df.columns:
            return pd.DataFrame()
        
        # Calculer weight si manquant
        df_work = df.copy()
        if 'weight' not in df_work.columns and 'amount' in df_work.columns:
            total_value = df_work['amount'].sum()
            if total_value > 0:
                df_work['weight'] = df_work['amount'] / total_value
            else:
                return pd.DataFrame()
        
        # Mapping exchange -> région
        exchange_to_region = {
            'NYSE': 'USA', 'NASDAQ': 'USA', 'NYSEArca': 'USA',
            'Paris': 'Europe', 'London': 'Europe', 'Frankfurt': 'Europe',
            'Milan': 'Europe', 'Amsterdam': 'Europe', 'Swiss': 'Europe',
            'Tokyo': 'Asia', 'Hong Kong': 'Asia', 'Shanghai': 'Asia',
            'Toronto': 'North America', 'TSX': 'North America'
        }
        
        df_work['region'] = df_work['exchange'].map(
            lambda x: next((region for exch, region in exchange_to_region.items() 
                          if exch.lower() in str(x).lower()), 'Other')
        )
        
        try:
            geo_analysis = df_work.groupby('region').agg({
                'weight': 'sum',
                'amount': 'sum',
                'perf': 'mean',
                'name': 'count'
            }).round(4)
            
            geo_analysis.columns = ['Weight', 'Amount', 'Avg_Performance', 'Count']
            geo_analysis['Weight_Pct'] = geo_analysis['Weight'] * 100
            
            return geo_analysis.sort_values('Weight', ascending=False)
        except Exception as e:
            st.warning(f"Erreur dans l'analyse géographique: {e}")
            return pd.DataFrame()


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
                      f"Considérez réduire vos 3 plus grosses positions qui représentent "
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
    
    # Nombre de positions
    if len(df) < 10:
        recommendations.append({
            'type': 'info',
            'title': '📊 Nombre de positions',
            'message': f"Avec {len(df)} positions, votre portefeuille pourrait bénéficier de plus de diversification. "
                      f"Considérez ajouter 5-10 positions supplémentaires pour réduire le risque spécifique."
        })
    elif len(df) > 50:
        recommendations.append({
            'type': 'warning',
            'title': '📊 Trop de positions',
            'message': f"Avec {len(df)} positions, votre portefeuille pourrait être trop complexe à gérer. "
                      f"Considérez consolider vers 20-30 positions principales."
        })
    
    # Analyse des performances
    if 'perf' in df.columns:
        avg_perf = df['perf'].mean()
        perf_std = df['perf'].std()
        
        if perf_std > 50:  # Volatilité élevée
            recommendations.append({
                'type': 'warning',
                'title': '📈 Volatilité élevée',
                'message': f"La volatilité de vos positions est élevée (écart-type: {perf_std:.1f}%). "
                          f"Considérez ajouter des actifs plus stables (obligations, dividendes)."
            })
        
        # Positions perdantes
        losing_positions = df[df['perf'] < -20]
        if len(losing_positions) > len(df) * 0.3:  # Plus de 30% de positions perdantes
            recommendations.append({
                'type': 'warning',
                'title': '📉 Positions perdantes',
                'message': f"{len(losing_positions)} positions affichent des pertes > 20%. "
                          f"Évaluez si certaines doivent être soldées pour limiter les pertes."
            })
    
    # Recommandations positives
    if concentration['hhi'] < 0.10 and len(df) >= 15:
        recommendations.append({
            'type': 'success',
            'title': '✅ Bonne diversification',
            'message': "Votre portefeuille présente une bonne diversification avec un risque de concentration faible."
        })
    
    if not sector_analysis.empty and len(sector_analysis) >= 5:
        recommendations.append({
            'type': 'success',
            'title': '✅ Diversification sectorielle',
            'message': f"Excellente diversification avec {len(sector_analysis)} secteurs représentés."
        })
    
    # Affichage des recommandations
    if recommendations:
        for rec in recommendations:
            if rec['type'] == 'warning':
                st.markdown(f"""
                <div class="warning-card">
                    <h4>{rec['title']}</h4>
                    <p>{rec['message']}</p>
                </div>
                """, unsafe_allow_html=True)
            elif rec['type'] == 'success':
                st.markdown(f"""
                <div class="success-card">
                    <h4>{rec['title']}</h4>
                    <p>{rec['message']}</p>
                </div>
                """, unsafe_allow_html=True)
            else:  # info
                st.markdown(f"""
                <div class="metric-card">
                    <h4>{rec['title']}</h4>
                    <p>{rec['message']}</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Aucune recommandation spécifique pour le moment.")

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

def display_portfolio_summary(df: pd.DataFrame):
    """Affiche un résumé avancé du portefeuille"""
    st.header("📋 Résumé du portefeuille")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔝 Top 5 positions")
        top5 = df.nlargest(5, 'weight_pct')[['name', 'weight_pct', 'perf']]
        top5.columns = ['Action', 'Poids (%)', 'Performance (%)']
        st.dataframe(top5.style.format({
            'Poids (%)': '{:.1f}',
            'Performance (%)': '{:.2f}'
        }), use_container_width=True)
    
    with col2:
        st.subheader("📉 Plus fortes baisses")
        worst5 = df.nsmallest(5, 'perf')[['name', 'weight_pct', 'perf']]
        worst5.columns = ['Action', 'Poids (%)', 'Performance (%)']
        st.dataframe(worst5.style.format({
            'Poids (%)': '{:.1f}',
            'Performance (%)': '{:.2f}'
        }), use_container_width=True)

def create_risk_analysis(df: pd.DataFrame):
    """Crée une analyse de risque du portefeuille"""
    st.subheader("⚠️ Analyse de risque")
    
    # Calcul du VaR simplifié (basé sur les performances historiques)
    if 'perf' in df.columns and len(df) > 0:
        portfolio_weights = df['weight'].values
        portfolio_returns = df['perf'].values / 100  # Conversion en décimal
        
        # VaR à 95% (approximation)
        portfolio_return = np.dot(portfolio_weights, portfolio_returns)
        portfolio_var = np.dot(portfolio_weights**2, portfolio_returns**2)  # Simplification
        portfolio_vol = np.sqrt(portfolio_var)
        
        var_95 = portfolio_return - 1.645 * portfolio_vol  # VaR à 95%
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Rendement attendu", f"{portfolio_return:.2%}")
        with col2:
            st.metric("Volatilité estimée", f"{portfolio_vol:.2%}")
        with col3:
            st.metric("VaR 95% (approx.)", f"{var_95:.2%}")
        
        # Analyse par quintiles de risque
        df_risk = df.copy()
        df_risk['risk_score'] = np.abs(df_risk['perf'])  # Score de risque basique
        df_risk['risk_quintile'] = pd.qcut(df_risk['risk_score'], 5, labels=['Très Faible', 'Faible', 'Moyen', 'Élevé', 'Très Élevé'])
        
        risk_analysis = df_risk.groupby('risk_quintile').agg({
            'weight_pct': 'sum',
            'amount': 'sum',
            'name': 'count'
        }).round(2)
        
        st.subheader("📊 Répartition par niveau de risque")
        fig_risk = px.bar(risk_analysis, x=risk_analysis.index, y='weight_pct',
                         title="Exposition par niveau de risque (%)")
        fig_risk.update_layout(height=400, xaxis_title="Niveau de risque", yaxis_title="Poids (%)")
        st.plotly_chart(fig_risk, use_container_width=True)

def export_portfolio_report(df: pd.DataFrame):
    """Permet d'exporter un rapport du portefeuille"""
    st.subheader("📤 Export du rapport")
    
    if st.button("📊 Générer rapport CSV"):
        # Préparation des données d'export
        export_df = df[['name', 'symbol', 'quantity', 'buyingPrice', 'lastPrice', 
                       'amount', 'weight_pct', 'perf', 'sector', 'asset_type']].copy()
        
        export_df.columns = ['Nom', 'Symbole', 'Quantité', 'Prix_Achat', 'Prix_Actuel',
                            'Montant', 'Poids_Pct', 'Performance_Pct', 'Secteur', 'Type_Actif']
        
        csv = export_df.to_csv(index=False)
        st.download_button(
            label="💾 Télécharger CSV",
            data=csv,
            file_name=f"portfolio_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
        st.success("✅ Rapport généré avec succès!")
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
                            st.write(f"**{ticker_data['name']}**")
                            st.write(f"Prix: {ticker_data['price']:.2f} {ticker_data['currency']}")
                            st.write(f"Secteur: {ticker_data.get('sector', 'N/A')}")
                        
                        with col2:
                            quantity = st.number_input("Quantité:", min_value=1, value=1, key=f"qty_{selected_symbol}")
                            
                            if st.button("➕ Ajouter", key=f"add_{selected_symbol}"):
                                success = portfolio_manager.add_stock_to_portfolio(ticker_data, quantity)
                                if success:
                                    st.success(f"✅ {ticker_data['name']} ajouté au portefeuille!")
                                    st.rerun()
                    else:
                        st.error(f"❌ Ticker invalide: {ticker_data.get('error', 'Erreur inconnue')}")
            else:
                st.warning("Aucun résultat trouvé")
        
        # Boutons d'actions sur le portefeuille
        st.subheader("🛠️ Gestion du portefeuille")
        
        if not st.session_state.portfolio_df.empty:
            if st.button("🔄 Actualiser les prix", use_container_width=True):
                with st.spinner("Actualisation des prix..."):
                    df = st.session_state.portfolio_df.copy()
                    
                    for idx, row in df.iterrows():
                        if row['symbol']:
                            try:
                                ticker = yf.Ticker(row['symbol'])
                                current_price = ticker.history(period="1d")['Close'].iloc[-1]
                                df.at[idx, 'lastPrice'] = current_price
                                df.at[idx, 'amount'] = row['quantity'] * current_price
                                df.at[idx, 'variation'] = ((current_price - row['buyingPrice']) / row['buyingPrice']) * 100
                            except:
                                continue
                    
                    st.session_state.portfolio_df = df
                    st.success("✅ Prix actualisés!")
                    st.rerun()
            
            if st.button("🗑️ Vider le portefeuille", use_container_width=True):
                st.session_state.portfolio_df = pd.DataFrame()
                st.session_state.original_df = pd.DataFrame()
                st.warning("Portfolio vidé!")
                st.rerun()
            
            # Affichage des statistiques rapides
            df = st.session_state.portfolio_df
            total_value = df['amount'].sum()
            total_positions = len(df)
            
            st.markdown("---")
            st.metric("💰 Valeur totale", f"{total_value:,.2f} EUR")
            st.metric("📊 Positions", total_positions)
            
            if 'perf' in df.columns:
                weighted_perf = (df['weight'] * df['perf']).sum() if 'weight' in df.columns else df['perf'].mean()
                st.metric("📈 Performance moyenne", f"{weighted_perf:.2f}%")
    
    # Zone principale
    if st.session_state.portfolio_df.empty:
        st.info("👆 Commencez par importer un fichier CSV ou ajouter des actions manuellement dans la barre latérale")
        
        # Exemple de format CSV
        st.subheader("📝 Format CSV attendu")
        example_df = pd.DataFrame({
            'name': ['Apple Inc.', 'Microsoft Corporation', 'LVMH'],
            'quantity': [10, 5, 2],
            'buyingPrice': [150.00, 280.00, 650.00],
            'lastPrice': [175.00, 310.00, 680.00],
            'symbol': ['AAPL', 'MSFT', 'MC.PA']
        })
        st.dataframe(example_df, use_container_width=True)
        
        csv_example = example_df.to_csv(index=False)
        st.download_button(
            label="📥 Télécharger exemple CSV",
            data=csv_example,
            file_name="exemple_portfolio.csv",
            mime="text/csv"
        )
    
    else:
        df = st.session_state.portfolio_df.copy()
        
        # Mise à jour des métriques avec gestion d'erreurs
        try:
            metrics = portfolio_manager.update_portfolio_metrics()
        except Exception as e:
            st.error(f"Erreur lors du calcul des métriques: {e}")
            # Calculs de base en cas d'erreur
            total_value = df['amount'].sum() if 'amount' in df.columns else 0
            metrics = {'total_value': total_value, 'portfolio_performance': 0}
        
        # S'assurer que les colonnes nécessaires existent
        if 'weight_pct' not in df.columns and 'amount' in df.columns:
            total_value = df['amount'].sum()
            df['weight_pct'] = (df['amount'] / total_value * 100) if total_value > 0 else 0
        
        if 'perf' not in df.columns:
            if 'buyingPrice' in df.columns and 'lastPrice' in df.columns:
                df['perf'] = ((df['lastPrice'] - df['buyingPrice']) / df['buyingPrice'] * 100).fillna(0)
            else:
                df['perf'] = 0
        
        # Onglets principaux
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📊 Vue d'ensemble", 
            "🎯 Diversification", 
            "⚖️ Répartition",
            "📈 Performance", 
            "⚠️ Analyse de risque",
            "📤 Export"
        ])
        
        with tab1:
            # Métriques principales
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 Valeur totale", f"{metrics.get('total_value', 0):,.2f} EUR")
            
            with col2:
                st.metric("📊 Nombre de positions", len(df))
            
            with col3:
                portfolio_perf = metrics.get('portfolio_performance', 0)
                st.metric("📈 Performance globale", f"{portfolio_perf:.2f}%")
            
            with col4:
                try:
                    if len(df) > 0 and 'perf' in df.columns:
                        best_idx = df['perf'].idxmax()
                        best_stock = df.loc[best_idx]
                        st.metric("🏆 Meilleure position", f"{best_stock['perf']:.2f}%", 
                                best_stock.get('name', 'N/A'))
                    else:
                        st.metric("🏆 Meilleure position", "N/A")
                except:
                    st.metric("🏆 Meilleure position", "N/A")
            
            # Résumé du portefeuille
            display_portfolio_summary(df)
            
            # Tableau détaillé
            st.subheader("📋 Détail des positions")
            
            # Sélection des colonnes à afficher
            display_columns = ['name', 'symbol', 'quantity', 'buyingPrice', 'lastPrice', 
                             'amount', 'weight_pct', 'perf', 'sector', 'asset_type']
            
            available_columns = [col for col in display_columns if col in df.columns]
            df_display = df[available_columns].copy()
            
            # Formatage des colonnes
            column_config = {
                'name': st.column_config.TextColumn('Nom', width='medium'),
                'symbol': st.column_config.TextColumn('Symbole', width='small'),
                'quantity': st.column_config.NumberColumn('Qté', format='%d'),
                'buyingPrice': st.column_config.NumberColumn('Prix achat', format='%.2f €'),
                'lastPrice': st.column_config.NumberColumn('Prix actuel', format='%.2f €'),
                'amount': st.column_config.NumberColumn('Montant', format='%.2f €'),
                'weight_pct': st.column_config.NumberColumn('Poids (%)', format='%.1f%%'),
                'perf': st.column_config.NumberColumn('Perf (%)', format='%.2f%%'),
                'sector': st.column_config.TextColumn('Secteur', width='medium'),
                'asset_type': st.column_config.TextColumn('Type', width='small')
            }
            
            st.dataframe(df_display, column_config=column_config, use_container_width=True, height=400)
        
        with tab2:
            st.header("🎯 Analyse de diversification")
            
            # Calcul des métriques de concentration
            concentration = DiversificationAnalyzer.calculate_concentration_metrics(df)
            
            # Métriques de concentration
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📊 Indice HHI", f"{concentration['hhi']:.3f}")
            
            with col2:
                st.metric("🔢 Actions effectives", f"{concentration['effective_stocks']:.1f}")
            
            with col3:
                st.metric("🎯 Top 3 concentration", f"{concentration['top3_concentration']:.1%}")
            
            with col4:
                st.metric("📈 Niveau de concentration", concentration['concentration_level'])
            
            # Analyses sectorielles et géographiques
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🏭 Diversification sectorielle")
                sector_analysis = DiversificationAnalyzer.analyze_sector_diversification(df)
                
                if not sector_analysis.empty:
                    st.dataframe(sector_analysis.style.format({
                        'Weight_Pct': '{:.1f}%',
                        'Avg_Performance': '{:.2f}%'
                    }), use_container_width=True)
                    
                    # Graphique secteurs
                    fig_sector = px.pie(sector_analysis, values='Weight', names=sector_analysis.index,
                                       title="Répartition sectorielle")
                    st.plotly_chart(fig_sector, use_container_width=True)
                else:
                    st.info("Données sectorielles non disponibles")
            
            with col2:
                st.subheader("🌍 Diversification géographique")
                geo_analysis = DiversificationAnalyzer.analyze_geographic_diversification(df)
                
                if not geo_analysis.empty:
                    st.dataframe(geo_analysis.style.format({
                        'Weight_Pct': '{:.1f}%',
                        'Avg_Performance': '{:.2f}%'
                    }), use_container_width=True)
                    
                    # Graphique géographique
                    fig_geo = px.pie(geo_analysis, values='Weight', names=geo_analysis.index,
                                    title="Répartition géographique")
                    st.plotly_chart(fig_geo, use_container_width=True)
                else:
                    st.info("Données géographiques non disponibles")
            
            # Recommandations
            st.subheader("💡 Recommandations de diversification")
            generate_recommendations(df, concentration, sector_analysis, geo_analysis)
        
        with tab3:
            st.header("⚖️ Répartition du portefeuille")
            
            # Graphique en secteurs des positions
            fig_allocation = px.pie(df, values='weight_pct', names='name',
                                   title="Répartition par position")
            fig_allocation.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_allocation, use_container_width=True)
            
            # Graphique en barres
            fig_bar = px.bar(df.sort_values('weight_pct', ascending=True).tail(15), 
                            x='weight_pct', y='name', orientation='h',
                            title="Top 15 des positions (% du portefeuille)")
            fig_bar.update_layout(height=600)
            st.plotly_chart(fig_bar, use_container_width=True)
            
            # Répartition par type d'actif
            if 'asset_type' in df.columns:
                asset_allocation = df.groupby('asset_type')['weight_pct'].sum().reset_index()
                fig_asset = px.bar(asset_allocation, x='asset_type', y='weight_pct',
                                  title="Répartition par type d'actif")
                st.plotly_chart(fig_asset, use_container_width=True)
        
        with tab4:
            st.header("📈 Analyse de performance")
            
            if 'perf' in df.columns:
                # Distribution des performances
                fig_perf_dist = px.histogram(df, x='perf', nbins=20,
                                           title="Distribution des performances (%)")
                st.plotly_chart(fig_perf_dist, use_container_width=True)
                
                # Performance vs poids
                fig_scatter = px.scatter(df, x='weight_pct', y='perf', 
                                       size='amount', hover_name='name',
                                       title="Performance vs Poids dans le portefeuille")
                fig_scatter.update_layout(
                    xaxis_title="Poids (%)",
                    yaxis_title="Performance (%)"
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
                
                # Top et bottom performers
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🏆 Top performers")
                    top_performers = df.nlargest(5, 'perf')[['name', 'perf', 'weight_pct']]
                    st.dataframe(top_performers.style.format({
                        'perf': '{:.2f}%',
                        'weight_pct': '{:.1f}%'
                    }), use_container_width=True)
                
                with col2:
                    st.subheader("📉 Underperformers")
                    underperformers = df.nsmallest(5, 'perf')[['name', 'perf', 'weight_pct']]
                    st.dataframe(underperformers.style.format({
                        'perf': '{:.2f}%',
                        'weight_pct': '{:.1f}%'
                    }), use_container_width=True)
            else:
                st.info("Données de performance non disponibles")
        
        with tab5:
            create_risk_analysis(df)
        
        with tab6:
            export_portfolio_report(df)

if __name__ == "__main__":
    main()
