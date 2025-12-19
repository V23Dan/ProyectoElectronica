import React from 'react';
import { Link } from 'react-router-dom';
import { Camera, Cpu, Database, Zap, Users, Award } from 'lucide-react';
import './Home.css';

const Home = () => {
  const features = [
    {
      icon: <Camera />,
      title: "Streaming en Tiempo Real",
      description: "Captura de video desde ESP32-CAM o cámara local con procesamiento inmediato"
    },
    {
      icon: <Cpu />,
      title: "IA Especializada",
      description: "Modelo LSTM entrenado con dataset colombiano para reconocimiento preciso"
    },
    {
      icon: <Database />,
      title: "Base de Datos Local",
      description: "Almacenamiento de sesiones y traducciones para análisis posterior"
    },
    {
      icon: <Zap />,
      title: "Procesamiento Optimizado",
      description: "Detección de manos con MediaPipe y clasificación en tiempo real"
    },
    {
      icon: <Users />,
      title: "Interfaz Intuitiva",
      description: "Diseño centrado en el usuario para fácil interacción y monitoreo"
    },
    {
      icon: <Award />,
      title: "Tecnología Accesible",
      description: "Sistema de bajo costo usando hardware abierto y software libre"
    }
  ];

  const techStack = [
    { name: "React", description: "Frontend moderno y responsive" },
    { name: "FastAPI", description: "Microservicio Python para IA" },
    { name: "TensorFlow", description: "Redes neuronales y modelos LSTM" },
    { name: "MediaPipe", description: "Detección de landmarks de manos" },
    { name: "ESP32-CAM", description: "Hardware para captura de video" },
    { name: "WebSockets", description: "Comunicación en tiempo real" }
  ];

  return (
    <div className="home-page">
      <section className="hero">
        <div className="hero-content">
          <h1 className="hero-title">
            Revolucionando la Comunicación con 
            <span className="highlight"> Lengua de Señas Colombiana</span>
          </h1>
          <p className="hero-description">
            Sistema de inteligencia artificial que traduce lenguaje de señas colombiano 
            a texto en tiempo real. Tecnología accesible para construir puentes de comunicación.
          </p>
          <div className="hero-actions">
            <Link to="/translation" className="cta-button primary">
              Comenzar Traducción
            </Link>
            <button className="cta-button secondary">
              Ver Demo
            </button>
          </div>
        </div>
        <div className="hero-visual">
          <div className="floating-cards">
            <div className="card hand-card">👋</div>
            <div className="card ai-card">🤖</div>
            <div className="card text-card">📝</div>
          </div>
        </div>
      </section>

      <section className="features">
        <div className="container">
          <h2 className="section-title">Características Principales</h2>
          <div className="features-grid">
            {features.map((feature, index) => (
              <div key={index} className="feature-card">
                <div className="feature-icon">
                  {feature.icon}
                </div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="how-it-works">
        <div className="container">
          <h2 className="section-title">¿Cómo Funciona?</h2>
          <div className="steps">
            <div className="step">
              <div className="step-number">1</div>
              <h3>Captura de Video</h3>
              <p>La cámara captura los movimientos de las manos en tiempo real</p>
            </div>
            <div className="step">
              <div className="step-number">2</div>
              <h3>Detección de Manos</h3>
              <p>MediaPipe identifica y extrae 21 landmarks por mano</p>
            </div>
            <div className="step">
              <div className="step-number">3</div>
              <h3>Clasificación</h3>
              <p>El modelo LSTM analiza secuencias para identificar la seña</p>
            </div>
            <div className="step">
              <div className="step-number">4</div>
              <h3>Traducción</h3>
              <p>La seña reconocida se convierte a texto en español</p>
            </div>
          </div>
        </div>
      </section>

      <section className="tech-stack">
        <div className="container">
          <h2 className="section-title">Tecnologías Utilizadas</h2>
          <div className="tech-grid">
            {techStack.map((tech, index) => (
              <div key={index} className="tech-item">
                <h3>{tech.name}</h3>
                <p>{tech.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="cta-section">
        <div className="container">
          <h2>¿Listo para Comenzar?</h2>
          <p>Prueba nuestro sistema de traducción en tiempo real</p>
          <Link to="/translation" className="cta-button large">
            Ir a Traducción en Vivo
          </Link>
        </div>
      </section>
    </div>
  );
};

export default Home;