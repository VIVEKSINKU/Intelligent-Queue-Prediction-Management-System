import React from 'react';
import { Clock, AlertTriangle, ChevronRight, MapPin, Layers } from 'lucide-react';
import { FacilityStatus } from '../services/api';

interface FacilityCardProps {
  facility: FacilityStatus;
  onSelect: (facilityId: string) => void;
}

export const FacilityCard: React.FC<FacilityCardProps> = ({ facility, onSelect }) => {
  const getBadgeStyle = (level: string) => {
    switch (level) {
      case 'Low':
        return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800';
      case 'Medium':
        return 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border-amber-300 dark:border-amber-800';
      case 'High':
        return 'bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300 border-rose-300 dark:border-rose-800';
      default:
        return 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400 border-slate-300 dark:border-slate-700';
    }
  };

  const getWaitColor = (min: number, level: string) => {
    if (level === 'Closed') return 'text-slate-400 dark:text-slate-600';
    if (min < 5) return 'text-emerald-600 dark:text-emerald-400';
    if (min < 14) return 'text-amber-600 dark:text-amber-400';
    return 'text-rose-600 dark:text-rose-400';
  };

  return (
    <div className="group relative bg-white dark:bg-slate-900 rounded-2xl p-5 border border-slate-200/80 dark:border-slate-800 shadow-sm hover:shadow-xl hover:border-indigo-400/50 dark:hover:border-indigo-600/50 transition-all duration-300 flex flex-col justify-between">
      {/* Top row: Type badge & Peak warning */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
            {facility.facility_type}
          </span>
          <div className="flex items-center space-x-1.5">
            {facility.is_peak && (
              <span className="inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
                <AlertTriangle className="w-3.5 h-3.5 mr-1 text-amber-500" />
                Peak Rush
              </span>
            )}
            <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${getBadgeStyle(facility.crowd_level)}`}>
              {facility.crowd_level}
            </span>
          </div>
        </div>

        {/* Facility Title & Location */}
        <h3 className="text-lg font-bold text-slate-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
          {facility.name}
        </h3>
        <p className="flex items-center text-xs text-slate-500 dark:text-slate-400 mt-1">
          <MapPin className="w-3.5 h-3.5 mr-1 flex-shrink-0 text-slate-400" />
          <span className="truncate">{facility.location}</span>
        </p>

        {/* ML Prediction Overview Box */}
        <div className="grid grid-cols-2 gap-3 my-5 py-3 px-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
          <div>
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center">
              <Clock className="w-3 h-3 mr-1" />
              Predicted Wait
            </span>
            <div className="mt-1 flex items-baseline space-x-1">
              {facility.crowd_level === 'Closed' ? (
                <div className="flex flex-col">
                  <span className="text-lg font-bold text-slate-400">Closed</span>
                  <span className="text-[10px] text-slate-400">Reopens 08:00 AM</span>
                </div>
              ) : (
                <>
                  <span className={`text-2xl font-black ${getWaitColor(facility.estimated_wait_time_min, facility.crowd_level)}`}>
                    {facility.estimated_wait_time_min}
                  </span>
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400">min</span>
                </>
              )}
            </div>
          </div>

          <div>
            <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center">
              <Layers className="w-3 h-3 mr-1" />
              Service Desks
            </span>
            <div className="mt-1 flex items-baseline space-x-1">
              <span className="text-2xl font-black text-slate-900 dark:text-white">
                {facility.max_counters}
              </span>
              <span className="text-xs font-medium text-slate-500 dark:text-slate-400">counters</span>
            </div>
          </div>
        </div>

        {/* Operating hours */}
        <div className="text-xs text-slate-500 dark:text-slate-400 py-1">
          <span className="font-semibold text-slate-700 dark:text-slate-300">Hours: </span>
          {facility.operating_hours}
        </div>
      </div>

      {/* Action Footer */}
      <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80">
        <button
          onClick={() => onSelect(facility.facility_id)}
          className="w-full inline-flex items-center justify-center py-2.5 px-3 rounded-xl bg-slate-100 hover:bg-indigo-600 text-slate-700 hover:text-white dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-indigo-600 dark:hover:text-white font-medium text-xs transition duration-200 shadow-sm"
        >
          <span>View Forecast & Best Time</span>
          <ChevronRight className="w-3.5 h-3.5 ml-1" />
        </button>
      </div>
    </div>
  );
};
