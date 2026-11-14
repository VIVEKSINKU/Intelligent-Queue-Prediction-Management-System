import React from 'react';
import { Clock, RefreshCw, Sun, Moon, Sparkles, Building2, Calendar, LineChart, ShieldAlert } from 'lucide-react';

interface NavbarProps {
  activeTab: 'overview' | 'detail' | 'predictor' | 'peaks' | 'analytics';
  setActiveTab: (tab: 'overview' | 'detail' | 'predictor' | 'peaks' | 'analytics') => void;
  lastUpdated: string;
  isRefreshing: boolean;
  onRefresh: () => void;
  darkMode: boolean;
  setDarkMode: (val: boolean) => void;
  countdown: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  lastUpdated,
  isRefreshing,
  onRefresh,
  darkMode,
  setDarkMode,
  countdown
}) => {
  return (
    <header className="sticky top-0 z-50 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('overview')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-sky-400 flex items-center justify-center shadow-lg shadow-indigo-500/20 text-white font-bold text-xl">
              Q
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-indigo-600 to-sky-500 bg-clip-text text-transparent dark:from-indigo-400 dark:to-sky-300">
                  SmartQueue
                </span>
                <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1 animate-pulse"></span>
                  Live Replay
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 hidden sm:block">
                Intelligent Queue Prediction & Management
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="hidden md:flex space-x-1 lg:space-x-2">
            {[
              { id: 'overview', label: 'Live Overview', icon: Building2 },
              { id: 'detail', label: 'Facility Forecast', icon: Calendar },
              { id: 'predictor', label: 'Predict Wait', icon: Sparkles },
              { id: 'peaks', label: 'Peak Advice', icon: ShieldAlert },
              { id: 'analytics', label: 'ML Analytics', icon: LineChart }
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`inline-flex items-center px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shadow-sm border border-indigo-200/50 dark:border-indigo-800/50'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60'
                  }`}
                >
                  <Icon className="w-4 h-4 mr-1.5" />
                  {tab.label}
                </button>
              );
            })}
          </nav>

          {/* Refresh counter & Dark Mode Toggle */}
          <div className="flex items-center space-x-3">
            <div className="hidden lg:flex flex-col items-end text-xs text-slate-500 dark:text-slate-400">
              <span className="flex items-center">
                <Clock className="w-3.5 h-3.5 mr-1 text-slate-400" />
                Updated: {lastUpdated ? lastUpdated.split(' ')[1] : 'Syncing...'}
              </span>
              <span className="text-[11px] text-indigo-500 dark:text-indigo-400 font-mono">
                Refresh in {countdown}s
              </span>
            </div>

            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              title="Refresh Queue Status"
              className="p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-indigo-600' : ''}`} />
            </button>

            <button
              onClick={() => setDarkMode(!darkMode)}
              title="Toggle theme"
              className="p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:text-amber-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            >
              {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Subnav */}
        <div className="flex md:hidden overflow-x-auto py-2 space-x-1 border-t border-slate-100 dark:border-slate-800 text-xs scrollbar-none">
          {[
            { id: 'overview', label: 'Overview' },
            { id: 'detail', label: 'Forecast' },
            { id: 'predictor', label: 'Predict' },
            { id: 'peaks', label: 'Peak Advice' },
            { id: 'analytics', label: 'ML Hub' }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-3 py-1.5 rounded-md whitespace-nowrap font-medium ${
                activeTab === tab.id
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
};
