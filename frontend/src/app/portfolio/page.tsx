"use client";

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
    Briefcase, BarChart3, Plus, Trash2, TrendingUp, TrendingDown,
    Loader2, RefreshCw, Info, IndianRupee, DollarSign
} from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const getErrorMessage = (err: unknown) =>
    err instanceof Error ? err.message : 'Unexpected error';

interface PortfolioItem {
    id: number;
    ticker: string;
    shares: number;
    avg_price: number;
    added_at: string;
    latest_analysis?: {
        final_score: number;
        recommendation: string;
        confidence: number;
        company_name: string | null;
    };
}

interface PriceData {
    ticker: string;
    price: number | null;
    change: number;
    change_pct: number;
    high: number;
    low: number;
    currency: string;
    exchange: string;
    company_name: string;
    shares: number;
    avg_price: number;
    cost_basis: number;
    current_value: number;
    gain_loss: number;
    gain_loss_pct: number;
    error?: string;
}

interface PortfolioPrices {
    prices: Record<string, PriceData>;
    total_value: number;
    total_cost: number;
    total_gain_loss: number;
    total_gain_loss_pct: number;
}

const POLL_INTERVAL_MS = 60_000; // refresh prices every 60s

export default function PortfolioPage() {
    const [items, setItems] = useState<PortfolioItem[]>([]);
    const [priceData, setPriceData] = useState<PortfolioPrices | null>(null);
    const [loading, setLoading] = useState(true);
    const [pricesLoading, setPricesLoading] = useState(false);
    const [error, setError] = useState('');
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    // Form state
    const [newTicker, setNewTicker] = useState('');
    const [newShares, setNewShares] = useState('');
    const [newPrice, setNewPrice] = useState('');
    const [addingItem, setAddingItem] = useState(false);

    const fetchPortfolio = useCallback(async () => {
        try {
            setLoading(true);
            const res = await fetch(`${API_URL}/portfolio/`);
            if (!res.ok) throw new Error('Failed to fetch portfolio');
            const data = await res.json();
            setItems(data);
        } catch (err: unknown) {
            setError(getErrorMessage(err) || 'Failed to load portfolio');
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchPrices = useCallback(async (silent = false) => {
        if (!silent) setPricesLoading(true);
        try {
            const res = await fetch(`${API_URL}/portfolio/prices`);
            if (!res.ok) throw new Error('Failed to fetch prices');
            const data: PortfolioPrices = await res.json();
            setPriceData(data);
            setLastUpdated(new Date());
        } catch (err: unknown) {
            // Don't overwrite main error, just silently fail live prices
            console.warn('Price fetch failed:', getErrorMessage(err));
        } finally {
            if (!silent) setPricesLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchPortfolio().then(() => fetchPrices());
    }, [fetchPortfolio, fetchPrices]);

    // Auto-refresh prices every 60s
    useEffect(() => {
        if (items.length === 0) return;
        const interval = setInterval(() => fetchPrices(true), POLL_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [items.length, fetchPrices]);

    const handleAddItem = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newTicker.trim()) return;
        try {
            setAddingItem(true);
            const res = await fetch(`${API_URL}/portfolio/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticker: newTicker.trim().toUpperCase(),
                    shares: parseFloat(newShares) || 0,
                    avg_price: parseFloat(newPrice) || 0
                })
            });
            if (!res.ok) throw new Error('Failed to add item');
            setNewTicker(''); setNewShares(''); setNewPrice('');
            await fetchPortfolio();
            await fetchPrices();
        } catch (err: unknown) {
            setError(getErrorMessage(err) || 'Failed to add item');
        } finally {
            setAddingItem(false);
        }
    };

    const handleRemoveItem = async (ticker: string) => {
        if (!confirm(`Remove ${ticker} from your portfolio?`)) return;
        try {
            const res = await fetch(`${API_URL}/portfolio/${ticker}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Failed to remove item');
            setItems(items.filter(i => i.ticker !== ticker));
        } catch (err: unknown) {
            setError(getErrorMessage(err) || 'Failed to remove item');
        }
    };

    const getRecommendationColor = (rec?: string) => {
        switch (rec?.toLowerCase()) {
            case 'strong buy': case 'buy': return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
            case 'hold': return 'text-amber-500 bg-amber-500/10 border-amber-500/20';
            case 'sell': case 'strong sell': return 'text-rose-500 bg-rose-500/10 border-rose-500/20';
            default: return 'text-slate-500 bg-slate-500/10 border-slate-500/20';
        }
    };

    const fmtCurrency = (val: number, currency: string) => {
        const sym = currency === 'INR' ? '₹' : '$';
        const formatted = Math.abs(val).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return `${sym}${formatted}`;
    };

    const isIndian = (ticker: string) =>
        ticker.endsWith('.NS') || ticker.endsWith('.BO') ||
        ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'RELIANCE', 'ONGC', 'SBIN', 'HDFCBANK',
            'ICICIBANK', 'AXISBANK', 'KOTAKBANK', 'NTPC', 'MARUTI', 'TATAMOTORS'].includes(ticker);

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-slate-950 font-sans text-slate-900 dark:text-slate-100">
            {/* Background gradients */}
            <div className="fixed inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-0 right-1/4 w-96 h-96 bg-purple-500/20 blur-[128px] rounded-full mix-blend-multiply dark:mix-blend-screen opacity-70 animate-blob"></div>
                <div className="absolute -bottom-8 left-1/3 w-96 h-96 bg-blue-500/20 blur-[128px] rounded-full mix-blend-multiply dark:mix-blend-screen opacity-70 animate-blob animation-delay-2000"></div>
            </div>

            <div className="container relative z-10 max-w-6xl mx-auto px-4 py-8 md:py-12">
                <header className="mb-12 relative">
                    <div className="absolute top-0 right-0 flex gap-4">
                        <Link href="/" className="px-4 py-2 font-semibold text-slate-600 dark:text-slate-400 bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200/50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors flex items-center">
                            <BarChart3 size={18} className="mr-2" />Dashboard
                        </Link>
                        <Link href="/portfolio" className="px-4 py-2 font-semibold text-indigo-600 dark:text-indigo-400 bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200/50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors flex items-center">
                            <Briefcase size={18} className="mr-2" />Portfolio
                        </Link>
                    </div>

                    <div className="flex items-center gap-4 mt-12 md:mt-0">
                        <div className="w-14 h-14 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-indigo-500/20">
                            <Briefcase size={28} />
                        </div>
                        <div>
                            <h1 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-purple-600 dark:from-indigo-400 dark:to-purple-400">
                                My Portfolio
                            </h1>
                            <p className="text-slate-500 dark:text-slate-400 font-medium mt-1">
                                Live prices · US &amp; Indian stocks · Real-time P&amp;L
                            </p>
                        </div>
                    </div>
                </header>

                {error && (
                    <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-4 rounded-xl mb-8 border border-red-200 dark:border-red-900/50">
                        {error}
                    </div>
                )}

                {/* Portfolio Summary Bar */}
                {priceData && priceData.total_value > 0 && (
                    <div className="bg-white/70 dark:bg-slate-900/70 backdrop-blur-xl rounded-2xl p-5 shadow-lg border border-white/20 dark:border-slate-800/50 mb-8 flex flex-wrap gap-6 items-center">
                        <div>
                            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">Total Value</p>
                            <p className="text-2xl font-black text-slate-800 dark:text-white">
                                ${priceData.total_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </p>
                        </div>
                        <div>
                            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">Cost Basis</p>
                            <p className="text-xl font-bold text-slate-600 dark:text-slate-300">
                                ${priceData.total_cost.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </p>
                        </div>
                        <div>
                            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">Total Gain / Loss</p>
                            <p className={`text-xl font-bold flex items-center gap-1 ${priceData.total_gain_loss >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                {priceData.total_gain_loss >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                                ${Math.abs(priceData.total_gain_loss).toFixed(2)}
                                <span className="text-sm font-medium ml-1">({priceData.total_gain_loss_pct >= 0 ? '+' : ''}{priceData.total_gain_loss_pct.toFixed(2)}%)</span>
                            </p>
                        </div>
                        <div className="ml-auto flex items-center gap-3">
                            {lastUpdated && (
                                <span className="text-xs text-slate-400">
                                    Updated {lastUpdated.toLocaleTimeString()}
                                </span>
                            )}
                            <button
                                onClick={() => fetchPrices()}
                                disabled={pricesLoading}
                                className="p-2 text-slate-500 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-500/10 rounded-lg transition-colors"
                                title="Refresh prices"
                            >
                                <RefreshCw size={18} className={pricesLoading ? 'animate-spin' : ''} />
                            </button>
                        </div>
                    </div>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Add Item Form */}
                    <div className="col-span-1">
                        <div className="bg-white/70 dark:bg-slate-900/70 backdrop-blur-xl rounded-2xl p-6 shadow-xl border border-white/20 dark:border-slate-800/50 sticky top-8">
                            <h2 className="text-xl font-bold mb-2 flex items-center">
                                <Plus size={20} className="mr-2 text-indigo-500" />
                                Add Position
                            </h2>
                            <p className="text-xs text-slate-500 dark:text-slate-400 mb-5 flex items-start gap-1.5">
                                <Info size={12} className="mt-0.5 shrink-0" />
                                <span>US stocks: <strong>AAPL, MSFT</strong><br />Indian stocks: <strong>TCS, INFY, RELIANCE</strong></span>
                            </p>

                            <form onSubmit={handleAddItem} className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Ticker Symbol</label>
                                    <input
                                        type="text" required value={newTicker}
                                        onChange={(e) => setNewTicker(e.target.value)}
                                        placeholder="e.g. MSFT or TCS"
                                        className="w-full px-4 py-3 bg-slate-100/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none uppercase"
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Shares</label>
                                        <input
                                            type="number" step="any" min="0" value={newShares}
                                            onChange={(e) => setNewShares(e.target.value)}
                                            placeholder="0.00"
                                            className="w-full px-4 py-3 bg-slate-100/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Avg Price</label>
                                        <input
                                            type="number" step="any" min="0" value={newPrice}
                                            onChange={(e) => setNewPrice(e.target.value)}
                                            placeholder="0.00"
                                            className="w-full px-4 py-3 bg-slate-100/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
                                        />
                                    </div>
                                </div>
                                <button
                                    type="submit" disabled={addingItem || !newTicker.trim()}
                                    className="w-full mt-6 px-4 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold transition-all disabled:opacity-50 flex justify-center items-center"
                                >
                                    {addingItem ? <Loader2 size={18} className="animate-spin" /> : 'Add to Portfolio'}
                                </button>
                            </form>
                        </div>
                    </div>

                    {/* Portfolio List */}
                    <div className="col-span-1 lg:col-span-2">
                        {loading ? (
                            <div className="flex justify-center items-center h-64 bg-white/40 dark:bg-slate-900/40 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700">
                                <Loader2 size={32} className="animate-spin text-indigo-500" />
                            </div>
                        ) : items.length === 0 ? (
                            <div className="flex flex-col justify-center items-center h-64 bg-white/40 dark:bg-slate-900/40 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 text-slate-500">
                                <Briefcase size={48} className="mb-4 opacity-50" />
                                <p className="text-lg font-medium">Your portfolio is empty</p>
                                <p className="text-sm mt-1">Add US or Indian stocks to start tracking</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {items.map((item) => {
                                    const pd = priceData?.prices?.[item.ticker];
                                    const currency = pd?.currency ?? (isIndian(item.ticker) ? 'INR' : 'USD');
                                    const hasLivePrice = pd && pd.price !== null;
                                    const currencyIcon = currency === 'INR'
                                        ? <IndianRupee size={14} className="inline -mt-0.5 mr-0.5" />
                                        : <DollarSign size={14} className="inline -mt-0.5 mr-0.5" />;

                                    return (
                                        <div key={item.id} className="bg-white/70 dark:bg-slate-900/70 backdrop-blur-xl rounded-2xl p-6 shadow-lg border border-white/20 dark:border-slate-800/50 group hover:border-indigo-500/30 transition-colors">
                                            <div className="flex flex-col sm:flex-row justify-between items-start gap-4">
                                                {/* Left: Basic Info */}
                                                <div className="flex-1">
                                                    <div className="flex flex-wrap items-baseline gap-3 mb-2">
                                                        <h3 className="text-2xl font-black text-slate-800 dark:text-white tracking-tight">{item.ticker}</h3>
                                                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${currency === 'INR' ? 'bg-orange-500/10 text-orange-500' : 'bg-blue-500/10 text-blue-500'}`}>
                                                            {currency === 'INR' ? '🇮🇳 NSE' : '🇺🇸 NYSE/NASDAQ'}
                                                        </span>
                                                        {(pd?.company_name && pd.company_name !== item.ticker) && (
                                                            <span className="text-sm text-slate-500 truncate max-w-[200px]">{pd.company_name}</span>
                                                        )}
                                                        {(item.latest_analysis?.company_name && !pd?.company_name) && (
                                                            <span className="text-sm text-slate-500 truncate max-w-[200px]">{item.latest_analysis.company_name}</span>
                                                        )}
                                                    </div>

                                                    {/* Position details */}
                                                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm font-medium text-slate-600 dark:text-slate-400">
                                                        <span>{item.shares || 0} shares</span>
                                                        <span>·</span>
                                                        <span>Avg {currencyIcon}{(item.avg_price || 0).toFixed(2)}</span>
                                                        {item.shares > 0 && item.avg_price > 0 && (
                                                            <>
                                                                <span>·</span>
                                                                <span>Cost {currencyIcon}{(item.shares * item.avg_price).toFixed(2)}</span>
                                                            </>
                                                        )}
                                                    </div>
                                                </div>

                                                {/* Right: Actions */}
                                                <button
                                                    onClick={() => handleRemoveItem(item.ticker)}
                                                    className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors shrink-0"
                                                    title="Remove from portfolio"
                                                >
                                                    <Trash2 size={18} />
                                                </button>
                                            </div>

                                            {/* Live Price Row */}
                                            <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 flex flex-wrap justify-between items-center gap-4">
                                                {hasLivePrice ? (
                                                    <>
                                                        <div>
                                                            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">Live Price</p>
                                                            <div className="flex items-baseline gap-2">
                                                                <span className="text-xl font-black text-slate-800 dark:text-white">
                                                                    {currencyIcon}{pd!.price!.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                                                </span>
                                                                <span className={`text-sm font-bold flex items-center gap-0.5 ${pd!.change_pct >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                                                    {pd!.change_pct >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                                                                    {pd!.change_pct >= 0 ? '+' : ''}{pd!.change_pct.toFixed(2)}%
                                                                </span>
                                                            </div>
                                                        </div>

                                                        {pd?.current_value !== undefined && (
                                                            <div className="text-right">
                                                                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">Current Value</p>
                                                                <p className="text-xl font-black text-slate-800 dark:text-white">
                                                                    {fmtCurrency(pd.current_value, currency)}
                                                                </p>
                                                            </div>
                                                        )}

                                                        {pd?.gain_loss !== undefined && (
                                                            <div className="text-right">
                                                                <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">Gain / Loss</p>
                                                                <p className={`text-lg font-bold flex items-center gap-1 justify-end ${pd.gain_loss >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                                                    {pd.gain_loss >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                                                                    {fmtCurrency(pd.gain_loss, currency)}
                                                                    <span className="text-sm">({pd.gain_loss_pct >= 0 ? '+' : ''}{pd.gain_loss_pct.toFixed(2)}%)</span>
                                                                </p>
                                                            </div>
                                                        )}
                                                    </>
                                                ) : pd?.error ? (
                                                    <span className="text-xs text-slate-400 italic">{pd.error}</span>
                                                ) : (
                                                    <span className="text-xs text-slate-400 flex items-center gap-1.5">
                                                        <Loader2 size={12} className="animate-spin" /> Fetching live price…
                                                    </span>
                                                )}

                                                {/* AI Score */}
                                                {item.latest_analysis && (
                                                    <div className="flex items-center gap-3 ml-auto">
                                                        <div className="text-right">
                                                            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-0.5">AI Score</p>
                                                            <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-500 to-purple-500">
                                                                {item.latest_analysis.final_score.toFixed(1)}
                                                            </span>
                                                        </div>
                                                        <div className={`px-3 py-1.5 rounded-xl text-center border font-bold text-sm tracking-wide ${getRecommendationColor(item.latest_analysis.recommendation)}`}>
                                                            {item.latest_analysis.recommendation}
                                                        </div>
                                                    </div>
                                                )}

                                                {!item.latest_analysis && (
                                                    <Link href={`/?ticker=${item.ticker}`} className="ml-auto text-sm font-medium text-indigo-500 hover:text-indigo-600 dark:hover:text-indigo-400">
                                                        Run AI Analysis →
                                                    </Link>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
