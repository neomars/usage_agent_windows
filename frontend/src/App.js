import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout'; // To be created
import DashboardPage from './pages/DashboardPage'; // To be created
import './App.css';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          {/* Add other routes here later, e.g., for GroupsPage */}
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
