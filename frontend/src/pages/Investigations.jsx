import React from 'react';

export default function Investigations() {
  return (
    <div className="investigations-page">
      <div className="page-header">
        <h1 className="page-title">Investigation Workspace</h1>
        <p className="page-desc">Deep-dive forensics workspace connecting events, entities, and threat intelligence notes.</p>
      </div>

      <div className="card">
        <h2 className="card-title">Open Investigation Canvas</h2>
        <p className="page-desc">Select an entity or incident to launch an interactive forensic investigation canvas.</p>
      </div>
    </div>
  );
}
