import React, { useEffect, useState, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { Sun, Moon, Zap, Activity, AlertTriangle, Car, Leaf, ChevronDown, ChevronUp } from 'lucide-react';
import axios from 'axios';

const Dashboard = () => {
  const [latestData, setLatestData] = useState(null);
  const [historyData, setHistoryData] = useState([]);
  const [trafficData, setTrafficData] = useState([]);
  const [energyData, setEnergyData] = useState(null);
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showFormula, setShowFormula] = useState(false);

  // Poll Data every 2 seconds
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [latestRes, historyRes, trafficRes, energyRes, statusRes] = await Promise.all([
          axios.get('http://localhost:5000/api/latest'),
          axios.get('http://localhost:5000/api/data'),
          axios.get('http://localhost:5000/api/analytics/traffic'),
          axios.get('http://localhost:5000/api/analytics/energy'),
          axios.get('http://localhost:5000/api/status')
        ]);
        setLatestData(latestRes.data);
        const reversedData = [...historyRes.data].reverse();
        setHistoryData(reversedData);
        setTrafficData(trafficRes.data);
        setEnergyData(energyRes.data);
        setStatusData(statusRes.data);
        setLoading(false);
      } catch (error) {
        console.error("Error fetching data:", error);
        setLoading(false); 
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  // Calculate mode distribution for Pie Chart
  const modeDistribution = useMemo(() => {
    if (!historyData.length) return [];
    
    let offCount = 0;
    let ecoCount = 0;
    let activeCount = 0;
    
    historyData.forEach(item => {
      const brightness = item.brightness || 0;
      if (brightness === 0) {
        offCount++;
      } else if (brightness < 50) {
        ecoCount++;
      } else {
        activeCount++;
      }
    });
    
    return [
      { name: 'OFF', value: offCount, color: '#475569' },
      { name: 'ECO (30%)', value: ecoCount, color: '#22c55e' },
      { name: 'FULL (100%)', value: activeCount, color: '#3b82f6' }
    ].filter(item => item.value > 0);
  }, [historyData]);

  // Find peak and quiet hours for insight
  const trafficInsight = useMemo(() => {
    if (!trafficData.length) return { peak: '--', quiet: '--' };
    const sorted = [...trafficData].sort((a, b) => b.count - a.count);
    const peak = sorted[0]?.hour || '--';
    const quiet = sorted[sorted.length - 1]?.hour || '--';
    return { peak, quiet };
  }, [trafficData]);

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
            <span className="text-sm text-green-400">
              {latestData?.brightness === 100 ? 'FULL' : latestData?.brightness === 30 ? 'ECO' : 'OFF'}
            </span>
          </div>
          <div className="mt-4 w-full bg-slate-700 h-2 rounded-full overflow-hidden">
            <div className="bg-blue-500 h-full transition-all duration-500" style={{ width: `${latestData?.brightness}%` }}></div>
          </div>
        </div>

        {/* Night Mode Card */}
        <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl">
            <div className="flex justify-between items-start mb-4">
              <div className="p-3 bg-purple-500/10 rounded-xl">
                <Moon className="w-6 h-6 text-purple-400" />
              </div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Day/Night</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold">{latestData?.is_night ? 'NIGHT' : 'DAY'}</span>
            </div>
            <p className="text-sm text-slate-500 mt-2">LDR Reading: {latestData?.smooth_ldr || 0}/10</p>
        </div>

         {/* Motion Card */}
         <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl">
            <div className="flex justify-between items-start mb-4">
              <div className="p-3 bg-indigo-500/10 rounded-xl">
                <Activity className="w-6 h-6 text-indigo-400" />
              </div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Motion Sensor</span>
            </div>
            <div className="mt-1">
              {latestData?.motion ? (
                  <span className="text-3xl font-bold text-indigo-300 animate-pulse">DETECTED</span>
              ) : (
                  <span className="text-3xl font-bold text-slate-500">CLEAR</span>
              )}
              <p className="text-xs text-slate-500 mt-2">Last: {statusData?.last_motion || 'Unknown'}</p>
            </div>
        </div>

        {/* Energy Savings Card with Expandable Formula */}
        <div className="bg-gradient-to-br from-green-900/50 to-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-green-700/50 shadow-xl">
            <div className="flex justify-between items-start mb-4">
              <div className="p-3 bg-green-500/10 rounded-xl">
                <Leaf className="w-6 h-6 text-green-400" />
              </div>
              <span className="text-xs font-semibold text-green-400 uppercase tracking-wider">Energy Saved</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold text-green-400">{energyData?.energy_saved_percent || 0}%</span>
            </div>
            <p className="text-xs text-slate-400 mt-2">vs Traditional (Always ON)</p>
            
            {/* Expand/Collapse Button */}
            <button 
              onClick={() => setShowFormula(!showFormula)}
              className="mt-3 flex items-center gap-1 text-xs text-green-400 hover:text-green-300 transition-colors"
            >
              {showFormula ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              {showFormula ? 'Hide calculation' : 'Show calculation'}
            </button>
        </div>

      </div>

      {/* EXPANDABLE ENERGY FORMULA SECTION */}
      {showFormula && (
        <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-green-700/30 shadow-xl animate-fade-in">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber-400" />
            Energy Savings Calculation (Last 7 Days)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Formula Explanation */}
            <div className="space-y-3">
              <div className="bg-slate-900/50 p-4 rounded-lg font-mono text-sm">
                {/* <p className="text-slate-400 mb-2">// Normalized Formulas (P_full = 1.0, α = 0.3)</p> */}
                <p className="text-blue-300">E<sub>baseline</sub> = T<sub>night</sub> = <span className="text-white">{energyData?.t_night || 0}</span> readings</p>
                <p className="text-green-300 mt-1">E<sub>adaptive</sub> = T<sub>full</sub> + α×T<sub>dim</sub></p>
                <p className="text-green-300 ml-4">= {energyData?.t_full || 0} + (0.3 × {energyData?.t_dim || 0})</p>
                <p className="text-green-300 ml-4">= <span className="text-white font-bold">{energyData?.e_adaptive || 0}</span></p>
                <hr className="border-slate-700 my-2" />
                <p className="text-amber-300">Saved = ((E<sub>baseline</sub> - E<sub>adaptive</sub>) / E<sub>baseline</sub>) × 100</p>
                <p className="text-amber-300 ml-4">= (({energyData?.e_baseline || 0} - {energyData?.e_adaptive || 0}) / {energyData?.e_baseline || 0}) × 100</p>
                <p className="text-amber-400 ml-4 text-lg font-bold">= {energyData?.energy_saved_percent || 0}%</p>
              </div>
            </div>
            {/* Stats Breakdown */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-900/50 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-blue-400">{energyData?.t_full || 0}</p>
                <p className="text-xs text-slate-400 mt-1">T<sub>full</sub> (100% brightness)</p>
              </div>
              <div className="bg-slate-900/50 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-green-400">{energyData?.t_dim || 0}</p>
                <p className="text-xs text-slate-400 mt-1">T<sub>dim</sub> (30% ECO mode)</p>
              </div>
              <div className="bg-slate-900/50 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-slate-400">{energyData?.t_off || 0}</p>
                <p className="text-xs text-slate-400 mt-1">T<sub>off</sub> (Daytime OFF)</p>
              </div>
              <div className="bg-slate-900/50 p-4 rounded-lg text-center">
                <p className="text-3xl font-bold text-amber-400">{energyData?.t_night || 0}</p>
                <p className="text-xs text-slate-400 mt-1">T<sub>night</sub> (Total ON)</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CHARTS ROW */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-4">
          
          {/* Traffic Patterns - Busy Street Graph */}
          <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl">
              <div className="flex justify-between items-start mb-4">
                <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-2 h-6 bg-orange-500 rounded-full"></span>
                    <Car className="w-5 h-5 text-orange-400" />
                    Busy Street - Traffic Patterns
                </h3>
              </div>
              <p className="text-sm text-slate-400 mb-4">
                Motion triggers per hour — Peak: <span className="text-orange-400 font-semibold">{trafficInsight.peak}</span> | 
                Quiet: <span className="text-green-400 font-semibold">{trafficInsight.quiet}</span>
              </p>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={trafficData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                        <XAxis 
                          dataKey="hour" 
                          stroke="#475569" 
                          fontSize={10}
                          tickFormatter={(value) => value.replace(':00', 'h')}
                        />
                        <YAxis stroke="#475569" fontSize={12} />
                        <Tooltip 
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f8fafc' }}
                            formatter={(value) => [`${value} triggers`, 'Motion']}
                            labelFormatter={(label) => `Time: ${label}`}
                        />
                        <Bar 
                          dataKey="count" 
                          fill="#f97316" 
                          radius={[4, 4, 0, 0]}
                          name="Motion Triggers"
                        />
                    </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-slate-500 mt-3 italic">
                💡 Insight: Busy hours justify full brightness. Empty hours support dimming to save energy.
              </p>
          </div>

          {/* Mode Distribution Pie Chart */}
          <div className="bg-slate-800/50 backdrop-blur-md p-6 rounded-2xl border border-slate-700/50 shadow-xl">
              <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
                  <span className="w-2 h-6 bg-green-500 rounded-full"></span>
                  Mode Distribution (Last 50 Readings)
              </h3>
              <div className="h-64 flex items-center justify-center">
                {modeDistribution.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                          <Pie
                              data={modeDistribution}
                              cx="50%"
                              cy="50%"
                              innerRadius={60}
                              outerRadius={90}
                              paddingAngle={5}
                              dataKey="value"
                              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                              labelLine={false}
                          >
                              {modeDistribution.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={entry.color} />
                              ))}
                          </Pie>
                          <Tooltip 
                              contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f8fafc' }}
                              formatter={(value, name) => [`${value} readings`, name]}
                          />
                          <Legend 
                              verticalAlign="bottom" 
                              iconType="circle"
                              wrapperStyle={{ color: '#f8fafc' }}
                          />
                      </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-slate-500">No data available</p>
                )}
              </div>
          </div>

      </div>
    </div>
  );
};

export default Dashboard;
