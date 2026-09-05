import React from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Incidents from './pages/Incidents';
import Investigations from './pages/Investigations';

export default function App() {
  return (
    <Router>
      <div className="app-container">
        <header className="navbar">
          <div className="nav-brand">⚡ Security Intelligence Platform</div>
          <nav className="nav-links">
            <NavLink to="/" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
              Dashboard
            </NavLink>
            <NavLink to="/incidents" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
              Incidents
            </NavLink>
            <NavLink to="/investigations" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
              Investigations
            </NavLink>
          </nav>
        </header>

        <main className="content-body">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/incidents" element={<Incidents />} />
            <Route path="/investigations" element={<Investigations />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
