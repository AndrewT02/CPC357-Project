import React, { useEffect, useState } from 'react';
import { Container, Grid, Card, CardContent, Typography, Box, Badge, createTheme, ThemeProvider, CssBaseline, LinearProgress, Alert } from '@mui/material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area } from 'recharts';
import axios from 'axios';
import { io } from 'socket.io-client';
import LightModeIcon from '@mui/icons-material/LightMode';
import NightlightIcon from '@mui/icons-material/Nightlight';
import BoltIcon from '@mui/icons-material/Bolt';
import TrafficIcon from '@mui/icons-material/Traffic';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

// --- THEME & COLORS ---
const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#58a6ff' },
    secondary: { main: '#238636' },
    background: { default: '#0d1117', paper: '#161b22' },
    text: { primary: '#c9d1d9', secondary: '#8b949e' },
  },
  typography: {
    fontFamily: '"Exo 2", "Roboto", "Helvetica", "Arial", sans-serif',
    h3: { fontWeight: 700 },
    h6: { fontWeight: 600, letterSpacing: '0.5px' },
  },
});

const COLORS = ['#238636', '#1f6feb', '#d29922', '#da3633']; // Green, Blue, Yellow, Red

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={{ backgroundColor: 'rgba(22, 27, 34, 0.9)', border: '1px solid #30363d', padding: '10px', borderRadius: '4px' }}>
        <p style={{ color: '#c9d1d9', margin: 0 }}>{`${label} : ${payload[0].value}`}</p>
      </div>
    );
  }
  return null;
};

export default function Dashboard() {
  const [status, setStatus] = useState({});
  const [energyData, setEnergyData] = useState(null);
  const [trafficData, setTrafficData] = useState([]);
  const [modeData, setModeData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  // Fetch Data (Initial Load)
  useEffect(() => {
    const socket = io('http://localhost:5000');

    // Real-time Update Listener
    socket.on('update', (newData) => {
      // Update Status Card instantly
      const brightness = newData.brightness;
      const mode = brightness === 0 ? "OFF" : (brightness < 50 ? `ECO (${brightness}%)` : `ACTIVE (${brightness}%)`);

      setStatus({
        mode: mode,
        last_motion: "Just now",
        is_night: newData.is_night,
        power: newData.power
      });

      // Update Last Update Time
      setLastUpdate(new Date());
    });

    const fetchData = async () => {
      try {
        const [resStatus, resEnergy, resTraffic, resMode] = await Promise.all([
          axios.get('http://localhost:5000/api/status'),
          axios.get('http://localhost:5000/api/analytics/energy'),
          axios.get('http://localhost:5000/api/analytics/traffic'),
          axios.get('http://localhost:5000/api/analytics/modes')
        ]);

        setStatus(resStatus.data);
        setEnergyData(resEnergy.data);
        setTrafficData(resTraffic.data);

        // Process Mode Data: Combine ACTIVE/ECO into "Light On"
        const rawModes = resMode.data;
        const onCount = rawModes.reduce((acc, curr) => (curr.name.includes('ACTIVE') || curr.name.includes('ECO')) ? acc + curr.value : acc, 0);
        const offCount = rawModes.reduce((acc, curr) => (curr.name.includes('OFF')) ? acc + curr.value : acc, 0);

        setModeData([
          { name: 'Light On', value: onCount },
          { name: 'Light Off', value: offCount }
        ]);

        setLoading(false);
        setError(null); // Clear any previous error
        setLastUpdate(new Date());
      } catch (error) {
        console.error("Error fetching data", error);
        setError("Connection Lost: Unable to reach backend. Please ensure backend.py is running.");
        setLoading(false);
      }
    };

    fetchData();
    // const interval = setInterval(fetchData, 2000); // Polling Removed!
    // return () => clearInterval(interval);

    // Cleanup Socket
    return () => socket.disconnect();
  }, []);

  if (loading) return (
    <Box sx={{ width: '100%', height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column' }}>
      <Typography variant="h5" color="primary" gutterBottom>Initializing Smart City Link...</Typography>
      <LinearProgress sx={{ width: '300px' }} />
    </Box>
  );

  // Calculate Efficiency correctly for the graph
  const efficiency = energyData ? energyData.efficiency_score : 0;
  const energyChartData = energyData ? [
    { name: 'Traditional', value: energyData.traditional_w, fill: '#da3633' }, // Red for waste
    { name: 'Smart System', value: energyData.smart_avg_w, fill: '#238636' }   // Green for efficient
  ] : [];

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>

        <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
          <div>
            <Typography variant="h3" className="neon-text" gutterBottom sx={{ background: 'linear-gradient(45deg, #58a6ff, #238636)', backgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              SMART ADAPTIVE LIGHTING
            </Typography>
            <Typography variant="subtitle1" color="text.secondary">
              Live Telemetry • Last Update: {lastUpdate.toLocaleTimeString()}
            </Typography>
          </div>
          <Badge color={status.power > 0 ? "success" : "warning"} variant="dot" overlap="circular">
            <Box sx={{ p: 2, borderRadius: '50%', background: 'rgba(255,255,255,0.05)' }}>
              {status.is_night ? <NightlightIcon sx={{ fontSize: 40, color: '#e3b341' }} /> : <LightModeIcon sx={{ fontSize: 40, color: '#f78166' }} />}
            </Box>
          </Badge>
        </Box>

        {/* ERROR BANNER */}
        {error && (
          <Alert severity="error" icon={<ErrorOutlineIcon />} sx={{ mb: 4 }} className="glass-card">
            {error}
          </Alert>
        )}

        {/* NO DATA CHECK */}
        {!error && modeData.every(d => d.value === 0) && trafficData.every(d => d.count === 0) && (
          <Alert severity="info" sx={{ mb: 4 }} className="glass-card">
            No data available yet. Waiting for sensor data from the Cloud VM...
          </Alert>
        )}

        {/* 1. STATUS CARDS - KEY METRICS */}
        <Grid container spacing={4} mb={6}>
          <Grid item xs={12} md={3}>
            <Card className="glass-card">
              <CardContent>
                <Typography color="text.secondary" gutterBottom>Current Status</Typography>
                <Typography variant="h4" color="primary">{status.mode}</Typography>
                <LinearProgress variant="determinate" value={status.mode?.includes('ACTIVE') ? 100 : (status.mode?.includes('ECO') ? 30 : 0)} sx={{ mt: 2, height: 6, borderRadius: 5 }} />
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card className="glass-card">
              <CardContent>
                <Typography color="text.secondary" gutterBottom>Day / Night Status</Typography>
                <Box display="flex" alignItems="center">
                  {status.is_night ? <NightlightIcon sx={{ fontSize: 30, color: '#e3b341', mr: 1 }} /> : <LightModeIcon sx={{ fontSize: 30, color: '#f78166', mr: 1 }} />}
                  <Typography variant="h4" sx={{ color: status.is_night ? '#e3b341' : '#f78166' }}>
                    {status.is_night ? "Night" : "Day"}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card className="glass-card">
              <CardContent>
                <Typography color="text.secondary" gutterBottom>Last Motion Event</Typography>
                <Box display="flex" alignItems="center">
                  <TrafficIcon sx={{ mr: 1, color: '#d29922' }} />
                  <Typography variant="h5">{status.last_motion}</Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={3}>
            <Card className="glass-card" sx={{ background: 'linear-gradient(135deg, rgba(35, 134, 54, 0.2) 0%, rgba(35, 134, 54, 0) 100%)' }}>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>Efficiency Analysis</Typography>
                <Typography variant="h3" color="secondary">{efficiency}%</Typography>
                <Typography variant="caption">Energy Saved</Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* 2. MAIN ANALYTICS */}
        <Grid container spacing={4}>

          {/* TRAFFIC PATTERNS */}
          <Grid item xs={12} md={8}>
            <Card className="glass-card" sx={{ height: 450 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                  <TrafficIcon sx={{ mr: 1, color: '#58a6ff' }} />
                  Motion Detected by Time
                </Typography>
                <ResponsiveContainer width="100%" height={350}>
                  <AreaChart data={trafficData}>
                    <defs>
                      <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#58a6ff" stopOpacity={0.8} />
                        <stop offset="95%" stopColor="#58a6ff" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
                    <XAxis dataKey="hour" stroke="#8b949e" />
                    <YAxis stroke="#8b949e" />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="count" stroke="#58a6ff" fillOpacity={1} fill="url(#colorCount)" />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>

          {/* SYSTEM MODE DISTRIBUTION */}
          <Grid item xs={12} md={4}>
            <Card className="glass-card" sx={{ height: 450 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>Light On vs Off Duration</Typography>
                <Box height={350} position="relative">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={modeData}
                        cx="50%"
                        cy="50%"
                        innerRadius={80}
                        outerRadius={120}
                        paddingAngle={5}
                        dataKey="value"
                        stroke="none"
                      >
                        {modeData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip content={<CustomTooltip />} />
                      <Legend verticalAlign="bottom" height={36} />
                    </PieChart>
                  </ResponsiveContainer>
                  {/* Center Text */}
                  <Box position="absolute" top="45%" left="0" width="100%" textAlign="center" sx={{ pointerEvents: 'none' }}>
                    <Typography variant="h4" color="white">{status.mode?.split(' ')[0]}</Typography>
                    <Typography variant="caption" color="text.secondary">Current State</Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* ENERGY COMPARISON */}
          <Grid item xs={12}>
            <Card className="glass-card">
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                  <BoltIcon sx={{ mr: 1, color: '#e3b341' }} />
                  Energy Savings
                </Typography>
                <Grid container alignItems="center">
                  <Grid item xs={12} md={3}>
                    <Typography variant="body1" color="text.secondary" paragraph>
                      The Smart Adaptive System dynamically adjusts brightness based on real-time traffic and ambient light, significantly reducing waste compared to traditional fixed-power lighting.
                    </Typography>
                    <Typography variant="h2" sx={{ color: '#238636' }}>{efficiency}%</Typography>
                    <Typography variant="overline" color="text.secondary">More Efficient than Standard</Typography>
                  </Grid>
                  <Grid item xs={12} md={9} sx={{ height: 250 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart layout="vertical" data={energyChartData} barSize={40}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#30363d" horizontal={true} vertical={false} />
                        <XAxis type="number" unit=" W" stroke="#8b949e" />
                        <YAxis dataKey="name" type="category" width={120} stroke="#8b949e" />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
                        <Bar dataKey="value" radius={[0, 10, 10, 0]}>
                          {energyChartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

        </Grid>
      </Container>
    </ThemeProvider>
  );
}

