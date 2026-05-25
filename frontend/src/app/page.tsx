"use client";

import React, { useState } from 'react';
import Link from 'next/link';
import { Search, TrendingUp, ShieldAlert, BarChart3, Info, Download, Loader2, Briefcase, ChevronDown, ChevronUp, AlertTriangle, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import {
  Tooltip,
  ResponsiveContainer,
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis
} from 'recharts';

const API_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type AgentResult = {
  status?: 'success' | 'partial' | 'failed';
  score?: number | null;
  confidence: number;
  explanation?: string;
  signals?: string[];
  risks?: string[];
  warnings?: string[];
  data_source?: string;
};

type BrokenAgent = {
  agent_name: string;
  status: 'failed' | 'partial';
  reason: string;
};

type DataGap = {
  category: string;
  description: string;
  severity: 'high' | 'medium' | 'low';
};

type FinalDecision = {
  verdict: 'BUY' | 'HOLD' | 'SELL';
  score: number;
  reliability: number;
  reliability_label: 'Low' | 'Medium' | 'High';
  reason: string;
  positive_drivers: string[];
  negative_drivers: string[];
  missing_signals: string[];
};

type AnalysisResult = {
  ticker: string;
  company_name?: string;
  recommendation: 'BUY' | 'HOLD' | 'SELL';
  final_score: number;
  confidence: number;
  xai_explanation: string;
  final_decision?: FinalDecision;
  fundamental_score: AgentResult;
  technical_score: AgentResult;
  sentiment_score: AgentResult;
  governance_score: AgentResult;
  pead_score: AgentResult;
  financial_health_score: AgentResult;
  risk_score: AgentResult;
  macro_score?: AgentResult;
  insider_score?: AgentResult;
  system_debug_audit?: {
    reliability_score: number;
    failed_agents: number;
    partial_agents: number;
    successful_agents: number;
    excluded_from_score: string[];
    broken_agents: BrokenAgent[];
    data_gaps: DataGap[];
    invalid_outputs: string[];
    recommendations: string[];
    audit_timestamp: string;
    final_stance?: string;
  };
};

const getErrorMessage = (err: unknown) =>
  err instanceof Error ? err.message : 'Unexpected error';

export default function Home() {
  const [ticker, setTicker] = useState('AAPL');
  const [timeframe, setTimeframe] = useState('1y');
  const [risk, setRisk] = useState('balanced');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');
  const [auditOpen, setAuditOpen] = useState(false);

  const analyzeStock = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    if (!ticker.trim()) {
      setError('Please enter a stock ticker');
      return;
    }

    setLoading(true);
    setResults(null);
    setError('');

    try {
      const response = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ticker: ticker.trim().toUpperCase(),
          timeframe: timeframe,
          risk_preference: risk
        })
      });

      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`);
      }

      const data = await response.json();
      setResults(data);

    } catch (err: unknown) {
      setError(getErrorMessage(err) || 'An error occurred during analysis');
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = async () => {
    try {
      const response = await fetch(`${API_URL}/report/pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ticker: ticker.trim().toUpperCase(),
          timeframe: timeframe,
          risk_preference: risk
        })
      });

      if (!response.ok) {
        throw new Error('Report generation failed');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${ticker.trim().toUpperCase()}_report.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

    } catch (err: unknown) {
      setError('Failed to download report: ' + getErrorMessage(err));
    }
  };

  const getRecommendationColor = (rec: string) => {
    switch (rec?.toLowerCase()) {
      case 'strong buy':
      case 'buy': return 'from-emerald-400 to-emerald-600 shadow-emerald-500/30';
      case 'hold': return 'from-amber-400 to-amber-600 shadow-amber-500/30';
      case 'sell':
      case 'strong sell': return 'from-rose-400 to-rose-600 shadow-rose-500/30';
      default: return 'from-slate-400 to-slate-600 shadow-slate-500/30';
    }
  };

  const formatExplanation = (text: string) => {
    if (!text) return 'No explanation available';

    return text.split('\n\n').map((paragraph, idx) => {
      const formattedPara = paragraph.split('\n').map((line, lineIdx) => {
        // Handle bold text
        const parts = line.split(/(\*\*.*?\*\*)/);
        return (
          <React.Fragment key={lineIdx}>
            {parts.map((part, pIdx) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={pIdx} className="font-semibold text-slate-800 dark:text-slate-200">{part.slice(2, -2)}</strong>;
              }
              return part;
            })}
            {lineIdx < paragraph.split('\n').length - 1 && <br />}
          </React.Fragment>
        );
      });

      return <p key={idx} className="mb-4 text-slate-600 dark:text-slate-300 leading-relaxed">{formattedPara}</p>;
    });
  };

  // Process data for charts — only include agents with real (non-null) scores
  const getAgentChartData = () => {
    if (!results) return [];
    return [
      { name: 'Fundamental', value: results.fundamental_score?.score, fullMark: 100 },
      { name: 'Technical', value: results.technical_score?.score, fullMark: 100 },
      { name: 'Sentiment', value: results.sentiment_score?.score, fullMark: 100 },
      { name: 'Governance', value: results.governance_score?.score, fullMark: 100 },
      { name: 'PEAD', value: results.pead_score?.score, fullMark: 100 },
      { name: 'Financial', value: results.financial_health_score?.score, fullMark: 100 },
      { name: 'Risk', value: results.risk_score?.score, fullMark: 100 },
      { name: 'Macro', value: results.macro_score?.score, fullMark: 100 },
      { name: 'Insider', value: results.insider_score?.score, fullMark: 100 },
    ].filter(item => item.value != null && item.value > 0);
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'success':
        return <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"><CheckCircle size={10} />OK</span>;
      case 'partial':
        return <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500 border border-amber-500/20"><AlertCircle size={10} />PARTIAL</span>;
      case 'failed':
        return <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-500 border border-rose-500/20"><XCircle size={10} />FAILED</span>;
      default:
        return null;
    }
  };

  const getDecision = () => {
    if (!results) return null;
    const reliability = results.system_debug_audit?.reliability_score ?? results.confidence * 100;
    const reliabilityLabel =
      reliability >= 70 ? 'High' :
      reliability >= 40 ? 'Medium' : 'Low';

    return results.final_decision ?? {
      verdict: results.recommendation,
      score: results.final_score,
      reliability,
      reliability_label: reliabilityLabel,
      reason: `${results.recommendation} with a ${results.final_score.toFixed(1)}/100 score and ${reliabilityLabel.toLowerCase()} reliability.`,
      positive_drivers: [],
      negative_drivers: [],
      missing_signals: results.system_debug_audit?.excluded_from_score ?? []
    };
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 font-sans text-slate-900 dark:text-slate-100 selection:bg-indigo-500/30">
      {/* Background gradients */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-500/20 blur-[128px] rounded-full mix-blend-multiply dark:mix-blend-screen opacity-70 animate-blob"></div>
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-purple-500/20 blur-[128px] rounded-full mix-blend-multiply dark:mix-blend-screen opacity-70 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-1/3 w-96 h-96 bg-blue-500/20 blur-[128px] rounded-full mix-blend-multiply dark:mix-blend-screen opacity-70 animate-blob animation-delay-4000"></div>
      </div>

      <div className="container relative z-10 max-w-6xl mx-auto px-4 py-12 md:py-20">

        {/* Header Section */}
        <header className="text-center mb-16 space-y-4">
          <div className="absolute top-0 right-4 flex gap-4">
            <Link href="/" className="px-4 py-2 font-semibold text-indigo-600 dark:text-indigo-400 bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200/50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors flex items-center">
              <BarChart3 size={18} className="mr-2" />
              Dashboard
            </Link>
            <Link href="/portfolio" className="px-4 py-2 font-semibold text-slate-600 dark:text-slate-400 bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200/50 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors flex items-center">
              <Briefcase size={18} className="mr-2" />
              Portfolio
            </Link>
          </div>

          <div className="inline-flex items-center justify-center p-3 bg-white dark:bg-slate-900 rounded-2xl shadow-xl shadow-indigo-500/10 mb-6 border border-slate-200/50 dark:border-slate-800/50 mt-12 md:mt-0">
            <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center text-white">
              <BarChart3 size={28} />
            </div>
          </div>
          <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 dark:from-indigo-400 dark:via-purple-400 dark:to-indigo-400 pb-2">
            Cash Crew
          </h1>
          <p className="text-lg md:text-xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto font-medium">
            Next-Generation Multi-Agent AI Equity Research System
          </p>
        </header>

        {/* Input Card */}
        <div className="bg-white/70 dark:bg-slate-900/70 backdrop-blur-xl rounded-3xl p-6 md:p-8 shadow-2xl shadow-slate-200/50 dark:shadow-black/50 border border-white/20 dark:border-slate-800/50 mb-12">
          <form onSubmit={analyzeStock} className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-grow">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400">
                <Search size={20} />
              </div>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="Enter stock ticker (e.g., AAPL, MSFT)"
                className="w-full pl-12 pr-4 py-4 bg-slate-100/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl text-lg font-medium focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all outline-none placeholder:text-slate-400"
              />
            </div>

            <div className="flex gap-4">
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                className="px-6 py-4 bg-slate-100/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl text-base font-medium focus:ring-2 focus:ring-indigo-500 outline-none cursor-pointer appearance-none basis-1/2 md:basis-auto"
              >
                <option value="1y">1 Year</option>
                <option value="6m">6 Months</option>
                <option value="3m">3 Months</option>
              </select>

              <select
                value={risk}
                onChange={(e) => setRisk(e.target.value)}
                className="px-6 py-4 bg-slate-100/50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-2xl text-base font-medium focus:ring-2 focus:ring-indigo-500 outline-none cursor-pointer appearance-none basis-1/2 md:basis-auto"
              >
                <option value="risk-averse">Conservative</option>
                <option value="balanced">Balanced</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="px-8 py-4 bg-slate-900 dark:bg-indigo-600 hover:bg-slate-800 dark:hover:bg-indigo-500 text-white rounded-2xl font-bold text-lg transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5 disabled:opacity-70 disabled:cursor-not-allowed disabled:transform-none flex items-center justify-center min-w-[160px]"
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin mr-2" size={20} />
                  Analyzing...
                </>
              ) : (
                'Analyze'
              )}
            </button>
          </form>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-50/80 dark:bg-red-900/20 backdrop-blur-md text-red-600 dark:text-red-400 p-6 rounded-2xl mb-8 border border-red-200 dark:border-red-900/50 flex items-start shadow-sm">
            <ShieldAlert className="mr-3 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-lg mb-1">Analysis Error</h3>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 space-y-6">
            <div className="relative w-24 h-24">
              <div className="absolute inset-0 rounded-full border-t-4 border-indigo-500 animate-spin"></div>
              <div className="absolute inset-2 rounded-full border-r-4 border-purple-500 animate-spin automation-delay-150"></div>
              <div className="absolute inset-4 rounded-full border-b-4 border-blue-500 animate-spin automation-delay-300"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <BarChart3 className="text-indigo-500 animate-pulse" size={24} />
              </div>
            </div>
            <div className="text-center space-y-2">
              <h3 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 to-purple-600 dark:from-indigo-400 dark:to-purple-400">
                Orchestrating AI Agents
              </h3>
              <p className="text-slate-500 dark:text-slate-400 font-medium">Gathering data, running models, synthesizing insights...</p>
            </div>
          </div>
        )}

        {/* Results Section */}
        {results && !loading && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700 block">
            {(() => {
              const decision = getDecision();
              if (!decision) return null;

              return (
                <div className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl rounded-2xl p-6 shadow-xl border border-slate-100 dark:border-slate-800">
                  <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6">
                    <div>
                      <p className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Final Verdict</p>
                      <div className={`inline-flex items-center px-5 py-3 rounded-xl text-white font-black text-3xl bg-gradient-to-br ${getRecommendationColor(decision.verdict)}`}>
                        {decision.verdict}
                      </div>
                      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Score</p>
                          <p className="text-2xl font-black text-slate-800 dark:text-white">{decision.score.toFixed(1)}</p>
                        </div>
                        <div>
                          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Reliability</p>
                          <p className="text-2xl font-black text-slate-800 dark:text-white">{decision.reliability_label}</p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <p className="text-slate-700 dark:text-slate-300 font-medium">{decision.reason}</p>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                          <p className="text-xs font-bold uppercase tracking-wider text-emerald-500 mb-2">Top positives</p>
                          <ul className="space-y-1.5">
                            {(decision.positive_drivers?.length ? decision.positive_drivers : ['No strong positive driver surfaced.']).slice(0, 3).map((item: string, i: number) => (
                              <li key={i} className="text-xs text-slate-600 dark:text-slate-400">{item}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="text-xs font-bold uppercase tracking-wider text-rose-500 mb-2">Top concerns</p>
                          <ul className="space-y-1.5">
                            {(decision.negative_drivers?.length ? decision.negative_drivers : ['No major negative driver surfaced.']).slice(0, 3).map((item: string, i: number) => (
                              <li key={i} className="text-xs text-slate-600 dark:text-slate-400">{item}</li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="text-xs font-bold uppercase tracking-wider text-amber-500 mb-2">Missing signals</p>
                          <ul className="space-y-1.5">
                            {(decision.missing_signals?.length ? decision.missing_signals : ['None flagged.']).slice(0, 3).map((item: string, i: number) => (
                              <li key={i} className="text-xs text-slate-600 dark:text-slate-400">{item}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Top row: Recommendation and Radar Chart */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Recommendation Card */}
              <div className={`col-span-1 bg-gradient-to-br ${getRecommendationColor(results.recommendation)} rounded-3xl p-8 shadow-2xl text-white flex flex-col justify-center items-center text-center relative overflow-hidden`}>
                <div className="absolute top-0 right-0 p-3 opacity-20">
                  <TrendingUp size={120} />
                </div>

                <h3 className="text-xl font-medium opacity-90 mb-2 z-10 uppercase tracking-wider">{results.company_name} ({results.ticker})</h3>

                <div className="my-6 z-10">
                  <span className="text-7xl font-black tracking-tighter drop-shadow-md">
                    {results.recommendation.toUpperCase()}
                  </span>
                </div>

                <div className="flex items-center gap-6 mt-4 z-10 bg-black/10 backdrop-blur-sm px-6 py-3 rounded-full">
                  <div className="flex flex-col items-center">
                    <span className="text-sm font-medium opacity-80 uppercase tracking-widest text-[10px]">Score</span>
                    <span className="text-3xl font-bold">{results.final_score.toFixed(1)}</span>
                  </div>
                  <div className="w-px h-10 bg-white/20"></div>
                  <div className="flex flex-col items-center">
                    <span className="text-sm font-medium opacity-80 uppercase tracking-widest text-[10px]">Confidence</span>
                    <span className="text-3xl font-bold">{(results.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>

              {/* Radar Chart Card */}
              <div className="col-span-1 lg:col-span-2 bg-white/70 dark:bg-slate-900/70 backdrop-blur-xl rounded-3xl p-6 shadow-xl border border-white/20 dark:border-slate-800/50">
                <h3 className="text-xl font-bold mb-6 flex items-center text-slate-800 dark:text-slate-100">
                  <BarChart3 className="mr-2 text-indigo-500" />
                  Agent Consensus Breakdown
                </h3>
                <div className="h-[300px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="80%" data={getAgentChartData()}>
                      <PolarGrid strokeOpacity={0.2} />
                      <PolarAngleAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 12, fontWeight: 600 }} />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#94a3b8' }} />
                      <Radar
                        name="Score"
                        dataKey="value"
                        stroke="#6366f1"
                        strokeWidth={3}
                        fill="#6366f1"
                        fillOpacity={0.3}
                      />
                      <Tooltip
                        contentStyle={{
                          borderRadius: '12px',
                          border: 'none',
                          boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
                          backgroundColor: 'rgba(255, 255, 255, 0.95)',
                          color: '#0f172a'
                        }}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Individual Agent Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {[
                { name: 'Fundamental', data: results.fundamental_score, icon: '📊' },
                { name: 'Technical', data: results.technical_score, icon: '📈' },
                { name: 'Sentiment', data: results.sentiment_score, icon: '📰' },
                { name: 'Governance', data: results.governance_score, icon: '🏛️' },
                { name: 'PEAD', data: results.pead_score, icon: '🚀' },
                { name: 'Financial Health', data: results.financial_health_score, icon: '🏥' },
                { name: 'Risk', data: results.risk_score, icon: '🛡️' },
                { name: 'Macro', data: results.macro_score, icon: '🌍' },
                { name: 'Insider', data: results.insider_score, icon: '💼' }
              ].map((agent, index) => {
                const score = agent.data?.score ?? null;
                const signals = agent.data?.signals ?? [];
                const risks = agent.data?.risks ?? [];
                const warnings = agent.data?.warnings ?? [];
                const isFailed = !agent.data || score == null || agent.data.status === 'failed';
                const scoreColor =
                  isFailed ? 'text-slate-400' :
                  score >= 70 ? 'text-emerald-500' :
                  score >= 40 ? 'text-amber-500' : 'text-rose-500';
                const bgGradient =
                  isFailed ? 'from-slate-500/5 to-transparent' :
                  score >= 70 ? 'from-emerald-500/10 to-transparent' :
                  score >= 40 ? 'from-amber-500/10 to-transparent' : 'from-rose-500/10 to-transparent';

                return (
                  <div key={index} className={`bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl p-5 shadow-lg border transition-all hover:shadow-xl hover:-translate-y-1 group relative overflow-hidden ${isFailed ? 'border-rose-200/50 dark:border-rose-900/30 opacity-70' : 'border-slate-100 dark:border-slate-800'}`}>
                    <div className={`absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl ${bgGradient} rounded-bl-full -z-10 transition-opacity opacity-50 group-hover:opacity-100`}></div>

                    <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">{agent.icon}</span>
                        <h4 className="font-semibold text-slate-800 dark:text-slate-100 text-sm">{agent.name}</h4>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        {getStatusBadge(agent.data?.status)}
                        <span className={`text-2xl font-black ${scoreColor}`}>
                          {isFailed ? '—' : score.toFixed(1)}
                        </span>
                      </div>
                    </div>

                    <div className="mb-3">
                      <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 mb-1 overflow-hidden">
                        <div
                          className={`h-1.5 rounded-full transition-all ${scoreColor.replace('text-', 'bg-')}`}
                          style={{ width: isFailed ? '0%' : `${score}%` }}
                        ></div>
                      </div>
                      <div className="flex justify-between text-xs text-slate-500">
                        <span>{agent.data?.data_source ? `📡 ${agent.data.data_source}` : 'Score'}</span>
                        <span className="font-medium">Conf: {agent.data ? (agent.data.confidence * 100).toFixed(0) : 0}%</span>
                      </div>
                    </div>

                    <p className="text-xs text-slate-600 dark:text-slate-400 line-clamp-2 leading-relaxed mb-2">
                      {agent.data?.explanation || (isFailed ? 'Agent failed — excluded from score.' : 'No explanation.')}
                    </p>

                    {/* Signals */}
                    {signals.length > 0 && (
                      <div className="mt-2 space-y-0.5">
                        {signals.slice(0, 2).map((s: string, i: number) => (
                          <p key={i} className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-start gap-1"><span className="mt-0.5">↑</span>{s}</p>
                        ))}
                      </div>
                    )}
                    {/* Risks */}
                    {risks.length > 0 && (
                      <div className="mt-1 space-y-0.5">
                        {risks.slice(0, 2).map((r: string, i: number) => (
                          <p key={i} className="text-[10px] text-rose-500 dark:text-rose-400 flex items-start gap-1"><span className="mt-0.5">↓</span>{r}</p>
                        ))}
                      </div>
                    )}
                    {/* Warnings */}
                    {warnings.length > 0 && (
                      <div className="mt-1">
                        {warnings.slice(0, 1).map((w: string, i: number) => (
                          <p key={i} className="text-[10px] text-amber-500 dark:text-amber-400 flex items-start gap-1"><AlertTriangle size={9} className="mt-0.5 shrink-0" />{w}</p>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* XAI Final Explanation */}
            <div className="bg-white/80 dark:bg-slate-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-xl border border-slate-100 dark:border-slate-800">
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
                <h3 className="text-2xl font-bold flex items-center gap-3 text-slate-800 dark:text-white">
                  <div className="p-2 bg-indigo-100 dark:bg-indigo-900/50 rounded-lg text-indigo-600 dark:text-indigo-400">
                    <Info size={24} />
                  </div>
                  Executive Synthesis
                </h3>

                <button
                  onClick={downloadReport}
                  className="flex items-center gap-2 px-5 py-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-xl font-medium transition-colors border border-slate-200 dark:border-slate-700"
                >
                  <Download size={18} />
                  Download PDF Report
                </button>
              </div>

              <div className="prose prose-slate dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:mb-5">
                {formatExplanation(results.xai_explanation)}
              </div>
            </div>

            {/* ── System Debug Audit Panel ── */}
            {results.system_debug_audit && (
              <div className="rounded-2xl border border-rose-200/60 dark:border-rose-900/40 bg-white/60 dark:bg-slate-900/60 backdrop-blur-xl shadow-xl overflow-hidden">
                {/* Header — always visible */}
                <button
                  onClick={() => setAuditOpen(o => !o)}
                  className="w-full flex items-center justify-between px-6 py-4 hover:bg-rose-50/50 dark:hover:bg-rose-950/20 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 bg-rose-100 dark:bg-rose-900/40 rounded-lg">
                      <ShieldAlert size={18} className="text-rose-500" />
                    </div>
                    <div className="text-left">
                      <h3 className="font-bold text-slate-800 dark:text-slate-100">System Debug Audit</h3>
                      <p className="text-xs text-slate-500">
                        {results.system_debug_audit.failed_agents} failed · {results.system_debug_audit.partial_agents} partial · Reliability: {results.system_debug_audit.reliability_score.toFixed(0)}/100
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {/* Reliability pill */}
                    <span className={`text-xs font-bold px-3 py-1 rounded-full ${
                      results.system_debug_audit.reliability_score >= 70 ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400' :
                      results.system_debug_audit.reliability_score >= 40 ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400' :
                      'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-400'
                    }`}>
                      Reliability {results.system_debug_audit.reliability_score.toFixed(0)}%
                    </span>
                    {auditOpen ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
                  </div>
                </button>

                {auditOpen && (
                  <div className="px-6 pb-6 space-y-5 border-t border-rose-100 dark:border-rose-900/30 pt-5">

                    {/* Agent Status Summary */}
                    <div className="grid grid-cols-3 gap-3">
                      <div className="text-center p-3 rounded-xl bg-emerald-50 dark:bg-emerald-900/20">
                        <p className="text-2xl font-black text-emerald-500">{results.system_debug_audit.successful_agents}</p>
                        <p className="text-xs text-slate-500 mt-0.5">Successful</p>
                      </div>
                      <div className="text-center p-3 rounded-xl bg-amber-50 dark:bg-amber-900/20">
                        <p className="text-2xl font-black text-amber-500">{results.system_debug_audit.partial_agents}</p>
                        <p className="text-xs text-slate-500 mt-0.5">Partial</p>
                      </div>
                      <div className="text-center p-3 rounded-xl bg-rose-50 dark:bg-rose-900/20">
                        <p className="text-2xl font-black text-rose-500">{results.system_debug_audit.failed_agents}</p>
                        <p className="text-xs text-slate-500 mt-0.5">Failed</p>
                      </div>
                    </div>

                    {/* Reliability Bar */}
                    <div>
                      <div className="flex justify-between text-xs font-medium text-slate-500 mb-1">
                        <span>System Reliability</span>
                        <span>{results.system_debug_audit.reliability_score.toFixed(1)} / 100</span>
                      </div>
                      <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-2.5">
                        <div
                          className={`h-2.5 rounded-full transition-all ${
                            results.system_debug_audit.reliability_score >= 70 ? 'bg-emerald-500' :
                            results.system_debug_audit.reliability_score >= 40 ? 'bg-amber-500' : 'bg-rose-500'
                          }`}
                          style={{ width: `${results.system_debug_audit.reliability_score}%` }}
                        />
                      </div>
                    </div>

                    {/* Excluded from Score */}
                    {results.system_debug_audit.excluded_from_score?.length > 0 && (
                      <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-xl border border-amber-200/50 dark:border-amber-800/40">
                        <p className="text-xs font-bold text-amber-700 dark:text-amber-400 mb-1">⚠️ Excluded from final score</p>
                        <p className="text-xs text-slate-600 dark:text-slate-400">{results.system_debug_audit.excluded_from_score.join(', ')}</p>
                      </div>
                    )}

                    {/* Broken Agents */}
                    {results.system_debug_audit.broken_agents?.length > 0 && (
                      <div>
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Broken / Partial Agents</h4>
                        <div className="space-y-2">
                          {results.system_debug_audit.broken_agents.map((a: BrokenAgent, i: number) => (
                            <div key={i} className={`p-3 rounded-xl border text-xs ${
                              a.status === 'failed'
                                ? 'bg-rose-50 dark:bg-rose-900/20 border-rose-200/50 dark:border-rose-800/40'
                                : 'bg-amber-50 dark:bg-amber-900/20 border-amber-200/50 dark:border-amber-800/40'
                            }`}>
                              <div className="flex items-center gap-2 mb-0.5">
                                {a.status === 'failed' ? <XCircle size={12} className="text-rose-500" /> : <AlertCircle size={12} className="text-amber-500" />}
                                <span className="font-bold text-slate-700 dark:text-slate-300">{a.agent_name}</span>
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${a.status === 'failed' ? 'bg-rose-200 text-rose-700 dark:bg-rose-800 dark:text-rose-300' : 'bg-amber-200 text-amber-700 dark:bg-amber-800 dark:text-amber-300'}`}>{a.status.toUpperCase()}</span>
                              </div>
                              <p className="text-slate-500 dark:text-slate-400 pl-5">{a.reason}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Data Gaps */}
                    {results.system_debug_audit.data_gaps?.length > 0 && (
                      <div>
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Data Gaps</h4>
                        <div className="space-y-1.5">
                          {results.system_debug_audit.data_gaps.map((g: DataGap, i: number) => (
                            <div key={i} className="flex items-start gap-2 text-xs p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200/50 dark:border-slate-700/50">
                              <span className={`mt-0.5 shrink-0 w-2 h-2 rounded-full ${ g.severity === 'high' ? 'bg-rose-500' : g.severity === 'medium' ? 'bg-amber-500' : 'bg-slate-400'}`} />
                              <div>
                                <span className="font-semibold text-slate-700 dark:text-slate-300">{g.category.replace(/_/g,' ')}: </span>
                                <span className="text-slate-500">{g.description}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Invalid Outputs */}
                    {results.system_debug_audit.invalid_outputs?.length > 0 && (
                      <div>
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Suspicious Outputs</h4>
                        <div className="space-y-1">
                          {results.system_debug_audit.invalid_outputs.map((o: string, i: number) => (
                            <p key={i} className="text-xs text-rose-600 dark:text-rose-400 flex items-start gap-1.5 p-2 rounded-lg bg-rose-50 dark:bg-rose-900/20">
                              <AlertTriangle size={11} className="mt-0.5 shrink-0" />{o}
                            </p>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recommendations */}
                    {results.system_debug_audit.recommendations?.length > 0 && (
                      <div>
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Recommendations</h4>
                        <ul className="space-y-1.5">
                          {results.system_debug_audit.recommendations.map((r: string, i: number) => (
                            <li key={i} className="text-xs text-slate-600 dark:text-slate-400 flex items-start gap-2">
                              <span className="text-indigo-500 mt-0.5 shrink-0">→</span>{r}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <p className="text-[10px] text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-800">
                      Audit generated at {new Date(results.system_debug_audit.audit_timestamp).toLocaleTimeString()} · Final stance: <strong>{results.system_debug_audit.final_stance?.toUpperCase()}</strong>
                    </p>
                  </div>
                )}
              </div>
            )}

          </div>
        )}
        <p className="mt-12 text-center text-xs text-slate-500 dark:text-slate-500 max-w-3xl mx-auto">
          CashCrew is an educational AI research assistant. It does not provide financial advice. Users should verify outputs before making investment decisions.
        </p>
      </div>
    </div>
  );
}
