import React, { useState, useEffect } from 'react';
import { ShieldAlert, Lightbulb, Clock, CheckCircle2, ChevronRight, Zap } from 'lucide-react';
import { api, PeakPeriod, RecommendationItem } from '../services/api';

export const PeakGuides: React.FC = () => {
  const [peaks, setPeaks] = useState<PeakPeriod[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterFacility, setFilterFacility] = useState<string>('all');

  useEffect(() => {
    async function loadData() {
      try {
        const [peakData, recData] = await Promise.all([
          api.getPeakPeriods(),
          api.getRecommendations()
        ]);
        setPeaks(peakData);
        setRecommendations(recData);
      } catch (err) {
        console.error('Error loading peaks & recommendations:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'Critical':
        return 'bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300 border-rose-300 dark:border-rose-800';
      case 'High':
        return 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border-amber-300 dark:border-amber-800';
      default:
        return 'bg-blue-100 text-blue-800 dark:bg-blue-950/80 dark:text-blue-300 border-blue-300 dark:border-blue-800';
    }
  };

  const filteredPeaks = filterFacility === 'all' 
    ? peaks 
    : peaks.filter(p => p.facility_id === filterFacility);

  return (
    <div className="space-y-10 animate-fadeIn">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto space-y-2">
        <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 border border-rose-200/50 dark:border-rose-800/50">
          <ShieldAlert className="w-3.5 h-3.5 mr-1 text-rose-500" />
          Queue Avoidance & Strategy
        </div>
        <h1 className="text-3xl font-black text-slate-900 dark:text-white">
          Peak Periods & Student Advisories
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Proactively plan your visits around university bottleneck hours and take advantage of express counter throughput tips.
        </p>
      </div>

      {/* Recommendations & Fast-Track Section */}
      <div className="space-y-4">
        <div className="flex items-center space-x-2">
          <span className="p-2 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
            <Lightbulb className="w-5 h-5" />
          </span>
          <div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">
              Smart Campus Queue Tips
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Live efficiency recommendations to shave 10-25 minutes off your wait time
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {recommendations.map((rec) => (
            <div
              key={rec.id}
              className="bg-white dark:bg-slate-900 rounded-2xl p-5 border border-slate-200/80 dark:border-slate-800 shadow-sm hover:shadow-md transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                    {rec.facility_name}
                  </span>
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${
                    rec.priority === 'Urgent' ? 'bg-rose-50 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400' : 'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400'
                  }`}>
                    {rec.category}
                  </span>
                </div>
                <h3 className="font-bold text-slate-900 dark:text-white text-sm mb-2 flex items-center">
                  <Zap className="w-4 h-4 mr-1.5 text-amber-500 flex-shrink-0" />
                  {rec.title}
                </h3>
                <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                  {rec.tip_text}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 text-[11px] font-medium text-emerald-600 dark:text-emerald-400 flex items-center">
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                Verified Student Advice
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recurring Peak Periods Schedule */}
      <div className="space-y-4 pt-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <span className="p-2 rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400">
              <Clock className="w-5 h-5" />
            </span>
            <div>
              <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                Detected Campus Peak Bottlenecks
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Pattern-identified surges by academic timetable and service schedules
              </p>
            </div>
          </div>

          {/* Filter pills */}
          <div className="flex flex-wrap gap-1.5 text-xs">
            <button
              onClick={() => setFilterFacility('all')}
              className={`px-3 py-1.5 rounded-xl font-medium transition ${
                filterFacility === 'all'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'
              }`}
            >
              All Facilities
            </button>
            <button
              onClick={() => setFilterFacility('FAC_02')}
              className={`px-3 py-1.5 rounded-xl font-medium transition ${
                filterFacility === 'FAC_02'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'
              }`}
            >
              Cafeteria
            </button>
            <button
              onClick={() => setFilterFacility('FAC_01')}
              className={`px-3 py-1.5 rounded-xl font-medium transition ${
                filterFacility === 'FAC_01'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'
              }`}
            >
              Admin
            </button>
            <button
              onClick={() => setFilterFacility('FAC_05')}
              className={`px-3 py-1.5 rounded-xl font-medium transition ${
                filterFacility === 'FAC_05'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'
              }`}
            >
              Fee Counter
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filteredPeaks.map((peak, idx) => (
            <div
              key={idx}
              className="bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-4"
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                    {peak.facility_name}
                  </span>
                  <h3 className="text-base font-bold text-slate-900 dark:text-white mt-0.5">
                    {peak.period_name}
                  </h3>
                </div>
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${getSeverityBadge(peak.severity)}`}>
                  {peak.severity} Severity
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 py-3 px-4 rounded-2xl bg-slate-50 dark:bg-slate-800/60 text-xs">
                <div>
                  <span className="text-slate-400 font-medium">Rush Hours</span>
                  <div className="font-bold text-slate-800 dark:text-slate-200 mt-0.5">
                    {peak.time_range}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400 font-medium">Expected Peak Wait</span>
                  <div className="font-bold text-rose-600 dark:text-rose-400 mt-0.5">
                    ~{peak.expected_wait_min} min
                  </div>
                </div>
                <div className="col-span-2 pt-2 border-t border-slate-200/60 dark:border-slate-700/60">
                  <span className="text-slate-400 font-medium">Days Observed</span>
                  <div className="font-bold text-slate-800 dark:text-slate-200 mt-0.5">
                    {peak.peak_days}
                  </div>
                </div>
              </div>

              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                <strong className="text-slate-900 dark:text-white">Cause: </strong>
                {peak.peak_reason}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
