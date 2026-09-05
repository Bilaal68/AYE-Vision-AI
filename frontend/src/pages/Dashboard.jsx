import React from 'react';

export default function Dashboard() {
  return (
    <div className="dashboard-page">
      <div className="page-header">
        <h1 className="page-title">Security Intelligence Dashboard</h1>
        <p className="page-desc">Real-time threat monitoring, geospatial analytics, and event correlation graph.</p>
      </div>

      <div className="grid-layout">
        <div className="card">
          <h2 className="card-title">Live Threat Map</h2>
          <p className="page-desc">Geospatial telemetry visualization powered by Leaflet.</p>
        </div>
        <div className="card">
          <h2 className="card-title">Entity Relationship Graph</h2>
          <p className="page-desc">Network node graph visualization powered by react-force-graph.</p>
        </div>
        <div className="card">
          <h2 className="card-title">AI Analyst Assistant</h2>
          <p className="page-desc">Automated RAG pipeline & anomaly detection scoring feed.</p>
        </div>
      </div>
    </div>
  );
}
