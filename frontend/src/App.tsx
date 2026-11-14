import React, { useState, useEffect, useMemo } from 'react';
import { Search, Filter, AlertTriangle, Users, Clock, CheckCircle2, Building, RefreshCw } from 'lucide-react';
import { api, FacilityStatus } from './services/api';
import { Navbar } from './components/Navbar';
import { FacilityCard } from './components/FacilityCard';
import { FacilityDetail } from './components/FacilityDetail';
import { WaitTimePredictor } from './components/WaitTimePredictor';
import { PeakGuides } from './components/PeakGuides';
import { AnalyticsHub } from './components/AnalyticsHub';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'detail' | 'predictor' | 'peaks' | 'analytics'>('overview');
  const [selectedFacilityId, setSelectedFacilityId] = useState<string>('FAC_02');
  const [facilities, setFacilities] = useState<FacilityStatus[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [countdown, setCountdown] = useState<number>(30);
  
  // Search & Type Filter State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedType, setSelectedType] = useState<string>('All');
  
  // Dark mode
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return localStorage.getItem('smartqueue_theme') === 'dark' ||
      (!('smartqueue_theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches);
  });

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('smartqueue_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('smartqueue_theme', 'light');
    }
  }, [darkMode]);

  // Fetch facilities
  const loadFacilities = async (showRefreshSpinner = false) => {
    if (showRefreshSpinner) setIsRefreshing(true);
    try {
      const data = await api.getFacilities();
      setFacilities(data);
      if (data.length > 0) {
        setLastUpdated(data[0].last_updated);
      }
    } catch (err) {
      console.error('Error fetching facilities:', err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
      setCountdown(30);
    }
  };

  // Initial load
  useEffect(() => {
    loadFacilities();
  }, []);

  // Polling every 30 seconds + countdown timer
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          loadFacilities();
          return 30;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // Facility Types available
  const facilityTypes = useMemo(() => {
    const types = new Set(facilities.map(f => f.facility_type));
    return ['All', ...Array.from(types)];
  }, [facilities]);

  // Filtered facilities
  const filteredFacilities = useMemo(() => {
    return facilities.filter(fac => {
      const matchesSearch = fac.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            fac.location.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            fac.facility_type.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesType = selectedType === 'All' || fac.facility_type === selectedType;
      return matchesSearch && matchesType;
    });
  }, [facilities, searchQuery, selectedType]);

  // Overall Campus Stats
  const campusStats = useMemo(() => {
    const totalInQueue = facilities.reduce((acc, f) => acc + (f.current_queue_length || 0), 0);
    const activeCounters = facilities.reduce((acc, f) => acc + (f.counters_open || 0), 0);
    const openFacilities = facilities.filter(f => f.crowd_level !== 'Closed').length;
    const avgWait = openFacilities > 0 
      ? (facilities.filter(f => f.crowd_level !== 'Closed').reduce((acc, f) => acc + f.estimated_wait_time_min, 0) / openFacilities).toFixed(1)
      : '0.0';
    const peakFacilities = facilities.filter(f => f.is_peak);
    return { totalInQueue, activeCounters, avgWait, peakFacilities };
  }, [facilities]);

  const handleSelectFacility = (facId: string) => {
    setSelectedFacilityId(facId);
    setActiveTab('detail');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        lastUpdated={lastUpdated}
        isRefreshing={isRefreshing}
        onRefresh={() => loadFacilities(true)}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        countdown={countdown}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* TAB 1: LIVE OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="space-y-8 animate-fadeIn">
            {/* Hero / Quick Stats Bar */}
            <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 border border-slate-200/80 dark:border-slate-800 shadow-sm">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div>
                  <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/50 dark:border-indigo-800/50 mb-3">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 mr-2 animate-ping"></span>
                    Live Campus Queue Monitor (30s Polling)
                  </div>
                  <h1 className="text-3xl sm:text-4xl font-black tracking-tight text-slate-900 dark:text-white">
                    Campus Queue Prediction & Traffic
                  </h1>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 max-w-2xl">
                    View real-time waiting times, active counters, and machine learning forecasts across all main university service desks and cafeterias.
                  </p>
                </div>

                {/* Campus Quick KPI Pills */}
                <div className="grid grid-cols-3 gap-3 sm:gap-4 flex-shrink-0">
                  <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-center">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Total In Queue</span>
                    <div className="text-2xl font-black text-slate-900 dark:text-white mt-0.5 flex items-center justify-center">
                      <Users className="w-4 h-4 mr-1 text-indigo-500" />
                      {campusStats.totalInQueue}
                    </div>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-center">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Campus Avg Wait</span>
                    <div className="text-2xl font-black text-indigo-600 dark:text-indigo-400 mt-0.5 flex items-center justify-center">
                      <Clock className="w-4 h-4 mr-1" />
                      {campusStats.avgWait}m
                    </div>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-center">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Staffed Desks</span>
                    <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-0.5 flex items-center justify-center">
                      <CheckCircle2 className="w-4 h-4 mr-1" />
                      {campusStats.activeCounters}
                    </div>
                  </div>
                </div>
              </div>

              {/* Peak Alert Banner if any facility is at peak */}
              {campusStats.peakFacilities.length > 0 && (
                <div className="mt-6 p-4 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 flex items-center justify-between text-xs sm:text-sm">
                  <div className="flex items-center space-x-2">
                    <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0" />
                    <span>
                      <strong>High Traffic Alert: </strong>
                      {campusStats.peakFacilities.map(f => f.name).join(', ')} currently experiencing peak rush lines.
                    </span>
                  </div>
                  <button
                    onClick={() => setActiveTab('peaks')}
                    className="font-bold underline text-amber-900 dark:text-amber-200 hover:text-amber-700 whitespace-nowrap ml-2"
                  >
                    View Avoidance Tips →
                  </button>
                </div>
              )}
            </div>

            {/* Filter and Search Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              {/* Search Box */}
              <div className="relative flex-1 max-w-md">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search facility name, location, or service type..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl py-2.5 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder-slate-400 text-slate-900 dark:text-white shadow-sm"
                />
              </div>

              {/* Category Filter Pills */}
              <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 scrollbar-none text-xs">
                <Filter className="w-3.5 h-3.5 text-slate-400 mr-1 flex-shrink-0" />
                {facilityTypes.map((type) => (
                  <button
                    key={type}
                    onClick={() => setSelectedType(type)}
                    className={`px-3 py-1.5 rounded-xl font-semibold whitespace-nowrap transition ${
                      selectedType === type
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            {/* Facility Cards Grid */}
            {loading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-64 rounded-2xl bg-white dark:bg-slate-900 animate-pulse border border-slate-200 dark:border-slate-800"></div>
                ))}
              </div>
            ) : filteredFacilities.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredFacilities.map((fac) => (
                  <FacilityCard
                    key={fac.facility_id}
                    facility={fac}
                    onSelect={handleSelectFacility}
                  />
                ))}
              </div>
            ) : (
              <div className="p-12 text-center bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800">
                <Building className="w-10 h-10 text-slate-400 mx-auto mb-2" />
                <h3 className="text-base font-bold text-slate-700 dark:text-slate-300">No facilities match your search</h3>
                <p className="text-xs text-slate-400 mt-1">Try resetting the filter or search query.</p>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: FACILITY DETAIL & FORECAST */}
        {activeTab === 'detail' && (
          <FacilityDetail
            selectedFacilityId={selectedFacilityId}
            facilities={facilities}
            onSelectFacility={(id) => setSelectedFacilityId(id)}
            onBack={() => setActiveTab('overview')}
          />
        )}

        {/* TAB 3: CUSTOM WAIT TIME PREDICTOR */}
        {activeTab === 'predictor' && (
          <WaitTimePredictor facilities={facilities} />
        )}

        {/* TAB 4: PEAK PERIODS & ADVICE */}
        {activeTab === 'peaks' && (
          <PeakGuides />
        )}

        {/* TAB 5: ANALYTICS & ML PERFORMANCE HUB */}
        {activeTab === 'analytics' && (
          <AnalyticsHub />
        )}
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200 dark:border-slate-800/80 bg-white dark:bg-slate-900 py-6 text-xs text-slate-500 dark:text-slate-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>Intelligent Queue Prediction & Management System — Supervised Learning Course Project</span>
          </div>
          <div className="flex items-center space-x-4">
            <span>FastAPI Backend</span>
            <span>•</span>
            <span>XGBoost ML Pipeline</span>
            <span>•</span>
            <span>React + Vite</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
