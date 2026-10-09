"use client";

import React, { useEffect, useState } from "react";
import { 
  TrendingUp, 
  DollarSign, 
  Layers, 
  Activity, 
  ArrowUpRight, 
  RefreshCw 
} from "lucide-react";
import { 
  LineChart, 
  Line, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from "recharts";

interface KPIData {
  total_revenue: number;
  total_cost: number;
  net_profit: number;
  net_margin_pct: number;
  total_units: number;
  rev_per_unit: number;
}

interface TrendData {
  date: string;
  revenue: number;
  cost: number;
  profit: number;
}

interface EntityData {
  entity_name: string;
  category: string;
  revenue: number;
  profit: number;
  volume: number;
}

export default function Dashboard() {
  const [kpis, setKpis] = useState<KPIData | null>(null);
  const [trend, setTrend] = useState<TrendData[]>([]);
  const [entities, setEntities] = useState<EntityData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [kpiRes, trendRes, entityRes] = await Promise.all([
        fetch("http://localhost:8020/api/analytics/summary"),
        fetch("http://localhost:8020/api/analytics/timeseries"),
        fetch("http://localhost:8020/api/analytics/by-entity"),
      ]);

      setKpis(await kpiRes.json());
      setTrend(await trendRes.json());
      setEntities(await entityRes.json());
    } catch (err) {
      console.error("Failed to load analytics payload:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <header className="flex justify-between items-center mb-8 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Business Intelligence Dashboard</h1>
          <p className="text-sm text-slate-400">FastAPI + DuckDB Analytical Engine (Port 8020)</p>
        </div>
        <button 
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-md border border-slate-700 text-sm transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </header>

      {/* KPI Headline Cards */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-lg">
          <div className="flex justify-between items-center text-slate-400 text-xs font-semibold uppercase">
            <span>Gross Revenue</span>
            <DollarSign className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            ${kpis?.total_revenue?.toLocaleString() ?? "0.00"}
          </div>
          <div className="text-xs text-emerald-400 flex items-center mt-1">
            <ArrowUpRight className="w-3 h-3 mr-0.5" /> Margin: {kpis?.net_margin_pct ?? 0}%
          </div>
        </div>

        <div className="p-5 bg-slate-900 border border-slate-800 rounded-lg">
          <div className="flex justify-between items-center text-slate-400 text-xs font-semibold uppercase">
            <span>Net Profit</span>
            <TrendingUp className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            ${kpis?.net_profit?.toLocaleString() ?? "0.00"}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Total Cost: ${kpis?.total_cost?.toLocaleString() ?? "0.00"}
          </div>
        </div>

        <div className="p-5 bg-slate-900 border border-slate-800 rounded-lg">
          <div className="flex justify-between items-center text-slate-400 text-xs font-semibold uppercase">
            <span>Units Processed</span>
            <Layers className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            {kpis?.total_units?.toLocaleString() ?? 0}
          </div>
          <div className="text-xs text-slate-400 mt-1">Total Records</div>
        </div>

        <div className="p-5 bg-slate-900 border border-slate-800 rounded-lg">
          <div className="flex justify-between items-center text-slate-400 text-xs font-semibold uppercase">
            <span>Rev / Unit</span>
            <Activity className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            ${kpis?.rev_per_unit ?? "0.00"}
          </div>
          <div className="text-xs text-slate-400 mt-1">Average Yield</div>
        </div>
      </section>

      {/* Visual Analytics */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-lg">
          <h2 className="text-sm font-semibold uppercase text-slate-300 mb-4 tracking-wider">
            Revenue vs. Cost Over Time
          </h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                <Line type="monotone" dataKey="revenue" stroke="#10b981" strokeWidth={2} name="Revenue" />
                <Line type="monotone" dataKey="cost" stroke="#ef4444" strokeWidth={2} name="Cost" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="p-5 bg-slate-900 border border-slate-800 rounded-lg">
          <h2 className="text-sm font-semibold uppercase text-slate-300 mb-4 tracking-wider">
            Revenue by Dimension
          </h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={entities}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="entity_name" stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                <Bar dataKey="revenue" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Revenue" />
                <Bar dataKey="profit" fill="#10b981" radius={[4, 4, 0, 0]} name="Profit" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      {/* Table Breakdown */}
      <section className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800">
          <h3 className="font-semibold text-sm text-slate-200 uppercase tracking-wide">
            Entity Performance Records
          </h3>
        </div>
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-slate-950 text-slate-400 uppercase text-xs">
            <tr>
              <th className="px-6 py-3">Entity Name</th>
              <th className="px-6 py-3">Category</th>
              <th className="px-6 py-3">Units Processed</th>
              <th className="px-6 py-3">Total Revenue</th>
              <th className="px-6 py-3">Net Profit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {entities.map((item, idx) => (
              <tr key={idx} className="hover:bg-slate-800/50">
                <td className="px-6 py-4 font-medium text-white">{item.entity_name}</td>
                <td className="px-6 py-4">{item.category}</td>
                <td className="px-6 py-4">{item.volume}</td>
                <td className="px-6 py-4 font-mono">${item.revenue.toFixed(2)}</td>
                <td className="px-6 py-4 font-mono text-emerald-400">${item.profit.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
