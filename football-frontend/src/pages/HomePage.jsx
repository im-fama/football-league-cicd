// src/pages/HomePage.jsx
import { Link } from "react-router-dom";
import "../css/HomePage.css";

// Set by the CI/CD pipeline at build time (e.g. "1.0.12"); "dev" when running locally.
const APP_VERSION = import.meta.env.VITE_APP_VERSION || "dev";

export default function HomePage() {
  return (
    <div className="home-container">
      <h1>Welcome to Football League Management System — Deployed with CI/CD by Fatima</h1>
      <p>Choose your dashboard to continue:</p>

      <div className="button-group">
        <Link to="/admin">
          <button className="home-btn">Admin Dashboard</button>
        </Link>

        <Link to="/dashboard">
          <button className="home-btn">User Dashboard</button>
        </Link>
      </div>

      <p className="version-badge">Version {APP_VERSION}</p>
    </div>
  );
}
