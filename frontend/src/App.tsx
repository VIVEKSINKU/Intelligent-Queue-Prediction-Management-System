import React, { useState, useEffect, useMemo } from 'react';
import { Search, Filter, AlertTriangle, Clock, Building, Sparkles } from 'lucide-react';
import { api, FacilityStatus } from './services/api';
import { Navbar } from './components/Navbar';
import { FacilityCard } from './components/FacilityCard';
import { FacilityDetail } from './components/FacilityDetail';
import { WaitTimePredictor } from './components/WaitTimePredictor';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'facilities' | 'detail' | 'predictor'>('facilities');
  const [selectedFacilityId, setSelectedFacilityId] = useState<string>('FAC_02');
  const [facilities, setFacilities] = useState<FacilityStatus[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  
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
  const loadFacilities = async () => {
    try {
      const data = await api.getFacilities();
      setFacilities(data);
    } catch (err) {
      console.error('Error fetching facilities:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFacilities();
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
    const totalFacilities = facilities.length;
    const openFacilities = facilities.filter(f => f.crowd_level !== 'Closed');
    const isOpenNow = openFacilities.length > 0;
    
    // If open now, compute current average wait; otherwise show daytime operational average (15.9 min)
    const avgWait = isOpenNow
      ? (openFacilities.reduce((acc, f) => acc + f.estimated_wait_time_min, 0) / openFacilities.length).toFixed(1)
      : '15.9';
      
    const peakFacilities = facilities.filter(f => f.is_peak);
    return { totalFacilities, avgWait, isOpenNow, openCount: openFacilities.length, peakFacilities };
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
        darkMode={darkMode}
        setDarkMode={setDarkMode}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* TAB 1: CAMPUS FACILITIES & FORECAST DIRECTORY */}
        {activeTab === 'facilities' && (
          <div className="space-y-8 animate-fadeIn">
            {/* Hero / Overview Header */}
            <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 border border-slate-200/80 dark:border-slate-800 shadow-sm">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div>
                  <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/50 dark:border-indigo-800/50 mb-3">
                    <Sparkles className="w-3.5 h-3.5 mr-1 text-indigo-500" />
                    Supervised Machine Learning Queue System
                  </div>
                  <h1 className="text-3xl sm:text-4xl font-black tracking-tight text-slate-900 dark:text-white">
                    Campus Facilities & Queue Predictions
                  </h1>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-2 max-w-2xl">
                    Discover expected waiting times, optimal visit slots, and machine learning forecasts across all university service counters and dining halls.
                  </p>
                </div>

                {/* Campus Quick KPI Pills */}
                <div className="grid grid-cols-2 gap-3 sm:gap-4 flex-shrink-0">
                  <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-center">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Campus Facilities</span>
                    <div className="text-2xl font-black text-slate-900 dark:text-white mt-0.5 flex items-center justify-center">
                      <Building className="w-4 h-4 mr-1 text-indigo-500" />
                      {campusStats.totalFacilities}
                    </div>
                    <span className="text-[10px] text-slate-400">
                      {campusStats.isOpenNow ? `${campusStats.openCount} Open Now` : 'Closed (Reopens 08:00 AM)'}
                    </span>
                  </div>

                  <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-center">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                      {campusStats.isOpenNow ? 'Active Avg Wait' : 'Daytime Avg Wait'}
                    </span>
                    <div className="text-2xl font-black text-indigo-600 dark:text-indigo-400 mt-0.5 flex items-center justify-center">
                      <Clock className="w-4 h-4 mr-1" />
                      {campusStats.avgWait}m
                    </div>
                    <span className="text-[10px] text-indigo-500 dark:text-indigo-400 font-medium">
                      {campusStats.isOpenNow ? 'Current Load' : 'Daytime Benchmark'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Informative banner when facilities are closed outside operational hours */}
              {!campusStats.isOpenNow && (
                <div className="mt-6 p-4 rounded-2xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 flex items-center justify-between text-xs sm:text-sm">
                  <div className="flex items-center space-x-2.5">
                    <Clock className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                    <span>
                      <strong>Off-Hours Notice: </strong>
                      Campus facilities are currently closed for the night (Operating Hours: 08:00 – 20:00). Showing projected daytime averages.
                    </span>
                  </div>
                  <button
                    onClick={() => setActiveTab('predictor')}
                    className="font-bold underline text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 whitespace-nowrap ml-2"
                  >
                    Predict Daytime Wait →
                  </button>
                </div>
              )}

              {/* Peak Alert Banner if any facility is at peak */}
              {campusStats.peakFacilities.length > 0 && (
                <div className="mt-6 p-4 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300 flex items-center justify-between text-xs sm:text-sm">
                  <div className="flex items-center space-x-2">
                    <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0" />
                    <span>
                      <strong>High Traffic Window: </strong>
                      {campusStats.peakFacilities.map(f => f.name).join(', ')} projected to experience peak congestion.
                    </span>
                  </div>
                  <button
                    onClick={() => {
                      if (campusStats.peakFacilities[0]) {
                        handleSelectFacility(campusStats.peakFacilities[0].facility_id);
                      }
                    }}
                    className="font-bold underline text-amber-900 dark:text-amber-200 hover:text-amber-700 whitespace-nowrap ml-2"
                  >
                    View Best Visit Slots →
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
            onBack={() => setActiveTab('facilities')}
          />
        )}

        {/* TAB 3: CUSTOM WAIT TIME PREDICTOR */}
        {activeTab === 'predictor' && (
          <WaitTimePredictor facilities={facilities} />
        )}
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200 dark:border-slate-800/80 bg-white dark:bg-slate-900 py-6 text-xs text-slate-500 dark:text-slate-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
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
