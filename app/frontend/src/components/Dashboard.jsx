import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Sun, Moon, Zap, Activity, AlertTriangle } from 'lucide-react';
import axios from 'axios';

const Dashboard = () => {
  const [latestData, setLatestData] = useState(null);
  const [historyData, setHistoryData] = useState([]);
  const [loading, setLoading] = useState(true);

  // Poll Data every 2 seconds
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [latestRes, historyRes] = await Promise.all([
          axios.get('http://localhost:5000/api/latest'),
          axios.get('http://localhost:5000/api/data')
        ]);
        setLatestData(latestRes.data);
        // Reverse history to show oldest -> newest
        setHistoryData(historyRes.data.reverse());
        setLoading(false);
      } catch (error) {
        console.error("Error fetching data:", error);
        // Fallback for demo if API fails
        setLoading(false); 
      }
    };

    fetchData(); // Initial Calculation
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="text-white text-2xl flex justify-center items-center h-screen">Connecting to Smart City Network...</div>;

  return (
    <div className="p-6 space-y-6 animate-fade-in text-slate-100">
      
      {/* HEADER */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
            Smart StreetLight Control
          </h1>
          <p className="text-slate-400 mt-1">Adaptive Lighting System &bull; Zone A</p>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg border border-slate-700">
            <div className={`w-3 h-3 rounded-full ${latestData?.anomaly ? 'bg-red-500 animate-pulse' : 'bg-green-500'}`}></div>
            <span className="text-sm font-medium">{latestData?.anomaly ? 'SYSTEM FAULT' : 'SYSTEM ONLINE'}</span>
        </div>
      </div>

      {/* METRICS GRID */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        
        {/* Brightness Card */}
        <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl">
          <div className="flex justify-between items-start mb-4">
            <div className="p-3 bg-blue-500/10 rounded-xl">
              <Sun className="w-6 h-6 text-blue-400" />
            </div>
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Target Brightness</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold">{latestData?.brightness || 0}%</span>
            <span className="text-sm text-green-400">+2% vs avg</span>
          </div>
          <div className="mt-4 w-full bg-slate-700 h-2 rounded-full overflow-hidden">
            <div className="bg-blue-500 h-full transition-all duration-500" style={{ width: `${latestData?.brightness}%` }}></div>
          </div>
        </div>

        {/* LDR Card */}
        <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl">
            <div className="flex justify-between items-start mb-4">
              <div className="p-3 bg-purple-500/10 rounded-xl">
                <Moon className="w-6 h-6 text-purple-400" />
              </div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Ambient Light</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold">{latestData?.smooth_ldr || 0}</span>
              <span className="text-sm text-slate-500">Lux (Raw: {latestData?.ldr})</span>
            </div>
        </div>

         {/* Motion Card */}
         <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl">
            <div className="flex justify-between items-start mb-4">
              <div className="p-3 bg-indigo-500/10 rounded-xl">
                <Activity className="w-6 h-6 text-indigo-400" />
              </div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Motion Sensor</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              {latestData?.motion ? (
                  <span className="text-3xl font-bold text-indigo-300 animate-pulse">DETECTED</span>
              ) : (
                  <span className="text-3xl font-bold text-slate-500">CLEAR</span>
              )}
            </div>
        </div>

        {/* Power Card */}
        <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl">
            <div className="flex justify-between items-start mb-4">
              <div className="p-3 bg-amber-500/10 rounded-xl">
                <Zap className="w-6 h-6 text-amber-400" />
              </div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Power Draw</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold">{latestData?.power}</span>
              <span className="text-sm text-slate-500">Watts</span>
            </div>
            {latestData?.anomaly > 0 && (
                <div className="mt-2 flex items-center gap-2 text-red-400 text-xs font-bold bg-red-900/20 p-1 rounded">
                    <AlertTriangle size={14} /> 
                    {latestData.anomaly === 1 ? 'BLOWN BULB DETECTED' : 'POWER LEAK DETECTED'}
                </div>
            )}
        </div>

      </div>

      {/* CHARTS ROW */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-4">
          
          {/* Brightness History */}
          <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl">
              <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                  <span className="w-2 h-6 bg-blue-500 rounded-full"></span>
                  Brightness Activity
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={historyData}>
                        <defs>
                            <linearGradient id="colorBrightness" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                        <XAxis dataKey="timestamp" hide />
                        <YAxis stroke="#475569" fontSize={12} />
                        <Tooltip 
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f8fafc' }}
                            itemStyle={{ color: '#3b82f6' }}
                        />
                        <Area type="monotone" dataKey="brightness" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorBrightness)" />
                    </AreaChart>
                </ResponsiveContainer>
              </div>
          </div>

          {/* LDR History */}
          <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl">
              <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                  <span className="w-2 h-6 bg-purple-500 rounded-full"></span>
                  Ambient Light Sensor (Smoothed)
              </h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={historyData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                        <XAxis dataKey="timestamp" hide />
                        <YAxis stroke="#475569" fontSize={12} domain={[0, 1024]} />
                        <Tooltip 
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f8fafc' }}
                        />
                        <Line type="monotone" dataKey="smooth_ldr" stroke="#a855f7" strokeWidth={3} dot={false} />
                        <Line type="monotone" dataKey="ldr" stroke="#475569" strokeWidth={1} dot={false} strokeDasharray="5 5" />
                    </LineChart>
                </ResponsiveContainer>
              </div>
          </div>

      </div>
    </div>
  );
};

export default Dashboard;
