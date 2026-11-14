import React, { useState, useEffect } from 'react';
import {
  LineChart as LineChartIcon, Award, Cpu, BarChart2,
  TrendingUp, CheckCircle, ExternalLink, Image as ImageIcon
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, Legend, CartesianGrid
} from 'recharts';
import { api, AnalyticsTrendsResponse, ModelMetricsResponse } from '../services/api';

export const AnalyticsHub: React.FC = () => {
  const [trends, setTrends] = useState<AnalyticsTrendsResponse | null>(null);
  const [metrics, setMetrics] = useState<ModelMetricsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedPlot, setSelectedPlot] = useState<string>('actual_vs_predicted_wait_time.png');

  useEffect(() => {
    async function loadData() {
      try {
        const [trendData, metricData] = await Promise.all([
          api.getAnalyticsTrends(),
          api.getModelMetrics()
        ]);
        setTrends(trendData);
        setMetrics(metricData);
      } catch (err) {
        console.error('Error loading analytics and metrics:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const plotLabels: Record<string, string> = {
    'actual_vs_predicted_wait_time.png': 'Actual vs Predicted (Wait Time)',
    'actual_vs_predicted_queue_length.png': 'Actual vs Predicted (Queue Length)',
    'residuals_distribution.png': 'Residuals Distribution (Error Analysis)',
    'feature_importance.png': 'Feature Importance Ranking',
    'confusion_matrix_peak.png': 'Peak Classification Confusion Matrix',
    'model_comparison_bar.png': 'Regression Model Benchmark Bar'
  };

  return (
    <div className="space-y-10 animate-fadeIn">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto space-y-2">
        <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 border border-emerald-200/50 dark:border-emerald-800/50">
          <Cpu className="w-3.5 h-3.5 mr-1 text-emerald-500" />
          Course Machine Learning Dashboard
        </div>
        <h1 className="text-3xl font-black text-slate-900 dark:text-white">
          Historical Trends & ML Performance Hub
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Inspect model validation metrics (R², RMSE, MAE, F1), feature engineering weights, and time-series patterns across 67,160 campus queue records.
        </p>
      </div>

      {/* Model Performance Cards */}
      {metrics && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center">
              <Award className="w-5 h-5 mr-2 text-indigo-600 dark:text-indigo-400" />
              Supervised Learning Model Comparison
            </h2>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              Split: Time-Based (70% Train / 15% Val / 15% Test)
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Waiting Time Card */}
            <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
                  Target 1: Waiting Time
                </span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300">
                  Best: {metrics.best_models.waiting_time}
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Waiting Time Regressors
              </h3>

              <div className="space-y-2 text-xs">
                {Object.entries(metrics.waiting_time_models).map(([name, m]) => (
                  <div
                    key={name}
                    className={`p-2.5 rounded-xl border flex items-center justify-between ${
                      name === metrics.best_models.waiting_time
                        ? 'bg-indigo-50/60 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-800 font-bold'
                        : 'bg-slate-50 dark:bg-slate-800/40 border-slate-100 dark:border-slate-800 text-slate-600 dark:text-slate-400'
                    }`}
                  >
                    <span>{name}</span>
                    <div className="space-x-2 font-mono">
                      <span>R²={m.R2}</span>
                      <span className="text-slate-400">|</span>
                      <span>MAE={m.MAE}m</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Queue Length Card */}
            <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                  Target 2: Queue Length
                </span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300">
                  Best: {metrics.best_models.queue_length}
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Queue Length Regressors
              </h3>

              <div className="space-y-2 text-xs">
                {Object.entries(metrics.queue_length_models).map(([name, m]) => (
                  <div
                    key={name}
                    className={`p-2.5 rounded-xl border flex items-center justify-between ${
                      name === metrics.best_models.queue_length
                        ? 'bg-emerald-50/60 dark:bg-emerald-950/40 border-emerald-300 dark:border-emerald-800 font-bold'
                        : 'bg-slate-50 dark:bg-slate-800/40 border-slate-100 dark:border-slate-800 text-slate-600 dark:text-slate-400'
                    }`}
                  >
                    <span>{name}</span>
                    <div className="space-x-2 font-mono">
                      <span>R²={m.R2}</span>
                      <span className="text-slate-400">|</span>
                      <span>MAE={m.MAE}p</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Peak Classifier Card */}
            <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200/80 dark:border-slate-800 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                  Target 3: Peak Classification
                </span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300">
                  Best: {metrics.best_models.peak_classifier}
                </span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Peak Status Classifiers
              </h3>

              <div className="space-y-2 text-xs">
                {Object.entries(metrics.peak_classifier_models).map(([name, m]) => (
                  <div
                    key={name}
                    className={`p-2.5 rounded-xl border flex items-center justify-between ${
                      name === metrics.best_models.peak_classifier
                        ? 'bg-amber-50/60 dark:bg-amber-950/40 border-amber-300 dark:border-amber-800 font-bold'
                        : 'bg-slate-50 dark:bg-slate-800/40 border-slate-100 dark:border-slate-800 text-slate-600 dark:text-slate-400'
                    }`}
                  >
                    <span>{name}</span>
                    <div className="space-x-2 font-mono">
                      <span>Acc={m.Accuracy}</span>
                      <span className="text-slate-400">|</span>
                      <span>F1={m.F1}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Feature Importance & Day of Week Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Top Feature Importance Bar */}
        <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center">
              <BarChart2 className="w-5 h-5 mr-2 text-indigo-600 dark:text-indigo-400" />
              Engineered Feature Importance (Top 8)
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Contribution of lag variables, cyclical sine/cos encodings, and rolling metrics
            </p>
          </div>

          <div className="h-72 w-full">
            {metrics?.top_feature_importance ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={metrics.top_feature_importance.slice(0, 8)}
                  layout="vertical"
                  margin={{ top: 5, right: 20, left: 40, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.6} />
                  <XAxis type="number" stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <YAxis type="category" dataKey="feature" stroke="#94a3b8" fontSize={11} tickLine={false} width={130} />
                  <Tooltip
                    formatter={(val: any) => [val, 'Importance Score']}
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      color: '#f8fafc',
                      borderRadius: '12px',
                      fontSize: '12px'
                    }}
                  />
                  <Bar dataKey="importance" fill="#6366f1" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                Loading feature weights...
              </div>
            )}
          </div>
        </div>

        {/* Day-of-Week Comparison Bar */}
        <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center">
              <TrendingUp className="w-5 h-5 mr-2 text-emerald-600 dark:text-emerald-400" />
              Day-of-Week Queue Trends
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Average wait time across campus facilities by day of the week
            </p>
          </div>

          <div className="h-72 w-full">
            {trends?.weekly_trends ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trends.weekly_trends} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.6} />
                  <XAxis dataKey="day_name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} label={{ value: 'Wait (min)', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 11 }} />
                  <Tooltip
                    formatter={(val: any) => [`${val} min`, 'Avg Wait']}
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      color: '#f8fafc',
                      borderRadius: '12px',
                      fontSize: '12px'
                    }}
                  />
                  <Bar dataKey="avg_waiting_time_min" fill="#10b981" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                Loading weekly comparison...
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Multi-Month Timeline Trend Line */}
      <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div>
          <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center">
            <LineChartIcon className="w-5 h-5 mr-2 text-indigo-600 dark:text-indigo-400" />
            Daily Average Wait Time & Volume (6-Month Historical Profile)
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Timeline showing spikes during registration periods, fee payment deadlines, and midterm examinations
          </p>
        </div>

        <div className="h-72 w-full">
          {trends?.daily_trends ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trends.daily_trends} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.6} />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis yAxisId="left" stroke="#6366f1" fontSize={11} tickLine={false} label={{ value: 'Avg Wait (min)', angle: -90, position: 'insideLeft', fill: '#6366f1', fontSize: 11 }} />
                <YAxis yAxisId="right" orientation="right" stroke="#f59e0b" fontSize={11} tickLine={false} label={{ value: 'Queue (people)', angle: 90, position: 'insideRight', fill: '#f59e0b', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    color: '#f8fafc',
                    borderRadius: '12px',
                    fontSize: '12px'
                  }}
                />
                <Legend verticalAlign="top" height={36} />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="avg_waiting_time_min"
                  name="Daily Avg Wait (min)"
                  stroke="#6366f1"
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="avg_queue_length"
                  name="Daily Avg Queue (people)"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  strokeDasharray="3 3"
                  dot={{ r: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-400 text-sm">
              Loading timeline trends...
            </div>
          )}
        </div>
      </div>

      {/* Generated Evaluation Plots Gallery */}
      <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
        <div>
          <h3 className="text-xl font-bold text-slate-900 dark:text-white flex items-center">
            <ImageIcon className="w-5 h-5 mr-2 text-indigo-600 dark:text-indigo-400" />
            Model Evaluation Diagnostics & Plots
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Interactive visual review of actual vs. predicted curves, residual histograms, and confusion matrix generated during ML training
          </p>
        </div>

        {/* Plot Selector Tabs */}
        <div className="flex flex-wrap gap-2">
          {metrics?.available_plots.map((plot) => (
            <button
              key={plot}
              onClick={() => setSelectedPlot(plot)}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition ${
                selectedPlot === plot
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {plotLabels[plot] || plot}
            </button>
          ))}
        </div>

        {/* Plot Display Container */}
        <div className="bg-slate-50 dark:bg-slate-950/60 rounded-2xl p-4 border border-slate-200/80 dark:border-slate-800 flex flex-col items-center justify-center">
          <img
            src={`/plots/${selectedPlot}`}
            alt={plotLabels[selectedPlot] || selectedPlot}
            className="max-h-[500px] w-auto rounded-xl shadow-lg border border-slate-200 dark:border-slate-800 object-contain"
            onError={(e: any) => {
              e.target.onerror = null;
              e.target.src = '';
              e.target.alt = 'Plot image generated in ml/plots directory';
            }}
          />
          <span className="text-xs text-slate-400 mt-3 font-mono">
            ml/plots/{selectedPlot}
          </span>
        </div>
      </div>
    </div>
  );
};
