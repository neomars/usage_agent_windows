import React from 'react';
// Optional: import { Link } from 'react-router-dom'; // If you want a navbar
import './Layout.css'; // Create this for basic layout styling

const Layout = ({ children }) => {
  return (
    <div className="layout">
      <header className="layout-header">
        <h1>Agent Monitoring Dashboard</h1>
        {/* Basic Navbar Example (optional)
        <nav>
          <Link to="/">Dashboard</Link> | <Link to="/groups">Groups</Link>
        </nav>
        */}
      </header>
      <main className="layout-main">
        {children}
      </main>
      <footer className="layout-footer">
        <p>&copy; {new Date().getFullYear()} Monitoring Service</p>
      </footer>
    </div>
  );
};

export default Layout;
