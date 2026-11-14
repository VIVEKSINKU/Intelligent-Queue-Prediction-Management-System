import React, { useState } from 'react';
import { Sparkles, Clock, Users, AlertTriangle, ArrowRight, CheckCircle2, Sliders } from 'lucide-react';
import { api, FacilityStatus, PredictResponse } from '../services/api';

interface WaitTimePredictorProps {
  facilities: FacilityStatus[];
}

export const WaitTimePredictor: React.FC<WaitTimePredictorProps> = ({ facilities }) => {
  const [selectedFacility, setSelectedFacility] = useState<string>(facilities[0]?.facility_id || 'FAC_02');
  
  // Default to today at 12:30 PM
  const getTodayAt1230 = () => {
    const d = new Date();
    d.setHours(12, 30, 0, 0);
    return d.toISOString().slice(0, 16);
  };

  const [datetimeStr, setDatetimeStr] = useState<string>(getTodayAt1230());
  const [countersOpen, setCountersOpen] = useState<number>(3);
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const currentMeta = facilities.find(f => f.facility_id === selectedFacility) || facilities[0];

  const handlePredict = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const formatted = datetimeStr.replace('T', ' ') + ':00';
      const res = await api.predictCustom(selectedFacility, formatted, countersOpen);
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Prediction failed');
    } finally {
      setLoading(false);
    }
  };

  const setPreset = (hour: number, minute: number, daysAhead = 0) => {
    const d = new Date();
    d.setDate(d.getDate() + daysAhead);
    d.setHours(hour, minute, 0, 0);
    setDatetimeStr(d.toISOString().slice(0, 16));
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fadeIn">
      {/* Title */}
      <div className="text-center space-y-2">
        <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/50 dark:border-indigo-800/50">
          <Sparkles className="w-3.5 h-3.5 mr-1 text-indigo-500" />
          Point Inference Engine
        </div>
        <h1 className="text-3xl font-black text-slate-900 dark:text-white">
          Predict Your Wait Time
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 max-w-xl mx-auto">
          Planning your campus day? Select a facility and target time slot to get an instant ML-generated estimate of wait time and crowd congestion.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Form Panel */}
        <div className="lg:col-span-7 bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
          <form onSubmit={handlePredict} className="space-y-5">
            {/* Facility Picker */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                1. Select Campus Facility
              </label>
              <select
                value={selectedFacility}
                onChange={(e) => {
                  setSelectedFacility(e.target.value);
                  const fac = facilities.find(f => f.facility_id === e.target.value);
                  if (fac) setCountersOpen(fac.counters_open || fac.default_counters || 2);
                }}
                className="w-full bg-slate-50 dark:bg-slate-800/70 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white rounded-xl py-3 px-4 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {facilities.map((fac) => (
                  <option key={fac.facility_id} value={fac.facility_id}>
                    {fac.name} ({fac.facility_type})
                  </option>
                ))}
              </select>
            </div>

            {/* Quick Presets */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                Quick Schedule Presets
              </label>
              <div className="flex flex-wrap gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => setPreset(12, 30, 0)}
                  className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-indigo-50 dark:bg-slate-800 dark:hover:bg-indigo-950/60 text-slate-700 dark:text-slate-300 font-medium transition"
                >
                  Today 12:30 PM (Lunch)
                </button>
                <button
                  type="button"
                  onClick={() => setPreset(15, 0, 0)}
                  className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-indigo-50 dark:bg-slate-800 dark:hover:bg-indigo-950/60 text-slate-700 dark:text-slate-300 font-medium transition"
                >
                  Today 3:00 PM (Afternoon)
                </button>
                <button
                  type="button"
                  onClick={() => setPreset(9, 30, 1)}
                  className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-indigo-50 dark:bg-slate-800 dark:hover:bg-indigo-950/60 text-slate-700 dark:text-slate-300 font-medium transition"
                >
                  Tomorrow 9:30 AM (Morning)
                </button>
              </div>
            </div>

            {/* Target Date and Time */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                2. Target Date & Time
              </label>
              <input
                type="datetime-local"
                value={datetimeStr}
                onChange={(e) => setDatetimeStr(e.target.value)}
                required
                className="w-full bg-slate-50 dark:bg-slate-800/70 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white rounded-xl py-3 px-4 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Counter slider */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center">
                  <Sliders className="w-3.5 h-3.5 mr-1" />
                  Staffed Counters Open
                </label>
                <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">
                  {countersOpen} Counters
                </span>
              </div>
              <input
                type="range"
                min="1"
                max={currentMeta?.max_counters || 6}
                value={countersOpen}
                onChange={(e) => setCountersOpen(parseInt(e.target.value))}
                className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-indigo-600"
              />
              <div className="flex justify-between text-[10px] text-slate-400 mt-1">
                <span>1 (Minimal)</span>
                <span>{currentMeta?.max_counters || 6} (Full Capacity)</span>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-sm shadow-lg shadow-indigo-600/30 flex items-center justify-center space-x-2 transition disabled:opacity-50"
            >
              {loading ? (
                <span>Inference Running...</span>
              ) : (
                <>
                  <span>Calculate Wait Time</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {error && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
              {error}
            </div>
          )}
        </div>

        {/* Prediction Output Card */}
        <div className="lg:col-span-5">
          {result ? (
            <div className="bg-gradient-to-br from-indigo-950 via-slate-900 to-slate-950 text-white rounded-3xl p-6 sm:p-8 border border-indigo-800/40 shadow-xl space-y-6 animate-scaleUp">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-white/10 text-indigo-300 border border-white/10">
                    Model Inference Result
                  </span>
                  {result.is_peak ? (
                    <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center">
                      <AlertTriangle className="w-3 h-3 mr-1" />
                      Peak Rush
                    </span>
                  ) : (
                    <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center">
                      <CheckCircle2 className="w-3 h-3 mr-1" />
                      Normal Flow
                    </span>
                  )}
                </div>
                <h3 className="text-xl font-black mt-3">{result.facility_name}</h3>
                <p className="text-xs text-indigo-200/80 mt-0.5">{result.requested_datetime}</p>
              </div>

              {/* Big Metrics */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-2xl bg-white/10 backdrop-blur-md border border-white/10">
                  <span className="text-[11px] font-medium uppercase tracking-wider text-indigo-200 flex items-center">
                    <Clock className="w-3.5 h-3.5 mr-1" />
                    Predicted Wait
                  </span>
                  <div className="text-3xl font-black mt-1 text-emerald-400">
                    {result.predicted_wait_time_min}
                    <span className="text-xs font-normal text-white ml-1">min</span>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-white/10 backdrop-blur-md border border-white/10">
                  <span className="text-[11px] font-medium uppercase tracking-wider text-indigo-200 flex items-center">
                    <Users className="w-3.5 h-3.5 mr-1" />
                    Queue Length
                  </span>
                  <div className="text-3xl font-black mt-1">
                    {result.predicted_queue_length}
                    <span className="text-xs font-normal text-white ml-1">people</span>
                  </div>
                </div>
              </div>

              {/* Explanation text */}
              <div className="p-4 rounded-2xl bg-white/5 border border-white/10 text-xs leading-relaxed text-indigo-100">
                <p className="font-semibold text-white mb-1">Queue Intelligence Advisory:</p>
                {result.explanation}
              </div>

              <div className="text-[11px] text-indigo-300/60 text-center">
                Inference powered by XGBoost regressor trained on 67k campus observations.
              </div>
            </div>
          ) : (
            <div className="h-full min-h-[350px] rounded-3xl border-2 border-dashed border-slate-200 dark:border-slate-800 p-8 flex flex-col items-center justify-center text-center text-slate-400 space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-indigo-500">
                <Sparkles className="w-6 h-6" />
              </div>
              <h4 className="font-bold text-slate-700 dark:text-slate-300">Ready to Predict</h4>
              <p className="text-xs max-w-xs">
                Select your parameters on the left and click "Calculate Wait Time" to preview expected crowd conditions.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
