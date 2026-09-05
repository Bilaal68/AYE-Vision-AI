import React from 'react';

export default function Incidents() {
  return (
    <div className="incidents-page">
      <div className="page-header">
        <h1 className="page-title">Incident & Case Management</h1>
        <p className="page-desc">Track active security incidents, assign severity levels, and manage response workflows.</p>
      </div>

      <div className="card">
        <h2 className="card-title">Active Incidents Queue</h2>
        <p className="page-desc">No active high-priority incidents reported.</p>
      </div>
    </div>
  );
}
