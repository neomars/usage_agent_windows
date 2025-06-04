import React, { useState, useEffect } from 'react';
import './DashboardPage.css'; // Create this for page styling

const DashboardPage = () => {
  const [computers, setComputers] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch('/api/dashboard_data');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.status === "error") { // Handle application-level errors from API
          throw new Error(data.message || "Error fetching dashboard data");
        }
        setComputers(data.computers || []);
        setAlerts(data.alerts || []);
      } catch (e) {
        setError(e.message);
        console.error("Failed to fetch dashboard data:", e);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []); // Empty dependency array means this effect runs once on mount

  if (loading) {
    return <p>Loading dashboard data...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>Error loading dashboard data: {error}</p>;
  }

  return (
    <div className="dashboard-page">
      <h2>Dashboard</h2>

      <section className="computers-section">
        <h3>Computers ({computers.length})</h3>
        {computers.length > 0 ? (
          <table>
            <thead>
              <tr>
                <th>NetBIOS Name</th>
                <th>IP Address</th>
                <th>Last Seen</th>
                <th>Group</th>
              </tr>
            </thead>
            <tbody>
              {computers.map(comp => (
                <tr key={comp.id}>
                  <td>{comp.netbios_name}</td>
                  <td>{comp.ip_address}</td>
                  <td>{comp.last_seen}</td>
                  <td>{comp.group_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No computers reporting.</p>
        )}
      </section>

      <section className="alerts-section">
        <h3>Alerts ({alerts.length})</h3>
        {alerts.length > 0 ? (
          <ul>
            {alerts.map((alert, index) => (
              <li key={index}>
                <strong>{alert.alert_type}</strong> on {alert.netbios_name} ({alert.ip_address}): {alert.details}
              </li>
            ))}
          </ul>
        ) : (
          <p>No active alerts.</p>
        )}
      </section>
    </div>
  );
};

export default DashboardPage;
