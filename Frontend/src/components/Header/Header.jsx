// src/components/Header.js
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Camera, Home, Activity } from 'lucide-react';
import './Header.css';

const Header = () => {
  const location = useLocation();

  return (
    <header className="header">
      <div className="header-content">
        <div className="logo">
          <Camera className="logo-icon" />
          <h1>SeñasCol</h1>
          <span className="beta-tag">Beta</span>
        </div>
        
        <nav className="navigation">
          <Link 
            to="/" 
            className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
          >
            <Home size={18} />
            Inicio
          </Link>
          <Link 
            to="/translation" 
            className={`nav-link ${location.pathname === '/translation' ? 'active' : ''}`}
          >
            <Activity size={18} />
            Traducción
          </Link>
        </nav>

        <div className="connection-status">
          <div className={`status-dot ${location.pathname === '/translation' ? 'pulse' : ''}`} />
          <span>{location.pathname === '/translation' ? 'En Vivo' : 'Conectado'}</span>
        </div>
      </div>
    </header>
  );
};

export default Header;