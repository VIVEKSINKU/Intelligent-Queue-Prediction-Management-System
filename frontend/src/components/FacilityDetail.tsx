import React, { useState, useEffect } from 'react';
import {
  Clock, Users, Calendar, Sparkles, AlertTriangle,
  ArrowLeft, CheckCircle2, ChevronDown, Info
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, Legend, CartesianGrid
} from 'recharts';
import { api, FacilityStatus, ForecastResponse, BestTimeResponse, HourlyPatternItem } from '../services/api';

interface FacilityDetailProps {
  selectedFacilityId: string;
  facilities: FacilityStatus[];
  onSelectFacility: (id: string) => void;
  onBack: () => void;
}

export const FacilityDetail: React.FC<FacilityDetailProps> = ({
  selectedFacilityId,
  facilities,
  onSelectFacility,
  onBack,
}) => {
  const [forecastHours, setForecastHours] = useState<number>(3);
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [bestTimes, setBestTimes] = useState<BestTimeResponse | null>(null);
  const [hourlyPatterns, setHourlyPatterns] = useState<HourlyPatternItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const currentFacility = facilities.find(f => f.facility_id === selectedFacilityId) || facilities[0];

  useEffect(() => {
    let isMounted = true;
    async function loadDetailData() {
      if (!currentFacility) return;
      setLoading(true);
      try {
        const [forecastRes, bestRes, patternRes] = await Promise.all([
          api.getFacilityForecast(currentFacility.facility_id, forecastHours),
          api.getBestTimeSlots(currentFacility.facility_id),
          api.getHourlyPattern(currentFacility.facility_id)
        ]);
        if (isMounted) {
          setForecastData(forecastRes);
          setBestTimes(bestRes);
          setHourlyPatterns(patternRes.patterns);
        }
      } catch (err) {
        console.error('Error loading facility detail:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadDetailData();
    return () => { isMounted = false; };
  }, [currentFacility?.facility_id, forecastHours]);

  if (!currentFacility) return null;

  // Build weekday matrix for heatmap
  const daysOfWeek = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const hoursList = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19];

  // Helper to extract heatmap cell value
  const getHeatmapWait = (dayIdx: number, hour: number) => {
    const item = hourlyPatterns.find(p => p.day_of_week === dayIdx && p.hour === hour);
    return item ? item.avg_wait_time_min : 0;
  };

  const getHeatmapColor = (val: number) => {
    if (val === 0) return 'bg-slate-100 dark:bg-slate-800/40 text-slate-400';
    if (val < 4) return 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 font-medium';
    if (val < 10) return 'bg-emerald-200 dark:bg-emerald-900/60 text-emerald-900 dark:text-emerald-200 font-semibold';
    if (val < 16) return 'bg-amber-100 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300 font-semibold';
    if (val < 24) return 'bg-amber-300 dark:bg-amber-800/70 text-amber-950 dark:text-amber-100 font-bold';
    return 'bg-rose-400 dark:bg-rose-900/80 text-white font-bold';
  };

  // Filter today's hourly pattern for the bar chart
  const todayDow = new Date().getDay() === 0 ? 6 : new Date().getDay() - 1; // 0=Mon, 6=Sun
  const todayHourly = hourlyPatterns.filter(p => p.day_of_week === todayDow);

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Bar Navigation & Facility Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
              Facility Analytics & Prediction
            </span>
            <h1 className="text-2xl font-black text-slate-900 dark:text-white">
              {currentFacility.name}
            </h1>
          </div>
        </div>

        {/* Facility Dropdown switcher */}
        <div className="relative">
          <select
            value={currentFacility.facility_id}
            onChange={(e) => onSelectFacility(e.target.value)}
            className="appearance-none bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white rounded-xl py-2.5 pl-4 pr-10 text-sm font-semibold shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
          >
            {facilities.map((f) => (
              <option key={f.facility_id} value={f.facility_id}>
                {f.name} ({f.facility_type})
              </option>
            ))}
          </select>
          <ChevronDown className="w-4 h-4 text-slate-500 absolute right-3.5 top-3.5 pointer-events-none" />
        </div>
      </div>

      {/* Live Status Header Banner */}
      <div className="bg-gradient-to-br from-indigo-900 via-indigo-800 to-slate-900 text-white rounded-3xl p-6 sm:p-8 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 -mt-10 -mr-10 w-72 h-72 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none"></div>

        <div className="relative z-10 grid grid-cols-1 md:grid-cols-4 gap-6 items-center">
          <div className="md:col-span-2 space-y-2">
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wide bg-white/10 text-indigo-200 border border-white/10">
                {currentFacility.facility_type}
              </span>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-indigo-500/30 text-white border border-indigo-400/30">
                {currentFacility.crowd_level} Crowd
              </span>
              {currentFacility.is_peak && (
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-500/30 text-amber-300 border border-amber-400/30 flex items-center">
                  <AlertTriangle className="w-3.5 h-3.5 mr-1" />
                  Peak Active
                </span>
              )}
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight">{currentFacility.name}</h2>
            <p className="text-sm text-indigo-200">{currentFacility.location}</p>
            <p className="text-xs text-indigo-300/80">Hours: {currentFacility.operating_hours}</p>
          </div>

          <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/10 text-center">
            <span className="text-xs font-medium uppercase tracking-wider text-indigo-200 flex items-center justify-center">
              <Clock className="w-3.5 h-3.5 mr-1" />
              Current Estimated Wait
            </span>
            <div className="text-4xl font-black mt-2">
              {currentFacility.crowd_level === 'Closed' ? 'Closed' : `${currentFacility.estimated_wait_time_min}`}
              {currentFacility.crowd_level !== 'Closed' && <span className="text-sm font-normal text-indigo-200 ml-1">min</span>}
            </div>
            <p className="text-xs text-indigo-200 mt-1 capitalize">
              Trend: {currentFacility.trend}
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/10 text-center">
            <span className="text-xs font-medium uppercase tracking-wider text-indigo-200 flex items-center justify-center">
              <Users className="w-3.5 h-3.5 mr-1" />
              Queue & Staffing
            </span>
            <div className="text-4xl font-black mt-2">
              {currentFacility.current_queue_length}
              <span className="text-sm font-normal text-indigo-200 ml-1">in line</span>
            </div>
            <p className="text-xs text-indigo-200 mt-1">
              {currentFacility.counters_open} of {currentFacility.max_counters} counters staffed
            </p>
          </div>
        </div>
      </div>

      {/* Grid: Forecast Line Chart (Left) & Best Times to Visit (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Forecast Line Chart */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center">
                <Clock className="w-5 h-5 mr-2 text-indigo-600 dark:text-indigo-400" />
                Live Machine Learning Queue Forecast
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Predicted at 15-minute intervals using trained supervised XGBoost models
              </p>
            </div>

            {/* Forecast range switcher */}
            <div className="inline-flex bg-slate-100 dark:bg-slate-800 p-1 rounded-xl text-xs font-semibold">
              {[1, 2, 3].map((hr) => (
                <button
                  key={hr}
                  onClick={() => setForecastHours(hr)}
                  className={`px-3 py-1.5 rounded-lg transition ${
                    forecastHours === hr
                      ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  {hr} Hour{hr > 1 ? 's' : ''}
                </button>
              ))}
            </div>
          </div>

          <div className="h-72 w-full pt-4">
            {loading ? (
              <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                Generating model forecast...
              </div>
            ) : forecastData && forecastData.intervals.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={forecastData.intervals} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.6} />
                  <XAxis dataKey="time_label" stroke="#94a3b8" fontSize={12} tickLine={false} />
                  <YAxis yAxisId="left" stroke="#6366f1" fontSize={12} tickLine={false} label={{ value: 'Wait (min)', angle: -90, position: 'insideLeft', fill: '#6366f1', fontSize: 11 }} />
                  <YAxis yAxisId="right" orientation="right" stroke="#10b981" fontSize={12} tickLine={false} label={{ value: 'Queue (people)', angle: 90, position: 'insideRight', fill: '#10b981', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      color: '#f8fafc',
                      borderRadius: '12px',
                      border: 'none',
                      fontSize: '12px',
                      boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.3)'
                    }}
                  />
                  <Legend verticalAlign="top" height={36} iconType="circle" />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="waiting_time_min"
                    name="Wait Time (min)"
                    stroke="#6366f1"
                    strokeWidth={3}
                    dot={{ r: 4, strokeWidth: 2, fill: '#ffffff' }}
                    activeDot={{ r: 6 }}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="queue_length"
                    name="Queue Length (people)"
                    stroke="#10b981"
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    dot={{ r: 3, fill: '#10b981' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                Facility closed during selected window.
              </div>
            )}
          </div>
        </div>

        {/* Best Time to Visit Panel */}
        <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center space-x-2 mb-2">
              <span className="p-2 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
                <Sparkles className="w-5 h-5" />
              </span>
              <div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                  Best Time to Visit Today
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Top 3 lowest predicted wait slots
                </p>
              </div>
            </div>

            <div className="space-y-3 mt-4">
              {bestTimes && bestTimes.best_slots.length > 0 ? (
                bestTimes.best_slots.map((slot, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-2xl bg-gradient-to-r from-slate-50 to-indigo-50/40 dark:from-slate-800/60 dark:to-indigo-950/20 border border-slate-200/80 dark:border-slate-800 flex items-center justify-between"
                  >
                    <div className="flex items-center space-x-3">
                      <div className="w-7 h-7 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center shadow-md shadow-indigo-500/20">
                        #{idx + 1}
                      </div>
                      <div>
                        <div className="font-bold text-slate-900 dark:text-white text-sm">
                          {slot.time_slot}
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center">
                          <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-500" />
                          Crowd: {slot.crowd_level} (~{slot.queue_length} in queue)
                        </div>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-lg font-black text-emerald-600 dark:text-emerald-400">
                        ~{slot.waiting_time_min} <span className="text-xs font-normal">min</span>
                      </div>
                      <span className="text-[10px] uppercase font-bold text-slate-400">
                        Expected Wait
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-sm text-slate-400 py-6 text-center">
                  Calculating optimal visit windows...
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 p-3.5 rounded-2xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300 flex items-start space-x-2">
            <Info className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-600 dark:text-amber-400" />
            <p>
              Slots updated dynamically every 30 seconds based on live counter throughput and class schedule density.
            </p>
          </div>
        </div>
      </div>

      {/* Today's Hourly Crowd Bar Chart */}
      <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center">
            <Calendar className="w-5 h-5 mr-2 text-indigo-600 dark:text-indigo-400" />
            Today's Hourly Crowd Profile (08:00 - 20:00)
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Average expected waiting time per hour for today ({daysOfWeek[todayDow]})
          </p>
        </div>

        <div className="h-64 w-full">
          {todayHourly.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={todayHourly} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.6} />
                <XAxis dataKey="hour_label" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} label={{ value: 'Wait (min)', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip
                  formatter={(val: any) => [`${val} min`, 'Avg Wait Time']}
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    color: '#f8fafc',
                    borderRadius: '12px',
                    border: 'none',
                    fontSize: '12px'
                  }}
                />
                <Bar dataKey="avg_wait_time_min" fill="#6366f1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-400 text-sm">
              Loading hourly pattern data...
            </div>
          )}
        </div>
      </div>

      {/* Weekly Heatmap (Hour x Weekday) */}
      <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">
              Weekly Wait Time Heatmap (Hour × Weekday)
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Aggregated historical wait matrix showing low-wait windows (green) and peak traffic (orange/red)
            </p>
          </div>

          {/* Heatmap Legend */}
          <div className="flex items-center space-x-2 text-xs text-slate-500 dark:text-slate-400">
            <span>Low (&lt;4m)</span>
            <div className="flex space-x-1">
              <span className="w-3.5 h-3.5 rounded bg-emerald-100 dark:bg-emerald-950"></span>
              <span className="w-3.5 h-3.5 rounded bg-emerald-300 dark:bg-emerald-800"></span>
              <span className="w-3.5 h-3.5 rounded bg-amber-200 dark:bg-amber-900"></span>
              <span className="w-3.5 h-3.5 rounded bg-amber-400 dark:bg-amber-700"></span>
              <span className="w-3.5 h-3.5 rounded bg-rose-400 dark:bg-rose-900"></span>
            </div>
            <span>High (&gt;24m)</span>
          </div>
        </div>

        <div className="overflow-x-auto pb-2">
          <table className="min-w-full text-center border-collapse">
            <thead>
              <tr>
                <th className="py-2 px-3 text-xs font-semibold text-slate-400 text-left">Time</th>
                {daysOfWeek.map((day, idx) => (
                  <th
                    key={day}
                    className={`py-2 px-3 text-xs font-semibold ${
                      idx === todayDow ? 'text-indigo-600 dark:text-indigo-400 font-bold underline' : 'text-slate-500 dark:text-slate-400'
                    }`}
                  >
                    {day.substring(0, 3)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {hoursList.map((hour) => (
                <tr key={hour} className="border-t border-slate-100 dark:border-slate-800/60">
                  <td className="py-2 px-3 text-xs text-slate-500 dark:text-slate-400 font-mono text-left whitespace-nowrap">
                    {hour < 10 ? `0${hour}` : hour}:00
                  </td>
                  {daysOfWeek.map((_, dayIdx) => {
                    const wait = getHeatmapWait(dayIdx, hour);
                    return (
                      <td key={dayIdx} className="p-1">
                        <div
                          className={`py-2 px-1 rounded-lg text-xs transition duration-150 hover:scale-105 cursor-default ${getHeatmapColor(wait)}`}
                          title={`${daysOfWeek[dayIdx]} ${hour}:00 - Avg wait: ${wait} min`}
                        >
                          {wait > 0 ? `${wait}m` : '—'}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
